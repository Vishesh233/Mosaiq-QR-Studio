"""Optional drag & drop of files onto the window (tkinterdnd2 + the tkdnd Tcl package).

create_root() returns (root, error). `error` is None when drops are available;
otherwise it explains why not and the app runs normally without drop support
(Browse, Paste, Screen Region and Camera all still work).
"""

import tkinter
import traceback

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError as e:
    DND_FILES = None
    TkinterDnD = None
    _IMPORT_ERROR = e
else:
    _IMPORT_ERROR = None


def create_root():

    if TkinterDnD is None:
        reason = f"tkinterdnd2 is not installed ({_IMPORT_ERROR})"
        print(f"[dnd] drag & drop disabled: {reason}")
        return ctk.CTk(), reason

    class DnDRoot(ctk.CTk, TkinterDnD.DnDWrapper):

        def __init__(self):
            super().__init__()
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except (RuntimeError, tkinter.TclError):
                self.destroy()
                raise

    try:
        return DnDRoot(), None
    except (RuntimeError, tkinter.TclError) as e:
        traceback.print_exc()
        reason = f"the tkdnd library could not be loaded ({e})"
        print(f"[dnd] drag & drop disabled: {reason}")
        return ctk.CTk(), reason
