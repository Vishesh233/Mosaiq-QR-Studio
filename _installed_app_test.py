"""Drive the real app window once: Generate a QR code, scan it back, close the app.

Works on the built exe or on the installed Store package (launched through its app id), so the
same check runs before and after packaging. It moves the mouse and types: keep your hands off
the keyboard and mouse while it runs (about a minute; the intro plays first in the package).

Run (exe-intro plays the intro first, like a fresh install):  .venv\\Scripts\\python.exe _installed_app_test.py exe
      .venv\\Scripts\\python.exe _installed_app_test.py shell:AppsFolder\\<PackageFamilyName>!MosaiqQRStudio

Only the app's own window is captured (PrintWindow), never the screen.
Exit code 0 = generate and scan worked in that app.
"""
import ctypes
import os
import subprocess
import sys
import tempfile
import time

ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

import win32api
import win32clipboard
import win32con
import win32gui
import win32process

import _window_capture as wc
from utils.qr_generator import QRGenerator
from utils.qr_scanner import QRScanner

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "MosaiqQRStudio", "MosaiqQRStudio.exe")
URL = "https://example.com/installed-app-test"
PLAIN = "scan check 2.2.0.0"

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())
    print(("ok   " if ok else "FAIL ") + label + (f"  {detail}" if detail and not ok else ""))


def pump(seconds):
    time.sleep(seconds)


before_launch = set()          # windows of any other Mosaiq instance (for example the user's own)


def all_windows():
    found = []

    def collect(handle, _):
        if win32gui.IsWindowVisible(handle) and win32gui.GetWindowText(handle) == "Mosaiq QR Studio":
            _tid, pid = win32process.GetWindowThreadProcessId(handle)
            found.append((handle, pid))

    win32gui.EnumWindows(collect, None)
    return found


def find_window():
    """The main window this test started (not one already open), once the intro is over and it is
    shown maximized. Anything earlier (the intro's own windows) does not count."""
    for handle, pid in all_windows():
        if handle not in before_launch and win32gui.GetWindowPlacement(handle)[1] == win32con.SW_SHOWMAXIMIZED:
            return handle, pid
    return None, None


def intro_windows(main, pid):
    """Visible full-screen windows of the app other than the main one (the intro's last frame
    stays on top of the main window for a moment while it hands over)."""
    found = []

    def collect(handle, _):
        if handle != main and win32gui.IsWindowVisible(handle)                 and win32process.GetWindowThreadProcessId(handle)[1] == pid:
            left, top, right, bottom = win32gui.GetWindowRect(handle)
            if right - left >= win32api.GetSystemMetrics(0) - 8:
                found.append(handle)

    win32gui.EnumWindows(collect, None)
    return found


def click(x, y):
    win32api.SetCursorPos((int(x), int(y)))
    pump(0.25)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    pump(0.1)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    pump(0.8)


def ctrl(key):
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(ord(key), 0, 0, 0)
    win32api.keybd_event(ord(key), 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    pump(0.6)


def set_clipboard_text(text):
    for _ in range(40):
        try:
            win32clipboard.OpenClipboard()
            break
        except win32clipboard.error:
            time.sleep(0.05)
    else:
        raise OSError("clipboard busy")
    try:
        win32clipboard.EmptyClipboard()
        if text is not None:
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def get_clipboard_text():
    for _ in range(40):
        try:
            win32clipboard.OpenClipboard()
            break
        except win32clipboard.error:
            time.sleep(0.05)
    else:
        return None
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()


def small(image):
    import numpy as np
    return np.asarray(image.convert("RGB").resize((48, 30))).astype(int)


def settings_window(main):
    """The app's own Settings dialog (another program's window may also be called "Settings")."""
    main_pid = win32process.GetWindowThreadProcessId(main)[1]
    for handle, pid in all_windows_titled("Settings"):
        if handle != main and pid == main_pid:
            return handle
    return None


def all_windows_titled(title):
    found = []

    def collect(handle, _):
        if win32gui.IsWindowVisible(handle) and win32gui.GetWindowText(handle) == title:
            found.append((handle, win32process.GetWindowThreadProcessId(handle)[1]))

    win32gui.EnumWindows(collect, None)
    return found


def what_is_shown(main, pid):
    """The picture the user sees in the main window's area: the transition's overlay window while it
    is up (it is a window of its own), else the main window. Only these app windows are captured."""
    overlays = intro_windows(main, pid)
    return small(wc.capture_window(overlays[0] if overlays else main))


def theme_transition_check(hwnd, left, top, width, height):
    """Open Settings, pick Emerald: what is shown must change frame by frame (the blob transition),
    a click must skip to the final theme, and Cancel must go back (also animated)."""
    import numpy as np

    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    scale = ctypes.windll.user32.GetDpiForSystem() / 96.0
    before = what_is_shown(hwnd, pid)
    click(left + width - 74, top + 102)                      # the gear button
    dialog = None
    end = time.time() + 10
    while time.time() < end and not dialog:
        dialog = settings_window(hwnd)
        pump(0.3)
    check("Settings opens", bool(dialog))
    if not dialog:
        return
    pump(1.0)
    dl, dt, dr, db = win32gui.GetWindowRect(dialog)
    dw = dr - dl
    click(dl + dw * 580 / 968, dt + 495 * scale / 1.25)      # the Emerald tile (second row, third)
    samples = []
    for _ in range(20):                                      # watch the main window's area for about 5 s
        samples.append(what_is_shown(hwnd, pid))
        pump(0.1)
    moves = sum(1 for a, b in zip(samples, samples[1:]) if np.abs(a - b).mean() > 0.8)
    check("what is shown changes frame by frame while the theme animates", moves >= 4, f"{moves} changing steps")
    pump(2.0)
    final = what_is_shown(hwnd, pid)
    check("... and ends in a different look than it started",
          np.abs(final - before).mean() > 3.0, f"{np.abs(final - before).mean():.2f}")
    check("... and the animation is over (no overlay window, picture is stable)",
          not intro_windows(hwnd, pid) and np.abs(what_is_shown(hwnd, pid) - final).mean() < 0.5)

    # a click skips: pick another theme (Ember) and click inside the dialog while it animates
    click(dl + dw * 365 / 968, dt + 495 * scale / 1.25)
    started = time.time()
    mid = None
    while time.time() - started < 6 and mid is None:         # wait until the overlay is up
        if intro_windows(hwnd, pid):
            mid = what_is_shown(hwnd, pid)
        pump(0.05)
    check("a second theme change shows the animation again", mid is not None)
    overlay_up = bool(intro_windows(hwnd, pid))
    if overlay_up:
        click(dl + dw * 0.5, dt + 120 * scale / 1.25)        # a click on the dialog's heading skips
    pump(0.4)
    check("a click skips: the overlay is gone at once", not intro_windows(hwnd, pid))
    skipped = what_is_shown(hwnd, pid)
    pump(1.0)
    settled = what_is_shown(hwnd, pid)
    check("... and nothing changes afterwards", np.abs(skipped - settled).mean() < 0.5,
          f"{np.abs(skipped - settled).mean():.2f}")

    # Cancel goes back to the starting theme
    dl, dt, dr, db = win32gui.GetWindowRect(dialog)
    click(dl + (dr - dl) * 847 / 968, db - 60 * scale / 1.25)    # Cancel in the footer
    pump(5.0)
    after_cancel = what_is_shown(hwnd, pid)
    check("Cancel closes the dialog", not win32gui.IsWindow(dialog) or not win32gui.IsWindowVisible(dialog))
    check("Cancel brings the starting theme back", np.abs(after_cancel - before).mean() < 4.0,
          f"{np.abs(after_cancel - before).mean():.2f}")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "exe"
    proc = None
    before_launch.update(handle for handle, _pid in all_windows())
    if target in ("exe", "exe-intro"):
        env = dict(os.environ, APPDATA=tempfile.mkdtemp())
        if target == "exe":
            env["QRSTUDIO_NO_SPLASH"] = "1"          # "exe-intro" plays the intro, like a fresh install
        else:
            env.pop("QRSTUDIO_NO_SPLASH", None)
        proc = subprocess.Popen([EXE], env=env)
    else:
        subprocess.Popen(["explorer.exe", target])

    hwnd = pid = None
    end = time.time() + 90
    while time.time() < end and not hwnd:
        hwnd, pid = find_window()
        pump(0.3)
    check("the main window appears (after the intro)", bool(hwnd))
    if not hwnd:
        return
    end = time.time() + 30
    while time.time() < end and intro_windows(hwnd, pid):
        pump(0.3)
    check("the intro has closed", not intro_windows(hwnd, pid))
    pump(3)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
    pump(1.0)                                              # let it come to the front before the first click
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    check("the window is on screen", left < 100 and top < 100 and right > 600 and bottom > 400,
          f"{(left, top, right, bottom)}")
    check("the window is maximized", win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED)

    # ---- Generate: paste a link into the first field and press Generate QR ----
    decoded = None
    for attempt in range(3):                               # the first click can be eaten while focus moves
        set_clipboard_text(URL)
        click(left + 700, top + 415)
        ctrl("A")
        ctrl("V")
        click(left + width - 280, top + height - 142)      # Generate QR
        pump(3)
        shot = wc.capture_window(hwnd)
        preview = shot.crop((width - 520, 200, width - 40, 800))
        decoded = QRScanner.decode_image(preview.convert("RGB"))
        if decoded == URL:
            break
    check("Generate: the preview holds a QR code that decodes to the typed link", decoded == URL, repr(decoded))

    # ---- Scan: paste a picture of another code and read it ----
    click(left + 110, top + 295)                             # Scan QR in the sidebar
    pump(1)
    from utils.clipboard import ClipboardManager
    ClipboardManager.copy_image(QRGenerator().generate(PLAIN))
    ctrl("V")
    pump(2.5)
    got = None
    for y in (height - 142, height - 80, height - 150):
        set_clipboard_text(None)
        click(left + width - 280, top + y)
        got = get_clipboard_text()
        if got:
            break
    check("Scan: the pasted code is read and its Copy button copies the text", got == PLAIN, repr(got))

    # ---- Settings: a theme change plays the transition; a click skips it; Cancel reverts ----
    theme_transition_check(hwnd, left, top, width, height)

    # ---- close ----
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    end = time.time() + 15
    while time.time() < end and win32gui.IsWindow(hwnd) and find_window()[0]:
        pump(0.3)
    check("the app closes", not find_window()[0])
    if proc is not None:
        try:
            check("the process exits", proc.wait(timeout=10) == 0)
        except subprocess.TimeoutExpired:
            proc.kill()
            check("the process exits", False, "had to be killed")


if __name__ == "__main__":
    main()
    if problems:
        print("INSTALLED_APP_FAIL")
        sys.exit(1)
    print("INSTALLED_APP_OK: generate and scan worked in the real app window, and it closed cleanly")
