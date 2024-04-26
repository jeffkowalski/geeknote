# -*- coding: utf-8 -*-

from . import out
import sys
import time


def checkIsInt(value):
    try:
        int(value)
        return True
    except ValueError:
        return False


def getch():
    """
    Pause program until any keyboard key is pressed
    (Gets a character from the console without echo)
    """
    try:
        import msvcrt

        return msvcrt.getch()

    except ImportError:
        import sys
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


def strip(data):
    if not data:
        return data

    if isinstance(data, bytes):
        data = data.decode('utf-8')

    if isinstance(data, dict):
        items = iter(data.items())
        return dict([[key.strip(" \t\n\r\"'"), val] for key, val in items])

    if isinstance(data, list):
        return [val.strip(" \t\n\r\"'") for val in data]

    if isinstance(data, str):
        return data.strip(" \t\n\r\"'")

    raise Exception("Unexpected args type: " "%s. Expect list or dict" % type(data))


class ExitException(Exception):
    pass


def _exit(message, code):
    out.preloader.exit(code)
    time.sleep(0.33)
    raise ExitException(message)


def exit(message="exit", code=0):
    _exit(message, code)


def exitErr(message="exit", code=1):
    _exit(message, code)


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


def decodeArgs(args):
    return [stdinEncode(val) for val in args]


def stdoutEncode(data):
    # this is not for logging output, it is for output from geeknote queries to evernote
    if isinstance(sys.stdout.encoding, str) and sys.stdout.encoding != 'utf-8':
        return data.encode('utf-8').decode(sys.stdout.encoding)
    else:
        return data


def stdinEncode(data):
    if isinstance(sys.stdin.encoding, str) and sys.stdin.encoding.lower() != 'utf-8':
        return data.encode(sys.stdin.encoding).decode('utf-8')
    else:
        return data
