# -*- coding: utf-8 -*-

import os
import sys
import tempfile
from bs4 import BeautifulSoup, NavigableString
import threading
import hashlib
import html2text as html2text
import markdown2 as markdown
from . import tools
from . import out
import re
from . import config
from .storage import Storage
from .log import logging
from xml.sax.saxutils import escape, unescape


class EditorThread(threading.Thread):
    def __init__(self, editor):
        threading.Thread.__init__(self)
        self.editor = editor

    def run(self):
        self.editor.edit()


class Editor(object):
    # escape() and unescape() takes care of &, < and >.

    @staticmethod
    def getHtmlEscapeTable():
        return {'"': "&quot;", "'": "&apos;", "\n": "<br />"}

    @staticmethod
    def getHtmlUnescapeTable():
        return dict((v, k) for k, v in list(Editor.getHtmlEscapeTable().items()))

    @staticmethod
    def HTMLEscape(text):
        return escape(text, Editor.getHtmlEscapeTable())

    @staticmethod
    def HTMLEscapeTag(text):
        return escape(text)

    @staticmethod
    def HTMLUnescape(text):
        return unescape(text, Editor.getHtmlUnescapeTable())

    @staticmethod
    def getImages(contentENML):
        """
        Creates a list of image resources to save.
        Each has a hash and extension attribute.
        """
        soup = BeautifulSoup(contentENML, features='lxml')
        imageList = []
        for section in soup.findAll("en-media"):
            if "type" in section.attrs and "hash" in section.attrs:
                imageType, imageExtension = section["type"].split("/")
                if imageType == "image":
                    imageList.append(
                        {"hash": section["hash"], "extension": imageExtension}
                    )
        return imageList

    @staticmethod
    def checklistInENMLtoSoup(soup):
        """
        Transforms Evernote checklist elements to github `* [ ]` task list style
        """
        for section in soup.findAll("en-todo", checked="true"):
            section.replace_with("<br />* [x]")

        for section in soup.findAll("en-todo"):
            section.replace_with("<br />* [ ]")

    @staticmethod
    def ENMLtoText(
        contentENML,
        format="default",
        imageOptions={"saveImages": False},
        imageFilename="",
    ):
        soup = BeautifulSoup(contentENML, "html.parser")

        if format == "pre":
            #
            # Expect to find at least one 'pre' section. Otherwise, the note
            # was not created using the format='pre' option. In that case,
            # revert back the defaults. When found, form the note from the
            # first 'pre' section only. The others were added by the user.
            #
            sections = soup.select("pre")
            if len(sections) >= 1:
                content = ""
                for c in sections[0].contents:
                    content = "".join((content, c))
                pass
            else:
                format = "default"

        if format == "default":
            # In ENML, each line in paragraph have <div> tag.
            for section in soup.find_all("div"):
                if not section.br:
                    section.append(soup.new_tag("br"))
                section.unwrap()

            for section in soup.select("li > p"):
                section.replace_with(section.contents[0])

            for section in soup.select("li > br"):
                if section.next_sibling:
                    next_sibling = section.next_sibling.next_sibling
                    if next_sibling:
                        if next_sibling.find("li"):
                            section.extract()
                    else:
                        section.extract()

            Editor.checklistInENMLtoSoup(soup)

            # change <en-media> tags to <img> tags
            if "saveImages" in imageOptions and imageOptions["saveImages"]:
                for section in soup.findAll("en-media"):
                    if "type" in section.attrs and "hash" in section.attrs:
                        imageType, imageExtension = section["type"].split("/")
                        if imageType == "image":
                            newTag = soup.new_tag("img")
                            newTag["src"] = "{}-{}.{}".format(
                                imageOptions["baseFilename"],
                                section["hash"],
                                imageExtension,
                            )
                            section.replace_with(newTag)

            # Keep Evernote media elements in html format in markdown so
            # they'll stay in place over an edit
            for section in soup.find_all("en-media"):
                section.replace_with(str(section))

        content = html2text.html2text(str(soup), "")

        content = re.sub(r" *\n", os.linesep, content)
        content = content.replace(chr(160), " ")  # no-break space
        content = Editor.HTMLUnescape(content)

        return content

    @staticmethod
    def wrapENML(contentHTML):
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">\n'
            "<en-note>%s</en-note>" % contentHTML
        )
        return body

    @staticmethod
    def checklistInSoupToENML(soup):
        """
        Transforms github style checklists `* [ ]` in the BeautifulSoup tree to ENML.
        """

        checktodo_re = re.compile(r"\[([ x])\]")

        # To be more github compatible, if all elements in a list begin with '[ ]',
        # convert them to en-todo evernote elements
        for ul in soup.find_all("ul"):
            tasks = []
            istodo = True

            for li in ul.find_all("li"):
                task = soup.new_tag("div")
                todo_tag = soup.new_tag("en-todo")

                reg = checktodo_re.match(li.get_text())
                istodo = istodo and reg
                character = reg.group(1) if reg else None
                if character == "x":
                    todo_tag["checked"] = "true"

                task.append(todo_tag)
                if reg:
                    task.append(NavigableString(li.get_text()[3:].strip()))
                tasks.append(task)

            if istodo:
                for task in tasks[::-1]:
                    ul.insert_after(task)
                ul.extract()

    @staticmethod
    def textToENML(content, raise_ex=False, format="markdown", rawmd=False):
        """
        Transform formatted text to ENML
        """

        if not isinstance(content, str):
            content = ""
        try:
            # add 2 space before new line in paragraph for creating br tags
            content = re.sub(r"([^\r\n])([\r\n])([^\r\n])", r"\1  \n\3", content)
            # content = re.sub(r'\r\n', '\n', content)

            if format == "pre":
                # For the 'pre' format, simply wrap the content with a 'pre' tag.
                # Do not perform any further parsing/mutation.
                contentHTML = "".join(("<pre>", content, "</pre>")).encode("utf-8")
            elif format == "markdown":
                # Markdown format https://daringfireball.net/projects/markdown/basics
                extras = None

                if not rawmd:
                    storage = Storage()
                    extras = storage.getUserprop("markdown2_extras")
                    content = Editor.HTMLEscapeTag(content)

                contentHTML = markdown.markdown(content, extras=extras)

                soup = BeautifulSoup(contentHTML, "html.parser")
                Editor.checklistInSoupToENML(soup)
                contentHTML = str(soup)
            elif format == "html":
                # Html to ENML http://dev.evernote.com/doc/articles/enml.php
                soup = BeautifulSoup(content, "html.parser")
                ATTR_2_REMOVE = [
                    "id",
                    "class",
                    # "on*",
                    "accesskey",
                    "data",
                    "dynsrc",
                    "tabindex",
                ]

                for tag in soup.findAll():
                    if hasattr(tag, "attrs"):
                        for k in list(tag.attrs.keys()):
                            if k in ATTR_2_REMOVE or k.find("on") == 0:
                                tag.attrs.pop(k, None)
                contentHTML = str(soup)
            else:
                # Plain text format
                contentHTML = Editor.HTMLEscape(content)

                tmpstr = ""
                for l in contentHTML.split("\n"):
                    if l == "":
                        tmpstr = tmpstr + "<div><br/></div>"
                    else:
                        tmpstr = tmpstr + "<div>" + l + "</div>"

                contentHTML = tmpstr.encode("utf-8")
                contentHTML = contentHTML.replace(
                    "[x]", '<en-todo checked="true"></en-todo>'
                )
                contentHTML = contentHTML.replace("[ ]", "<en-todo></en-todo>")

            return Editor.wrapENML(contentHTML)

        except:
            import traceback

            traceback.print_exc()
            if raise_ex:
                raise Exception("Error while parsing text to html.")
            logging.error("Error while parsing text to html.")
            out.failureMessage("Error while parsing text to html.")
            return tools.exitErr()

    def __init__(self, editor, content, noteExtension, raw=False):
        if not isinstance(content, str):
            raise Exception(
                "Note content must be an instance "
                "of string, '%s' given." % type(content)
            )

        if not noteExtension:
            noteExtension = config.DEF_NOTE_EXT
        (tempfileHandler, tempfileName) = tempfile.mkstemp(suffix=noteExtension)
        content = content if raw else self.ENMLtoText(content)
        os.write(tempfileHandler, content.encode('utf-8'))
        os.close(tempfileHandler)

        self.content = content
        self.tempfile = tempfileName
        self.editor = editor

    def getTempfileChecksum(self):
        with open(self.tempfile, "rb") as fileHandler:
            checksum = hashlib.md5()
            while True:
                data = fileHandler.read(8192)
                if not data:
                    break
                checksum.update(data)

            return checksum.hexdigest()

    def edit(self):
        """
        Call the system editor, that types as a default in the system.
        Editing goes in markdown format, and then the markdown
        converts into HTML, before uploading to Evernote.
        """

        # Try to find default editor in the system.
        editor = self.editor
        if not editor:
            editor = os.environ.get("editor")

        if not editor:
            editor = os.environ.get("EDITOR")

        if not editor:
            # If default editor is not finded, then use nano as a default.
            if sys.platform == "win32":
                editor = config.DEF_WIN_EDITOR
            else:
                editor = config.DEF_UNIX_EDITOR

        # Make a system call to open file for editing.
        logging.debug("launch system editor: %s %s" % (editor, self.tempfile))

        out.preloader.stop()
        os.system(editor + " " + self.tempfile)
        out.preloader.launch()
        newContent = open(self.tempfile, "r").read()

        return newContent

    def deleteTempfile(self):
        os.remove(self.tempfile)
