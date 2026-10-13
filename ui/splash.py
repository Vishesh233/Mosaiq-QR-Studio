"""Cinematic splash for QR Code Studio V2 — a palette-aware port of the reference.

This is a faithful Python + numpy + Pillow port of ``reference/qr-splash-
reference.html`` (the ground-truth source). Every timing and random value is
taken verbatim from that file, and every layer is composited the way the
reference canvas / CSS composites it, so the composition, choreography and
motion match the reference.

Window
    A borderless, topmost ``Toplevel`` covering the whole monitor that hosts
    the application (see :func:`splash_rect`); the scene is built at that
    monitor's pixel size, and all its geometry is derived from ``(W, H)``.
    ``SPLASH_W x SPLASH_H`` (1280 x 800, the reference size) is used for
    headless renders and validation. Palette chips along the bottom edge
    recolour the running intro (see :class:`_ChipBar`).

Palettes
    :data:`PALETTES` holds the three coordinated looks (Aqua Mint, Ultraviolet,
    Ember). The colour-agnostic scene data (QR matrix, module and particle
    constants, ambient layout, radial fields, glyph masks) is cached per
    ``(W, H, ss)`` in :class:`_Geometry`, while :class:`Scene` only owns the
    palette-dependent paint. Switching palette (:meth:`Splash.turn_palette_on`)
    therefore costs a few milliseconds, never restarts the timeline and never
    rebuilds geometry.

Performance
    :func:`render_frame_into` renders into buffers the intro allocates once,
    and incrementally: only the 32 px tiles that changed are restored,
    converted and blitted (GDI on Windows). The radial vignette is folded into the ambient draws that need it
    (vignetting is affine per pixel, so this is exact), the glow rings are one
    vectorised pass over their own bounding box, and the QR modules and
    particles are computed as arrays. :class:`Splash` paces frames against
    the wall clock.

Design rule (from the reference): rendering is a PURE function of ``(t, ts)``.
All randomness is precomputed once with the bit-exact ``mulberry32`` PRNG into
per-module / per-particle constants, and every static asset (glyph masks,
gradient fill, blurred glows, vignette, glow-radius field, background plate) is
pre-rendered once at startup. Nothing integrates per-frame state, so any frame
can be reproduced exactly and Replay is deterministic.

Playback (see :class:`Splash`): ``t`` runs 0 -> 8800 ms once; the main window
is built before the intro starts, so it is ready at 8800 and the splash hands
over immediately. The dev flag ``--splash-loop`` uses ``t = ts mod 11000`` so
the loop can be compared against the reference.

Disable with ``QRSTUDIO_NO_SPLASH=1`` or ``--no-splash`` / ``--fast`` (see
:func:`splash_disabled`).
"""

from __future__ import annotations

import json
import math
import os
import sys
import traceback

import tkinter as tk
from PIL import ImageTk
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# --- Paths -------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_REF_DIR = os.path.join(_ROOT, "reference")
_QR_JSON = os.path.join(_REF_DIR, "qr_matrix.json")
_FONT_TTF = os.path.join(_REF_DIR, "Exo2-BlackItalic.ttf")


# --- Window ------------------------------------------------------------------
# The reference spec's splash size ("a borderless, centred, non-resizable window
# of SPLASH_W x SPLASH_H = 1280 x 800"): headless renders and validation. The
# live intro covers the whole monitor instead.
SPLASH_W = 1280
SPLASH_H = 800

# Target frame period for the playback tick (ms). The next tick is scheduled
# TICK_MS after the START of the current one, so a frame that took longer than
# that is followed immediately instead of after a further fixed 16 ms.
TICK_MS = 16

# Hand-off: the main window is revealed underneath the (topmost) splash, which
# keeps showing its final frame this long while the main window maps and
# paints, then closes. The user never sees the desktop or a half-drawn window.
HANDOFF_MS = 150


# --- Timeline (ms) — verbatim from the reference -----------------------------
T = 11000
ASM0 = 900
ASM_SPAN = 1100
ASM_DUR = 700
FO0 = 900
FO1 = 2600
SCAN0 = 2800
SCAN1 = 4000
DIS0 = 4600
DIS_SPAN = 1500
FI0 = 7600
FI1 = 8800
DIM = 0.3
STATIC_T = 3400


# --- Palettes ---------------------------------------------------------------
# Three coordinated looks shared by the splash (and, later, the app shell).
# Aqua Mint is the reference palette, so the historic module-level names (BG, A,
# B, ICE, GLOW, DEEP, STROKE and their normalised _F copies) still resolve to
# exactly the values they had before.
#
#   BG     near-black base           A0/A/B  title gradient A0 -> A -> B
#   GLOW   restrained ambient glow   DEEP    drifting pixel pairs
#   ICE    highlight / scan bar      STROKE  V2 hard shadow
#
# The QR row gradient is A -> B, so each palette spans its own two accents.

DEFAULT_PALETTE = "Aqua Mint"

PALETTES = {
    # Dark teal / aqua / mint — the original reference look.
    "Aqua Mint": {
        "BG": (6, 10, 14),
        "A0": (79, 227, 246),
        "A": (34, 211, 238),
        "B": (110, 231, 183),
        "ICE": (184, 243, 255),
        "GLOW": (16, 72, 84),
        "DEEP": (13, 45, 52),
        "STROKE": (27, 127, 143),
    },
    # Deep violet base, lilac -> pink core (reference page's "violet").
    "Ultraviolet": {
        "BG": (8, 6, 15),
        "A0": (216, 196, 255),
        "A": (167, 139, 250),
        "B": (244, 114, 182),
        "ICE": (240, 226, 255),
        "GLOW": (62, 32, 104),
        "DEEP": (34, 20, 62),
        "STROKE": (96, 56, 168),
    },
    # Warm charcoal base, gold -> orange -> rose core (reference "ember").
    "Ember": {
        "BG": (13, 8, 6),
        "A0": (253, 224, 71),
        "A": (251, 146, 60),
        "B": (244, 63, 94),
        "ICE": (255, 236, 210),
        "GLOW": (104, 46, 22),
        "DEEP": (54, 28, 18),
        "STROKE": (160, 74, 32),
    },
}

_DEFAULT_COLORS = PALETTES[DEFAULT_PALETTE]
BG = _DEFAULT_COLORS["BG"]
A0 = _DEFAULT_COLORS["A0"]
A = _DEFAULT_COLORS["A"]
B = _DEFAULT_COLORS["B"]
ICE = _DEFAULT_COLORS["ICE"]
GLOW = _DEFAULT_COLORS["GLOW"]
DEEP = _DEFAULT_COLORS["DEEP"]
STROKE = _DEFAULT_COLORS["STROKE"]

# Normalised ([0, 1]) copies of the default palette. The renderer itself reads
# the palette off the Scene (see Scene._apply_palette); these remain for the
# module-level API and for callers that only need the default look.
BG_F = np.array(BG, np.float32) / 255.0
GLOW_F = np.array(GLOW, np.float32) / 255.0
DEEP_F = np.array(DEEP, np.float32) / 255.0
A_F = np.array(A, np.float32) / 255.0
ICE_F = np.array(ICE, np.float32) / 255.0

# Background tonal variation amplitude. The reference used a dead-flat fill;
# a few levels of soft diagonal lift give the "subtle tonal variation" the
# premium direction calls for without adding noise. Set to 0.0 to reproduce the
# reference background exactly (used by the regression check in validation).
_BG_TONE = 0.022


# --- Font metrics (Exo 2 Black Italic) — from the reference spec -------------
ASCENT_EM = 0.999
DESCENT_EM = 0.201
CONTENT_EM = 1.2


# --- Small helpers -----------------------------------------------------------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(u):
    u = clamp(u)
    return 1.0 - (1.0 - u) ** 3


def smooth(u):
    u = clamp(u)
    return u * u * (3.0 - 2.0 * u)


def mix(c1, c2, m):
    """Blend two colours; m=0 -> c1, m=1 -> c2. Returns a float triple."""
    return (c1[0] + (c2[0] - c1[0]) * m,
            c1[1] + (c2[1] - c1[1]) * m,
            c1[2] + (c2[2] - c1[2]) * m)


def js_round(x):
    """JavaScript Math.round (round half up), not Python's banker's rounding."""
    return math.floor(x + 0.5)


def mulberry32(seed):
    """Bit-exact port of the reference PRNG (matches the self-test values)."""
    s = seed & 0xFFFFFFFF

    def rnd():
        nonlocal s
        s = (s + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((s ^ (s >> 15)) * (1 | s)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rnd


def splash_disabled():
    """True if the intro should be skipped (env var or CLI flag)."""
    val = os.environ.get("QRSTUDIO_NO_SPLASH", "").strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    for arg in sys.argv[1:]:
        if arg in ("--no-splash", "--nosplash", "--fast", "--skip-splash"):
            return True
    return False


def splash_loop_mode():
    """Dev flag: loop t = ts mod 11000 so the intro can be compared to video."""
    return "--splash-loop" in sys.argv[1:]


def _splash_debug():
    return os.environ.get("QRSTUDIO_SPLASH_DEBUG", "").strip().lower() in (
        "1", "true", "yes", "on")


def splash_rect(root):
    """``(x, y, w, h)`` of the monitor that should carry the intro, in Tk units.

    Tk's screen metrics are already expressed in the coordinate space that
    ``geometry()`` expects (they carry the display scaling), so no manual DPI
    conversion is performed. On Windows the exact monitor rectangle is asked of
    the shell so a secondary display is covered as well; every step is best
    effort and degrades to the whole Tk screen — the area a maximised window
    would occupy anyway. The window is placed at the monitor's own origin, so
    the splash always starts at a real screen corner.
    """
    try:
        sw = int(root.winfo_screenwidth())
        sh = int(root.winfo_screenheight())
        vx = int(root.winfo_vrootx())
        vy = int(root.winfo_vrooty())
    except Exception:
        sw, sh, vx, vy = SPLASH_W, SPLASH_H, 0, 0

    x, y, w, h = vx, vy, sw, sh
    try:
        import ctypes
        from ctypes import byref, wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = (
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            )

        # A private handle: prototypes set here must not leak into the shared
        # ctypes.windll.user32 that CustomTkinter's DPI tracker also calls.
        user32 = ctypes.WinDLL("user32")
        user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = (ctypes.c_void_p, wintypes.LPCVOID)
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        hmon = user32.MonitorFromWindow(int(root.winfo_id()), 2)  # NEAREST
        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, byref(mi)):
                rc = mi.rcMonitor
                mw = int(rc.right) - int(rc.left)
                mh = int(rc.bottom) - int(rc.top)
                # Trust the shell only when the rectangle is plausible; a bogus
                # value must never leave the splash off-screen.
                if (mw > 0 and mh > 0
                        and abs(mw - sw) * 2 <= sw + mw
                        and abs(mh - sh) * 2 <= sh + mh):
                    x, y, w, h = int(rc.left), int(rc.top), mw, mh
    except Exception as exc:
        if _splash_debug():
            print("[splash] monitor query failed, falling back to the Tk "
                  "screen metrics:", exc, file=sys.stderr)
    return x, y, w, h


# =============================================================================
# _Geometry — colour-agnostic scene data, built once per (W, H, ss) and shared
# by every palette. The QR matrix, module / particle constants, ambient layout,
# radial fields and the wordmark + V2 glyph masks do not depend on colour, so
# switching palettes never pays for them twice. The palette-dependent paint
# lives in :class:`Scene`, which delegates everything else here.
# =============================================================================
class _Geometry:
    def __init__(self, w=SPLASH_W, h=SPLASH_H, ss=1):
        self.W = w
        self.H = h
        # Supersample factor. The runtime splash renders straight into the
        # window buffer, so ss must stay 1: the QR is axis-aligned rectangles
        # and PIL text is already antialiased, while ss=2 would force a full
        # frame downsample on every tick (measured ~2.5 s/frame that way).
        self.k = ss
        self.pw = w * ss          # pixel width / height of the working buffer
        self.ph = h * ss

        self._load_matrix()
        self._build_modules()
        self._build_ambient()
        self._layout()
        self._build_qr_arrays()
        self._build_fields()
        self._build_glyphs()

    # -- QR matrix (used verbatim; never regenerated) ------------------------
    def _load_matrix(self):
        with open(_QR_JSON, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.N = int(data["size"])
        self.rows = data["rows"]
        # rowColor[r] = mix(A, B, r/(N-1)), truncated to int (reference does
        # `c[0]|0` when building the CSS colour, i.e. truncation toward zero).
        denom = max(1, self.N - 1)
        self.row_color = []
        for r in range(self.N):
            m = r / denom
            self.row_color.append((int(A[0] + (B[0] - A[0]) * m),
                                    int(A[1] + (B[1] - A[1]) * m),
                                    int(A[2] + (B[2] - A[2]) * m)))

    # -- Per-module / per-particle constants (R = mulberry32(7)) -------------
    def _build_modules(self):
        R = mulberry32(7)
        N = self.N
        self.mods1 = []   # intact-module draw data: (r, c, sx, sy, asmT, brkT)
        self.mods3 = []   # particle draw data: (r, c, bx, by, brkT, subs[4])
        for r0 in range(N):
            for c0 in range(N):
                if self.rows[r0][c0] != "1":
                    continue
                ang = R() * math.tau
                rad = 0.5 + R() * 0.9
                dist = math.hypot(c0 - N / 2, r0 - N / 2) / (N * 0.7)
                fa = clamp(0.65 * R() + 0.35 * dist)
                fb = clamp((c0 / N) * 0.72 + R() * 0.28)
                subs = []
                for s in range(4):
                    qx = s & 1
                    qy = s >> 1
                    dly = R() * 140
                    life = 1100 + R() * 1100
                    vx = 80 + R() * 240
                    vy = -(20 + R() * 180) + (R() - 0.5) * 80
                    ta = R() * math.tau
                    tf = 2 + R() * 3
                    tm = 6 + R() * 16
                    subs.append((qx, qy, dly, life, vx, vy, ta, tf, tm))
                sx = math.cos(ang) * rad
                sy = math.sin(ang) * rad
                asmT = ASM0 + fa * ASM_SPAN
                brkT = DIS0 + fb * DIS_SPAN
                self.mods1.append((r0, c0, sx, sy, asmT, brkT))
                self.mods3.append((r0, c0, brkT, subs))
        self.n_modules = len(self.mods1)

    # -- Ambient pixel pairs + dust (rr = mulberry32(3), one shared stream) ---
    def _build_ambient(self):
        rr = mulberry32(3)
        W, H = self.W, self.H
        k = clamp(W / 1200, 0.6, 1.2)
        count = js_round(clamp(W * H / 52000, 10, 26))
        self.pairs = []
        for _ in range(count):
            x = rr() * W
            y0 = rr() * (H + 80)
            s = (10 + rr() * 22) * k
            sp = 4 + rr() * 10
            al = 0.4 + rr() * 0.55
            self.pairs.append((x, y0, s, sp, al))
        self.dust = []
        for _ in range(70):
            x = rr() * W
            y = rr() * H
            r = 0.6 + rr() * 1.1
            ph = rr() * math.tau
            sp = 0.4 + rr() * 1.2
            self.dust.append((x, y, r, ph, sp))

    # -- Layout (all derived from W, H; centred on (W/2, H/2)) ---------------
    def _layout(self):
        W, H = self.W, self.H
        self.S = min(0.52 * W, 0.34 * H, 300)
        self.gap1 = clamp(0.03 * H, 14, 28)
        self.titleFS = clamp(0.072 * W, 26, 60)
        self.verFS = clamp(0.17 * W, 72, 140)
        self.title_box_h = 1.05 * self.titleFS
        self.ver_box_h = 0.95 * self.verFS
        total = self.S + self.gap1 + self.title_box_h + 2 + self.ver_box_h
        top = (H - total) / 2
        self.qr_x = (W - self.S) / 2
        self.qr_y = top
        self.title_box_top = top + self.S + self.gap1
        self.ver_box_top = self.title_box_top + self.title_box_h + 2
        # QR cell geometry.
        self.cell = self.S / self.N
        self.size = 0.84 * self.cell
        self.inset = 0.08 * self.cell
        self.sc = self.S / 300
        # Baselines via the half-leading model (ascent 0.999, descent 0.201,
        # content 1.2 em) so glyph baselines land on the reference numbers.
        self.title_base = self.title_box_top + (self.title_box_h - CONTENT_EM * self.titleFS) / 2 + ASCENT_EM * self.titleFS
        self.ver_base = self.ver_box_top + (self.ver_box_h - CONTENT_EM * self.verFS) / 2 + ASCENT_EM * self.verFS

    # -- Module / particle constants as arrays (buffer pixels) ---------------
    def _build_qr_arrays(self):
        """Flatten ``mods1`` / ``mods3`` into arrays for the vectorised passes.

        Positions are precomputed in buffer pixels; ``m_cy`` stays in CSS px
        because the scan "hot" test compares it with the CSS scan line.
        """
        ss = self.k
        cell, size, inset = self.cell * ss, self.size * ss, self.inset * ss
        m = np.array(self.mods1, dtype=np.float64)        # r, c, sx, sy, asmT, brkT
        row = m[:, 0].astype(np.intp)
        self.m_row = row
        self.m_bx = self.qr_x * ss + m[:, 1] * cell + inset
        self.m_by = self.qr_y * ss + row * cell + inset
        self.m_dx = m[:, 2] * self.S * ss
        self.m_dy = m[:, 3] * self.S * ss
        self.m_asm = m[:, 4]
        self.m_brk = m[:, 5]
        self.m_cy = self.qr_y + (row + 0.5) * self.cell

        # Four sub-particles per module, in the reference's drawing order.
        subs = np.array([s for (_, _, _, quads) in self.mods3 for s in quads],
                        dtype=np.float64)                 # qx, qy, dly, life, vx, vy, ta, tf, tm
        rep = np.repeat(np.arange(len(self.mods3)), 4)
        self.p_half = size / 2.0
        self.p_row = row[rep]
        self.p_brk = self.m_brk[rep]
        self.p_x = self.m_bx[rep] + subs[:, 0] * self.p_half
        self.p_y = self.m_by[rep] + subs[:, 1] * self.p_half
        (self.p_dly, self.p_life, self.p_vx, self.p_vy,
         self.p_ta, self.p_tf, self.p_tm) = (np.ascontiguousarray(a) for a in subs[:, 2:].T)


    # -- Precomputed static fields: glow radius field + vignette + tone -------
    def _build_fields(self):
        ss = self.k
        pw, ph = self.pw, self.ph
        cx, cy = pw / 2.0, ph / 2.0
        # 1-D axes + broadcasting instead of two full mgrid meshes: the fields
        # are the most expensive part of the build (they used to cost ~96 ms of
        # the ~150 ms scene build at 1920x1200). Sampled at pixel centres.
        xr = np.arange(pw, dtype=np.float32) + 0.5 - cx
        yr = np.arange(ph, dtype=np.float32) + 0.5 - cy

        # Vignette alpha field (radial; blends drawn content toward BG).
        r0 = min(self.W, self.H) * 0.35 * ss
        r1 = math.hypot(self.W, self.H) * 0.6 * ss
        rad = np.sqrt(xr[None, :] ** 2 + yr[:, None] ** 2)
        self._vig = (np.clip((rad - r0) / (r1 - r0), 0.0, 1.0) * 0.7).astype(np.float32)

        # Subtle tonal lift: brightest toward the top-left, darkest bottom-right,
        # pre-multiplied by (1 - vignette) so the finished background plate can be
        # built with a single add at palette time.
        tx = (np.arange(pw, dtype=np.float32) / max(1, pw - 1)) * 2.0 - 1.0
        ty = (np.arange(ph, dtype=np.float32) / max(1, ph - 1)) * 2.0 - 1.0
        tone = -(tx[None, :] * 0.55 + ty[:, None] * 0.45) * 0.5
        self._tone_eff = (tone * (1.0 - self._vig)).astype(np.float32)

        # Glow ellipses. They only ever cover this box, so the per-frame ring
        # pass runs over ~0.5 M px instead of the whole frame. 1.02 is the
        # breathing head-room of the radius, +1 px guards the rounding. _e0g is
        # each pixel's elliptical radius (x, y / 0.64): ring i covers a pixel
        # exactly when _e0g <= Rr * (1 - i/9).
        rr_max = clamp(0.48 * self.W, 220, 430) * 1.02 * ss
        half_w = int(math.ceil(rr_max)) + 1
        half_h = int(math.ceil(0.64 * rr_max)) + 1
        gx0 = max(0, int(cx) - half_w)
        gx1 = min(pw, int(cx) + half_w + 1)
        gy0 = max(0, int(cy) - half_h)
        gy1 = min(ph, int(cy) + half_h + 1)
        self._glow_box = (gx0, gy0, gx1, gy1)
        gxr = xr[gx0:gx1]
        gyr = yr[gy0:gy1]
        self._e0g = np.sqrt(gxr[None, :] ** 2 + (gyr[:, None] / 0.64) ** 2).astype(np.float32)
        self._vig_g = self._vig[gy0:gy1, gx0:gx1]

    # -- Text glyph masks (title + V2) — palette independent --------------------
    def _build_glyphs(self):
        """Glyph coverage of the title and V2 layers, plus their alpha.

        Each mask is padded by 3 sigma so its blurred glow is never clipped.
        The layers are stacked with exact source-over alpha
        (a = a_top + a_below * (1 - a_top)); only the colours depend on the
        palette (see :meth:`Scene._apply_palette`).
        """
        ss = self.k

        # Title: CSS drop-shadow(0 0 16px rgba(A, .22)) BEHIND the gradient
        # fill, i.e. a sigma-8 glow at 60 px (scaled with the font) at 0.22.
        t_sigma = 8.0 * self.titleFS / 60.0 * ss
        x0, y0, mask, width = self._glyph_mask(
            "MOSAIQ QR STUDIO", self._font(self.titleFS), 0.01 * self.titleFS,
            self.title_base, self.W / 2.0, pad_px=int(math.ceil(3.0 * t_sigma)) + 2)
        self._tx0, self._ty0 = x0, y0
        self._title_mask = mask
        self._title_width = width
        self._title_glow = self._blur(mask, t_sigma) * 0.22
        self._title_alpha = mask + self._title_glow * (1.0 - mask)

        # V2, bottom to top: glow (sigma 22 at 140 px, GLOW at 0.55), hard
        # shadow (+3 px, +3 px at 140 px, opaque STROKE), ICE fill. Sigma and
        # offset scale with the font size relative to the 140 px reference.
        v_sigma = 22.0 * self.verFS / 140.0 * ss
        sh = max(1, int(round(3.0 * self.verFS / 140.0 * ss)))
        pad = max(int(math.ceil(3.0 * v_sigma)) + 2, sh + 2)
        x0, y0, mask, width = self._glyph_mask(
            "V2", self._font(self.verFS), 0.0, self.ver_base, self.W / 2.0, pad_px=pad)
        self._v2_ox, self._v2_oy = x0, y0
        self._v2_mask = mask
        self._v2_width = width
        self._sh_x = self._sh_y = sh
        self._v2_glow = self._blur(mask, v_sigma) * 0.55
        self._v2_shadow = np.zeros_like(mask)      # the padding keeps it in the box
        self._v2_shadow[sh:, sh:] = mask[:-sh, :-sh]
        under = self._v2_shadow + self._v2_glow * (1.0 - self._v2_shadow)
        self._v2_alpha = mask + under * (1.0 - mask)

    # -- Fonts (pixel resolution) --------------------------------------------
    def _font(self, css_px):
        return ImageFont.truetype(_FONT_TTF, max(1, int(round(css_px * self.k))))

    # -- Glyph mask (cropped, with blur padding) for a string ----------------
    def _glyph_mask(self, text, font, spacing, baseline_px, center_css, pad_px=0):
        """Render text to a cropped float alpha mask in pixel space.

        Returns (x0, y0, mask, text_width_css) where mask is float32 [0,1] and
        (x0, y0) is the top-left of the crop in buffer-pixel coordinates.
        """
        ss = self.k
        adv = [font.getlength(ch) for ch in text]
        width = sum(adv) + spacing * ss * len(text)      # buffer px
        text_width_css = width / ss
        start_css = center_css - text_width_css / 2.0
        ascent, descent = font.getmetrics()
        base_px = baseline_px * ss
        px0 = int(math.floor(start_css * ss)) - pad_px
        top_px = int(math.floor(base_px - ascent)) - pad_px
        bot_px = int(math.ceil(base_px + descent)) + pad_px
        crop_w = max(1, int(math.ceil(start_css * ss + width)) + pad_px - px0)
        crop_h = max(1, bot_px - top_px)
        layer = Image.new("L", (crop_w, crop_h), 0)
        d = ImageDraw.Draw(layer)
        cur = start_css * ss - px0
        for i, ch in enumerate(text):
            d.text((cur, base_px - top_px), ch, font=font, fill=255, anchor="ls")
            cur += adv[i] + spacing * ss
        mask = np.asarray(layer, dtype=np.float32) / 255.0
        return px0, top_px, mask, text_width_css

    @staticmethod
    def _blur(mask, sigma_px):
        if sigma_px <= 0.05:
            return mask
        im = Image.fromarray((np.clip(mask, 0, 1) * 255.0).astype(np.uint8), "L")
        im = im.filter(ImageFilter.GaussianBlur(sigma_px))
        return np.asarray(im, dtype=np.float32) / 255.0



# =============================================================================
# Scene — palette-dependent paint over the shared :class:`_Geometry`.
#
# Everything colour-agnostic lives in the cached geometry (QR matrix, module /
# particle constants, ambient layout, radial fields, glyph masks + alpha). This
# class owns only what a palette switch must recompute: the QR row gradient,
# the wordmark / V2 colour layers, the per-palette colour arrays and the
# background plate. A switch is a few milliseconds and never touches the
# timeline, the window or the geometry.
# =============================================================================
class Scene:
    """One renderable scene: shared geometry + exactly one palette's colours."""

    _GEO = {}

    def __init__(self, w=SPLASH_W, h=SPLASH_H, ss=1, palette=None):
        self.W = w
        self.H = h
        self.k = ss
        self.pw = w * ss
        self.ph = h * ss
        key = (w, h, ss)
        geo = Scene._GEO.get(key)
        if geo is None:
            geo = _Geometry(w, h, ss)
            Scene._GEO[key] = geo
        self._geo = geo
        self._bg_plate = None
        self.palette = None
        # Per-frame scratch for the glow-ring pass (ring count -> blend weight).
        gx0, gy0, gx1, gy1 = geo._glow_box
        box = (gy1 - gy0, gx1 - gx0)
        self._ring_f = np.empty(box, np.float32)
        self._ring_i = np.empty(box, np.intp)
        self._ring_w = np.empty(box, np.float32)
        self._apply_palette(palette or DEFAULT_PALETTE)

    def __getattr__(self, name):
        """Fall through to the shared geometry for anything this class does not own."""
        if name.startswith("__"):
            raise AttributeError(name)
        geo = self.__dict__.get("_geo")
        if geo is None:
            raise AttributeError(name)
        return getattr(geo, name)

    # ------------------------------------------------------------------
    def set_palette(self, name):
        """Recolour in place. Returns True if anything changed.

        Deliberately does NOT touch the geometry cache, the window or any
        timing state: palette switching must never restart or stutter the intro.
        """
        if name == self.palette or name not in PALETTES:
            return False
        self._apply_palette(name)
        return True


    # ------------------------------------------------------------------
    def _apply_palette(self, name):
        col = PALETTES[name]
        self.palette = name
        ss = self.k

        # --- normalised colours the renderer reads every frame -----------
        bg = np.array(col["BG"], np.float32) / 255.0
        glow = np.array(col["GLOW"], np.float32) / 255.0
        deep = np.array(col["DEEP"], np.float32) / 255.0
        acc_a = np.array(col["A"], np.float32) / 255.0
        ice = np.array(col["ICE"], np.float32) / 255.0
        self._bg_f = bg
        self._glow_f = glow
        self._deep_f = deep
        self._a_f = acc_a
        self._ice_f = ice
        # Pairs and dust blend toward their colour vignetted toward BG:
        # colour + (BG - colour) * vig, see _over_vignetted().
        self._deep_to_bg = bg - deep
        self._a_to_bg = bg - acc_a

        # --- QR row gradient A -> B (truncated toward zero, per reference) -
        a_rgb, b_rgb = col["A"], col["B"]
        denom = max(1, self.N - 1)
        self.row_color = []
        for r in range(self.N):
            m = r / denom
            self.row_color.append((int(a_rgb[0] + (b_rgb[0] - a_rgb[0]) * m),
                                   int(a_rgb[1] + (b_rgb[1] - a_rgb[1]) * m),
                                   int(a_rgb[2] + (b_rgb[2] - a_rgb[2]) * m)))
        self._row_arr = np.array(self.row_color, np.float32) / 255.0
        self._row_f = list(self._row_arr)

        # --- background plate: BG + subtle tonal lift, vignette baked in ---
        # Built with two vector passes on a switch, then copied into the frame
        # buffer every tick — the per-frame path never recomputes it.
        if self._bg_plate is None:
            self._bg_plate = np.empty((self.ph, self.pw, 3), np.float32)
        # The tone field is (H, W); add the channel axis to fill the (H, W, 3) plate.
        np.multiply(self._tone_eff[..., None], _BG_TONE, out=self._bg_plate)
        np.add(self._bg_plate, bg, out=self._bg_plate)
        np.clip(self._bg_plate, 0.0, 1.0, out=self._bg_plate)

        # --- glow rings: frame = plate + w * (vignette(GLOW) - plate) -------
        # Nine source-over GLOW ellipses at alpha ga move a pixel covered by k
        # of them w = 1 - (1 - ga)^k of the way to GLOW. The vignette after
        # them is affine, so the vignetted result is plate + w times this
        # static per-pixel delta; a frame only computes w.
        gx0, gy0, gx1, gy1 = self._glow_box
        vig_g = self._vig_g[..., None]
        self._glow_delta = ((glow + (bg - glow) * vig_g)
                            - self._bg_plate[gy0:gy1, gx0:gx1]).astype(np.float32)

        # --- wordmark: gradient fill OVER its glow (premultiplied colour) --
        # CSS linear-gradient(90deg, A0 0%, A 40%, B 100%) across the
        # background box (text width + 0.24 em), sampled at pixel centres.
        box_w = (self._title_width + 0.24 * self.titleFS) * ss
        box_x = self.W / 2.0 * ss - box_w / 2.0
        tw = self._title_mask.shape[1]
        frac = np.clip((self._tx0 + np.arange(tw) + 0.5 - box_x) / box_w, 0.0, 1.0)
        grad = np.stack([np.interp(frac, (0.0, 0.4, 1.0),
                                   (col["A0"][ch], col["A"][ch], col["B"][ch]))
                         for ch in range(3)], axis=1).astype(np.float32) / 255.0
        m = self._title_mask[..., None]
        g = self._title_glow[..., None]
        self._title_layer = (grad[None, :, :] * m + acc_a * g * (1.0 - m)).astype(np.float32)

        # --- V2: ICE fill over the STROKE shadow over the GLOW halo --------
        stroke = np.array(col["STROKE"], np.float32) / 255.0
        f = self._v2_mask[..., None]
        s = self._v2_shadow[..., None]
        g = self._v2_glow[..., None]
        under = stroke * s + glow * g * (1.0 - s)
        self._v2_layer = (ice * f + under * (1.0 - f)).astype(np.float32)


# =============================================================================
# Frame rendering — pure function of (t_ms, ts_ms)
# =============================================================================
_RENDER_SCENE = None


def _scene():
    """Module-level :class:`Scene`, built once (all static assets are pre-rendered)."""
    global _RENDER_SCENE
    if _RENDER_SCENE is None:
        _RENDER_SCENE = Scene(SPLASH_W, SPLASH_H)
    return _RENDER_SCENE


class _Tiles:
    """Which 32 px tiles of the frame changed, for incremental rendering.

    ``cur`` collects the tiles drawn this frame; ``prev`` those drawn last
    frame (which must go back to the static background before drawing).
    Everything outside ``prev | cur`` is unchanged, so only those tiles are
    converted and put on screen (``updated``).
    """

    SIZE = 32

    def __init__(self, pw, ph):
        self.pw, self.ph = pw, ph
        self.nx = -(-pw // self.SIZE)
        self.ny = -(-ph // self.SIZE)
        self.prev = np.ones((self.ny, self.nx), bool)    # first frame: everything
        self.cur = np.zeros((self.ny, self.nx), bool)
        self.updated = [(0, 0, pw, ph)]
        self._row = np.zeros(self.nx + 2, np.int8)

    def invalidate(self):
        """Redo the whole frame next time (e.g. after a palette switch)."""
        self.prev[:] = True

    def mark(self, x0, y0, x1, y1):
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.pw, x1), min(self.ph, y1)
        if x1 > x0 and y1 > y0:
            s = self.SIZE
            self.cur[y0 // s:(y1 - 1) // s + 1, x0 // s:(x1 - 1) // s + 1] = True

    def mark_many(self, x0, y0, x1, y1):
        """Arrays of clipped, non-empty rectangles no larger than a tile."""
        s = self.SIZE
        tx0, ty0 = x0 // s, y0 // s
        tx1, ty1 = (x1 - 1) // s, (y1 - 1) // s
        for ty in (ty0, ty1):
            for tx in (tx0, tx1):
                self.cur[ty, tx] = True

    def rects(self, mask):
        """Pixel rectangles covering ``mask``: runs per tile row, merged downwards."""
        out = []
        open_runs = {}
        row = self._row
        for ty in range(self.ny):
            row[1:-1] = mask[ty]
            d = np.diff(row)
            runs = set(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))
            for key in [k for k in open_runs if k not in runs]:
                out.append(self._rect(key, open_runs.pop(key), ty))
            for key in runs:
                open_runs.setdefault(key, ty)
        for key, ty0 in open_runs.items():
            out.append(self._rect(key, ty0, self.ny))
        return out

    def _rect(self, run, ty0, ty1):
        s = self.SIZE
        return (run[0] * s, ty0 * s, min(self.pw, run[1] * s), min(self.ph, ty1 * s))

    def finish_frame(self, rects):
        self.updated = rects
        self.prev, self.cur = self.cur, self.prev
        self.cur[:] = False


def _no_mark(*_args):
    pass


def _mark_squares(mark_many, x0, y0, x1, y1, pw, ph):
    """Clip square arrays to the frame and mark the non-empty ones."""
    x0, y0 = np.clip(x0, 0, pw), np.clip(y0, 0, ph)
    x1, y1 = np.clip(x1, 0, pw), np.clip(y1, 0, ph)
    keep = (x1 > x0) & (y1 > y0)
    if keep.any():
        mark_many(x0[keep], y0[keep], x1[keep], y1[keep])


def _blit_over(buf, layer, alpha, ox, oy, opacity=1.0):
    """Source-over a premultiplied ``layer`` with coverage ``alpha`` at ``opacity``.

    ``layer`` is already colour * coverage, so the blend is
    ``dst * (1 - opacity * alpha) + opacity * layer`` — CSS ``opacity`` on the
    whole element, without multiplying the colour by its coverage again.
    """
    ph, pw = buf.shape[:2]
    lh, lw = alpha.shape
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(pw, ox + lw), min(ph, oy + lh)
    if x1 <= x0 or y1 <= y0:
        return
    lx0, ly0 = x0 - ox, y0 - oy
    sub = buf[y0:y1, x0:x1]
    la = layer[ly0:ly0 + (y1 - y0), lx0:lx0 + (x1 - x0)]
    wa = alpha[ly0:ly0 + (y1 - y0), lx0:lx0 + (x1 - x0)]
    sub *= (1.0 - opacity * wa)[..., None]
    sub += la * opacity


def _over_vignetted(buf, vig, colour, to_bg, alpha, x0, y0, x1, y1):
    """Source-over ``colour`` at ``alpha`` on ``[x0, x1) x [y0, y1)``, vignetted.

    The reference draws the pixel pairs and dust, then a radial BG vignette over
    everything drawn so far. Vignetting is affine per pixel
    (c -> c + (BG - c) * vig), so blending the vignetted colour over the
    already-vignetted frame is exactly the reference result while touching only
    this rectangle. ``to_bg`` is ``BG - colour``.
    """
    ph, pw = buf.shape[:2]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(pw, x1), min(ph, y1)
    if x1 <= x0 or y1 <= y0:
        return
    sub = buf[y0:y1, x0:x1]
    src = colour + to_bg * vig[y0:y1, x0:x1, None]
    src -= sub
    src *= alpha
    sub += src


def _add_squares(buf, x, y, size, rgb):
    """Additively draw pixel-rounded squares, then clamp the touched pixels at 1.

    The particles use 'lighter' blending, out = min(1, dst + colour * alpha).
    Every contribution is non-negative, so summing them all and clamping once is
    identical to clamping after each square. ``rgb`` holds colour * alpha per
    square; ``buf`` must be C-contiguous. Returns the clipped squares as
    ``(x0, y0, x1, y1)`` arrays, or None when nothing was drawn.
    """
    ph, pw = buf.shape[:2]
    x0 = np.clip(np.floor(x + 0.5), 0, pw).astype(np.intp)
    y0 = np.clip(np.floor(y + 0.5), 0, ph).astype(np.intp)
    x1 = np.clip(np.floor(x + size + 0.5), 0, pw).astype(np.intp)
    y1 = np.clip(np.floor(y + size + 0.5), 0, ph).astype(np.intp)
    w, h = x1 - x0, y1 - y0
    keep = (w > 0) & (h > 0)
    if not keep.any():
        return None
    x0, y0, w, h, rgb = x0[keep], y0[keep], w[keep], h[keep], rgb[keep]
    k = np.arange(int(max(w.max(), h.max())))
    inside = (k[None, :, None] < h[:, None, None]) & (k[None, None, :] < w[:, None, None])
    pix = ((y0[:, None, None] + k[None, :, None]) * pw
           + (x0[:, None, None] + k[None, None, :]))[inside]
    flat = buf.view()
    flat.shape = (ph * pw, 3)                    # raises rather than copying
    np.add.at(flat, pix, np.repeat(rgb.astype(np.float32), w * h, axis=0))
    hit = flat[pix]
    np.minimum(hit, 1.0, out=hit)
    flat[pix] = hit
    return x0, y0, x0 + w, y0 + h


def render_frame_into(sc, out, u8, t_ms, ts_ms=None, tiles=None, overlays=()):
    """Render frame ``(t, ts)`` of ``sc`` into pre-allocated buffers.

    ``t_ms`` is the animation time and ``ts_ms`` the continuous clock driving
    the background (ring breathing, drifting pairs, dust); it defaults to
    ``t_ms``. The playback policy (one-shot hold at 8800 ms, ``--splash-loop``)
    lives in :class:`Splash`, so this stays a pure function of ``(t, ts)``.

    ``out`` is a C-contiguous float32 ``(H, W, 3)`` scratch frame in [0, 1] and
    ``u8`` the uint8 result; the intro allocates both once. Values stay in
    [0, 1] by construction (every composite is a convex blend or a clamped
    additive), so the conversion is two in-place passes plus one cast. Set
    ``render_frame._verify = True`` to have that invariant re-checked.

    ``tiles`` (a :class:`_Tiles`) switches to incremental rendering for the
    live intro: only what was drawn last frame is restored from the static
    background, every draw marks the tiles it touches, and only changed
    tiles are converted; ``tiles.updated`` then lists the rectangles to put
    on screen. ``out`` must then be kept between frames, and ``u8`` may be
    any RGB-ordered view (e.g. into a BGRX buffer). ``overlays`` are
    ``(layer, alpha, x, y)`` premultiplied layers drawn on top (the palette
    chips). The resulting pixels are identical in both modes.
    """
    ts = float(t_ms) if ts_ms is None else float(ts_ms)
    t = clamp(float(t_ms), 0, T)

    ss = sc.k
    pw, ph = sc.pw, sc.ph
    plate, vig = sc._bg_plate, sc._vig

    # 1) Background plate (BG + tonal lift, vignette baked in) everywhere the
    #    glow pass below does not write every pixel itself.
    gx0, gy0, gx1, gy1 = sc._glow_box
    if tiles is None:
        mark = mark_many = _no_mark
        np.copyto(out[:gy0], plate[:gy0])
        np.copyto(out[gy1:], plate[gy1:])
        np.copyto(out[gy0:gy1, :gx0], plate[gy0:gy1, :gx0])
        np.copyto(out[gy0:gy1, gx1:], plate[gy0:gy1, gx1:])
    else:
        # Outside last frame's tiles the frame already IS the plate.
        mark, mark_many = tiles.mark, tiles.mark_many
        for (x0, y0, x1, y1) in tiles.rects(tiles.prev):
            np.copyto(out[y0:y1, x0:x1], plate[y0:y1, x0:x1])
        mark(gx0, gy0, gx1, gy1)

    # 2) Glow rings: nine stacked GLOW ellipses at alpha ga, rx = Rr(1 - i/9).
    #    A pixel inside k of them sits at w = 1 - (1 - ga)^k toward GLOW, with
    #    k = clip(floor(10 - 9 * e0 / Rr), 0, 9) from its elliptical radius e0.
    Rr = clamp(0.48 * sc.W, 220, 430) * (1 + 0.02 * math.sin(ts * 0.0008)) * ss
    ga = 0.04 * (1 + 0.7 * qr_presence(t))
    weights = (1.0 - (1.0 - ga) ** np.arange(10)).astype(np.float32)
    f, k, w = sc._ring_f, sc._ring_i, sc._ring_w
    np.multiply(sc._e0g, -9.0 / Rr, out=f)
    np.add(f, 10.0, out=f)
    np.copyto(k, f, casting="unsafe")           # truncation: floor wherever f >= 0
    np.take(weights, k, out=w, mode="clip")     # f < 1 -> no ring, f >= 10 -> all 9
    box = out[gy0:gy1, gx0:gx1]
    np.multiply(sc._glow_delta, w[..., None], out=box)
    np.add(box, plate[gy0:gy1, gx0:gx1], out=box)

    # 3) Ambient pixel pairs (drift + wrap) and dust (twinkle with ts): DEEP /
    #    A at their alpha, under the vignette (see _over_vignetted).
    deep, deep_to_bg = sc._deep_f, sc._deep_to_bg
    H80 = sc.H + 80
    for (x, py0, ps, psp, al) in sc.pairs:
        py = ((py0 - psp * ts / 1000) % H80 + H80) % H80 - 40
        for (rx, ry, rs) in ((x, py, ps),
                             (x + 0.85 * ps, py + 0.85 * ps, 0.8 * ps)):
            rect = (js_round(rx * ss), js_round(ry * ss),
                    js_round((rx + rs) * ss), js_round((ry + rs) * ss))
            _over_vignetted(out, vig, deep, deep_to_bg, al, *rect)
            mark(*rect)

    acol, a_to_bg = sc._a_f, sc._a_to_bg
    for (dx, dy, dr, phs, dsp) in sc.dust:
        al = 0.12 + 0.3 * (0.5 + 0.5 * math.sin(ts * 0.001 * dsp + phs))
        # An r x r square at (x, y) with r < 2 px: drawn as the nearest n x n
        # pixel block (n = ceil(r)), alpha scaled by the area it stands for.
        r = dr * ss
        n = max(1, math.ceil(r))
        x0 = js_round(dx * ss + (r - n) / 2)
        y0 = js_round(dy * ss + (r - n) / 2)
        _over_vignetted(out, vig, acol, a_to_bg, al * (r / n) ** 2,
                        x0, y0, x0 + n, y0 + n)
        mark(x0, y0, x0 + n, y0 + n)

    # 4) QR code — three passes in the reference's order, after the vignette.
    if t >= ASM0:
        S = sc.S
        ox, oy, cell = sc.qr_x, sc.qr_y, sc.cell
        size_px = sc.size * ss
        row, ice = sc._row_f, sc._ice_f
        scan_on = SCAN0 <= t <= SCAN1
        ly = oy + clamp((t - SCAN0) / (SCAN1 - SCAN0)) * S

        # PASS 1 - intact modules, normal blending, drawn in module order.
        act = np.flatnonzero((t >= sc.m_asm) & (t < sc.m_brk))
        if act.size:
            e = 1.0 - (1.0 - np.clip((t - sc.m_asm[act]) / ASM_DUR, 0.0, 1.0)) ** 3
            sz = size_px * (0.4 + 0.6 * e)
            x = sc.m_bx[act] + sc.m_dx[act] * (1.0 - e) + (size_px - sz) / 2
            y = sc.m_by[act] + sc.m_dy[act] * (1.0 - e) + (size_px - sz) / 2
            X0, Y0 = np.floor(x + 0.5).astype(np.intp), np.floor(y + 0.5).astype(np.intp)
            X1 = np.floor(x + sz + 0.5).astype(np.intp)
            Y1 = np.floor(y + sz + 0.5).astype(np.intp)
            _mark_squares(mark_many, X0, Y0, X1, Y1, pw, ph)
            if scan_on:
                hot = (np.abs(sc.m_cy[act] - ly) < 1.4 * cell).tolist()
            else:
                hot = [False] * act.size
            for x0, y0, x1, y1, a, h, r in zip(
                    X0.tolist(), Y0.tolist(), X1.tolist(), Y1.tolist(),
                    np.minimum(1.0, 1.7 * e).tolist(), hot,
                    sc.m_row[act].tolist()):
                x0, y0 = max(0, x0), max(0, y0)
                x1, y1 = min(pw, x1), min(ph, y1)
                if x1 <= x0 or y1 <= y0:
                    continue
                sub = out[y0:y1, x0:x1]
                col = ice if h else row[r]
                if a >= 1.0:
                    sub[...] = col
                else:
                    sub *= 1.0 - a
                    sub += col * a

        # PASS 2 - scan bar: ICE, additive, alpha 0 -> 0.5 -> 0 over ly +- 14.
        if scan_on:
            ly_px = ly * ss
            cx0 = max(0, int(math.floor((ox - 10) * ss)))
            cx1 = min(pw, int(math.ceil((ox + S + 10) * ss)))
            ry0 = max(0, int(math.floor(ly_px - 14 * ss)))
            ry1 = min(ph, int(math.ceil(ly_px + 14 * ss)))
            if cx1 > cx0 and ry1 > ry0:
                yy = np.arange(ry0, ry1, dtype=np.float32) + 0.5
                a = 0.5 * np.maximum(0.0, 1.0 - np.abs(yy - ly_px) / (14.0 * ss))
                band = out[ry0:ry1, cx0:cx1]
                mark(cx0, ry0, cx1, ry1)
                band += (a[:, None] * ice)[:, None, :]
                np.minimum(band, 1.0, out=band)

        # PASS 3 - particles, additive, as one vectorised draw. Quads of a
        # broken module rest in place until their delay passes (tau <= 0).
        if t >= DIS0:
            tau = (t - sc.p_brk - sc.p_dly) * 0.001
            live = np.flatnonzero((t >= sc.p_brk) & (tau * 1000.0 < sc.p_life))
            if live.size:
                tau = tau[live]
                fly = tau > 0
                ft = np.where(fly, tau, 0.0)
                ul = ft * 1000.0 / sc.p_life[live]
                ksc = sc.sc * ss
                phase = ft * sc.p_tf[live] + sc.p_ta[live]
                wob = sc.p_tm[live] * ksc * ft
                px = (sc.p_x[live] + sc.p_vx[live] * ksc * ft * (1 + 0.4 * ft)
                      + np.sin(phase) * wob)
                py = (sc.p_y[live] + sc.p_vy[live] * ksc * ft - 30 * ksc * ft * ft
                      + np.cos(phase) * wob * 0.6)
                alpha = np.where(fly, (1.0 - ul) ** 1.4, 1.0)
                cols = np.where((fly & (ul < 0.12))[:, None], ice,
                                sc._row_arr[sc.p_row[live]])
                drawn = _add_squares(out, px, py, sc.p_half * (1.0 - 0.7 * ul),
                                     cols * alpha[:, None])
                if drawn is not None:
                    mark_many(*drawn)

    # 5) Title, then V2 (drawn last), each one group at opacity alpha_title(t).
    ta = title_alpha(t)
    if ta > 0:
        _blit_over(out, sc._title_layer, sc._title_alpha, sc._tx0, sc._ty0, ta)
        _blit_over(out, sc._v2_layer, sc._v2_alpha, sc._v2_ox, sc._v2_oy, ta)
        for (lay, ox_, oy_) in ((sc._title_alpha, sc._tx0, sc._ty0),
                                (sc._v2_alpha, sc._v2_ox, sc._v2_oy)):
            mark(ox_, oy_, ox_ + lay.shape[1], oy_ + lay.shape[0])

    # 6) Overlays on top of everything (the palette chips).
    for (layer, alpha, ox_, oy_) in overlays:
        _blit_over(out, layer, alpha, ox_, oy_)
        mark(ox_, oy_, ox_ + alpha.shape[1], oy_ + alpha.shape[0])

    if getattr(render_frame, "_verify", False):
        lo, hi = float(out.min()), float(out.max())
        if lo < -1e-6 or hi > 1.0001:
            raise AssertionError("frame left [0, 1]: min=%g max=%g" % (lo, hi))

    # 7) float32 -> uint8: scale, round, cast.
    if tiles is None:
        np.multiply(out, 255.0, out=out)
        np.add(out, 0.5, out=out)
        # ndarray.astype() has no `out=`; an unsafe copyto truncates in place.
        np.copyto(u8, out, casting="unsafe")
        return u8
    # Incremental: `out` must stay intact, so convert through a temporary,
    # covering this frame's tiles and last frame's (now plate again).
    rects = tiles.rects(tiles.prev | tiles.cur)
    for (x0, y0, x1, y1) in rects:
        tmp = out[y0:y1, x0:x1] * 255.0
        tmp += 0.5
        np.copyto(u8[y0:y1, x0:x1], tmp, casting="unsafe")
    tiles.finish_frame(rects)
    return u8


def render_frame(t_ms, ts_ms=None):
    """Pure wrapper around :func:`render_frame_into` that allocates its buffers.

    Returns a numpy uint8 array shaped ``(H, W, 3)``, RGB in [0, 255], for
    animation time ``t_ms`` with the background clock at ``ts_ms`` (defaults to
    ``t_ms``). The intro itself calls :func:`render_frame_into` so it can keep
    its buffers alive for the whole playback.
    """
    sc = _scene()
    out = np.empty((sc.ph, sc.pw, 3), dtype=np.float32)
    u8 = np.empty((sc.ph, sc.pw, 3), dtype=np.uint8)
    return render_frame_into(sc, out, u8, t_ms, ts_ms)


# =============================================================================
# Title / V2 alpha and static layer helpers
# =============================================================================
def title_alpha(t):
    """Opacity of the title + V2 layers as defined by the reference spec."""
    if t < FO0:
        return 1.0
    if t < FO1:
        return 1.0 + (DIM - 1.0) * smooth((t - FO0) / (FO1 - FO0))
    if t < FI0:
        return DIM
    if t < FI1:
        return DIM + (1.0 - DIM) * smooth((t - FI0) / (FI1 - FI0))
    return 1.0


def qr_presence(t):
    """Glow strength: ramps up while the QR assembles, fades as it breaks apart."""
    return clamp(clamp((t - 1500) / 1200) - clamp((t - DIS0 - 300) / 1500))


# =============================================================================
# Presenters — how a finished frame reaches the screen
# =============================================================================
class _GdiPresenter:
    """Blits the changed rectangles of a BGRX frame straight onto a window.

    Windows only. A full-screen PhotoImage paste + redraw costs ~21 ms per
    1920x1200 frame; SetDIBitsToDevice of just the tiles that changed costs a
    few. ``rgb`` is an RGB-ordered view into the BGRX buffer for the renderer.
    """

    def __init__(self, widget, w, h):
        import ctypes
        from ctypes import wintypes

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = (
                ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            )

        self._byref = ctypes.byref
        # Private handles: no prototype changes leak to ctypes.windll users.
        self._user32 = ctypes.WinDLL("user32")
        self._gdi32 = ctypes.WinDLL("gdi32")
        self._user32.GetDC.argtypes = (wintypes.HWND,)
        self._user32.GetDC.restype = wintypes.HDC
        self._user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
        self._gdi32.SetDIBitsToDevice.argtypes = (
            wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.UINT,
            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
        self._bmi = BITMAPINFOHEADER()
        self._bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self._bmi.biPlanes = 1
        self._bmi.biBitCount = 32                  # BI_RGB, top-down (negative height)
        self._widget = widget
        self.w, self.h = w, h
        self.frame = np.zeros((h, w, 4), np.uint8)
        self.rgb = self.frame[..., 2::-1]

    def present(self, rects):
        hwnd = self._widget.winfo_id()
        dc = self._user32.GetDC(hwnd)
        if not dc:
            return
        try:
            for (x0, y0, x1, y1) in rects:
                w, h = x1 - x0, y1 - y0
                if w <= 0 or h <= 0:
                    continue
                block = np.ascontiguousarray(self.frame[y0:y1, x0:x1])
                self._bmi.biWidth = w
                self._bmi.biHeight = -h
                self._gdi32.SetDIBitsToDevice(dc, x0, y0, w, h, 0, 0, 0, h,
                                              block.ctypes.data, self._byref(self._bmi), 0)
        finally:
            self._user32.ReleaseDC(hwnd, dc)

    def present_all(self):
        self.present([(0, 0, self.w, self.h)])


class _PhotoPresenter:
    """Portable fallback: one Canvas PhotoImage, pasted whole every frame."""

    def __init__(self, canvas, w, h):
        self._canvas = canvas
        self._photo = None
        self.rgb = np.zeros((h, w, 3), np.uint8)

    def present(self, _rects=None):
        frame = Image.fromarray(self.rgb, "RGB")
        if self._photo is None:
            # Owned by this window's interpreter, not tkinter's default root.
            self._photo = ImageTk.PhotoImage(frame, master=self._canvas)
            self._canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self._photo.paste(frame)
        # Draw now, so an immediately due next tick cannot starve the redraw.
        self._canvas.update_idletasks()

    def present_all(self):
        self.present()


def _ui_scale():
    """Windows display scaling (1.0 at 100 %), for the size of the chip row."""
    try:
        import ctypes
        return max(1.0, ctypes.WinDLL("user32").GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


def _ui_font(px):
    """A monospace UI font like the reference's JetBrains Mono."""
    for name in ("consola.ttf", "CascadiaMono.ttf", "cour.ttf", _FONT_TTF):
        try:
            return ImageFont.truetype(name, px)
        except Exception:
            continue
    return ImageFont.load_default()


# =============================================================================
# Palette chips — the reference page's palette row, drawn into the frame
# =============================================================================
class _ChipBar:
    """``PALETTE  [Aqua Mint] [Ultraviolet] [Ember]`` along the bottom edge.

    Styled like the reference page: a muted, letter-spaced PALETTE tag, then
    one chip per palette with a translucent panel, a 1 px border, an A -> B
    swatch and a monospace label. The active chip has an A border and ICE
    text, a hovered chip an A border. Each state is rendered once with Pillow
    into a premultiplied layer that the renderer draws on top of the scene.
    """

    NAMES = ("Aqua Mint", "Ultraviolet", "Ember")
    PANEL = (8, 16, 20, 189)          # rgba(8, 16, 20, .74)
    LINE = (23, 54, 60)               # #17363c
    FG = (215, 244, 247)              # #d7f4f7
    MUTED = (134, 169, 175)           # #86a9af

    def __init__(self, W, H, scale=1.0):
        u = scale
        self._u = u
        self._font = _ui_font(max(9, int(round(13 * u))))
        self._tag_font = _ui_font(max(8, int(round(11 * u))))
        self._pad_x, self._pad_y = int(round(12 * u)), int(round(8 * u))
        self._sw_w, self._sw_h = int(round(30 * u)), int(round(10 * u))
        self._sw_gap = int(round(8 * u))
        self._gap = int(round(12 * u))
        self._border = max(1, int(round(u)))
        self._radius = int(round(4 * u))
        self.chip_h = int(round(13 * u * 1.5)) + 2 * self._pad_y + 2 * self._border

        self._tag = "PALETTE"
        self._tag_spacing = 0.14 * 11 * u
        tag_w = int(math.ceil(sum(self._tag_font.getlength(ch) + self._tag_spacing
                                  for ch in self._tag)))
        widths = [self._pad_x * 2 + self._sw_w + self._sw_gap
                  + int(math.ceil(self._font.getlength(n))) + 2 * self._border
                  for n in self.NAMES]
        total = tag_w + self._gap + sum(widths) + self._gap * (len(widths) - 1)

        self.x = int((W - total) // 2)
        self.y = int(H - round(44 * u) - self.chip_h)
        self.w, self.h = total, self.chip_h
        self._tag_w = tag_w
        self.rects = {}
        cx = self.x + tag_w + self._gap
        for name, cw in zip(self.NAMES, widths):
            self.rects[name] = (cx, self.y, cx + cw, self.y + self.chip_h)
            cx += cw + self._gap
        self._cache = {}

    def hit(self, x, y):
        """Palette name of the chip at window pixel (x, y), or None."""
        for name, (x0, y0, x1, y1) in self.rects.items():
            if x0 <= x < x1 and y0 <= y < y1:
                return name
        return None

    def layer(self, active, hover):
        """``(premultiplied colour, alpha, x, y)`` for this chip state."""
        key = (active, hover)
        cached = self._cache.get(key)
        if cached is None:
            cached = self._cache[key] = self._render(active, hover)
        return cached

    def _render(self, active, hover):
        bar = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        text = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        dt = ImageDraw.Draw(text)

        # Tag, vertically centred, letter-spaced.
        cx = 0.0
        for ch in self._tag:
            dt.text((cx, self.h / 2), ch, font=self._tag_font,
                    fill=self.MUTED + (255,), anchor="lm")
            cx += self._tag_font.getlength(ch) + self._tag_spacing

        for name in self.NAMES:
            x0, _, x1, _ = self.rects[name]
            x0 -= self.x
            x1 -= self.x
            pal = PALETTES[name]
            accent = pal["A"]
            on = name == active
            border = accent if (on or name == hover) else self.LINE
            chip = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            ImageDraw.Draw(chip).rounded_rectangle(
                (x0, 0, x1 - 1, self.h - 1), radius=self._radius,
                fill=self.PANEL, outline=border + (255,), width=self._border)
            bar = Image.alpha_composite(bar, chip)

            # A -> B swatch with rounded corners.
            sx = x0 + self._border + self._pad_x
            sy = (self.h - self._sw_h) // 2
            ramp = np.linspace(0.0, 1.0, self._sw_w, dtype=np.float32)[:, None]
            row = np.array(pal["A"], np.float32) * (1 - ramp) + np.array(pal["B"], np.float32) * ramp
            sw = Image.fromarray(np.repeat(row[None].round().astype(np.uint8), self._sw_h, 0), "RGB")
            mask = Image.new("L", sw.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, self._sw_w - 1, self._sw_h - 1), radius=max(1, int(round(2 * self._u))), fill=255)
            bar.paste(sw, (sx, sy), mask)

            dt.text((sx + self._sw_w + self._sw_gap, self.h / 2), name, font=self._font,
                    fill=(pal["ICE"] if on else self.FG) + (255,), anchor="lm")

        bar = Image.alpha_composite(bar, text)
        rgba = np.asarray(bar, dtype=np.float32) / 255.0
        alpha = np.ascontiguousarray(rgba[..., 3])
        premult = np.ascontiguousarray(rgba[..., :3] * alpha[..., None])
        return premult, alpha, self.x, self.y


# =============================================================================
# Splash — the cinematic intro
# =============================================================================
class Splash:
    """Full-screen intro driven by :func:`render_frame_into`, with palette chips.

    :meth:`start` covers the monitor that hosts the app (see
    :func:`splash_rect`), builds the scene at its pixel size and renders the
    first frame before the window is mapped. A ``root.after()`` tick then
    renders each frame incrementally (only changed tiles, see :class:`_Tiles`)
    and puts the changed rectangles on screen — straight through GDI on
    Windows, a reused ``PhotoImage`` elsewhere — scheduled ``TICK_MS`` after
    the start of the previous tick. ``t = 0`` is the first visible frame.

    The chips along the bottom edge recolour the running intro in place —
    background, glow, pixel pairs, QR, scan bar, particles and wordmark —
    without restarting the timeline; ``on_palette(name)`` reports the choice.

    Hand-off (:meth:`_finish`): ``on_done`` reveals the main window underneath
    the topmost splash, which keeps its final frame for ``HANDOFF_MS`` while the
    main window paints, then closes. A frame that fails to render is reported
    and hands over at once instead of leaving a frozen window up.

    Attributes:
        on_done: called (with no arguments) once, when the intro ends.
        on_palette: called with the palette name when the user picks a chip.
    """

    _loop = False

    def __init__(self, on_done=None, palette=None, on_palette=None):
        self.on_done = on_done
        self.on_palette = on_palette
        self.palette = palette if palette in PALETTES else DEFAULT_PALETTE
        # Built in start(), before any window is mapped.
        self.scene = None
        self.root = None
        self.win = None
        self.surface = None
        self.W = SPLASH_W
        self.H = SPLASH_H
        self._presenter = None
        self._tiles = None
        self._chips = None
        self._hover = None
        self._buf_f = None
        self._after_id = None
        self._start_time = None     # perf_counter() ms at t = 0
        self._mapped = False
        self._full_present = True
        self._done = False

    def _palette(self):
        return PALETTES.get(self.palette, PALETTES[DEFAULT_PALETTE])

    def _bg_hex(self):
        return "#%02x%02x%02x" % self._palette()["BG"]

    def turn_palette_on(self, name):
        """Switch the live palette. Returns True if the scene was recoloured.

        Only the scene's colour layers change: the timeline, the window and the
        geometry cache are untouched, so playback neither restarts nor stutters.
        Called before :meth:`start`, it selects the starting palette.
        """
        if name not in PALETTES or name == self.palette:
            return False
        try:
            if self.scene is not None:
                self.scene.set_palette(name)
        except Exception:
            # Never let a recolour take the intro down with it.
            traceback.print_exc()
            return False
        self.palette = name
        if self._tiles is not None:
            self._tiles.invalidate()            # the background itself changed
        # The window/surface background is deliberately left alone: changing
        # it makes Tk repaint the surface flat over the blitted frame, which
        # shows as a flash until the next frame arrives.
        return True

    def start(self, root):
        """Build the scene and the full-screen window, render frame 0, start the tick.

        Exceptions propagate: when the intro cannot start, the caller reveals
        the main window itself.
        """
        self.root = root
        if splash_loop_mode():
            Splash._loop = True

        mx, my, W, H = splash_rect(root)
        self.W, self.H = W, H
        self.scene = Scene(W, H, palette=self.palette)
        self._buf_f = np.empty((H, W, 3), np.float32)
        self._tiles = _Tiles(W, H)
        self._chips = _ChipBar(W, H, _ui_scale())

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=self._bg_hex())
        self.win.geometry(f"{W}x{H}+{mx}+{my}")
        self._presenter = self._make_presenter(W, H)
        render_frame_into(self.scene, self._buf_f, self._presenter.rgb, 0.0, 0.0,
                          tiles=self._tiles, overlays=self._overlays())

        self.win.bind("<Map>", self._on_map, add="+")
        self.surface.bind("<Expose>", self._on_expose, add="+")
        self.surface.bind("<Motion>", self._on_motion, add="+")
        self.surface.bind("<Leave>", lambda _e: self._set_hover(None), add="+")
        self.surface.bind("<Button-1>", self._on_click, add="+")
        self._after_id = self.win.after(TICK_MS, self._tick)
        return True

    def _make_presenter(self, W, H):
        """GDI blits on Windows; a Canvas PhotoImage anywhere else."""
        if sys.platform.startswith("win"):
            try:
                # bg="" makes Tk never paint this frame: a flat background
                # repaint (an Expose, a stall) would otherwise wipe the blitted
                # image, and only the tiles changed afterwards would come back.
                self.surface = tk.Frame(self.win, width=W, height=H, bg="",
                                        highlightthickness=0, borderwidth=0)
                self.surface.pack()
                return _GdiPresenter(self.surface, W, H)
            except Exception:
                traceback.print_exc()
                if self.surface is not None:
                    self.surface.destroy()
                    self.surface = None
        self.surface = tk.Canvas(self.win, width=W, height=H, bg=self._bg_hex(),
                                 highlightthickness=0, borderwidth=0)
        self.surface.pack()
        return _PhotoPresenter(self.surface, W, H)

    def _overlays(self):
        return (self._chips.layer(self.palette, self._hover),)

    # -- events ---------------------------------------------------------------
    def _on_map(self, event):
        """Start the clock at the first frame the user actually sees."""
        if self._mapped or str(event.widget) != str(self.win):
            return
        self._mapped = True
        self._start_time = time.perf_counter() * 1000.0
        self._request_full_present()

    def _on_expose(self, _event):
        # Tk repaints the surface background at idle time after an Expose;
        # put the whole frame back right after that repaint.
        self._request_full_present()

    def _request_full_present(self):
        self._full_present = True
        if self.win is not None:
            self.win.after_idle(self._present_now)

    def _present_now(self):
        try:
            self._present()
        except Exception:
            traceback.print_exc()

    def _set_hover(self, name):
        if name != self._hover:
            self._hover = name
            try:
                self.surface.configure(cursor="hand2" if name else "")
            except Exception:
                pass

    def _on_motion(self, event):
        self._set_hover(self._chips.hit(event.x, event.y))

    def _on_click(self, event):
        if self._done:
            # The main window is already being revealed in the chosen theme;
            # a late click would change the saved theme but not the window.
            return
        name = self._chips.hit(event.x, event.y)
        if not name or not self.turn_palette_on(name):
            return
        # Show the recoloured frame right away instead of on the next tick.
        try:
            ts = time.perf_counter() * 1000.0 - (self._start_time or 0.0)
            t = ts % T if Splash._loop else min(ts, FI1)
            render_frame_into(self.scene, self._buf_f, self._presenter.rgb, t, ts,
                              tiles=self._tiles, overlays=self._overlays())
            self._present()
        except Exception:
            traceback.print_exc()
        if self.on_palette is not None:
            try:
                self.on_palette(name)
            except Exception:
                traceback.print_exc()

    # -- frames ---------------------------------------------------------------
    def _present(self):
        if not self._mapped or self._presenter is None:
            return
        if self._full_present:
            self._full_present = False
            self._presenter.present_all()
        else:
            self._presenter.present(self._tiles.updated)

    def _tick(self):
        """Render and show one frame, then schedule the next one (or finish)."""
        self._after_id = None
        if self._done or self.win is None:
            return
        try:
            alive = bool(self.win.winfo_exists())
        except Exception:
            alive = False
        if not alive:
            self._finish()
            return

        now = time.perf_counter() * 1000.0
        if self._start_time is None:
            # No <Map> yet: count from here anyway, so the timeline always
            # reaches the hand-off even if the event never arrives.
            self._start_time = now
        ts = now - self._start_time
        t = ts % T if Splash._loop else min(ts, FI1)
        try:
            render_frame_into(self.scene, self._buf_f, self._presenter.rgb, t, ts,
                              tiles=self._tiles, overlays=self._overlays())
            self._present()
        except Exception:
            # Fail fast: report, then hand over to the main window instead of
            # leaving a frozen splash up until the timeline runs out.
            traceback.print_exc()
            self._finish()
            return

        if not Splash._loop and ts >= FI1:
            self._finish()
            return
        spent = time.perf_counter() * 1000.0 - now
        self._after_id = self.win.after(max(1, int(TICK_MS - spent)), self._tick)

    def _cancel_tick(self):
        if self._after_id is not None:
            try:
                if self.win is not None:
                    self.win.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def stop(self):
        """Close the splash window now (no hand-off)."""
        self._cancel_tick()
        if self.win is not None:
            try:
                self.win.destroy()
            except Exception:
                pass
            self.win = None
        self.surface = None
        self._presenter = None

    def _finish(self):
        """Hand over to the main window exactly once.

        ``on_done`` reveals the main window underneath the topmost splash; the
        splash keeps its final frame for ``HANDOFF_MS`` while that window maps
        and paints, then closes — the cut goes from a full frame to a fully
        drawn window, never through the desktop.
        """
        if self._done:
            return
        self._done = True
        self._cancel_tick()
        if self.on_done is not None:
            try:
                self.on_done()
            except Exception:
                traceback.print_exc()
        if self.win is not None:
            try:
                self._after_id = self.win.after(HANDOFF_MS, self.stop)
                return
            except Exception:
                pass
        self.stop()


def main():
    """Entry point: play the splash intro, then hand over to the app."""
    if splash_loop_mode():
        Splash._loop = True

    # Deferred: ui.app imports THIS module for Splash/splash_disabled, and the
    # old body here created a second, stray Tk root that was never destroyed.
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    app.run(show_splash=True)


if __name__ == "__main__":
    main()


