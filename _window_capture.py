"""Capture ONE window (not the screen), for tests and screenshots.

PrintWindow renders the window's own content, so nothing from other windows or the
desktop can end up in the picture, whatever is on top of it. Also: find a window by the
process that owns it.
"""
import ctypes

import win32con
import win32gui
import win32process
import win32ui
from PIL import Image

PW_RENDERFULLCONTENT = 2


def windows_of_process(pid, visible_only=True):
    found = []

    def collect(handle, _):
        if win32process.GetWindowThreadProcessId(handle)[1] != pid:
            return
        if visible_only and not win32gui.IsWindowVisible(handle):
            return
        found.append(handle)

    win32gui.EnumWindows(collect, None)
    return found


def find_main_window(pid, title_prefix="Mosaiq QR Studio"):
    for handle in windows_of_process(pid):
        if win32gui.GetWindowText(handle).startswith(title_prefix):
            return handle
    return None


def capture_window(handle):
    """The window's pixels as an RGB PIL image (its own content only)."""
    left, top, right, bottom = win32gui.GetWindowRect(handle)
    width, height = right - left, bottom - top

    window_dc = win32gui.GetWindowDC(handle)
    source = win32ui.CreateDCFromHandle(window_dc)
    memory = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source, width, height)
    memory.SelectObject(bitmap)

    try:
        if not ctypes.windll.user32.PrintWindow(handle, memory.GetSafeHdc(), PW_RENDERFULLCONTENT):
            raise OSError("PrintWindow failed for this window")
        data = bitmap.GetBitmapBits(True)
        return Image.frombuffer("RGB", (width, height), data, "raw", "BGRX", 0, 1)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        memory.DeleteDC()
        source.DeleteDC()
        win32gui.ReleaseDC(handle, window_dc)
