"""Keeps real dialogs off the screen while the tests run (not part of the app).

A message box or file dialog that really opens blocks the test until somebody clicks it.
``install()`` replaces every tkinter message box and file dialog with a recorder:

  * file dialogs answer "cancelled" (empty string) unless a test sets ``answers``
  * ``askyesno`` and friends answer "no" unless a test sets ``answers``
  * every call is kept in ``calls`` as (kind, title, message)

An error or warning box that nobody expected makes the test fail when it ends: the app showed
the user an error the test did not look for. A test that expects one passes the box it
saw to ``expect()`` (or installs its own mock over these, which bypasses the recording).

Usage, near the top of a test, before the window is created:

    import _test_dialogs
    dialogs = _test_dialogs.install()
"""
import atexit
import os
import sys
from tkinter import filedialog, messagebox

calls = []
answers = {}
_expected = []

_BOXES = ("showinfo", "showwarning", "showerror", "askyesno", "askokcancel",
          "askquestion", "askretrycancel", "askyesnocancel")
_FILE_DIALOGS = ("asksaveasfilename", "askopenfilename", "askopenfilenames", "askdirectory",
                 "asksaveasfile", "askopenfile")
_ALERTS = ("showwarning", "showerror")
_installed = False


def _box(kind):
    def fake(title=None, message=None, *args, **kwargs):
        calls.append((kind, title, message))
        if kind in answers:
            answer = answers[kind]
            return answer(title, message) if callable(answer) else answer
        if kind == "askquestion":
            return "no"
        if kind == "askyesnocancel":
            return None
        return False if kind.startswith("ask") else "ok"
    return fake


def _file_dialog(kind):
    def fake(*args, **kwargs):
        calls.append((kind, kwargs.get("title"), None))
        if kind in answers:
            answer = answers[kind]
            return answer(**kwargs) if callable(answer) else answer
        return () if kind == "askopenfilenames" else ""
    return fake


def unexpected():
    """Error and warning boxes shown and not claimed with expect()."""
    return [c for c in calls if c[0] in _ALERTS and c not in _expected]


def expect(*boxes):
    """Mark boxes (as found in ``calls``) as expected; a test calls this after checking them."""
    _expected.extend(boxes)


def clear():
    calls.clear()
    _expected.clear()


def _finish():
    stray = unexpected()
    if not stray:
        return
    for kind, title, message in stray:
        print(f"UNEXPECTED DIALOG: {kind}: {title!r}: {message!r}", file=sys.stderr)
    print("DIALOG_FAIL: the app showed an error/warning box the test did not expect")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)


def install():
    """Replace the dialogs (once per process); returns this module for ``calls`` / ``answers``."""
    global _installed
    if not _installed:
        for name in _BOXES:
            setattr(messagebox, name, _box(name))
        for name in _FILE_DIALOGS:
            setattr(filedialog, name, _file_dialog(name))
        atexit.register(_finish)
        _installed = True
    return sys.modules[__name__]
