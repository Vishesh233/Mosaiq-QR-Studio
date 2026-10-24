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

The mask is drawn at half resolution (and the picture at a smaller size when frames take too long)
and scaled up, so its edges stay smooth. Frames are drawn on a worker thread while the main thread
shows the previous one; the animation follows the real clock (a slow PC drops frames instead of
making the animation longer).

It does not run at start-up, when "Animate theme changes" is off, when Windows' "Animation effects"
are off, or when no snapshot can be taken (that is logged as a warning and the theme is applied at once).
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

ENABLED_OVERRIDE = None                  # the Settings dialog sets this while its switch is being changed
ENV_DISABLE = "QRSTUDIO_NO_THEME_ANIMATION"
SETTING_KEY = "animate_theme_changes"

SPI_GETCLIENTAREAANIMATION = 0x1042
PW_RENDERFULLCONTENT = 0x2


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


def enabled():
    """Should a theme change be animated right now?"""
    if os.environ.get(ENV_DISABLE, "").strip().lower() in ("1", "true", "yes"):
        return False
    wanted = ENABLED_OVERRIDE if ENABLED_OVERRIDE is not None else bool(settings_store.get(SETTING_KEY, True))
    return wanted and system_animations_enabled()


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
        self._stop_flag.set()
        for thread in self._threads:
            thread.join(timeout=2.0)


class _Overlay:
    """A borderless window exactly over a window's client area, showing the old snapshot at once and
    then the frames. It is a window of its own (not a child), so a snapshot of the covered window
    taken while the overlay is up never contains the overlay."""

    def __init__(self, window, old):
        self.window = window
        self.size = old.size
        self.top = tkinter.Toplevel(window)
        self.top.overrideredirect(True)              # no frame, no taskbar button
        self.top.transient(window)                   # stays above its window only
        self.top.configure(bg="black", cursor="arrow")
        width, height = old.size
        self.top.geometry(f"{width}x{height}+{window.winfo_rootx()}+{window.winfo_rooty()}")
        self.canvas = tkinter.Canvas(self.top, width=width, height=height, highlightthickness=0, bd=0, bg="black")
        self.canvas.pack()
        self.photo = ImageTk.PhotoImage(old)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.renderer = None
        self.producer = None
        self.shown_T = -1.0
        self.bindings = []
        self.top.update()                            # on screen now
        self.where = self._where()

    def _where(self):
        return (self.window.winfo_rootx(), self.window.winfo_rooty(),
                self.window.winfo_width(), self.window.winfo_height())

    def moved(self):
        """Did the covered window move or change size?"""
        return self._where() != self.where

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
        self._started = 0.0
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
        """Apply ``change`` with the transition. Returns True when an animation started."""
        self.finish()                                # an earlier animation jumps to its end first
        if not enabled():
            change()
            return False
        windows = [w for w in self._windows() if w is not None and w.winfo_exists()]
        try:
            before = [capture_client(w) for w in windows]
        except SnapshotError as e:
            get_logger().warning("Theme transition skipped (no snapshot of the window): %s", e)
            change()
            return False
        # The old picture goes up now, so the window does not look frozen while the change is applied.
        for window, old in zip(windows, before):
            overlay = _Overlay(window, old)
            self._overlays.append(overlay)
            self._hook_skip(overlay)
        self._raise_dialogs()
        try:
            change()
            after = [capture_client(w) for w in windows]
        except SnapshotError as e:
            get_logger().warning("Theme transition skipped (no snapshot after the change): %s", e)
            self.finish()
            return False
        except Exception:
            self.finish()                            # never leave the old picture over the window
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
        self._tick()
        return True

    def finish(self):
        """Jump to the final state now (the new theme is already applied underneath)."""
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None
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
    def _toplevels(self):
        """The application's other windows that are showing (a Settings dialog ...)."""
        import customtkinter as ctk
        found, stack = [], list(self.root.winfo_children())
        while stack:
            widget = stack.pop()
            if isinstance(widget, ctk.CTkToplevel) and widget.winfo_viewable():
                found.append(widget)
            stack.extend(widget.winfo_children())
        return found

    def _raise_dialogs(self):
        """A dialog stays on top of the effect (it changes theme at once)."""
        for dialog in self._toplevels():
            dialog.lift()

    def _hook_skip(self, overlay):
        """A click on the overlay or a key skips at once. Clicks and keys anywhere else in the app (a
        Settings dialog, the window itself) and moving or resizing the window skip too, but those are
        attached a moment later: the click that started this transition is still being delivered and
        must not end it."""
        skip = lambda _event=None: self.finish()
        overlay.top.bind("<Button>", skip)
        overlay.top.bind("<Key>", skip)
        self.root.after(80, lambda: self._attach_skip(overlay, skip))

    def _attach_skip(self, overlay, skip):
        if overlay not in self._overlays or not overlay.alive():
            return
        for widget in [overlay.window] + self._toplevels():
            for sequence in ("<Key>", "<Button>"):
                overlay.bindings.append((widget, sequence, widget.bind(sequence, skip, add="+")))
        funcid = overlay.window.bind("<Configure>", lambda _e: overlay.moved() and self.finish(), add="+")
        overlay.bindings.append((overlay.window, "<Configure>", funcid))

    def _tick(self):
        """Show the newest finished frame of every overlay; ends the animation on time."""
        self._job = None
        if not self._overlays:
            return
        now = time.perf_counter()
        T = (now - self._started) / self._duration
        self._overlays = [o for o in self._overlays if o.alive()]    # a closed window drops out
        failed = next((o.producer.error for o in self._overlays if o.producer and o.producer.error), None)
        if failed is not None:
            get_logger().error("Theme transition stopped: %s", failed, exc_info=failed)
        if T >= 1.0 or not self._overlays or failed is not None:
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
