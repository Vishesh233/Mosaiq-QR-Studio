"""Liquid blob transition shown when the app's theme changes.

The old look is "wiped" away by three ink blobs that grow from the top-left corner, the middle
and the bottom-right corner; small ink droplets ride just outside their edge and are swallowed as
they grow, and a glow in the new theme's accent colour follows the outer edge of all the ink.
It lasts DURATION_SEC. The shapes follow docs/design/liquid-blob-transition.html.

How it works (everything lives here; the app only calls ``ThemeTransition.run``):

1. a snapshot of the window's own client area (``PrintWindow``, never the screen) before the change;
2. a borderless window showing that snapshot is put over the client area at once, so the window
   never looks frozen while the change is being applied underneath;
3. the change is applied (the theme) and a second snapshot is taken (the overlay is a separate
   window, so it is not in that snapshot);
4. every frame shows the new snapshot where an ink mask is white and the old one elsewhere
   (``Image.composite``), plus the edge glow, until the end or until the user clicks / presses a key
   / moves or resizes the window, which jumps straight to the final state.

The overlay is a tool window (no taskbar button, not in Alt+Tab, never takes the focus). The effect ends
at once when the window is minimized or moved, when the focus goes to another program, or on any click
or key; and a safety timer removes the overlay DURATION_SEC + 1 s after the start whatever happens (a
worker stuck in a frame can never keep it, or the window, waiting).

The mask is drawn at half resolution (and the picture at a smaller size when frames take too long)
and scaled up, so its edges stay smooth. Frames are drawn on a worker thread while the main thread
shows the previous one; the animation follows the real clock (a slow PC drops frames instead of
making the animation longer).

It does not run at start-up, when "Animate theme changes" is off, when Windows' "Animation effects"
are off, or when no snapshot can be taken (that is logged as a warning and the theme is applied at once).

Every change is written to mosaiq.log with its outcome: "started", then "finished" or "skipped (reason)"
(click, key, moved, resized, minimized, focus-lost, new-change, safety-timer, window-closed, worker-error),
or "not started (reason)" (setting-off, windows-animations-off, disabled-by-environment, snapshot-failed).

Changes never overlap: a change that arrives while another one is still being set up waits and is applied
right after it (the latest one wins), so the application never shows a mix of two themes.
"""
import ctypes
import math
import os
import sys
import threading
import time
import tkinter
from ctypes import wintypes

from PIL import Image, ImageChops, ImageDraw, ImageTk

from utils import settings_store
from utils.app_log import get_logger

DURATION_SEC = 2.0

# The reference page draws on an 840 x 520 canvas; lengths in px below are in that canvas.
REFERENCE_SIZE = (840, 520)
REFERENCE_DIAGONAL = math.hypot(*REFERENCE_SIZE)

# Every number of the effect.
CONFIG = {
    "patches": 3,
    "wobble": 1.2,
    "inkDroplets": True,
    "edgeGlow": True,
    # centres: (x, y, margin in px): top-left (-30, -30), middle (52 %, 50 %), bottom-right (W + 30, H + 30)
    "centres": ((None, None, -30), (0.52, 0.50, 0), (None, None, 30)),
    # final radius of each blob: the reference's 520 / 470 / 1000 px, as a share of its diagonal
    "rmax": (520 / REFERENCE_DIAGONAL, 470 / REFERENCE_DIAGONAL, 1000 / REFERENCE_DIAGONAL),
    "stagger": 0.225,                    # patch k starts at T = k * stagger
    "span": 0.55,                        # and takes this much of T
    "seeds": (0.0, 1.9, 3.3),
    "points": 96,                        # corners of a blob outline
    "dropletsPerPatch": 9,
    "dropletWindow": (0.08, 0.92),       # droplets exist while the patch progress is inside this
    "glowWide": (22.0, 0.18),            # stroke width (reference px) and strength of the soft glow
    "glowThin": (6.0, 0.55),             # ... and of the sharp one
    "maskScale": 0.5,                    # the mask is drawn at this fraction of the window size
    "glowScale": 0.35,                   # the glow is soft: drawn at this fraction
    "targetFrameMs": 33,                 # slower frames than this lower the resolution
    "minQuality": 0.4,
    "fps": 60,
}

ENABLED_OVERRIDE = None                  # the Settings page sets this while its switch is being changed
ENV_DISABLE = "QRSTUDIO_NO_THEME_ANIMATION"
SETTING_KEY = "animate_theme_changes"

SPI_GETCLIENTAREAANIMATION = 0x1042
PW_RENDERFULLCONTENT = 0x2

# Window styles of the overlay: a tool window (no taskbar button, not in Alt+Tab) that never takes focus.
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020      # NOSIZE | NOMOVE | NOZORDER | NOACTIVATE | FRAMECHANGED
SAFETY_EXTRA_SEC = 1.0                   # the overlay is destroyed at most this long after DURATION_SEC, whatever happens
FOCUS_GRACE_SEC = 0.3                    # focus changes in the first 300 ms never end the effect (windows settle then)


def make_tool_window(window):
    """Make a Tk window a tool window that is never activated: it gets no taskbar button, is not
    listed by Alt+Tab, and clicking it does not take the focus from the application."""
    if not sys.platform.startswith("win"):
        return
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.GetWindowLongW.restype = ctypes.c_long
    user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
    user32.SetWindowLongW.restype = ctypes.c_long
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, wintypes.UINT)
    hwnd = wintypes.HWND(window.winfo_id())
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, (style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW)
    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, SWP_FLAGS)


class SnapshotError(Exception):
    """A snapshot of the window could not be taken."""


# ------------------------------------------------------------------ the maths

def clamp01(value):
    return max(0.0, min(1.0, value))


def ease_out(p):
    return 1 - (1 - p) ** 2


def patch_progress(T, k, config=CONFIG):
    """Progress 0..1 of patch ``k`` at overall time ``T`` (0..1)."""
    return clamp01((T - k * config["stagger"]) / config["span"])


def blob_factor(angle, seed, t, wobble):
    """Radius multiplier of the blob outline at ``angle`` (a polar curve; ``t`` in seconds)."""
    return 1 + wobble * (0.10 * math.sin(3 * angle + seed + 0.9 * t)
                         + 0.06 * math.sin(5 * angle + 2.3 * seed - 1.4 * t)
                         + 0.04 * math.sin(2 * angle + 4.1 * seed)
                         + 0.03 * math.sin(8 * angle + 1.7 * seed + 2.2 * t))


def patch_radius(T, k, diag, config=CONFIG):
    """Base radius (px) of patch ``k`` at time ``T``: ease-out growth to its final size."""
    return config["rmax"][k] * diag * ease_out(patch_progress(T, k, config))


def patch_centre(k, width, height, scaling, config=CONFIG):
    fx, fy, margin = config["centres"][k]
    if fx is not None:
        return fx * width, fy * height
    margin *= scaling
    return (margin, margin) if margin < 0 else (width + margin, height + margin)


def blob_outline(centre, radius, seed, t, wobble, points):
    return [(centre[0] + radius * blob_factor(a, seed, t, wobble) * math.cos(a),
             centre[1] + radius * blob_factor(a, seed, t, wobble) * math.sin(a))
            for a in (2 * math.pi * i / points for i in range(points))]


def droplets(k, T, centre, diag, config=CONFIG):
    """[(x, y, radius)] of the ink droplets of patch ``k``. As in the reference: nine droplets ride
    just outside the blob's (unwobbled) radius, at 1.06 to 1.22 times it; the wobbling edge swallows
    them as the blob grows, and their size follows sin(pi p)."""
    p = patch_progress(T, k, config)
    low, high = config["dropletWindow"]
    if p < low or p > high:
        return []
    seed = config["seeds"][k]
    r = patch_radius(T, k, diag, config)
    unit = diag / REFERENCE_DIAGONAL
    out = []
    for d in range(config["dropletsPerPatch"]):
        angle = seed * 2.1 + d * 0.71 + math.sin(d * 3.7) * 0.3
        lag = 1.06 + ((d * 37) % 10) / 55
        size = (4 + (d * 13) % 9) * math.sin(math.pi * p) * unit
        out.append((centre[0] + math.cos(angle) * r * lag, centre[1] + math.sin(angle) * r * lag, size))
    return out


def build_shapes(size, T, config=CONFIG, scaling=1.0, phase=None):
    """The ink at time ``T`` as outlines in window pixels: ("poly", points) for blobs and
    ("circle", x, y, radius) for droplets. ``phase`` (seconds) drives the wobble; default T * duration."""
    width, height = size
    diag = math.hypot(width, height)
    t = T * DURATION_SEC if phase is None else phase
    shapes = []
    for k in range(config["patches"]):
        if patch_progress(T, k, config) <= 0:
            continue
        centre = patch_centre(k, width, height, scaling, config)
        shapes.append(("poly", blob_outline(centre, patch_radius(T, k, diag, config), config["seeds"][k], t,
                                            config["wobble"], config["points"])))
        if config["inkDroplets"]:
            shapes.extend(("circle", x, y, r) for x, y, r in droplets(k, T, centre, diag, config))
    return shapes


def _fill(draw, shapes, scale):
    for shape in shapes:
        if shape[0] == "poly":
            draw.polygon([(x * scale, y * scale) for x, y in shape[1]], fill=255)
        else:
            _kind, x, y, r = shape
            r *= scale
            if r >= 0.5:
                draw.ellipse((x * scale - r, y * scale - r, x * scale + r, y * scale + r), fill=255)


def render_mask(size, T, config=CONFIG, scale=None, scaling=1.0, phase=None, shapes=None):
    """The ink mask ("L": 255 = new theme) for a window of ``size`` px at time ``T`` (0..1),
    drawn at ``scale`` times that size (default config["maskScale"])."""
    scale = config["maskScale"] if scale is None else scale
    small = (max(1, round(size[0] * scale)), max(1, round(size[1] * scale)))
    if T >= 1.0:
        return Image.new("L", small, 255)
    mask = Image.new("L", small, 0)
    if T <= 0.0:
        return mask
    _fill(ImageDraw.Draw(mask), shapes if shapes is not None else build_shapes(size, T, config, scaling, phase),
          scale)
    return mask


def covered_fraction(mask):
    """Share (0..1) of the mask that is ink."""
    histogram = mask.histogram()
    total = sum(histogram)
    weighted = sum(i * n for i, n in enumerate(histogram))
    return weighted / (255.0 * total) if total else 0.0


def glow_strength(T):
    """0 at the start and the end, 1 half way."""
    return math.sin(math.pi * clamp01(T))


def _scale_table(factor):
    return [min(255, int(v * factor + 0.5)) for v in range(256)]


def edge_glow_alpha(size, T, config=CONFIG, scale=None, scaling=1.0, phase=None, shapes=None):
    """Alpha ("L", ``scale`` times ``size``) of the glow, like the reference: every outline is stroked
    wide and soft (22 px, 18 %) and thin and sharp (6 px, 55 %) in the accent colour, then everything
    INSIDE the union of the ink is removed, so only the outer half of the strokes shows (the lines
    where blobs overlap never do). Times sin(pi T): nothing at the start and the end."""
    strength = glow_strength(T)
    if strength <= 0.01 or not config["edgeGlow"]:
        return None
    scale = config["glowScale"] if scale is None else scale
    shapes = shapes if shapes is not None else build_shapes(size, T, config, scaling, phase)
    small = (max(1, round(size[0] * scale)), max(1, round(size[1] * scale)))
    unit = math.hypot(*size) / REFERENCE_DIAGONAL
    layers = []
    for stroke, gain in (config["glowWide"], config["glowThin"]):
        layer = Image.new("L", small, 0)
        draw = ImageDraw.Draw(layer)
        width = max(1, round(stroke * unit * scale))
        for shape in shapes:
            if shape[0] == "poly":
                points = [(x * scale, y * scale) for x, y in shape[1]]
                draw.line(points + [points[0]], fill=255, width=width, joint="curve")
            else:
                _kind, x, y, r = shape
                r = r * scale + width / 2
                if r >= 0.5:
                    draw.ellipse((x * scale - r, y * scale - r, x * scale + r, y * scale + r), outline=255, width=width)
        layers.append(layer.point(_scale_table(gain * strength)))
    alpha = ImageChops.screen(layers[0], layers[1])
    inside = Image.new("L", small, 0)
    _fill(ImageDraw.Draw(inside), shapes, scale)
    return ImageChops.multiply(alpha, ImageChops.invert(inside))


class FrameRenderer:
    """Frames between two snapshots of the same size."""

    def __init__(self, old, new, accent, config=CONFIG, scaling=1.0):
        self.old, self.new = old, new
        self.config = config
        self.scaling = scaling
        self.size = old.size
        self.accent = accent
        self._accent_images = {}
        self._pair = {}

    def _images(self, quality):
        if quality not in self._pair:
            size = (max(1, round(self.size[0] * quality)), max(1, round(self.size[1] * quality)))
            if size == self.size:
                self._pair[quality] = (self.old, self.new)
            else:
                self._pair[quality] = (self.old.resize(size, Image.Resampling.BILINEAR),
                                       self.new.resize(size, Image.Resampling.BILINEAR))
        return self._pair[quality]

    def _accent_image(self, size):
        if size not in self._accent_images:
            self._accent_images[size] = Image.new("RGB", size, self.accent)
        return self._accent_images[size]

    def render(self, T, quality=1.0, phase=None):
        """The frame at time ``T`` as an RGB image of the window's size. ``quality`` < 1 composes
        at a smaller size first (faster) and scales the result up."""
        if T >= 1.0:
            return self.new
        if T <= 0.0:
            return self.old
        old, new = self._images(quality)
        shapes = build_shapes(self.size, T, self.config, self.scaling, phase)
        mask = render_mask(self.size, T, self.config, scaling=self.scaling, shapes=shapes)
        full = mask.resize(old.size, Image.Resampling.BILINEAR)
        frame = Image.composite(new, old, full)
        alpha = edge_glow_alpha(self.size, T, self.config, scaling=self.scaling, shapes=shapes)
        if alpha is not None:
            alpha = alpha.resize(old.size, Image.Resampling.BILINEAR)
            frame = Image.composite(self._accent_image(old.size), frame, alpha)
        if frame.size != self.size:
            frame = frame.resize(self.size, Image.Resampling.BILINEAR)
        return frame


# ------------------------------------------------------------------ snapshots and system switches

def system_animations_enabled():
    """False when Windows' "Animation effects" is switched off (reduced motion)."""
    if not sys.platform.startswith("win"):
        return True
    flag = ctypes.c_int(1)
    try:
        if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(flag), 0):
            get_logger().warning("Could not ask Windows whether animations are on; assuming they are.")
            return True
    except OSError:
        get_logger().warning("Could not ask Windows whether animations are on; assuming they are.", exc_info=True)
        return True
    return bool(flag.value)


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def capture_client(window):
    """A snapshot (RGB, physical pixels) of the client area of ``window``: only that window,
    through PrintWindow of its frame (cropped to the client area), so nothing else on the screen
    can be in it. Raises SnapshotError."""
    if not sys.platform.startswith("win"):
        raise SnapshotError("snapshots need Windows")
    window.update_idletasks()
    width, height = window.winfo_width(), window.winfo_height()
    if width < 8 or height < 8 or not window.winfo_viewable():
        raise SnapshotError(f"the window is not showing ({width}x{height})")
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    for fn, res, args in ((user32.GetParent, wintypes.HWND, (wintypes.HWND,)),
                          (user32.GetWindowRect, wintypes.BOOL, (wintypes.HWND, ctypes.POINTER(wintypes.RECT))),
                          (user32.ClientToScreen, wintypes.BOOL, (wintypes.HWND, ctypes.POINTER(wintypes.POINT))),
                          (user32.GetWindowDC, wintypes.HDC, (wintypes.HWND,)),
                          (user32.ReleaseDC, ctypes.c_int, (wintypes.HWND, wintypes.HDC)),
                          (gdi32.CreateCompatibleDC, wintypes.HDC, (wintypes.HDC,)),
                          (gdi32.CreateCompatibleBitmap, wintypes.HBITMAP, (wintypes.HDC, ctypes.c_int, ctypes.c_int)),
                          (gdi32.SelectObject, wintypes.HGDIOBJ, (wintypes.HDC, wintypes.HGDIOBJ)),
                          (gdi32.DeleteObject, wintypes.BOOL, (wintypes.HGDIOBJ,)),
                          (gdi32.DeleteDC, wintypes.BOOL, (wintypes.HDC,)),
                          (user32.PrintWindow, wintypes.BOOL, (wintypes.HWND, wintypes.HDC, wintypes.UINT)),
                          (gdi32.GetDIBits, ctypes.c_int, (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                                           ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT))):
        fn.restype, fn.argtypes = res, args
    inner = wintypes.HWND(window.winfo_id())
    frame = user32.GetParent(inner) or inner                  # the top-level window with its title bar
    rect = wintypes.RECT()
    origin = wintypes.POINT(0, 0)
    if not user32.GetWindowRect(frame, ctypes.byref(rect)) or not user32.ClientToScreen(inner, ctypes.byref(origin)):
        raise SnapshotError("could not find the window's client area")
    full_w, full_h = rect.right - rect.left, rect.bottom - rect.top
    from utils import window_guard
    if window_guard.needs_recovery((rect.left, rect.top, rect.right, rect.bottom), window_guard.work_areas()):
        # A window outside every monitor is not painted by Tk, so its snapshot would be blank.
        raise SnapshotError("the window is outside every monitor")
    window_dc = user32.GetWindowDC(frame)
    if not window_dc:
        raise SnapshotError("GetWindowDC failed")
    memory = bitmap = None
    try:
        memory = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, full_w, full_h)
        if not memory or not bitmap:
            raise SnapshotError("could not create a bitmap")
        old = gdi32.SelectObject(memory, bitmap)
        if not user32.PrintWindow(frame, memory, PW_RENDERFULLCONTENT):
            raise SnapshotError("PrintWindow failed")
        info = _BitmapInfo(ctypes.sizeof(_BitmapInfo), full_w, -full_h, 1, 32, 0)   # top-down BGRA
        buffer = ctypes.create_string_buffer(full_w * full_h * 4)
        gdi32.SelectObject(memory, old)
        if not gdi32.GetDIBits(memory, bitmap, 0, full_h, buffer, ctypes.byref(info), 0):
            raise SnapshotError("GetDIBits failed")
    finally:
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory:
            gdi32.DeleteDC(memory)
        user32.ReleaseDC(frame, window_dc)
    image = Image.frombuffer("RGB", (full_w, full_h), buffer, "raw", "BGRX", 0, 1)
    left, top = origin.x - rect.left, origin.y - rect.top
    if left < 0 or top < 0 or left + width > full_w or top + height > full_h:
        raise SnapshotError(f"client area {(left, top, width, height)} is outside the window {(full_w, full_h)}")
    image = image.crop((left, top, left + width, top + height))
    if image.getextrema() == ((0, 0), (0, 0), (0, 0)):
        raise SnapshotError("the snapshot is blank")
    return image


def disabled_reason():
    """Why a theme change is not animated right now, or None when it is."""
    if os.environ.get(ENV_DISABLE, "").strip().lower() in ("1", "true", "yes"):
        return "disabled-by-environment"
    wanted = ENABLED_OVERRIDE if ENABLED_OVERRIDE is not None else bool(settings_store.get(SETTING_KEY, True))
    if not wanted:
        return "setting-off"
    if not system_animations_enabled():
        return "windows-animations-off"
    return None


def enabled():
    """Should a theme change be animated right now?"""
    return disabled_reason() is None


def another_program_has_focus():
    """True when the foreground window belongs to another program (the user really went elsewhere).
    A moment without any foreground window (windows being activated) does not count."""
    if not sys.platform.startswith("win"):
        return False
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    handle = user32.GetForegroundWindow()
    if not handle:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    return pid.value != os.getpid()


# ------------------------------------------------------------------ the animation on screen

class _Producer:
    """Renders frames for one overlay on worker threads while the main thread shows the previous
    one. Pillow does its heavy work without holding the GIL, so a few workers draw different
    moments at the same time and frames come out faster than one worker could make them.
    Only PIL images are touched here; everything Tk stays on the main thread.
    ``latest`` is the newest finished (T, image)."""

    WORKERS = max(1, min(3, (os.cpu_count() or 2) // 2))

    def __init__(self, renderer, started, duration):
        self.renderer = renderer
        self.started = started
        self.duration = duration
        self.quality = 1.0
        self.latest = None
        self.error = None
        self._lock = threading.Lock()
        self._claimed = -1.0
        self._stop_flag = threading.Event()
        self._threads = [threading.Thread(target=self._work, daemon=True, name=f"theme-transition-{i}")
                         for i in range(self.WORKERS)]

    def start(self):
        for thread in self._threads:
            thread.start()

    def _work(self):
        try:
            while not self._stop_flag.is_set():
                with self._lock:
                    T = (time.perf_counter() - self.started) / self.duration
                    fresh = T - self._claimed >= 0.003            # nobody drew (nearly) this moment yet
                    if fresh:
                        self._claimed = T
                if T >= 1.0:
                    return
                if not fresh:
                    time.sleep(0.002)
                    continue
                image = self.renderer.render(T, self.quality)
                with self._lock:
                    if self.latest is None or T > self.latest[0]:  # a slower worker never shows an older moment
                        self.latest = (T, image)
        except Exception as e:          # reported by the main thread (it ends the animation, logs it)
            self.error = e

    def stop(self):
        """Ask the workers to stop. Never waits: a worker stuck in a frame is a daemon thread and
        simply finishes (or not) on its own, it must never keep the window waiting."""
        self._stop_flag.set()


class _Overlay:
    """A borderless window exactly over a window's client area, showing the old snapshot at once and
    then the frames. It is a window of its own (not a child), so a snapshot of the covered window
    taken while the overlay is up never contains the overlay."""

    def __init__(self, window, old):
        self.window = window
        self.size = old.size
        self.top = tkinter.Toplevel(window)
        self.top.withdraw()                          # styled before it is shown
        self.top.overrideredirect(True)              # no frame
        self.top.transient(window)                   # stays above its window only
        self.top.configure(bg="black", cursor="arrow")
        make_tool_window(self.top)                   # no taskbar button, not in Alt+Tab, never takes focus
        width, height = old.size
        self.top.geometry(f"{width}x{height}+{window.winfo_rootx()}+{window.winfo_rooty()}")
        self.canvas = tkinter.Canvas(self.top, width=width, height=height, highlightthickness=0, bd=0, bg="black")
        self.canvas.pack()
        self.photo = ImageTk.PhotoImage(old)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.top.deiconify()
        make_tool_window(self.top)                   # (Tk may have re-created the window when it was shown)
        self.renderer = None
        self.producer = None
        self.shown_T = -1.0
        self.bindings = []
        self.top.update()                            # on screen now (a change asked for meanwhile waits: see run)
        self.where = self._where()

    def _where(self):
        return (self.window.winfo_rootx(), self.window.winfo_rooty(),
                self.window.winfo_width(), self.window.winfo_height())

    def changed(self):
        """"moved" or "resized" when the covered window is no longer where it was, else None."""
        now = self._where()
        if now == self.where:
            return None
        return "resized" if now[2:] != self.where[2:] else "moved"

    def show(self, image):
        self.photo.paste(image)

    def alive(self):
        return bool(self.window.winfo_exists() and self.top.winfo_exists())

    def destroy(self):
        if self.top.winfo_exists():
            self.top.destroy()


class ThemeTransition:
    """Runs the transition for an application window.

    ``run(change)`` takes the "before" snapshot, covers the window with it at once, calls
    ``change()`` (which switches the theme), takes the "after" snapshot and animates between them.
    ``windows`` gives the windows to cover (the main window first); ``accent`` the new theme's accent colour.
    """

    def __init__(self, root, windows=None, accent=None, config=CONFIG):
        self.root = root
        self._windows = windows or (lambda: [root])
        self._accent = accent or (lambda: "#FFFFFF")
        self.config = config
        self._overlays = []
        self._job = None
        self._safety_job = None
        self._setting_up = False        # run() is busy: a change that arrives now waits (see run)
        self._queued = None
        self._began = 0.0               # when the overlay went up
        self._started = 0.0             # when the animation started (0 while it is being set up)
        self._quality = 1.0
        self._frame_times = []          # the last few frames (decides the resolution)
        self._all_times = []            # every frame of this animation (for the statistics)
        self._frames = 0
        self._last_shown = None
        self._duration = DURATION_SEC
        self.last_run = None            # facts about the latest animation (frames, average ms ...)
        self.runs = 0                   # how many animations were started

    @property
    def running(self):
        return bool(self._overlays)

    # ---- public ----
    def run(self, change, duration=DURATION_SEC):
        """Apply ``change`` with the transition. Returns True when an animation started.

        Changes never overlap: while one is being set up (an event handled in the meantime may ask for
        another change), the new one waits and runs right after, so only the latest request is shown
        and the application never holds a mix of two themes."""
        if self._setting_up:
            self._queued = (change, duration)
            get_logger().info("Theme transition: a change arrived while another was being set up; it runs next")
            return False
        self._setting_up = True
        try:
            started = self._run(change, duration)
        finally:
            self._setting_up = False
        queued, self._queued = self._queued, None
        if queued is not None:
            return self.run(*queued)
        return started

    def _run(self, change, duration):
        self.finish("new-change")                    # an earlier animation jumps to its end first
        reason = disabled_reason()
        if reason is not None:
            get_logger().info("Theme transition not started (%s)", reason)
            change()
            return False
        windows = [w for w in self._windows() if w is not None and w.winfo_exists()]
        try:
            before = [capture_client(w) for w in windows]
        except SnapshotError as e:
            get_logger().warning("Theme transition not started (snapshot-failed: no snapshot of the window): %s", e)
            change()
            return False
        # The old picture goes up now, so the window does not look frozen while the change is applied.
        self._began = time.perf_counter()
        self._started = 0.0
        for window, old in zip(windows, before):
            overlay = _Overlay(window, old)
            self._overlays.append(overlay)
            self._hook_skip(overlay)
        try:
            change()
            after = [capture_client(w) for w in windows]
        except SnapshotError as e:
            get_logger().warning("Theme transition not started (snapshot-failed: no snapshot after the change): %s", e)
            self.finish("snapshot-failed")
            return False
        except Exception:
            self.finish("error-in-change")           # never leave the old picture over the window
            raise
        return self.start(before, after, duration)

    def start(self, before, after, duration=DURATION_SEC):
        """Animate the covered windows between the snapshots (``run`` calls this)."""
        scaling = self._overlays[0].window._get_window_scaling() if hasattr(
            self._overlays[0].window, "_get_window_scaling") else 1.0
        accent = self._accent()
        for overlay, old, new in zip(self._overlays, before, after):
            if old.size != new.size:
                new = new.resize(old.size, Image.Resampling.BILINEAR)
            overlay.renderer = FrameRenderer(old, new, accent, self.config, scaling=scaling)
            overlay.renderer.render(0.5, 1.0)        # warm the caches: no slow first frame
        self.runs += 1
        self._duration = duration
        self._started = time.perf_counter()
        self._quality = 1.0
        self._frame_times = []
        self._all_times = []
        self._frames = 0
        self._last_shown = None
        for overlay in self._overlays:
            overlay.producer = _Producer(overlay.renderer, self._started, duration)
            overlay.producer.start()
        # Safety net, independent of the frame loop and of the workers: whatever goes wrong, the
        # overlay is gone DURATION_SEC + 1 s after the start.
        self._safety_job = self.root.after(int((duration + SAFETY_EXTRA_SEC) * 1000), self._safety)
        get_logger().info("Theme transition started (%.1f s, %d window(s), %dx%d)", duration,
                          len(self._overlays), *self._overlays[0].size)
        self._tick()
        return True

    def _safety(self):
        self._safety_job = None
        if self._overlays:
            get_logger().warning("Theme transition was still showing %.1f s after its start; it was ended.",
                                 time.perf_counter() - self._started)
            self.finish("safety-timer")

    def finish(self, reason="finished"):
        """Jump to the final state now (the new theme is already applied underneath). ``reason`` is
        what ended it: "finished" at the natural end, otherwise why it was skipped (it goes to the log)."""
        if self._overlays:
            if reason == "finished":
                get_logger().info("Theme transition finished (%d frames, %.0f ms on average)", self._frames,
                                  sum(self._all_times) / len(self._all_times) if self._all_times else 0.0)
            elif self._started:
                get_logger().info("Theme transition skipped (%s) %.2f s into the animation", reason,
                                  time.perf_counter() - self._started)
            else:
                get_logger().info("Theme transition skipped (%s) while it was being set up", reason)
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
        if self._safety_job is not None:
            self.root.after_cancel(self._safety_job)
            self._safety_job = None
        for overlay in self._overlays:
            if overlay.producer is not None:
                overlay.producer.stop()
            for widget, sequence, funcid in overlay.bindings:
                try:
                    widget.unbind(sequence, funcid)
                except tkinter.TclError:
                    pass                              # the window was closed meanwhile
            overlay.destroy()
        if self._overlays and self._all_times:
            self.last_run = {"frames": self._frames, "avg_ms": sum(self._all_times) / len(self._all_times),
                             "max_ms": max(self._all_times), "quality": self._quality}
        self._overlays = []

    # ---- internals ----
    def _hook_skip(self, overlay):
        """A click on the overlay or a key skips at once. Clicks and keys anywhere else in the window and
        moving or resizing it skip too, but those are attached a moment later: the click that started
        this transition is still being delivered and must not end it."""
        overlay.top.bind("<Button>", lambda _event=None: self.finish("click"))
        overlay.top.bind("<Key>", lambda _event=None: self.finish("key"))
        self.root.after(80, lambda: self._attach_skip(overlay))

    def _attach_skip(self, overlay):
        if overlay not in self._overlays or not overlay.alive():
            return
        window = overlay.window

        def bind(sequence, handler):
            overlay.bindings.append((window, sequence, window.bind(sequence, handler, add="+")))

        bind("<Key>", lambda _e: self.finish("key"))
        bind("<Button>", lambda _e: self.finish("click"))
        bind("<Configure>", lambda e: e.widget is window and self._window_changed(overlay))
        bind("<Unmap>", lambda e: e.widget is window and self.finish("minimized"))      # minimized or hidden
        bind("<FocusOut>", lambda e: e.widget is window and self._focus_out())

    def _window_changed(self, overlay):
        reason = overlay.changed()
        if reason is not None:
            self.finish(reason)

    def _focus_out(self):
        """The window lost the focus. Not in the first FOCUS_GRACE_SEC of the animation (windows settle
        then); later it is looked at once the focus has settled."""
        if self._started and time.perf_counter() - self._started >= FOCUS_GRACE_SEC:
            self.root.after(60, self._focus_check)

    def _focus_check(self):
        """That ends the effect only when the user really went to another program."""
        if self._overlays and self.root.focus_displayof() is None and another_program_has_focus():
            self.finish("focus-lost")

    def _tick(self):
        """Show the newest finished frame of every overlay; ends the animation on time."""
        self._job = None
        if not self._overlays:
            return
        now = time.perf_counter()
        T = (now - self._started) / self._duration
        gone = [o for o in self._overlays if not (o.alive() and o.window.state() in ("normal", "zoomed"))]
        for overlay in gone:                          # a closed, minimized or hidden window ends its effect
            if overlay.producer is not None:
                overlay.producer.stop()
            overlay.destroy()
        self._overlays = [o for o in self._overlays if o not in gone]
        failed = next((o.producer.error for o in self._overlays if o.producer and o.producer.error), None)
        if failed is not None:
            get_logger().error("Theme transition stopped: %s", failed, exc_info=failed)
        if failed is not None or not self._overlays:
            self.finish("worker-error" if failed is not None else "window-closed")
            return
        if T >= 1.0:
            self.finish()
            return
        shown = False
        for overlay in self._overlays:
            latest = overlay.producer.latest
            if latest is not None and latest[0] != overlay.shown_T:
                overlay.shown_T = latest[0]
                overlay.show(latest[1])
                shown = True
        if shown:
            self.root.update_idletasks()
            self._frames += 1
            if self._last_shown is not None:
                interval = (time.perf_counter() - self._last_shown) * 1000
                self._frame_times.append(interval)
                self._all_times.append(interval)
                recent = self._frame_times[-6:]
                if (len(recent) >= 6 and sum(recent) / len(recent) > self.config["targetFrameMs"]
                        and self._quality > self.config["minQuality"]):
                    self._quality = max(self.config["minQuality"], self._quality * 0.85)   # slow: fewer pixels
                    for overlay in self._overlays:
                        overlay.producer.quality = self._quality
                    self._frame_times = []
            self._last_shown = time.perf_counter()
        self._job = self.root.after(4, self._tick)
