"""End-to-end test of the BUILT exe (dist\\MosaiqQRStudio\\MosaiqQRStudio.exe):

  * the process runs with PerMonitorV2 DPI awareness (from its embedded manifest)
  * the window opens maximized and the Scan page can be opened
  * Screen Region works on this PC's real display scaling: a QR code is shown in a window of
    this test, the exe's overlay is dragged around it with the real mouse, and the crop that
    comes back (read from the exe window with PrintWindow, never from the screen) still
    decodes; the exe's own result is read through its "Copy password" button.
  * closing the window exits the process by itself.

Only the exe's own window is ever captured. THE MOUSE MOVES BY ITSELF FOR ~10 SECONDS and the
exe hides itself briefly (that is the Screen Region feature): keep your hands off the mouse.

Run:  .venv\\Scripts\\python.exe _frozen_exe_test.py        (build first: .\\build.ps1)
"""
import ctypes
import os
import subprocess
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# MOSAIQ_TEST_EXE points the test at another copy of the build (the cold-start check runs a fresh copy each time).
EXE = os.environ.get("MOSAIQ_TEST_EXE") or os.path.join(HERE, "dist", "MosaiqQRStudio", "MosaiqQRStudio.exe")

# This process drives real mouse coordinates, so it must be per-monitor aware itself.
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

import numpy as np
import win32api
import win32clipboard
import win32con
import win32gui
from PIL import ImageTk

import _window_capture as wc
from utils import qr_payloads
from utils.qr_generator import QRGenerator
from utils.qr_scanner import QRScanner

problems = []
checks = [0]


def check(name, ok, detail=""):
    checks[0] += 1
    if not ok:
        problems.append(f"{name} {detail}".strip())


def refuse_if_app_running():
    """Another copy of the built app (yours, or one a failed run left behind) would sit on top of this
    test's windows and make its clicks land in the wrong place: say so and stop."""
    import subprocess as _sp
    out = _sp.run(["powershell", "-NoProfile", "-Command",
                   "Get-Process MosaiqQRStudio -ErrorAction SilentlyContinue | "
                   "Where-Object { $_.Path -like '*dist?MosaiqQRStudio?*' } | ForEach-Object { $_.Id }"],
                  capture_output=True, text=True).stdout.split()
    if out:
        print(f"STOP: Mosaiq QR Studio from dist is already running (process {', '.join(out)}). "
              "Close it and run this test again; nothing was started.")
        sys.exit(2)


def main():
    refuse_if_app_running()
    if not os.path.exists(EXE):
        print("dist exe not found; build it first")
        sys.exit(2)

    env = dict(os.environ, QRSTUDIO_NO_SPLASH="1")
    launched = time.time()
    proc = subprocess.Popen([EXE], env=env)
    target_root = tk.Tk()
    target_root.withdraw()
    target = None

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            target_root.update()
            time.sleep(0.02)

    def wait_for(cond, timeout, step=0.1):
        end = time.time() + timeout
        while time.time() < end:
            target_root.update()
            result = cond()
            if result:
                return result
            time.sleep(step)
        return None

    def click(x, y):
        win32api.SetCursorPos((x, y))
        pump(0.2)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        pump(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        pump(0.9)

    def region_sig(hwnd, box):
        return np.asarray(wc.capture_window(hwnd).crop(box).convert("L"), dtype=float)

    try:
        hwnd = wait_for(lambda: wc.find_main_window(proc.pid), 30)
        check("exe window appears", bool(hwnd))
        if not hwnd:
            return
        print(f"[exe] timing: window after {time.time() - launched:.1f} s")
        pump(3)

        # ---- DPI awareness comes from the manifest ----
        user32 = ctypes.windll.user32
        context = user32.GetWindowDpiAwarenessContext(hwnd)
        is_pmv2 = bool(user32.AreDpiAwarenessContextsEqual(ctypes.c_void_p(context), ctypes.c_void_p(-4)))
        check("exe runs PerMonitorV2", is_pmv2)
        dpi = user32.GetDpiForSystem()
        print(f"[exe] DPI awareness PerMonitorV2: {is_pmv2}; system scaling {dpi / 96 * 100:.0f}%")
        check("window is maximized", win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED)

        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        pump(0.5)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        # Positions in the 2.2 layout (physical px, window-relative): the four source tiles share
        # the left card, the pinned buttons sit at the bottom of the right column.
        region_tile = (365 + int((width - 555 - 365) * 0.625), 233)
        button_x, button_y = width - 280, height - 142

        # ---- open the Scan page (verified from the window's own pixels) ----
        header = (380, 250, 1290, 340)
        opened = False
        for attempt in range(4):
            before = region_sig(hwnd, header)
            click(left + 110, top + 295)
            if np.abs(region_sig(hwnd, header) - before).mean() > 0.5:
                opened = True
                break
        check("Scan page opens", opened)
        if not opened:
            return

        # ---- a QR code in a window of THIS test, in the middle of the screen ----
        text = qr_payloads.build_wifi("FrozenRegion", "region-pass-125", "WPA")
        image = QRGenerator().generate(text).convert("RGB")
        target = tk.Toplevel(target_root)
        target.overrideredirect(True)
        target.attributes("-topmost", True)
        target.geometry(f"{image.width}x{image.height}+300+260")
        photo = ImageTk.PhotoImage(image)
        label = tk.Label(target, image=photo, bd=0)
        label.image = photo
        label.pack()
        pump(0.6)
        box = (label.winfo_rootx(), label.winfo_rooty(), label.winfo_rootx() + image.width, label.winfo_rooty() + image.height)

        # ---- Screen Region: app hides, overlay appears, drag around the QR ----
        hidden = False
        for attempt in range(4):
            click(left + region_tile[0], top + region_tile[1])
            if wait_for(lambda: not win32gui.IsWindowVisible(hwnd), 2.5):
                hidden = True
                break
        check("Screen Region hides the window", hidden)
        if not hidden:
            return

        def overlay():
            for handle in wc.windows_of_process(proc.pid):
                l, t, r, b = win32gui.GetWindowRect(handle)
                if r - l >= 1900 and handle != hwnd:
                    return handle
            return None

        ov = wait_for(overlay, 6)
        check("overlay opens", bool(ov))
        if not ov:
            return
        ol, ot, orr, ob = win32gui.GetWindowRect(ov)
        screen = (win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79))
        print(f"[exe] overlay {orr - ol}x{ob - ot} at ({ol},{ot}); desktop {screen[0]}x{screen[1]} physical px")
        check("overlay covers the whole desktop", (orr - ol, ob - ot) == screen, f"{(orr - ol, ob - ot)} vs {screen}")

        pad = 16
        x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
        win32api.SetCursorPos((x0, y0)); pump(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0); pump(0.2)
        for i in range(1, 11):
            win32api.SetCursorPos((x0 + (x1 - x0) * i // 10, y0 + (y1 - y0) * i // 10)); pump(0.03)
        pump(0.3)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        released = time.time()

        back = wait_for(lambda: win32gui.IsWindowVisible(hwnd), 8)
        check("window comes back", bool(back))
        pump(2.0)
        check("window is maximized again", win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED)
        check("overlay is gone", overlay() is None)

        # ---- the crop that came back: read it from the exe window itself ----
        decoded = None
        for attempt in range(5):                           # the picture may still be painting
            shot = wc.capture_window(hwnd)
            decoded = QRScanner.decode_image(shot.crop((350, 230, width - 540, 660)))
            if decoded == text:
                break
            pump(1.0)
        check("the preview in the exe holds the whole QR (it decodes)", decoded == text, repr(decoded))

        # ---- the exe's own result: press "Copy password" and read the clipboard ----
        def clipboard_text():
            for _ in range(20):
                try:
                    win32clipboard.OpenClipboard()
                    break
                except win32clipboard.error:
                    time.sleep(0.05)
            else:
                return None
            try:
                win32clipboard.EmptyClipboard()
            finally:
                win32clipboard.CloseClipboard()
            return True

        clipboard_text()
        got = None
        # The first scan after a cold start can take a while (OpenCV is loaded by it): keep trying for 30 s
        # and say how long it took.
        positions = ((button_x, button_y), (button_x, button_y + 14), (button_x, button_y - 14))
        attempt = 0
        while not got and time.time() - released < 30:
            x, y = positions[attempt % 3]
            attempt += 1
            click(left + x, top + y)
            for _ in range(10):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                            got = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    finally:
                        win32clipboard.CloseClipboard()
                    break
                except win32clipboard.error:
                    time.sleep(0.05)
        print(f"[exe] timing: the result was there {time.time() - released:.1f} s after the drag ({attempt} click(s))")
        check("the exe decoded the region (Copy password gives the password)", got == "region-pass-125", repr(got))
        check("... within 12 s of the drag", time.time() - released < 12, f"{time.time() - released:.1f} s")

        # ---- closing with WM_CLOSE exits by itself ----
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        try:
            code = proc.wait(timeout=10)
            check("exe exits by itself after close", code == 0, f"exit code {code}")
        except subprocess.TimeoutExpired:
            check("exe exits by itself after close", False, "still running after 10 s")
    finally:
        if proc.poll() is None:
            proc.kill()
        if target is not None:
            target.destroy()
        target_root.destroy()
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    # (the report is printed after cleanup)


if __name__ == "__main__":
    main()
    if problems:
        print("FROZEN_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)
    print(f"FROZEN_OK: {checks[0]} checks")
