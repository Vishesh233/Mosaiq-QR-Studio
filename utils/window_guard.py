"""Make sure the main window can actually be seen after it opens.

A window that ends up outside every monitor (a monitor that was unplugged, a window parked
off-screen), minimized, or still hidden shows only as a taskbar button. ``ensure_visible``
looks at the real window rectangle and, when it is not on a monitor, puts the window back:
normal state, centred on the primary work area, then maximized like a normal start.

The rectangle maths (``needs_recovery``, ``centred``) is plain Python so it can be tested
without a screen.
"""
import ctypes
import sys
from ctypes import wintypes

# A window counts as reachable when at least this much of it lies on a monitor.
MIN_VISIBLE_W = 200
MIN_VISIBLE_H = 80


def _overlap(a, b):
    """Width and height of the overlap of two (left, top, right, bottom) rectangles."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0), max(h, 0)


def needs_recovery(window_rect, work_areas):
    """True when too little of ``window_rect`` is on any of the ``work_areas``."""
    if not work_areas:
        return False                      # unknown monitors: leave the window alone
    for area in work_areas:
        w, h = _overlap(window_rect, area)
        if w >= min(MIN_VISIBLE_W, window_rect[2] - window_rect[0]) \
                and h >= min(MIN_VISIBLE_H, window_rect[3] - window_rect[1]):
            return False
    return True


def centred(width, height, area):
    """(width, height, x, y) of a window of this size centred on ``area``, shrunk to fit it."""
    aw, ah = area[2] - area[0], area[3] - area[1]
    width, height = min(width, aw), min(height, ah)
    return width, height, area[0] + (aw - width) // 2, area[1] + (ah - height) // 2


# ------------------------------------------------------------------ Windows queries

def centred_over(parent_rect, work_areas, size_px):
    """(x, y) in physical px for a window of ``size_px`` = (width, height): centred over the parent
    rectangle (left, top, right, bottom), then moved so the WHOLE window is inside the work area of
    the monitor the parent is on. None when the parent is on no monitor (the system places it then)."""
    centre_x = (parent_rect[0] + parent_rect[2]) / 2
    centre_y = (parent_rect[1] + parent_rect[3]) / 2
    area = next((a for a in work_areas if a[0] <= centre_x < a[2] and a[1] <= centre_y < a[3]), None)
    if area is None:
        return None
    width, height = size_px
    x = min(max(round(centre_x - width / 2), area[0]), max(area[0], area[2] - width))
    y = min(max(round(centre_y - height / 2), area[1]), max(area[1], area[3] - height))
    return x, y


def work_areas():
    """Work areas (without the taskbar) of every monitor; primary first. [] off Windows."""
    if not sys.platform.startswith("win"):
        return []
    user32 = ctypes.windll.user32

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    found = []

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                       ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def on_monitor(handle, _dc, _rect, _data):
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcWork
            found.append((bool(info.dwFlags & 1), (r.left, r.top, r.right, r.bottom)))
        return True

    user32.EnumDisplayMonitors(None, None, callback_type(on_monitor), 0)
    found.sort(key=lambda item: not item[0])          # primary (flag 1) first
    return [area for _primary, area in found]


def _frame(root):
    """The top-level window handle of a Tk root (the frame around Tk's inner window)."""
    inner = root.winfo_id()
    return ctypes.windll.user32.GetParent(inner) or inner


def window_rect(root):
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(_frame(root), ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom


def ensure_visible(root, maximize=True):
    """Bring the window back when it cannot be seen. Returns what was done:
    "ok", "shown" (was hidden/minimized) or "recentred" (was off every monitor).
    """
    root.update_idletasks()
    action = "ok"

    state = root.state()
    if state in ("withdrawn", "iconic"):
        root.deiconify()
        root.update_idletasks()
        action = "shown"

    if not sys.platform.startswith("win"):
        return action
    areas = work_areas()
    rect = window_rect(root)
    if needs_recovery(rect, areas):
        width, height, x, y = centred(max(rect[2] - rect[0], 1100), max(rect[3] - rect[1], 700),
                                      areas[0])
        root.state("normal")
        scale = root._get_window_scaling() if hasattr(root, "_get_window_scaling") else 1.0
        root.geometry(f"{round(width / scale)}x{round(height / scale)}+{x}+{y}")
        root.update_idletasks()
        if maximize:
            root.state("zoomed")
        action = "recentred"
    if action != "ok":
        root.lift()
        root.focus_force()
    return action
