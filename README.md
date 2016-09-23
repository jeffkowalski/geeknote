Geeknote for Evernote (or 印象笔记)  [![Travis CI](https://travis-ci.org/jeffkowalski/geeknote.svg?branch=master)](https://travis-ci.org/jeffkowalski/geeknote) [![Circle CI](https://circleci.com/gh/jeffkowalski/geeknote.svg?&style=shield)](https://circleci.com/gh/jeffkowalski/geeknote)
===

Geeknote is a command line client for Evernote that can be use on Linux, FreeBSD and OS X.

It allows you to:
* create notes in your Evernote account;
* create tags, notebooks;
* use Evernote search from the console using different filters;
* edit notes directly in the console using any editor, such as nano, vim or mcedit;
* synchronize your local files and directories with Evernote;
* use Evernote with cron or any scripts.

Geeknote is open source and written in Python. Geeknote can be used anywhere you have Python installed (even in Windows if you like).

In this document we'll show how to work with Evernote's notes, notebooks, and tags using Geeknote and how to use Geeknote sync.

## Installation
You can install Geeknote using [Homebrew](http://brew.sh/)/[Linuxbrew](https://github.com/Homebrew/linuxbrew), or from its source.

##### Homebrew installation

``` sh
brew install --HEAD geeknote
```

##### Downloading and installing from source

``` sh
# Install dependencies. (This example for Debian-based systems):
sudo apt-get update; sudo apt-get -y install python-setuptools

# Download the repository.
git clone git://github.com/jeffkowalski/geeknote.git

cd geeknote

# Installation

# - if you have only a python2 environment,
python setup.py build
pip install --upgrade .

# - or, to force python2 in python3 environments
python2 setup.py build
pip2 install --upgrade .
```

##### Testing
Geeknote has a non-destructive unit test suite with fair coverage.

Ensure pytest framework is installed
``` sh
pip install --upgrade pytest
```

Execute the tests
``` sh
py.test
```

##### Un-installation

If originally installed via homebrew,

``` sh
brew remove geeknote
```

If originally installed from source,

``` sh
pip uninstall geeknote
```

## Geeknote Settings
##### Authorizing Geeknote
After installation, Geeknote must be authorized with Evernote prior to use. To authorize your Geeknote in Evernote launch the command *login*:

``` sh
geeknote login
```

This will start the authorization process. Geeknote will ask you to enter your credentials just once to generate access token, which will be saved in local database. Re-authorization is not required, if you won't decide to change user.
After authorization you can start to work with Geeknote.

##### Logging out and changing users
If you want to change Evernote user you should launch *logout* command:

``` sh
geeknote logout
```

Afterward, you can repeat the authorization step.

##### (Yìnxiàng Bǐjì notes)

If you want to use Evernote's separate service in China Yìnxiàng Bǐjì (印象笔记),
you need to set the environment variable `GEEKNOTE_BASE` to `yinxiang`.

``` sh
GEEKNOTE_BASE=yinxiang geeknote login
# or
export GEEKNOTE_BASE=yinxiang
geeknote ...commands...
```

Yìnxiàng Bǐjì (印象笔记) is faster in China and it supports Chinese payment methods.
Be aware that Yìnxiàng Bǐjì will not have support for sharing social features
like Twitter or Facebook. Furthermore, since data are stored on servers in China,
Chinese authorities have the right to access their data according to current
regulations.

For more information, see:
[Evernote Launches Separate Chinese Service](https://blog.evernote.com/blog/2012/05/09/evernote-launches-separate-chinese-service/)

##### Examining your settings

``` sh
$ geeknote settings
Geeknote
******************************
Version: 2.0.5
App dir: /Users/username/.geeknote
Error log: /Users/username/.geeknote/error.log
Current editor: vim
Markdown2 Extras: None
Note extension: .markdown, .org
******************************
Username: username
Id: 11111111
Email: example@gmail.com
```

##### Setting up the default editor
You can edit notes within console editors in plain text or markdown format.

You can setup the default editor you want to use. To check which editor is now set up as a default call:

``` sh
geeknote settings --editor
```

To change the default editor call:

``` sh
geeknote settings --editor vim
```

To use `gvim` you need to prevent forking from the terminal with `-f`:

``` sh
geeknote settings --editor 'gvim -f'
```

###### Example

``` sh
$ geeknote settings --editor
Current editor is: nano
$ geeknote settings --editor vim
Editor successfully saved
$ geeknote settings --editor
Current editor is: vim
```

## Working with Notes
### Notes: Creating notes
The main functionality that we need is creating notes in Evernote.

##### Synopsis

``` sh
geeknote create --title <title>
               [--content <content>]
               [--tag <tag>]
               [--created <date and time>]
               [--resource <attachment filename>]
               [--notebook <notebook where to save>]
               [--reminder <date and time>]
```

##### Options

| Option     | Argument | Description |
|------------|----------|-------------|
| ‑‑title    | title    | With this option we specify the title of new note we want to create. |
| ‑‑content  | content  | Specify the content of new note. The content must not contain double quotes. |
| ‑‑tag      | tag      | Specify tag that our note will have. May be repeated. |
| ‑‑created  | date     | Set note creation date and time in either 'yyyy-mm-dd' or 'yyyy-mm-dd HH:MM' format. |
| ‑‑resource | attachment filename, like: document.pdf |Specify file to be attached to the note.  May be repeated. |
| ‑‑notebook | notebook where to save | Specify the notebook where new note should be saved. This option is not required. If it isn't given, the note will be saved in default notebook. If notebook doesn't exist Geeknote will create it automatically. |
| ‑‑reminder | date     | Set reminder date and time in either 'yyyy-mm-dd' or 'yyyy-mm-dd HH:MM' format. Alternatively use TOMORROW and WEEK for 24 hours and a week ahead respectively, NONE for a reminder without a time. Use DONE to mark a reminder as completed. |
| --raw      |          | A flag signifying the content is in raw ENML format. |

##### Description
This command allows us to create a new note in Evernote. Geeknote has designed for using in console, so we have some restrictions like inability to use double quotes in **--content** option. But there is a method to avoid it - use stdin stream or file synchronization, we show it later in documentation.

##### Examples

Creating a new note with a PDF attachment:

``` sh
geeknote create --title "Shopping list"
                --content "Don't forget to buy milk, turkey and chips."
                --resource shoppinglist.pdf
                --notebook "Family"
                --tag "shop" --tag "holiday" --tag "important"
```

Creating a new note and editing content in editor (notice the lack of `content` argument):

``` sh
geeknote create --title "Meeting with customer"
                --notebook "Meetings"
                --tag "projectA" --tag "important" --tag "report"
                --created "2015-10-23 14:30"

```

### Notes: Searching for notes in Evernote

You can easily search notes in Evernote with Geeknote and output results in the console.

##### Synopsis

``` sh
geeknote find --search <text to find>
             [--tag <tag>]
             [--notebooks <notebook list>]
             [--date <date or date range>]
             [--count <how many results to show>]
             [--exact-entry]
             [--content-search]
             [--url-only]
             [--reminders-only]
             [--ignore-completed]
             [--with-tags]
             [--with-notebook]
             [--guid]
```

##### Description

Use **find** to search through your Evernote notebooks, with options to search and print more detail. Geeknote remembers the result of the last search. So, you can use the ID number of the note's position for future actions.
For example:

``` sh
$ geeknote find --search "Shopping"

Total found: 2
  1 : Grocery Shopping List
  2 : Gift Shopping List

$ geeknote show 2
```

That will show you the note "Gift Shopping List".

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑search           | text to find    | Set the text to find. You can use &quot;&#042;&quot; like this: *--search &quot;Shop&#042;&quot;* |
| ‑‑tag              | tag             | Filter by tag. May be repeated. |
| ‑‑notebooks        | list of notebooks to search | Search just in notebook/notebooks you need. The list of notebooks specify by comma. |
| ‑‑date             | date or range   | Filter by date. You can set a single date in 'yyyy-mm-dd' format or a range with 'yyyy-mm-dd/yyyy-mm-dd' |
| ‑‑count            | how many results to show | Limits the number of displayed results. |
| ‑‑content-search   |                 | *find* command searches by note's title. If you want to search by note's content - set this flag.                         |
| ‑‑exact-entry      |                 | By default Geeknote has a smart search, so it searches fuzzy entries. But if you need exact entry, you can set this flag. |
| ‑‑guid             |                 | Show GUID of the note as substitute for result index. |
| ‑‑ignore-completed |                 | Include only unfinished reminders. |
| ‑‑reminders-only   |                 | Include only notes with a reminder. |
| ‑‑with-notebook    |                 | Show notebook which contains the note after note title. |
| ‑‑with-tags        |                 | Show tags of the note after note title. |
| ‑‑with-url         |                 | Show results as a list of URLs to each note in Evernote's web-client. |

##### Examples

``` sh
geeknote find --search "How to patch KDE2" --notebooks "jokes" --date 2015-10-14/2015-10-28
geeknote find --search "apt-get install apache nginx" --content-search --notebooks "manual"
```

### Notes: Editing notes

With Geeknote you can edit your notes in Evernote using any editor you like (nano, vi, vim, emacs, etc.)

##### Synopsis

``` sh
geeknote edit --note <title or GUID of note to edit>
             [--title <the new title>]
             [--content <new content or "WRITE">]
             [--resource <attachment filename>]
             [--tag <tag>]
             [--created <date and time>]
             [--notebook <new notebook>]
             [--reminder <date and time>]
```

##### Options

| Option     | Argument | Description |
|------------|----------|-------------|
| ‑‑note     | title of note which to edit | Tells Geeknote which note we want to edit. Geeknote searches by that name to locate a note. If Geeknote finds more than one note with such name, it will ask you to make a choice. |
| ‑‑title    | a new title | Use this option if you want to rename your note. Just set a new title, and Geeknote will rename the old one. |
| ‑‑content  | new content or "WRITE" | Enter the new content of your notes in text, or write instead the option "WRITE". In the first case the old content of the note will be replaced with the new content. In the second case Geeknote will get the current content and open it in Markdown in a text editor. |
| ‑‑resource | attachment filename, like: document.pdf | Specify file to be attached to the note.  May be repeated.  Will replace existing resources. |
| ‑‑tag      | tag      | Tag to be assigned to the note.  May be repeated.  Will replace existing tags. |
| ‑‑created  | date     | Set note creation date date and time in either 'yyyy-mm-dd' or 'yyyy-mm-dd HH:MM' format. |
| ‑‑notebook | target notebook | With this option you can change the notebook which contains your note. |
| ‑‑reminder | date     | Set reminder date and time in either 'yyyy-mm-dd' or 'yyyy-mm-dd HH:MM' format. Alternatively use TOMORROW and WEEK for 24 hours and a week ahead respectively, NONE for a reminder without a time. Use DONE to mark a reminder as completed. Use DELETE to remove reminder from a note. |
| --raw      |          | A flag signifying the content is in raw ENML format. |

##### Examples

Renaming the note:

``` sh
geeknote edit --note "Naughty List" --title "Nice List"
```

Renaming the note and editing content in editor:

``` sh
geeknote edit --note "Naughty List" --title "Nice List" --content "WRITE"
```

### Notes: Showing note content

You can output any note in console using command *show* either independently or as a subsequent command to *find*. When you use *show* on a search made previously in which there was more than one result, Geeknote will ask you to make a choise.

##### Synopsis

``` sh
geeknote show <text or GUID to search and show>
```

##### Examples

``` sh
$ geeknote show "Shop*"

Total found: 2
  1 : Grocery Shopping List
  2 : Gift Shopping List
  0 : -Cancel-
: _
```

As we mentioned before, *show* can use the results of previous search, so if you have already done the search, just call *show* with number of previous search results.

``` sh
$ geeknote find --search "Shop*"

Total found: 2
  1 : Grocery Shopping List
  2 : Gift Shopping List

$ geeknote show 2
```

### Notes: Removing notes
You can remove notes with Geeknotes from Evernote.

##### Synopsis

``` sh
geeknote remove --note <note name or GUID>
               [--force]
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑note             | note name       | Name of the note you want to delete. If Geeknote will find more than one note, it will ask you to make a choice. |
| ‑‑force            |                 | A flag that says that Geeknote shouldn't ask for confirmation to remove note. |

##### Examples

``` sh
geeknote remove --note "Shopping list"
```

## Working with Notebooks
### Notebooks: show the list of notebooks

Geeknote can display the list of all notebooks you have in Evernote.

##### Synopsis

``` sh
geeknote notebook-list [--guid]
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑guid             |                 | Show GUID of the notebook as substitute for result index. |

### Notebooks: creating a notebook
With Geeknote you can create notebooks in Ever.0.0note right in console!

##### Synopsis

``` sh
geeknote notebook-create --title <notebook title>
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑title            | notebook title  | With this option we specify the title of new note we want to create. |

##### Examples

``` sh
geeknote notebook-create --title "Sport diets"
```

### Notebooks: renaming a notebook

With Geeknote it's possible to rename existing notebooks in Evernote.

##### Synopsis

``` sh
geeknote notebook-edit --notebook <old name>
                       --title <new name>
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑notebook         | old name        | Name of existing notebook you want to rename. |
| ‑‑title            | new name        | New title for notebook |

##### Examples

``` sh
geeknote notebook-edit --notebook "Sport diets" --title "Hangover"
```

## Working with Tags
### Tags: showing the list of tags

You can get the list of all tags you have in Evernote.

##### Synopsis

``` sh
geeknote tag-list [--guid]
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑guid             |                 | Show GUID of the tag as substitute for result index. |

### Tags: creating a new tag
Usually tags are created with publishing new note. But if you need, you can create a new tag with Geeknote.

##### Synopsis

``` sh
geeknote tag-create --title <tag name to create>
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑title            | tag name to create | Set the name of tag you want to create. |

##### Examples

``` sh
geeknote tag-create --title "Hobby"
```

### Tags: renaming a tag

You can rename the tag:

##### Synopsis

``` sh
geeknote tag-edit --tagname <old name>
                  --title <new name>
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑tagname          | old name        | Name of existing tag you want to rename. |
| ‑‑title            | new name        | New name for tag. |

##### Examples

``` sh
geeknote tag-edit --tagname "Hobby" --title "Girls"
```

## gnsync - synchronization app

Gnsync is an additional application installed with Geeknote. Gnsync allows synchronization of files in local directories with Evernote. It works with text data and html with picture attachment support.

##### Synopsis

``` sh
gnsync --path <path to directory which to sync>
      [--mask <unix shell-style wildcards to select the files, like *.* or *.txt or *.log>]
      [--format <in what format to save the note - plain, markdown, or html>]
      [--notebook <notebook, which will be used>]
      [--all]
      [--logpath <path to logfile>]
      [--two-way]
      [--download]
```

##### Options

| Option             | Argument        | Description |
|--------------------|-----------------|-------------|
| ‑‑path             | directory to sync | The directory you want to sync with Evernote. It should be the directory with text content files. |
| ‑‑mask             | unix shell-style wildcards to select the files | You can tell *gnsync* what filetypes to sync. By default *gnsync* tries to open every file in the directory. But you can set the mask like: &#042;.txt, &#042;.log, &#042;.md, &#042;.markdown. |
| ‑‑format           | in what format to save the note - plain or markdown | Set the engine which to use while files uploading. *gnsync* supports markdown and plain text formats. By default it uses plain text engine. |
| ‑‑notebook         | notebook where to save | You can set the notebook which will be syncronized with local directory. But if you won't set this option, *gnsync* will create new notebook with the name of the directory that you want to sync. |
| ‑‑all              |                 | You can specify to synchronize all notebooks already on the server, into subdirectories of the path. Useful with --download to do a backup of all notes. |
| ‑‑logpath          | path to logfile | *gnsync* can log information about syncing and with that option you can set the logfile. |
| ‑‑two-way          |                 | Normally *gnsync* will only upload files. Adding this flag will also make it download any notes not present as files in the notebook directory (after uploading any files not present as notes) |
| ‑‑download-only    |                 | Normally *gnsync* will only upload files. Adding this flag will make it download notes, but not upload any files |

##### Description
The application *gnsync* is very useful in system adminstration, because you can syncronize you local logs, statuses and any other production information with Evernote.

##### Examples

``` sh
gnsync --path /home/project/xmpp/logs/
       --mask "*.logs"
       --logpath /home/user/logs/xmpp2evernote.log
       --notebook "XMPP logs"
```

### Original Contributors
* Vitaliy Rodnenko
* Simon Moiseenko
* Ivan Gureev
* Roman Gladkov
* Greg V
* Ilya Shmygol
