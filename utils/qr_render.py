"""QR rendering: module shapes, eye shapes, gradients and logo, from the QR matrix.

The look is described once as a list of drawing primitives (``layout``) in module units.
PNG is drawn from it here; the SVG export (utils/qr_export.py) writes the same primitives,
so both outputs match. No UI code.

Primitives (x, y in module units, the quiet zone included):
    ("rect", x, y, w, h, radius, (tl, tr, br, bl))   dark rounded rectangle, corner flags
    ("circle", cx, cy, r)                             dark dot
    ("eye", x, y)                                     a 7x7 finder pattern (see ``eye_geometry``)
"""
from dataclasses import dataclass, replace

import numpy as np
from PIL import Image, ImageDraw

from utils import colors

MODULE_SHAPES = ("square", "rounded", "dots")
EYE_SHAPES = ("square", "rounded")
GRADIENTS = ("none", "linear", "radial")

DEFAULT_LOGO_SCALE = 0.2          # logo side as a fraction of the code's width (quiet zone excluded)
MAX_LOGO_SCALE = 0.30
LOGO_PAD = 0.10                   # clear space around the logo, as a fraction of its size


@dataclass(frozen=True)
class QRStyle:
    module_shape: str = "square"
    eye_shape: str = "square"
    fg: str = "#000000"
    bg: str = "#FFFFFF"
    gradient: str = "none"
    fg2: str = "#000000"          # the second colour of a gradient
    logo_scale: float = DEFAULT_LOGO_SCALE

    def __post_init__(self):
        object.__setattr__(self, "fg", colors.parse_color(self.fg) or "#000000")
        object.__setattr__(self, "bg", colors.parse_color(self.bg) or "#FFFFFF")
        object.__setattr__(self, "fg2", colors.parse_color(self.fg2) or self.fg)
        if self.module_shape not in MODULE_SHAPES:
            object.__setattr__(self, "module_shape", "square")
        if self.eye_shape not in EYE_SHAPES:
            object.__setattr__(self, "eye_shape", "square")
        if self.gradient not in GRADIENTS:
            object.__setattr__(self, "gradient", "none")
        try:
            scale = float(self.logo_scale)
        except (TypeError, ValueError):
            scale = DEFAULT_LOGO_SCALE
        object.__setattr__(self, "logo_scale", min(MAX_LOGO_SCALE, max(0.05, scale)))

    @property
    def colours(self):
        """Every colour the dark parts can have (for contrast checks)."""
        return (self.fg, self.fg2) if self.gradient != "none" else (self.fg,)

    def to_dict(self):
        return {"module_shape": self.module_shape, "eye_shape": self.eye_shape,
                "fg": self.fg, "bg": self.bg, "gradient": self.gradient,
                "fg2": self.fg2, "logo_scale": self.logo_scale}

    @classmethod
    def from_dict(cls, data):
        """A style from saved data; anything missing or damaged falls back to the default."""
        if not isinstance(data, dict):
            return cls()
        allowed = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**allowed)

    def with_(self, **changes):
        return replace(self, **changes)


# --------------------------------------------------------------------------- layout

def eye_geometry(shape):
    """Radii (in modules) of the three layers of a finder pattern: outer 7x7, hole 5x5, centre 3x3.

    The rounding is deliberately moderate: with rounder eyes OpenCV's detector (and many
    phone cameras) stop finding the code (measured with utils/qr_scanner on versions 2-7).
    """
    if shape == "rounded":
        return {"outer": 1.0, "hole": 0.6, "centre": 0.5}
    return {"outer": 0.0, "hole": 0.0, "centre": 0.0}


def finder_origins(size, border):
    """Top-left corners (in modules, quiet zone included) of the three finder patterns."""
    far = border + size - 7
    return [(border, border), (far, border), (border, far)]


def _is_eye(x, y, origins):
    return any(ox <= x < ox + 7 and oy <= y < oy + 7 for ox, oy in origins)


def layout(matrix, border, style):
    """Drawing primitives for ``matrix`` (list of rows of bool, quiet zone NOT included)."""
    size = len(matrix)
    origins = finder_origins(size, border)

    def dark(x, y):                      # matrix coordinates; outside = light
        return 0 <= x < size and 0 <= y < size and bool(matrix[y][x])

    prims = []
    for y in range(size):
        for x in range(size):
            if not matrix[y][x] or _is_eye(x + border, y + border, origins):
                continue
            px, py = x + border, y + border
            if style.module_shape == "dots":
                prims.append(("circle", px + 0.5, py + 0.5, 0.46))
            elif style.module_shape == "rounded":
                up, down = dark(x, y - 1), dark(x, y + 1)
                left, right = dark(x - 1, y), dark(x + 1, y)
                corners = (not up and not left, not up and not right,
                           not down and not right, not down and not left)
                prims.append(("rect", px, py, 1, 1, 0.5, corners))
            else:
                prims.append(("rect", px, py, 1, 1, 0.0, (False,) * 4))
    prims.extend(("eye", ox, oy) for ox, oy in origins)
    return prims


# --------------------------------------------------------------------------- PNG

def _supersample(total_modules, box):
    return max(1, min(4, 4000 // max(1, total_modules * box)))


def _draw_mask(prims, style, total, box, ss):
    """The dark parts as an 'L' mask, drawn at ``ss`` times the final resolution."""
    unit = box * ss
    side = total * unit
    mask = Image.new("L", (side, side), 0)
    draw = ImageDraw.Draw(mask)
    eye = eye_geometry(style.eye_shape)

    def rr(x0, y0, x1, y1, radius, fill, corners=(True,) * 4):
        """Filled rectangle (module units) with the chosen corners rounded."""
        px0, py0, px1, py1 = x0 * unit, y0 * unit, x1 * unit - 1, y1 * unit - 1
        r = int(min(radius * unit, (px1 - px0) / 2, (py1 - py0) / 2))
        if r < 1 or not any(corners):
            draw.rectangle((px0, py0, px1, py1), fill=fill)
            return
        # Own corner drawing: Pillow's rounded_rectangle(corners=...) fails when the
        # radius reaches half the shape.
        draw.rectangle((px0 + r, py0, px1 - r, py1), fill=fill)
        draw.rectangle((px0, py0 + r, px1, py1 - r), fill=fill)
        tl, tr, br, bl = corners
        for rounded, region, circle, start in (
            (tl, (px0, py0, px0 + r, py0 + r), (px0, py0, px0 + 2 * r, py0 + 2 * r), 180),
            (tr, (px1 - r, py0, px1, py0 + r), (px1 - 2 * r, py0, px1, py0 + 2 * r), 270),
            (br, (px1 - r, py1 - r, px1, py1), (px1 - 2 * r, py1 - 2 * r, px1, py1), 0),
            (bl, (px0, py1 - r, px0 + r, py1), (px0, py1 - 2 * r, px0 + 2 * r, py1), 90),
        ):
            if rounded:
                draw.pieslice(circle, start, start + 90, fill=fill)
            else:
                draw.rectangle(region, fill=fill)

    for prim in prims:
        kind = prim[0]
        if kind == "rect":
            _, x, y, w, h, radius, corners = prim
            rr(x, y, x + w, y + h, radius, 255, corners)
        elif kind == "circle":
            _, cx, cy, r = prim
            draw.ellipse(((cx - r) * unit, (cy - r) * unit,
                          (cx + r) * unit - 1, (cy + r) * unit - 1), fill=255)
        elif kind == "eye":
            _, x, y = prim
            rr(x, y, x + 7, y + 7, eye["outer"], 255)
            rr(x + 1, y + 1, x + 6, y + 6, eye["hole"], 0)
            rr(x + 2, y + 2, x + 5, y + 5, eye["centre"], 255)
    return mask


def _paint(style, side):
    """The colour of the dark parts over the whole picture: solid, linear or radial."""
    if style.gradient == "none" or style.fg == style.fg2:
        return Image.new("RGB", (side, side), style.fg)
    a = np.array(colors.hex_to_rgb(style.fg), dtype=np.float32)
    b = np.array(colors.hex_to_rgb(style.fg2), dtype=np.float32)
    axis = np.linspace(0.0, 1.0, side, dtype=np.float32)
    if style.gradient == "linear":                       # top-left -> bottom-right
        t = (axis[None, :] + axis[:, None]) / 2.0
    else:                                                # centre -> corners
        d = np.sqrt((axis[None, :] - 0.5) ** 2 + (axis[:, None] - 0.5) ** 2) / np.sqrt(0.5)
        t = np.clip(d, 0.0, 1.0)
    pixels = a[None, None, :] + (b - a)[None, None, :] * t[:, :, None]
    return Image.fromarray(np.clip(pixels + 0.5, 0, 255).astype("uint8"))


def render(matrix, style, box_size=10, border=4, logo=None):
    """The QR as an RGBA PIL image. ``logo`` is an optional PIL image placed in the middle."""
    size = len(matrix)
    total = size + 2 * border
    ss = _supersample(total, box_size)
    prims = layout(matrix, border, style)
    mask = _draw_mask(prims, style, total, box_size, ss)
    side = total * box_size
    if ss > 1:
        mask = mask.resize((side, side), Image.Resampling.BOX)   # exact averaging of the ss x ss blocks

    image = Image.new("RGB", (side, side), style.bg)
    image.paste(_paint(style, side), (0, 0), mask)
    image = image.convert("RGBA")

    if logo is not None:
        image = place_logo(image, logo, style, size, box_size, border)
    return image


def logo_box(style, size, box_size, border):
    """(left, top, side) in pixels of the square the logo occupies."""
    code = size * box_size
    side = int(round(code * style.logo_scale))
    left = border * box_size + (code - side) // 2
    return left, left, side


def place_logo(image, logo, style, size, box_size, border):
    """Paste ``logo`` in the middle on a clear patch of the background colour."""
    left, top, side = logo_box(style, size, box_size, border)
    logo = logo.convert("RGBA")
    logo.thumbnail((side, side), Image.Resampling.LANCZOS)
    pad = max(2, int(round(side * LOGO_PAD)))
    cx, cy = left + side // 2, top + side // 2
    half_w, half_h = logo.width // 2 + pad, logo.height // 2 + pad
    patch = ImageDraw.Draw(image)
    patch.rounded_rectangle((cx - half_w, cy - half_h, cx + half_w, cy + half_h),
                            radius=max(2, pad), fill=style.bg)
    image.paste(logo, (cx - logo.width // 2, cy - logo.height // 2), logo)
    return image
