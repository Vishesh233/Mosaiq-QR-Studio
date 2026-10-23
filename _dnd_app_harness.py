"""Test harness for _dnd_test.py (not part of the product).

Runs the real app and, every 100 ms, writes what the Scan page shows to a JSON
file so another process can drop files on the window and check the outcome.
Commands arrive as a JSON file: {"cmd": "show_scan" | "show_generate" |
"start_camera" | "clear" | "quit"}.

usage: python _dnd_app_harness.py STATE.json CMD.json
"""
import json
import os
import sys
import time
import tkinter

os.environ["QRSTUDIO_NO_SPLASH"] = "1"

from ui.app import QRCodeStudioApp

state_path, cmd_path = sys.argv[1], sys.argv[2]

import _test_dialogs
_test_dialogs.install()
app = QRCodeStudioApp()
root = app.root
sp = app.scan_page
uc, rc = sp.upload_card, sp.result_card


class FakeCamera:
    """A camera that shows a grey frame forever; remembers whether it was released."""

    released = False

    def __init__(self):
        import numpy as np
        self.frame = np.full((480, 640, 3), 90, np.uint8)
        FakeCamera.released = False

    def read(self):
        time.sleep(0.02)
        return True, self.frame

    def release(self):
        FakeCamera.released = True


def rect(widget):
    return [widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_width(), widget.winfo_height()]


def snapshot():
    return {
        "ready": True,
        "dnd_error": app.dnd_error,
        "result": rc.result,
        "label": rc.result_label.cget("text"),
        "chip": rc.status_chip.cget("text"),
        "action": list(rc.action) if rc.action else None,
        "has_content": uc.has_content,
        "image_path": uc.image_path,
        "subtitle": uc.subtitle.cget("text"),
        "title": uc.title_label.cget("text"),
        "camera_running": sp.camera is not None,
        "camera_released": FakeCamera.released,
        "upload_rect": rect(uc.camera_frame if uc.camera_visible else uc.upload_frame),
        "result_rect": rect(rc),
        "generate_rect": rect(app.generate_page),
        "scan_visible": bool(sp.winfo_ismapped()),
        "state": root.state(),
    }


def write_state():
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(snapshot(), fh)
    try:
        os.replace(tmp, state_path)
    except PermissionError:
        pass            # the test process is reading it right now; next tick retries


def run_command():
    if not os.path.exists(cmd_path):
        return
    try:
        with open(cmd_path, encoding="utf-8") as fh:
            cmd = json.load(fh)["cmd"]
    except (OSError, ValueError, KeyError):
        return                                  # half-written; try next tick
    os.remove(cmd_path)

    if cmd == "show_scan":
        app.show_scan_page()
    elif cmd == "show_generate":
        app.show_generate_page()
    elif cmd == "start_camera":
        sp.camera_factory = FakeCamera
        sp.start_camera()
    elif cmd == "clear":
        rc.clear()
        uc.clear()
    elif cmd == "quit":
        app.close()
        return


def tick():
    try:
        run_command()
        write_state()
        root.after(100, tick)
    except tkinter.TclError:
        pass            # the window was closed by the "quit" command


def setup():
    app.show_scan_page()
    root.attributes("-topmost", True)
    root.lift()
    tick()


root.after(1500, setup)
app.run()
