"""Premium brand mark for QR Code Studio v2 -- "digital disintegration" concept.

Rendered entirely in code with Pillow (supersampled), so it stays razor-sharp at
any size, needs no external downloads, and ships inside the frozen .exe without
extra data files.

Concept (matches the approved reference)
----------------------------------------
A QR-inspired module field whose left / centre stays crisp while the right edge
*disintegrates*: modules scatter, shrink and fade to the right, joined by
horizontal cyan motion streaks and glowing particles. The mark is an intentional
brand graphic -- it is NOT a scannable QR code and encodes no data.

Palette: electric cyan / ice blue / spring green on pure AMOLED black.

Public API:
    render_logo(size=256, glow=True)   -> PIL.Image (RGBA) square symbol
    render_wordmark(width=520, ...)    -> PIL.Image (RGBA) gradient italic wordmark
    logo_ctk_image(size=38)            -> customtkinter.CTkImage
    render_lockup(width=640, ...)      -> PIL.Image (RGBA) stacked symbol + wordmark
    save_logo_assets(...)              -> write reusable PNGs under assets/logo
    render_app_icon(size=256)          -> PIL.Image (RGBA) mark on a dark rounded plate
    save_app_icon(path=APP_ICON)       -> write the multi-size Windows .ico
    apply_window_icon(window)          -> brand icon in a window's title bar
"""

from __future__ import annotations

import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# Brand palette (electric cyan / ice blue / spring green on pure black)
# ---------------------------------------------------------------------------
ACCENT = (34, 211, 238)          # electric cyan  #22D3EE  (kept: splash imports it)
ACCENT_BRIGHT = (103, 232, 249)  # ice-blue       #67E8F9  (kept: splash imports it)
ACCENT_DIM = (21, 94, 117)       # deep cyan shadow

GREEN_TOP = (125, 240, 210)      # spring cyan-green (top of the module field)
BLUE_BOT = (40, 140, 235)        # deeper blue-cyan (bottom of the module field)
ICE = (190, 250, 255)            # near-white ice (scattered particles / streaks)

BRAND_WHITE = (243, 246, 250)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_DIR = os.path.join(_REPO_ROOT, "assets", "logo")
# Shipped with the app (the PyInstaller spec bundles it under assets/).
APP_ICON = os.path.join(_REPO_ROOT, "assets", "app.ico")
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

_cache: dict = {}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def _lerp(a, b, f):
    f = _clamp(f)
    return tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))


def _multistop(stops, f):
    """Interpolate across a list of (position, color) stops; position in [0,1]."""
    f = _clamp(f)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= f <= p1:
            t = 0.0 if p1 == p0 else (f - p0) / (p1 - p0)
            return _lerp(c0, c1, t)
    return stops[-1][1]


def _rounded(draw, box, radius, **kwargs):
    if hasattr(draw, "rounded_rectangle"):
        draw.rounded_rectangle(box, radius=radius, **kwargs)
    else:  # pragma: no cover
        draw.rectangle(box, **kwargs)


def _tint(img, color, amount):
    """Blend an RGBA image's RGB toward ``color`` by ``amount`` (keeps alpha)."""
    amount = _clamp(amount)
    solid = Image.new("RGBA", img.size, color + (255,))
    rgb = Image.blend(img, solid, amount)
    rgb.putalpha(img.split()[3])
    return rgb


# ---------------------------------------------------------------------------
# QR-inspired module matrix (a stylised, non-scannable field)
# ---------------------------------------------------------------------------
def _qr_matrix(n=25):
    """Build a QR-*inspired* boolean matrix.

    Three finder patterns, timing + alignment patterns, and a deterministic
    organic data fill. This is a brand graphic, not a real (scannable) QR code.
    """
    rng = random.Random(20240617)
    m = [[0] * n for _ in range(n)]
    reserved = [[False] * n for _ in range(n)]

    def block(r0, c0, h, w):
        for r in range(h):
            for c in range(w):
                if 0 <= r0 + r < n and 0 <= c0 + c < n:
                    reserved[r0 + r][c0 + c] = True

    def finder(r0, c0):
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                m[r0 + r][c0 + c] = 1 if (edge or core) else 0
        block(r0 - 1, c0 - 1, 9, 9)   # quiet separator ring

    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)

    # Timing patterns.
    for i in range(8, n - 8):
        m[6][i] = 1 if i % 2 == 0 else 0
        reserved[6][i] = True
        m[i][6] = 1 if i % 2 == 0 else 0
        reserved[i][6] = True

    # Alignment pattern (bottom-right area).
    ar, ac = n - 9, n - 9
    for r in range(5):
        for c in range(5):
            edge = r in (0, 4) or c in (0, 4)
            core = r == 2 and c == 2
            m[ar + r][ac + c] = 1 if (edge or core) else 0
    block(ar - 1, ac - 1, 7, 7)

    # Deterministic organic data fill.
    for r in range(n):
        for c in range(n):
            if reserved[r][c]:
                continue
            m[r][c] = 1 if rng.random() < 0.52 else 0
    return m

# ---------------------------------------------------------------------------
# Symbol: crisp QR field on the left, disintegrating modules on the right
# ---------------------------------------------------------------------------
def render_logo(size: int = 256, glow: bool = True) -> Image.Image:
    """Render the brand symbol at ``size`` px (RGBA, 4x supersampled).

    The left/centre of the module field is crisp; the right edge *disintegrates*
    into scattered, shrinking, fading modules plus glowing particles, and cyan
    motion streaks sweep to the right. Purely a brand graphic (no data).
    """
    key = (int(size), bool(glow))
    hit = _cache.get(key)
    if hit is not None:
        return hit.copy()

    s = max(16, int(size))
    ss = 4                                     # supersample factor
    R = s * ss
    detail = s >= 96                           # keep particles/streaks when legible
    # Below ~64px the scatter is tamed so the silhouette stays crisp (the app's
    # sidebar mark renders at 76px); large sizes get the full disintegration.
    mini = s < 64

    N = 21                                    # chunkier modules (reads like the ref)
    mat = _qr_matrix(N)

    # Working square with a little breathing room on every side.
    field = Image.new("RGBA", (R, R), (0, 0, 0, 0))
    fd = ImageDraw.Draw(field)

    pad = R * 0.035
    grid = R - pad * 2.0                       # QR field extent
    cell = grid / N

    # Where disintegration begins (fraction across the field). Modules to the
    # right of this progressively scatter, shrink and fade.
    dis_start = 0.52
    # Rightward "blow-out" region: the far-right columns detach most.
    rng = random.Random(7)

    def cell_rect(r, c):
        x0 = pad + c * cell
        y0 = pad + r * cell
        inset = cell * 0.06
        return [x0 + inset, y0 + inset, x0 + cell - inset, y0 + cell - inset]

    def module_color(r, c):
        """Vertical cyan->spring-green gradient across the field height."""
        t = (r / (N - 1)) * 0.85 + (c / (N - 1)) * 0.15
        return _multistop([(0.0, ACCENT_BRIGHT), (0.45, ACCENT),
                           (0.8, GREEN_TOP), (1.0, BLUE_BOT)], t)

    # ---- Draw modules: crisp on the left, disintegrating on the right ----
    for r in range(N):
        for c in range(N):
            if not mat[r][c]:
                continue
            base_col = module_color(r, c)
            # Horizontal progress of this column within the disintegration zone.
            u = (c / (N - 1))
            d = _clamp((u - dis_start) / (1.0 - dis_start))  # 0..1
            box = cell_rect(r, c)
            w = box[2] - box[0]
            h = box[3] - box[1]

            if d <= 0.0:
                # Crisp intact module.
                fd.rectangle(box, fill=base_col + (255,))
                continue

            # Disintegrating module: shrink, drift right/up, fade.
            shrink = 1.0 - (0.40 if mini else 0.62) * d
            drift_x = d * d * cell * (1.6 if mini else 3.4) * (0.6 + rng.random() * 0.9)
            drift_y = (rng.random() - 0.55) * cell * (1.1 if mini else 2.2) * d
            nw = w * shrink
            nh = h * shrink
            cx = box[0] + drift_x + (w - nw) / 2.0
            cy = box[1] + drift_y + (h - nh) / 2.0
            alpha = int(255 * (1.0 - (0.70 if mini else 0.88) * d))
            col = _lerp(base_col, ICE, d * (0.4 if mini else 0.55))
            fd.rectangle([cx, cy, cx + nw, cy + nh], fill=col + (alpha,))

    # ---- Scattered glowing particles to the right (only when legible) ----
    if detail:
        for _ in range(int(N * 3.4)):
            rr = rng.random()
            cc = dis_start + rng.random() * (1.05 - dis_start)
            px = pad + cc * grid + rng.random() * cell * 2.0
            py = pad + (rr * grid) + (rng.random() - 0.5) * cell
            pr = R * (0.004 + rng.random() * 0.013)
            pa = int(255 * (0.25 + rng.random() * 0.65) * (1.0 - (cc - dis_start)))
            pa = max(10, min(255, pa))
            pc = _lerp(ACCENT, ICE, rng.random())
            fd.ellipse([px - pr, py - pr, px + pr, py + pr], fill=pc + (pa,))

        # ---- Horizontal cyan motion streaks sweeping right ----
        streak_n = 9
        for i in range(streak_n):
            yy = pad + grid * ((i + 0.5) / streak_n) + (rng.random() - 0.5) * cell
            x_start = pad + grid * (dis_start - 0.04 + rng.random() * 0.14)
            length = grid * (0.18 + rng.random() * 0.48)
            thick = max(1.0, R * (0.004 + rng.random() * 0.005))
            a = int(255 * (0.20 + rng.random() * 0.55))
            col = _lerp(ACCENT, ICE, rng.random() * 0.6)
            # Soft leading edge via a short gradient of segments.
            seg = 12
            for k in range(seg):
                f0 = k / seg
                f1 = (k + 1) / seg
                xa = x_start + length * f0
                xb = x_start + length * f1
                ak = int(a * (1.0 - f1))
                fd.rectangle([xa, yy - thick / 2, xb, yy + thick / 2],
                             fill=col + (ak,))

    # ---- Compose: glow behind, crisp field in front ----
    base = Image.new("RGBA", (R, R), (0, 0, 0, 0))
    if glow:
        halo = field.filter(ImageFilter.GaussianBlur(R * 0.02))
        halo = _tint(halo, ACCENT, 0.35)
        # Restrain the halo so it reads as depth, not neon spill.
        ha = halo.split()[3].point(lambda v: int(v * 0.55))
        halo.putalpha(ha)
        base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, field)

    base = base.resize((s, s), Image.LANCZOS)
    _cache[key] = base
    return base.copy()

# ---------------------------------------------------------------------------
# Fonts + wordmark
# ---------------------------------------------------------------------------
_FONT_CANDIDATES = (
    ("segoeuib.ttf", "segoeui.ttf"),          # Segoe UI (ships with Windows)
    ("seguisb.ttf",),
    ("arialbd.ttf", "arial.ttf"),             # safe fallbacks
    ("calibrib.ttf", "calibri.ttf"),
    ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"),
)


def _load_font(px: int, bold: bool = True):
    """Resolve a bold UI font on Windows, falling back to PIL's default."""
    px = max(6, int(px))
    if bold:
        for names in _FONT_CANDIDATES:
            for name in names:
                try:
                    return ImageFont.truetype(name, px)
                except Exception:
                    continue
    try:                                        # non-bold request
        return ImageFont.truetype("segoeui.ttf", px)
    except Exception:
        pass
    try:                                        # last resort: default font scaled up
        return ImageFont.load_default(size=px)
    except Exception:
        return ImageFont.load_default()


def _shear(img: Image.Image, slant: float) -> Image.Image:
    """Apply a horizontal shear to fake an italic slant (top shifts right).

    ``slant`` ~0.2 gives a sporty italic lean without distorting glyph widths
    vertically. Uses a bicubic affine transform on an RGBA image.
    """
    w, h = img.size
    # x' = x + slant * (h - y)  => top of glyph moves right, bottom stays put.
    shift = slant * h
    matrix = (1.0, slant, -shift, 0.0, 1.0, 0.0)
    out_w = int(w + abs(shift)) + 2
    sheared = img.transform((out_w, h), Image.AFFINE, matrix,
                            resample=Image.BICUBIC)
    bbox = sheared.split()[3].getbbox()         # trim transparent margins
    if bbox:
        sheared = sheared.crop(bbox)
    return sheared


_WORD_STOPS = [
    (0.0, ACCENT_BRIGHT),
    (0.35, ACCENT),
    (0.7, GREEN_TOP),
    (1.0, (90, 235, 190)),
]


def render_wordmark(width: int = 520, text: str = "MOSAIQ",
                    glow: bool = True, slant: float = 0.22) -> Image.Image:
    """Render the bold, italic, gradient wordmark (RGBA).

    Text is drawn white on a transparent layer, sheared into an italic lean,
    then re-coloured with a left-to-right cyan -> spring-green gradient through
    the glyph alpha. A restrained cyan glow sits behind. Height scales with
    ``width``.
    """
    W = max(120, int(width))
    px = max(18, int(W * 0.20))                # base cap height driver
    font = _load_font(px, bold=True)

    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bbox = probe.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    canvas = Image.new("RGBA", (tw + px, th + px), (0, 0, 0, 0))
    cd = ImageDraw.Draw(canvas)
    cd.text((px // 2 - bbox[0], px // 2 - bbox[1]), text, font=font,
            fill=(255, 255, 255, 255))
    canvas = _shear(canvas, slant)

    cw, ch = canvas.size

    # Horizontal gradient ramp mapped through the glyph alpha.
    ramp = Image.new("RGBA", (cw, 1))
    rd = ImageDraw.Draw(ramp)
    for x in range(cw):
        f = x / max(1, cw - 1)
        col = _multistop(_WORD_STOPS, f)
        rd.point((x, 0), fill=col + (255,))
    ramp = ramp.resize((cw, ch))

    alpha = canvas.split()[3]
    gradient = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    gradient.paste(ramp, (0, 0), alpha)

    base = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    if glow:
        halo = gradient.filter(ImageFilter.GaussianBlur(max(2.0, ch * 0.06)))
        halo = _tint(halo, ACCENT, 0.4)
        ha = halo.split()[3].point(lambda v: int(v * 0.5))
        halo.putalpha(ha)
        base = Image.alpha_composite(base, halo)
    base = Image.alpha_composite(base, gradient)

    out_h = max(1, int(round(ch * (W / cw))))   # downscale, keep aspect
    base = base.resize((W, out_h), Image.LANCZOS)
    return base

def render_lockup(width: int = 640, glow: bool = True) -> Image.Image:
    """Symbol stacked above the gradient ``MOSAIQ`` wordmark (RGBA).

    Used to emit reusable brand assets (README / installer / docs); the app
    itself composes the symbol and wordmark at runtime.
    """
    W = max(240, int(width))
    sym = int(W * 0.86)
    sym_img = render_logo(sym, glow=glow)

    word = render_wordmark(int(W * 0.82), glow=glow)

    gap = int(sym * 0.10)
    H = sym_img.size[1] + gap + word.size[1] + int(sym * 0.06)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sx = (W - sym_img.size[0]) // 2
    img.alpha_composite(sym_img, (sx, 0))
    wx = (W - word.size[0]) // 2
    img.alpha_composite(word, (wx, sym_img.size[1] + gap))
    return img


# ---------------------------------------------------------------------------
# Framework adapters / asset export
# ---------------------------------------------------------------------------
def logo_ctk_image(size: int = 38):
    """Return a CTkImage of the mark (kept sharp on HiDPI)."""
    from customtkinter import CTkImage

    img = render_logo(int(size) * 2)
    return CTkImage(light_image=img, dark_image=img, size=(int(size), int(size)))


def save_logo_assets(sizes=(256, 128, 64, 48, 32, 24), directory: str = LOGO_DIR):
    """Write reusable PNG assets; returns the list of paths written."""
    os.makedirs(directory, exist_ok=True)
    paths = []
    for s in sizes:
        p = os.path.join(directory, f"qr-studio-logo-{s}.png")
        render_logo(s).save(p)
        paths.append(p)
    p = os.path.join(directory, "qr-studio-logo-flat-256.png")
    render_logo(256, glow=False).save(p)
    paths.append(p)
    p = os.path.join(directory, "qr-studio-wordmark-640.png")
    render_wordmark(640).save(p)
    paths.append(p)
    p = os.path.join(directory, "qr-studio-lockup-640.png")
    render_lockup(640).save(p)
    paths.append(p)
    return paths


def render_app_icon(size: int = 256) -> Image.Image:
    """The mark on a near-black rounded plate with a faint cyan rim.

    The bare mark's glow washes out on light backgrounds (light taskbar, the
    Daylight theme's title bar); the plate keeps it legible on both.
    """
    s = int(size)
    ss = 4
    R = s * ss
    plate = Image.new("RGBA", (R, R), (0, 0, 0, 0))
    rim = max(ss, int(round(R / 64)))
    ImageDraw.Draw(plate).rounded_rectangle(
        (0, 0, R - 1, R - 1), radius=int(R * 0.22),
        fill=(10, 14, 20, 255), outline=ACCENT + (90,), width=rim)
    plate = plate.resize((s, s), Image.LANCZOS)

    inner = max(1, int(round(s * 0.80)))
    mark = render_logo(inner)                  # renders at least 16 px
    if mark.width != inner:
        mark = mark.resize((inner, inner), Image.LANCZOS)
    off = (s - inner) // 2
    plate.alpha_composite(mark, (off, off))
    return plate


def save_app_icon(path: str = APP_ICON):
    """Write the Windows icon, rendering each size separately so small ones stay crisp.

    Frames are stored as BMP, not Pillow's default PNG: Tk cannot read the size
    of PNG frames, falls back to the first (16 px) one and Windows stretches it
    into a blurry title-bar / taskbar icon.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    images = [render_app_icon(s) for s in ICON_SIZES]
    images[-1].save(path, format="ICO", sizes=[(s, s) for s in ICON_SIZES],
                    append_images=images[:-1], bitmap_format="bmp")
    return path


def apply_window_icon(window):
    """Show the brand icon in ``window``'s title bar instead of CustomTkinter's.

    CustomTkinter swaps in its own icon 200 ms after a window is created unless
    iconbitmap() was called on it, so call this right after creating a window.
    """
    if os.path.exists(APP_ICON):
        try:
            window.iconbitmap(APP_ICON)
        except Exception:
            pass


if __name__ == "__main__":  # convenience: python -m ui.brand_logo
    for p in save_logo_assets():
        print("wrote", p)



