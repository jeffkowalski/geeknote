#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import os
import argparse
import binascii
import glob
import logging
import re
import hashlib
import binascii
import mimetypes

import evernote.edam.type.ttypes as Types
from evernote.edam.limits.constants import EDAM_USER_NOTES_MAX
from bs4 import BeautifulSoup

import config
from geeknote import GeekNote
from storage import Storage
from editor import Editor
import tools

# for prototyping...
# refactor should move code depending on these modules elsewhere
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import urlparse
import evernote.edam.notestore.NoteStore as NoteStore

# set default logger (write log to file)
def_logpath = os.path.join(config.APP_DIR, "gnsync.log")
formatter = logging.Formatter("%(asctime)-15s : %(message)s")
handler = logging.FileHandler(def_logpath)
handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

# http://en.wikipedia.org/wiki/Unicode_control_characters
CONTROL_CHARS_RE = re.compile(u"[\x00-\x08\x0e-\x1f\x7f-\x9f]")


def remove_control_characters(s):
    return CONTROL_CHARS_RE.sub("", s)


def log(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception, e:
            logger.exception("%s", str(e))

    return wrapper


@log
def reset_logpath(logpath):
    """
    Reset logpath to path from command line
    """
    global logger

    if not logpath:
        return

    # remove temporary log file if it's empty
    if os.path.isfile(def_logpath):
        if os.path.getsize(def_logpath) == 0:
            os.remove(def_logpath)

    # save previous handlers
    handlers = logger.handlers

    # remove old handlers
    for handler in handlers:
        logger.removeHandler(handler)

    # try to set new file handler
    handler = logging.FileHandler(logpath)
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def all_notebooks(sleep_on_ratelimit=False):
    geeknote = GeekNote(sleepOnRateLimit=sleep_on_ratelimit)
    return [notebook.name for notebook in geeknote.findNotebooks()]


def all_linked_notebooks():
    geeknote = GeekNote()
    return geeknote.findLinkedNotebooks()


class GNSync:
    notebook_name = None
    path = None
    mask = None
    twoway = None
    download_only = None
    nodownsync = None

    notebook_guid = None
    all_set = False
    sleep_on_ratelimit = False

    @log
    def __init__(
        self,
        notebook_name,
        path,
        mask,
        format,
        twoway=False,
        download_only=False,
        nodownsync=False,
        sleep_on_ratelimit=False,
        imageOptions={"saveImages": False, "imagesInSubdir": False},
    ):
        # check auth
        if not Storage().getUserToken():
            raise Exception("Auth error. There is not any oAuthToken.")

        # set path
        if not path:
            raise Exception("Path to sync directories does not select.")

        if not os.path.exists(path):
            raise Exception("Path to sync directories does not exist.  %s" % path)

        self.path = path

        # set mask
        if not mask:
            mask = "*.*"

        self.mask = mask

        # set format
        if not format:
            format = "plain"

        self.format = format

        if format == "markdown":
            self.extension = ".md"
        elif format == "html":
            self.extension = ".html"
        else:
            self.extension = ".txt"

        self.twoway = twoway
        self.download_only = download_only
        self.nodownsync = nodownsync

        logger.info("Sync Start")

        # set notebook
        self.notebook_guid, self.notebook_name = self._get_notebook(notebook_name, path)

        # set image options
        self.imageOptions = imageOptions

        # all is Ok
        self.all_set = True

        self.sleep_on_ratelimit = sleep_on_ratelimit

    @log
    def sync(self):
        """
        Synchronize files to notes
        TODO: add two way sync with meta support
        TODO: add specific notebook support
        """
        if not self.all_set:
            return

        files = self._get_files()
        notes = self._get_notes()

        if not self.download_only:
            for f in files:
                has_note = False
                meta = self._parse_meta(self._get_file_content(f["path"]))
                title = f["name"] if "title" not in meta else meta["title"].strip()
                tags = (
                    None
                    if "tags" not in meta
                    else meta["tags"].replace("[", "").replace("]", "").split(",")
                )
                tags = None if not tags else map(lambda x: x.strip(), tags)
                meta["tags"] = tags
                meta["title"] = title
                note = None

                if self.format == "html":
                    meta["mtime"] = f["mtime"]
                    note = self._html2note(meta)

                for n in notes:
                    if title == n.title:
                        has_note = True
                        if f["mtime"] > n.updated:
                            if self.format == "html":
                                gn = GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit)
                                note.guid = n.guid
                                gn.getNoteStore().updateNote(gn.authToken, note)
                                logger.info('Note "{0}" was updated'.format(note.title))
                            else:
                                self._update_note(f, n, title, meta["content"], tags)
                            break

                if not has_note:
                    if self.format == "html":
                        gn = GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit)
                        gn.getNoteStore().createNote(gn.authToken, note)
                        logger.info('Note "{0}" was created'.format(note.title))
                    else:
                        self._create_note(f, title, meta["content"], tags)

        if self.twoway or self.download_only:
            for n in notes:
                has_file = False
                for f in files:
                    if f["name"] == n.title:
                        has_file = True
                        if f["mtime"] < n.updated:
                            self._update_file(f, n)
                            break

                if not self.nodownsync:
                    if not has_file:
                        self._create_file(n)

        logger.info("Sync Complete")

    @log
    def _parse_meta(self, content):
        """
        Parse jekyll metadata of note, eg:
        ---
        layout: post
        title: draw uml with emacs
        tags: [uml, emacs]
        categories: [dev]
        ---
        and substitute meta from content.

        Caution: meta data will only work in one way
        mode! And I will never use two way mode, so
        two way sync will need your additional work!
        """
        metaBlock = re.compile("---(.*?)---", re.DOTALL)
        metaInfo = re.compile("(\w+):\s*?(.*)")
        block = metaBlock.search(content)
        if block is not None:
            info = metaInfo.findall(block.group(0))
            ret = dict(info)
            ret["content"] = metaBlock.sub("", content)
            return ret
        else:
            return {"content": content}

    @log
    def _html2note(self, meta):
        """
        parse html to note
        TODO: check if evernote need upload media evertime when update
        """
        note = Types.Note()
        note.title = meta["title"].strip() if "title" in meta else None
        note.tagNames = meta["tags"]
        note.created = meta["mtime"]
        note.resources = []
        soup = BeautifulSoup(meta["content"], "html.parser")
        for tag in soup.findAll("img"):  # image support is enough
            if "src" in tag.attrs and len(tag.attrs["src"]) > 0:
                img = None
                with open(tag.attrs["src"], "rb") as f:
                    img = f.read()
                md5 = hashlib.md5()
                md5.update(img)
                hash = md5.digest()
                hexHash = binascii.hexlify(hash)
                mime = mimetypes.guess_type(tag["src"])[0]

                data = Types.Data()
                data.size = len(img)
                data.bodyHash = hash
                data.body = img

                resource = Types.Resource()
                resource.mime = mime
                resource.data = data

                tag.name = "en-media"
                tag.attrs["type"] = mime
                tag.attrs["hash"] = hexHash
                tag.attrs.pop("src", None)

                note.resources.append(resource)
        note.notebookGuid = self.notebook_guid
        note.content = str(soup)
        return note

    @log
    def _update_note(self, file_note, note, title=None, content=None, tags=None):
        """
        Updates note from file
        """
        # content = self._get_file_content(file_note['path']) if content is None else content
        try:
            tags = tags or note.tagNames
        except AttributeError:
            tags = None

        result = GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).updateNote(
            guid=note.guid,
            title=title or note.title,
            content=content or self._get_file_content(file_note["path"]),
            tags=tags,
            notebook=self.notebook_guid,
        )

        if result:
            logger.info('Note "{0}" was updated'.format(note.title))
        else:
            raise Exception('Note "{0}" was not updated'.format(note.title))

        return result

    @log
    def _update_file(self, file_note, note):
        """
        Updates file from note
        """
        GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).loadNoteContent(note)
        content = Editor.ENMLtoText(note.content)
        open(file_note["path"], "w").write(content)
        updated_seconds = note.updated / 1000.0
        os.utime(file_note["path"], (updated_seconds, updated_seconds))

    @log
    def _create_note(self, file_note, title=None, content=None, tags=None):
        """
        Creates note from file
        """

        content = content or self._get_file_content(file_note["path"])

        if content is None:
            return

        result = GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).createNote(
            title=title or file_note["name"],
            content=content,
            notebook=self.notebook_guid,
            tags=tags or None,
            created=file_note["mtime"],
        )

        if result:
            logger.info('Note "{0}" was created'.format(title or file_note["name"]))
        else:
            raise Exception(
                'Note "{0}" was not' " created".format(title or file_note["name"])
            )

        return result

    @log
    def _create_file(self, note):
        """
        Creates file from note
        """
        GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).loadNoteContent(note)

        escaped_title = re.sub(os.sep, "-", note.title)

        # Save images
        if "saveImages" in self.imageOptions and self.imageOptions["saveImages"]:
            imageList = Editor.getImages(note.content)
            if imageList:
                if (
                    "imagesInSubdir" in self.imageOptions
                    and self.imageOptions["imagesInSubdir"]
                ):
                    try:
                        os.mkdir(os.path.join(self.path, escaped_title + "_images"))
                    except OSError:
                        # Folder already exists
                        pass
                    imagePath = os.path.join(
                        self.path, escaped_title + "_images", escaped_title
                    )
                    self.imageOptions["baseFilename"] = (
                        escaped_title + "_images/" + escaped_title
                    )
                else:
                    imagePath = os.path.join(self.path, escaped_title)
                    self.imageOptions["baseFilename"] = escaped_title
                for imageInfo in imageList:
                    filename = "{}-{}.{}".format(
                        imagePath, imageInfo["hash"], imageInfo["extension"]
                    )
                    logger.info("Saving image to {}".format(filename))
                    binaryHash = binascii.unhexlify(imageInfo["hash"])
                    GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).saveMedia(
                        note.guid, binaryHash, filename
                    )

        content = Editor.ENMLtoText(note.content, self.imageOptions)
        path = os.path.join(self.path, escaped_title + self.extension)
        open(path, "w").write(content)
        updated_seconds = note.updated / 1000.0
        os.utime(path, (updated_seconds, updated_seconds))
        return True

    @log
    def _get_file_content(self, path):
        """
        Get file content.
        """
        with codecs.open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # strip unprintable characters
        content = content.encode("ascii", errors="xmlcharrefreplace")
        content = Editor.textToENML(content=content, raise_ex=True, format=self.format)

        if content is None:
            logger.warning("File {0}. Content must be " "an UTF-8 encode.".format(path))
            return None

        return content

    @log
    def _get_notebook(self, notebook_name, path):
        """
        Get notebook guid and name.
        Takes default notebook if notebook's name does not select.
        """
        notebooks = GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit).findNotebooks()

        if not notebook_name:
            notebook_name = os.path.basename(os.path.realpath(path))

        notebook = [item for item in notebooks if item.name == notebook_name]
        guid = None
        if notebook:
            guid = notebook[0].guid

        if not guid:
            notebook = GeekNote(
                sleepOnRateLimit=self.sleep_on_ratelimit
            ).createNotebook(notebook_name)

            if notebook:
                logger.info('Notebook "{0}" was' " created".format(notebook_name))
            else:
                raise Exception(
                    'Notebook "{0}" was' " not created".format(notebook_name)
                )

            guid = notebook.guid

        return (guid, notebook_name)

    @log
    def _get_files(self):
        """
        Get files by self.mask from self.path dir.
        """

        file_paths = glob.glob(os.path.join(self.path, self.mask))

        files = []
        for f in file_paths:
            if os.path.isfile(f):
                file_name = os.path.basename(f)
                file_name = os.path.splitext(file_name)[0]

                mtime = int(os.path.getmtime(f) * 1000)

                files.append({"path": f, "name": file_name, "mtime": mtime})

        return files

    @log
    def _get_notes(self):
        """
        Get notes from evernote.
        """
        keywords = 'notebook:"{0}"'.format(
            tools.strip(self.notebook_name.encode("utf-8"))
        )
        return (
            GeekNote(sleepOnRateLimit=self.sleep_on_ratelimit)
            .findNotes(keywords, EDAM_USER_NOTES_MAX)
            .notes
        )


def main():
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--path", "-p", action="store", help="Path to synchronize directory"
        )
        parser.add_argument(
            "--mask",
            "-m",
            action="store",
            help='Mask of files to synchronize. Default is "*.*"',
        )
        parser.add_argument(
            "--format",
            "-f",
            action="store",
            default="plain",
            choices=["plain", "markdown", "html"],
            help='The format of the file contents. Default is "plain". Valid values are "plain" "html" and "markdown"',
        )
        parser.add_argument(
            "--notebook",
            "-n",
            action="store",
            help="Notebook name for synchronize. Default is default notebook unless all is selected",
        )
        parser.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Synchronize all notebooks",
            default=False,
        )
        parser.add_argument(
            "--all-linked", action="store_true", help="Get all linked notebooks"
        )
        parser.add_argument(
            "--logpath",
            "-l",
            action="store",
            help="Path to log file. Default is GeekNoteSync in home dir",
        )
        parser.add_argument(
            "--two-way",
            "-t",
            action="store_true",
            help="Two-way sync (also download from evernote)",
            default=False,
        )
        parser.add_argument(
            "--download-only",
            action="store_true",
            help="Only download from evernote; no upload",
            default=False,
        )
        parser.add_argument(
            "--nodownsync",
            "-d",
            action="store",
            help="Sync from Evernote only if the file is already local.",
        )
        parser.add_argument(
            "--save-images", action="store_true", help="save images along with text"
        )
        parser.add_argument(
            "--sleep-on-ratelimit",
            action="store_true",
            help="sleep on being ratelimited",
        )
        parser.add_argument(
            "--images-in-subdir",
            action="store_true",
            help="save images in a subdirectory (instead of same directory as file)",
        )

        args = parser.parse_args()

        path = args.path if args.path else "."
        mask = args.mask if args.mask else None
        format = args.format if args.format else None
        notebook = args.notebook if args.notebook else None
        logpath = args.logpath if args.logpath else None
        twoway = args.two_way
        download_only = args.download_only
        nodownsync = True if args.nodownsync else False

        # image options
        imageOptions = {}
        imageOptions["saveImages"] = args.save_images
        imageOptions["imagesInSubdir"] = args.images_in_subdir

        reset_logpath(logpath)

        geeknote = GeekNote()

        if args.all_linked:
            my_map = {}
            for notebook in all_linked_notebooks():
                print "Syncing notebook: " + notebook.shareName
                notebook_url = urlparse.urlparse(notebook.noteStoreUrl)
                sharedNoteStoreClient = THttpClient.THttpClient(notebook.noteStoreUrl)
                sharedNoteStoreProtocol = TBinaryProtocol.TBinaryProtocol(
                    sharedNoteStoreClient
                )
                sharedNoteStore = NoteStore.Client(sharedNoteStoreProtocol)

                sharedAuthResult = sharedNoteStore.authenticateToSharedNotebook(
                    notebook.shareKey, geeknote.authToken
                )
                sharedAuthToken = sharedAuthResult.authenticationToken
                sharedNotebook = sharedNoteStore.getSharedNotebookByAuth(
                    sharedAuthToken
                )

                my_filter = NoteStore.NoteFilter(
                    notebookGuid=sharedNotebook.notebookGuid
                )

                noteList = sharedNoteStore.findNotes(sharedAuthToken, my_filter, 0, 10)

                print "Found " + str(noteList.totalNotes) + " shared notes."

                print noteList.notes

                filename = notebook.shareName + "-" + noteList.notes[0].title + ".html"

                filename = filename.replace(" ", "-").replace("/", "-")

                content = sharedNoteStore.getNoteContent(
                    sharedAuthToken, noteList.notes[0].guid
                )

                with open(filename, "w") as f:
                    f.write(content)
            return

        if args.all:
            for notebook in all_notebooks(sleep_on_ratelimit=args.sleep_on_ratelimit):
                logger.info("Syncing notebook %s", notebook)
                escaped_notebook_path = re.sub(os.sep, "-", notebook)
                notebook_path = os.path.join(path, escaped_notebook_path)
                if not os.path.exists(notebook_path):
                    os.mkdir(notebook_path)
                GNS = GNSync(
                    notebook,
                    notebook_path,
                    mask,
                    format,
                    twoway,
                    download_only,
                    nodownsync,
                    sleep_on_ratelimit=args.sleep_on_ratelimit,
                    imageOptions=imageOptions,
                )
                GNS.sync()
        else:
            GNS = GNSync(
                notebook,
                path,
                mask,
                format,
                twoway,
                download_only,
                nodownsync,
                sleep_on_ratelimit=args.sleep_on_ratelimit,
                imageOptions=imageOptions,
            )
            GNS.sync()

    except (KeyboardInterrupt, SystemExit, tools.ExitException):
        pass

    except Exception, e:
        logger.error(str(e))


if __name__ == "__main__":
    main()
