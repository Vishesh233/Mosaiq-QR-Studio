"""Drag & drop tests.

Part 1 (fallback, in-process): without tkinterdnd2 / with a broken tkdnd library
the app must still start, show no drop hint, and report why.

Part 2 (real drop, two processes): the app runs in _dnd_app_harness.py; THIS
process is the drag source. Files are put on the clipboard, that IDataObject is
dragged with OLE DoDragDrop, and the mouse pointer is moved over the app window
and released, which is what Explorer does. THE POINTER MOVES BY ITSELF FOR A
FEW SECONDS PER DROP: keep your hands off the mouse while this runs.

Run:  .venv\\Scripts\\python.exe _dnd_test.py
Exit code 0 = every check passed.
"""
import sys
sys.coinit_flags = 2          # OLE drag and drop needs a single-threaded apartment
import ctypes
import faulthandler
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ["QRSTUDIO_NO_SPLASH"] = "1"

import pythoncom
import win32api
import win32con
import win32gui
from win32com.server.util import wrap

from PIL import Image

from utils import qr_payloads
from utils.qr_generator import QRGenerator

DROPEFFECT_COPY = 1

problems = []
checks = [0]


def check(name, ok, detail=""):
    checks[0] += 1
    if not ok:
        problems.append(f"{name} {detail}".strip())


# ======================================================================
# Part 1: fallback paths
# ======================================================================

def test_fallbacks():
    import customtkinter as ctk
    import ui.dnd_support as dnd

    # tkinterdnd2 missing
    saved = dnd.TkinterDnD, dnd._IMPORT_ERROR
    dnd.TkinterDnD, dnd._IMPORT_ERROR = None, ImportError("simulated: not installed")
    try:
        root, reason = dnd.create_root()
        check("fallback: missing package reports a reason", bool(reason) and "not installed" in reason, str(reason))
        check("fallback: plain window created", root.winfo_exists() == 1)
        root.destroy()
    finally:
        dnd.TkinterDnD, dnd._IMPORT_ERROR = saved

    # tkdnd native library fails to load
    original = dnd.TkinterDnD._require

    def broken(_root):
        raise RuntimeError("simulated: unable to load tkdnd")

    dnd.TkinterDnD._require = broken
    try:
        root, reason = dnd.create_root()
        check("fallback: broken tkdnd reports a reason", bool(reason) and "tkdnd" in reason, str(reason))
        check("fallback: plain window created (broken tkdnd)", root.winfo_exists() == 1)
        root.destroy()
    finally:
        dnd.TkinterDnD._require = original

    # The whole app starts and runs without drop support.
    import ui.app as appmod
    appmod.create_root = lambda: (ctk.CTk(), "simulated: no drop support")
    try:
        app = appmod.QRCodeStudioApp()
        sp = app.scan_page
        check("fallback: app starts", app.root.winfo_exists() == 1)
        check("fallback: no drop hint",
              sp.upload_card.subtitle.cget("text") == "Click to browse" and not sp.drop_enabled)
        sp.scan_dropped_files([])           # the handler stays safe to call
        app.root.update()
        check("fallback: handler reports non-image", "not an image" in sp.result_card.result_label.cget("text"))
        app.root.destroy()
    finally:
        appmod.create_root = dnd.create_root


# ======================================================================
# Part 2: real OLE drag and drop
# ======================================================================

class DropSource:
    _com_interfaces_ = [pythoncom.IID_IDropSource]
    _public_methods_ = ["QueryContinueDrag", "GiveFeedback"]

    def QueryContinueDrag(self, escape_pressed, key_state):
        if escape_pressed:
            return 0x40101                      # DRAGDROP_S_CANCEL
        if not key_state & win32con.MK_LBUTTON:
            return 0x40100                      # DRAGDROP_S_DROP
        return 0

    def GiveFeedback(self, effect):
        return 0x40102                          # DRAGDROP_S_USEDEFAULTCURSORS


def clipboard_files(paths):
    quoted = ",".join("'" + p.replace("'", "''") + "'" for p in paths)
    subprocess.run(["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Path {quoted}"], check=True)


# Runs in its own process: pythoncom.DoDragDrop keeps the GIL, so a thread in
# the process that drags could never move the mouse.
MOUSE_DRIVER = """
import ctypes, sys, time
import win32api, win32con
ctypes.windll.shcore.SetProcessDpiAwareness(2)
sx, sy, tx, ty = map(int, sys.argv[1:5])
win32api.SetCursorPos((sx, sy))
time.sleep(0.15)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
time.sleep(0.5)
for i in range(1, 26):
    win32api.SetCursorPos((sx + (tx - sx) * i // 25, sy + (ty - sy) * i // 25))
    time.sleep(0.02)
time.sleep(0.5)
win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
"""


_source_class_counter = [0]


def real_drop(paths, target_xy):
    """Drag `paths` (as a real file drag) and release over target_xy (screen px).

    Like Explorer, the drag starts from a window's WM_LBUTTONDOWN: OLE needs a
    window to capture the mouse. Returns the effect Windows reported
    (0 = nobody accepted the drop).
    """
    clipboard_files(paths)
    for attempt in range(20):
        try:
            data = pythoncom.OleGetClipboard()
            break
        except pythoncom.com_error:
            # Another program holds the shared clipboard for a moment.
            if attempt == 19:
                raise
            time.sleep(0.1)
    source = wrap(DropSource(), pythoncom.IID_IDropSource)

    size = 60
    sx, sy = target_xy[0] - 320, target_xy[1] - 140
    centre = (sx + size // 2, sy + size // 2)
    original = win32api.GetCursorPos()
    outcome = {}

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == win32con.WM_LBUTTONDOWN and "effect" not in outcome:
            result = pythoncom.DoDragDrop(data, source, DROPEFFECT_COPY)
            outcome["effect"] = result[-1] if isinstance(result, tuple) else result
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    _source_class_counter[0] += 1
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = f"MosaiqDndSource{_source_class_counter[0]}"
    wc.lpfnWndProc = wndproc
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.hbrBackground = win32gui.GetStockObject(win32con.WHITE_BRUSH)
    atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindowEx(
        win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW, atom, "drag source",
        win32con.WS_POPUP | win32con.WS_VISIBLE, sx, sy, size, size,
        0, 0, wc.hInstance, None
    )

    mouse = None
    try:
        win32gui.PumpWaitingMessages()
        mouse = subprocess.Popen([sys.executable, "-c", MOUSE_DRIVER,
                                  str(centre[0]), str(centre[1]),
                                  str(target_xy[0]), str(target_xy[1])])
        end = time.time() + 30
        while "effect" not in outcome:
            if time.time() > end:
                raise RuntimeError("the drag never completed")
            win32gui.PumpWaitingMessages()
            time.sleep(0.005)
    finally:
        if mouse is not None:
            try:
                mouse.wait(timeout=10)
            except subprocess.TimeoutExpired:
                mouse.kill()
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        win32gui.DestroyWindow(hwnd)
        win32gui.UnregisterClass(atom, wc.hInstance)
        win32api.SetCursorPos(original)
    return outcome["effect"]


def test_real_drop():

    # This process is the drag SOURCE and drives the mouse in real screen pixels.
    ctypes.windll.shcore.SetProcessDpiAwareness(2)

    tmp = tempfile.mkdtemp()
    state_path = os.path.join(tmp, "state.json")
    cmd_path = os.path.join(tmp, "cmd.json")
    harness = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_dnd_app_harness.py")
    proc = subprocess.Popen([sys.executable, harness, state_path, cmd_path])

    def read_state():
        try:
            with open(state_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def wait_state(pred, timeout=6.0):
        end = time.time() + timeout
        while time.time() < end:
            last = read_state()
            if last and pred(last):
                return last
            time.sleep(0.05)
        return None

    def command(name):
        with open(cmd_path, "w", encoding="utf-8") as fh:
            json.dump({"cmd": name}, fh)
        end = time.time() + 5
        while os.path.exists(cmd_path) and time.time() < end:
            time.sleep(0.05)
        time.sleep(0.4)

    def centre(rect):
        return (rect[0] + rect[2] // 2, rect[1] + rect[3] // 2)

    def drop_and_wait(paths, where, pred, timeout=6.0):
        # Real mouse input shares the desktop with whoever is at the keyboard, so
        # allow one retry; a genuine product bug fails both attempts.
        effect = 0
        for attempt in (1, 2):
            try:
                effect = real_drop(paths, where)
            except RuntimeError as e:
                print(f"[dnd] attempt {attempt}: {e}")
                continue
            st = wait_state(pred, timeout)
            if st is not None:
                return effect, st
            print(f"[dnd] attempt {attempt}: no matching result (effect={effect})")
        return effect, None

    try:
        st = wait_state(lambda s: s.get("scan_visible"), timeout=25)
        check("harness app started", st is not None)
        if st is None:
            return
        check("dnd available in this environment", st["dnd_error"] is None, str(st["dnd_error"]))
        check("drop hint is shown", "drop an image" in st["subtitle"], st["subtitle"])
        time.sleep(0.5)

        gen = QRGenerator()

        # 1. one image, unicode path -> scanned, preview, result
        text1 = qr_payloads.build_upi("drop@okaxis", "Drop Shop", "10.00", "dnd")
        p1 = os.path.join(tmp, "ड्रॉप क्यूआर ✓.png")
        gen.generate(text1).save(p1)
        effect, st = drop_and_wait([p1], centre(read_state()["upload_rect"]), lambda s: s["result"] == text1)
        check("1: Windows accepted the drop", effect != 0, f"effect={effect}")
        check("1: dropped image scanned", st is not None, repr((read_state() or {}).get("result")))
        if st:
            check("1: shows UPI result", st["action"] == ["Copy UPI ID", "drop@okaxis"])
            check("1: preview keeps the file path", st["has_content"] and os.path.normpath(st["image_path"] or "") == os.path.normpath(p1), repr(st["image_path"]))

        # 2. drop on the RESULT panel (a different widget on the page) also works
        command("clear")
        text2 = "https://example.com/dropped-on-result"
        p2 = os.path.join(tmp, "second.png")
        gen.generate(text2).save(p2)
        effect, st = drop_and_wait([p2], centre(read_state()["result_rect"]), lambda s: s["result"] == text2)
        check("2: drop on result panel scanned", st is not None, f"effect={effect}")

        # 3. non-image file -> clear message
        command("clear")
        p3 = os.path.join(tmp, "notes.txt")
        with open(p3, "w") as fh:
            fh.write("hello")
        effect, st = drop_and_wait([p3], centre(read_state()["upload_rect"]),
                                   lambda s: "not an image" in s["label"])
        check("3: non-image rejected with a message", st is not None and st["result"] == "",
              repr(read_state()["label"]))

        # 4. several files: first image is scanned
        command("clear")
        text4 = "first image wins"
        p4a = os.path.join(tmp, "a_first.png")
        p4b = os.path.join(tmp, "b_second.png")
        gen.generate(text4).save(p4a)
        gen.generate("second").save(p4b)
        effect, st = drop_and_wait([p4a, p4b], centre(read_state()["upload_rect"]),
                                   lambda s: s["result"] != "")
        check("4: the first image of the drop is scanned", st is not None and st["result"] == text4,
              repr(st and st["result"]))

        # 5. image with no QR -> not-found message
        command("clear")
        p5 = os.path.join(tmp, "blank.png")
        Image.new("RGB", (200, 200), "white").save(p5)
        effect, st = drop_and_wait([p5], centre(read_state()["upload_rect"]),
                                   lambda s: s["chip"] == "Nothing decoded")
        check("5: blank image -> no QR message", st is not None and st["result"] == "")

        # 6. corrupt image -> clear error
        command("clear")
        p6 = os.path.join(tmp, "broken.png")
        with open(p6, "wb") as fh:
            fh.write(b"not really a png")
        effect, st = drop_and_wait([p6], centre(read_state()["upload_rect"]),
                                   lambda s: "not a readable image" in s["label"])
        check("6: corrupt image -> error message", st is not None, repr(read_state()["label"]))

        # 7. drop while the camera view is open stops the camera and scans
        command("clear")
        command("start_camera")
        st = wait_state(lambda s: s["camera_running"])
        check("7: fake camera running", st is not None)
        effect, st = drop_and_wait([p2], centre(read_state()["upload_rect"]),
                                   lambda s: s["result"] == text2 and not s["camera_running"])
        check("7: drop stops the camera and scans", st is not None and st["camera_released"],
              repr(read_state()))

        # 8. dropping on the Generate page is not accepted
        command("show_generate")
        g = read_state()["generate_rect"]
        effect = real_drop([p2], (g[0] + g[2] // 2, g[1] + 300))
        check("8: Generate page does not accept drops", effect == 0, f"effect={effect}")
    finally:
        try:
            command("quit")
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            problems.append("harness did not exit; killed")


def main():
    # A stuck drag would otherwise hang forever with the mouse button held.
    faulthandler.dump_traceback_later(150, exit=True)
    try:
        test_fallbacks()
    except Exception as e:
        import traceback
        traceback.print_exc()
        problems.append(f"test_fallbacks raised {type(e).__name__}: {e}")
    try:
        pythoncom.OleInitialize()
        test_real_drop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        problems.append(f"test_real_drop raised {type(e).__name__}: {e}")

    if problems:
        print("DND_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)

    print(f"DND_OK: {checks[0]} checks")


if __name__ == "__main__":
    main()
