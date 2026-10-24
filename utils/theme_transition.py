"""Liquid blob transition shown when the app's theme changes.

The old look is "wiped" away by three ink blobs that grow from the top-left corner, the middle
and the bottom-right corner; small ink droplets run ahead of each blob and are swallowed by it,
and a thin glow in the new theme's accent colour follows the outer edge. It lasts DURATION_SEC.

How it works (everything lives here; the app only calls ``ThemeTransition.run``):

1. a snapshot of the window's own client area (``PrintWindow``, never the screen) before the change;
2. the change is applied (the theme), and a second snapshot is taken;
3. a canvas covering the window shows, every frame, the new snapshot where an ink mask is white and
   the old one elsewhere (``Image.composite``), plus the edge glow, until the end or until the user
   clicks / presses a key / resizes, which jumps straight to the final state.

The mask is drawn at half resolution (and smaller when frames take too long) and scaled up, so its
edges stay smooth. The animation is driven by ``after()`` and the real clock: the window keeps
answering, and a slow PC drops frames instead of making the animation longer.

It does not run at start-up, when "Animate theme changes" is off, when Windows' "Animation effects"
are off, or when no snapshot can be taken (that is logged as a warning and the theme is applied at once).
"""
import ctypes
import math
import os
import sys
import time
import threading
import tkinter
from ctypes import wintypes

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk

from utils import settings_store
from utils.app_log import get_logger

DURATION_SEC = 3.0

# Every number of the effect (the values locked for the design; see the module docstring).
CONFIG = {
    "patches": 3,
    "wobble": 1.2,
    "inkDroplets": True,
    "edgeGlow": True,
    # centres: (x, y, margin in px): "TL" (-30, -30), middle (52 %, 50 %), "BR" (W + 30, H + 30)
    "centres": ((None, None, -30), (0.52, 0.50, 0), (None, None, 30)),
    "rmax": (0.55, 0.50, 1.05),          # final radius of each blob, times the window diagonal
    "stagger": 0.225,                    # patch k starts at T = k * stagger
    "span": 0.55,                        # and takes this much of T
    "seeds": (0.0, 1.9, 3.3),
    "points": 96,                        # corners of a blob outline
    "dropletsPerPatch": 9,
    "dropletRadius": (0.006, 0.016),     # times the diagonal (smallest, largest)
    "dropletLead": (0.12, 0.30),         # how far a droplet runs ahead of its blob (in progress)
    "wobbleSettle": 0.7,                 # the wobble relaxes by this much as a blob finishes
    "lastPatchBoost": 0.55,              # the last blob swells a little at the end: no gaps remain
    "glowWide": (0.0075, 0.55),          # blur radius (times the diagonal), strength
    "glowThin": (0.0016, 1.0),
    "maskScale": 0.5,                    # the mask is drawn at this fraction of the window size
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
    p = patch_progress(T, k, config)
    radius = config["rmax"][k] * diag * ease_out(p)
    if k == config["patches"] - 1:
        radius *= 1 + config["lastPatchBoost"] * p ** 6
    return radius


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


def droplets(k, T, centre, diag, t, wobble, config=CONFIG):
    """[(x, y, radius)] of the ink droplets of patch ``k``: they sit just outside the blob, run
    ahead of its edge, shrink as the patch finishes and are swallowed as the blob catches up."""
    p = patch_progress(T, k, config)
    if p <= 0 or p >= 1:
        return []
    seed = config["seeds"][k]
    count = config["dropletsPerPatch"]
    base = config["rmax"][k] * diag
    size_lo, size_hi = config["dropletRadius"]
    lead_lo, lead_hi = config["dropletLead"]
    out = []
    for i in range(count):
        frac = (math.sin(i * 2.399 + seed * 1.7) + 1) / 2                 # 0..1, fixed per droplet
        angle = seed * 0.7 + 2 * math.pi * i / count + 0.35 * math.sin(i * 2.3 + seed)
        lead = lead_lo + (lead_hi - lead_lo) * frac
        radius = base * ease_out(clamp01(p + lead)) * (1.03 + 0.05 * frac)
        radius *= blob_factor(angle, seed, t, wobble)
        size = diag * (size_lo + (size_hi - size_lo) * frac) * math.sin(math.pi * p)
        out.append((centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle), size))
    return out


def render_mask(size, T, config=CONFIG, scale=None, scaling=1.0):
    """The ink mask ("L": 255 = new theme) for a window of ``size`` px at time ``T`` (0..1),
    drawn at ``scale`` times that size (default config["maskScale"])."""
    scale = config["maskScale"] if scale is None else scale
    width, height = size
    small = (max(1, round(width * scale)), max(1, round(height * scale)))
    if T >= 1.0:
        return Image.new("L", small, 255)
    mask = Image.new("L", small, 0)
    if T <= 0.0:
        return mask
    draw = ImageDraw.Draw(mask)
    diag = math.hypot(width, height)
    t = T * DURATION_SEC
    for k in range(config["patches"]):
        p = patch_progress(T, k, config)
        if p <= 0:
            continue
        centre = patch_centre(k, width, height, scaling, config)
        wobble = config["wobble"] * (1 - config["wobbleSettle"] * p * p)
        outline = blob_outline(centre, patch_radius(T, k, diag, config), config["seeds"][k], t, wobble,
                               config["points"])
        draw.polygon([(x * scale, y * scale) for x, y in outline], fill=255)
        if config["inkDroplets"]:
            for x, y, r in droplets(k, T, centre, diag, t, wobble, config):
                r *= scale
                if r >= 0.5:
                    draw.ellipse((x * scale - r, y * scale - r, x * scale + r, y * scale + r), fill=255)
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


def edge_glow_alpha(mask, T, config=CONFIG, reduce=1):
    """Alpha ("L") of the glow: a wide soft one plus a thin sharp one, only OUTSIDE the union of
    all blobs (so the lines where blobs overlap never show), times sin(pi T). Same size as ``mask``,
    or ``reduce`` times smaller (the glow is soft, so the frames compute it on fewer pixels)."""
    strength = glow_strength(T)
    if strength <= 0.01 or not config["edgeGlow"]:
        return None
    if reduce > 1:
        mask = mask.resize((max(1, mask.width // reduce), max(1, mask.height // reduce)), Image.Resampling.BILINEAR)
    diag = math.hypot(*mask.size)
    outside = ImageChops.invert(mask)
    wide_r, wide_gain = config["glowWide"]
    thin_r, thin_gain = config["glowThin"]
    wide = ImageChops.multiply(mask.filter(ImageFilter.GaussianBlur(max(2.0, wide_r * diag))), outside)
    thin = ImageChops.multiply(mask.filter(ImageFilter.GaussianBlur(max(0.8, thin_r * diag))), outside)
    alpha = ImageChops.lighter(wide.point(_scale_table(2.0 * wide_gain)),
                               thin.point(_scale_table(2.0 * thin_gain)))
    return alpha.point(_scale_table(strength))


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

    def render(self, T, quality=1.0):
        """The frame at time ``T`` as an RGB image of the window's size. ``quality`` < 1 composes
        at a smaller size first (faster) and scales the result up."""
        if T >= 1.0:
            return self.new
        if T <= 0.0:
            return self.old
        old, new = self._images(quality)
        mask = render_mask(self.size, T, self.config, scaling=self.scaling)
        full = mask.resize(old.size, Image.Resampling.BILINEAR)
        frame = Image.composite(new, old, full)
        alpha = edge_glow_alpha(mask, T, self.config, reduce=2)
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

class _Producer(threading.Thread):
    """Renders frames for one overlay on a worker thread while the main thread shows the previous
    one (Pillow does its heavy work without holding the GIL). Only PIL images are touched here;
    everything Tk stays on the main thread. ``latest`` is the newest finished (T, image)."""

    def __init__(self, renderer, started, duration):
        super().__init__(daemon=True, name="theme-transition")
        self.renderer = renderer
        self.started = started
        self.duration = duration
        self.quality = 1.0
        self.latest = None
        self.error = None
        self._stop_flag = threading.Event()

    def run(self):
        try:
            last = -1.0
            while not self._stop_flag.is_set():
                T = (time.perf_counter() - self.started) / self.duration
                if T >= 1.0:
                    return
                if T - last < 0.002:                 # nothing new to draw yet
                    time.sleep(0.002)
                    continue
                self.latest = (T, self.renderer.render(T, self.quality))
                last = T
        except Exception as e:          # reported by the main thread (it ends the animation, logs it)
            self.error = e

    def stop(self):
        self._stop_flag.set()
        self.join(timeout=2.0)


class _Overlay:
    """A canvas that covers one window and shows the frames."""

    def __init__(self, window, old, new, accent, scaling):
        self.window = window
        self.size = old.size
        self.renderer = FrameRenderer(old, new, accent, scaling=scaling)
        self.canvas = tkinter.Canvas(window, highlightthickness=0, bd=0, bg="black", cursor="arrow")
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        tkinter.Misc.tkraise(self.canvas)          # (Canvas.lift would raise canvas items)
        window.update_idletasks()
        self.photo = ImageTk.PhotoImage(old)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
        self.bindings = []
        self.producer = None
        self.shown_T = -1.0
        self.seen = (window.winfo_width(), window.winfo_height())     # the size a resize is judged against

    def show(self, image):
        self.photo.paste(image)

    def alive(self):
        return bool(self.window.winfo_exists())

    def destroy(self):
        if self.window.winfo_exists():
            self.canvas.destroy()


class ThemeTransition:
    """Runs the transition for an application window (and, when asked, its dialogs).

    ``run(change)`` takes the "before" snapshots, calls ``change()`` (which switches the theme),
    takes the "after" snapshots and animates between them. ``windows`` gives the windows to cover
    (the main window first); ``accent`` the new theme's accent colour.
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
        change()
        try:
            after = [capture_client(w) for w in windows]
        except SnapshotError as e:
            get_logger().warning("Theme transition skipped (no snapshot after the change): %s", e)
            return False
        return self.start(windows, before, after, duration)

    def start(self, windows, before, after, duration=DURATION_SEC):
        """Animate between ready-made snapshots (``run`` calls this)."""
        scaling = windows[0]._get_window_scaling() if hasattr(windows[0], "_get_window_scaling") else 1.0
        accent = self._accent()
        for window, old, new in zip(windows, before, after):
            if old.size != new.size:
                new = new.resize(old.size, Image.Resampling.BILINEAR)
            overlay = _Overlay(window, old, new, accent, scaling)
            self._overlays.append(overlay)
            self._hook_skip(overlay)
        for overlay in self._overlays:
            overlay.renderer.render(0.5, 1.0)                # warm the caches: no slow first frame
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
            for sequence, funcid in overlay.bindings:
                try:
                    overlay.window.unbind(sequence, funcid)
                except tkinter.TclError:
                    pass                              # the window was closed meanwhile
            overlay.destroy()
        if self._overlays and self._all_times:
            self.last_run = {"frames": self._frames, "avg_ms": sum(self._all_times) / len(self._all_times),
                             "max_ms": max(self._all_times), "quality": self._quality}
        self._overlays = []

    # ---- internals ----
    def _hook_skip(self, overlay):
        skip = lambda _event=None: self.finish()
        overlay.canvas.bind("<Button>", skip)
        overlay.canvas.bind("<Key>", skip)
        overlay.canvas.focus_set()
        for sequence in ("<Key>", "<Configure>"):
            handler = skip if sequence == "<Key>" else self._on_configure(overlay)
            funcid = overlay.window.bind(sequence, handler, add="+")
            overlay.bindings.append((sequence, funcid))

    def _on_configure(self, overlay):
        def handler(event):
            if event.widget is overlay.window and (event.width, event.height) != overlay.seen:
                self.finish()
        return handler

    def _tick(self):
        """Show the newest finished frame of every overlay; ends the animation on time."""
        self._job = None
        if not self._overlays:
            return
        now = time.perf_counter()
        T = (now - self._started) / self._duration
        self._overlays = [o for o in self._overlays if o.alive()]    # a closed dialog drops out
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
