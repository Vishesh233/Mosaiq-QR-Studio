"""Colour maths and the colour lists used by the picker (no UI code)."""
import colorsys
import re

from utils import settings_store

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Presets shown in the picker: neutrals first, then a spread of hues.
PRESET_COLORS = (
    "#000000", "#1F2937", "#4B5563", "#9CA3AF", "#E5E7EB", "#FFFFFF",
    "#7F1D1D", "#DC2626", "#EA580C", "#F59E0B", "#CA8A04", "#65A30D",
    "#15803D", "#0D9488", "#0E7490", "#0369A1", "#1D4ED8", "#4338CA",
    "#7C3AED", "#A21CAF", "#DB2777", "#BE123C", "#78350F", "#0F172A",
)

RECENT_KEY = "recent_colors"
MAX_RECENT = 10


def parse_color(text):
    """'#RRGGBB' (upper case) for '#abc', 'abc', '#aabbcc' or 'AABBCC'; None if it is not a colour."""
    match = _HEX.match((text or "").strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return "#" + digits.upper()


def hex_to_rgb(color):
    color = parse_color(color)
    if color is None:
        raise ValueError(f"not a colour: {color!r}")
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def rgb_to_hex(r, g, b):
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def rgb_to_hsv(r, g, b):
    """(h 0..1, s 0..1, v 0..1)."""
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)


def hsv_to_rgb(h, s, v):
    """(r, g, b) as 0..255 ints."""
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return tuple(int(round(c * 255)) for c in (r, g, b))


def relative_luminance(color):
    """WCAG relative luminance (0 black .. 1 white)."""
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(color)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a, b):
    """WCAG contrast ratio between two colours, 1 (identical) .. 21 (black on white)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------- recent colours

def load_recent():
    """The recently used colours, newest first. Anything malformed in the file is ignored."""
    stored = settings_store.get(RECENT_KEY, [])
    if not isinstance(stored, list):
        return []
    colours = []
    for item in stored:
        parsed = parse_color(item) if isinstance(item, str) else None
        if parsed and parsed not in colours:
            colours.append(parsed)
    return colours[:MAX_RECENT]


def remember(color):
    """Put ``color`` first in the recent list (no duplicates, at most MAX_RECENT)."""
    parsed = parse_color(color)
    if parsed is None:
        return
    colours = [parsed] + [c for c in load_recent() if c != parsed]
    settings_store.set(RECENT_KEY, colours[:MAX_RECENT])


def blend(a, b, t):
    """The colour ``t`` (0..1) of the way from ``a`` to ``b``, as "#RRGGBB"."""
    ra, ga, ba = hex_to_rgb(a)
    rb, gb, bb = hex_to_rgb(b)
    return rgb_to_hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)
