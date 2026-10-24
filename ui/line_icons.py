"""Consistent line icons (24-unit grid, round caps), drawn with Pillow.

Every icon is a few primitives on a 24x24 grid, rendered supersampled and tinted with any
colour, so the whole icon set shares one stroke weight and follows the theme. No icon
font and no image files are needed.

    image = line_icon("generate", "#22D3EE", size=20)   # a ctk.CTkImage

Primitives: ("rect", x, y, w, h, r)  ("circle", cx, cy, r)  ("line", (x, y), (x, y), ...)
            ("arc", cx, cy, r, start_deg, end_deg)  ("dot", x, y)
"""
import math

import customtkinter as ctk
from PIL import Image, ImageDraw

_SCALE = 16          # supersampling factor
_STROKE = 1.8        # stroke width in grid units

ICONS = {
    # sidebar / navigation
    "generate": [
        ("rect", 3, 3, 7, 7, 1.5), ("rect", 14, 3, 7, 7, 1.5), ("rect", 3, 14, 7, 7, 1.5),
        ("line", (14, 14), (17, 14), (17, 17), (14, 17), (14, 14)),
        ("line", (20.5, 14), (20.5, 14.2)), ("line", (14, 20.5), (14.2, 20.5)),
        ("line", (17, 20.5), (21, 20.5), (21, 17.5)),
    ],
    "scan": [
        ("line", (3, 7), (3, 5), (5, 3), (7, 3)), ("line", (17, 3), (19, 3), (21, 5), (21, 7)),
        ("line", (21, 17), (21, 19), (19, 21), (17, 21)), ("line", (7, 21), (5, 21), (3, 19), (3, 17)),
        ("line", (3, 12), (21, 12)),
    ],
    "history": [
        ("circle", 12, 12, 9), ("line", (12, 7), (12, 12), (15, 14)),
    ],
    "bulk": [
        ("rect", 3, 4, 18, 16, 2), ("line", (3.9, 10), (20.1, 10)), ("line", (9, 4.9), (9, 19.1)),
    ],
    # a cog: a ring, a hub and eight teeth
    "settings": [("circle", 12, 12, 6.2), ("circle", 12, 12, 2.4)] + [
        ("line", (12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a)), (12 + 9.4 * math.cos(a), 12 + 9.4 * math.sin(a)))
        for a in (i * math.pi / 4 for i in range(8))],
    # QR types
    "url": [
        ("line", (10, 14), (11, 14.8), (13, 15), (15, 14), (19, 10), (19.5, 7), (17, 4.5), (14, 5), (12, 7)),
        ("line", (14, 10), (13, 9.2), (11, 9), (9, 10), (5, 14), (4.5, 17), (7, 19.5), (10, 19), (12, 17)),
    ],
    "upi": [
        ("rect", 3, 6, 18, 12, 2), ("line", (3.9, 10), (20.1, 10)), ("line", (7, 14.5), (10, 14.5)),
    ],
    "wifi": [
        ("arc", 12, 17, 12, 225, 315), ("arc", 12, 17, 8, 225, 315), ("arc", 12, 17, 4, 225, 315),
        ("dot", 12, 19.5),
    ],
    "contact": [
        ("circle", 12, 8, 4), ("arc", 12, 21, 8, 180, 360),
    ],
    "email": [
        ("rect", 3, 5, 18, 14, 2), ("line", (4, 7.5), (12, 13), (20, 7.5)),
    ],
    "sms": [
        ("rect", 3, 4, 18, 13, 3), ("line", (8, 17.5), (8, 21), (12.5, 17.5)),
    ],
    # scan sources
    "image": [
        ("rect", 3, 4, 18, 16, 2), ("circle", 9, 10, 2), ("line", (20, 15.5), (15.5, 11), (8, 19)),
    ],
    "camera": [
        ("rect", 2, 6, 13, 12, 2), ("line", (15, 10), (20, 7), (20, 17), (15, 14)),
    ],
    "screen": [
        ("rect", 2, 4, 20, 13, 2), ("line", (8, 21), (16, 21)), ("line", (12, 17), (12, 21)),
    ],
    "paste": [
        ("rect", 8, 2, 8, 4, 1), ("line", (16, 4), (18, 4), (20, 6), (20, 20), (18, 22), (6, 22), (4, 20), (4, 6), (6, 4), (8, 4)),
    ],
    # style picker (shapes are filled)
    "shape_square": [("frect", 5, 5, 14, 14, 0)],
    "shape_rounded": [("frect", 5, 5, 14, 14, 5)],
    "shape_dots": [("fcircle", 7, 7, 3), ("fcircle", 17, 7, 3), ("fcircle", 7, 17, 3), ("fcircle", 17, 17, 3)],
    "eye_square": [("rect", 3, 3, 18, 18, 0), ("frect", 8, 8, 8, 8, 0)],
    "eye_rounded": [("rect", 3, 3, 18, 18, 6), ("frect", 8, 8, 8, 8, 3)],
    "upload": [
        ("line", (12, 16), (12, 4)), ("line", (7, 9), (12, 4), (17, 9)),
        ("line", (4, 16), (4, 19), (6, 21), (18, 21), (20, 19), (20, 16)),
    ],
}

_cache = {}


def _hex(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def render(name, color, size=20):
    """The icon as an RGBA PIL image of ``size`` px (a square), tinted ``color``."""
    key = (name, color.upper(), size)
    if key in _cache:
        return _cache[key]
    big = size * _SCALE
    unit = big / 24.0
    width = _STROKE * unit
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rgb = _hex(color) + (255,)

    def px(x, y):
        return (x * unit, y * unit)

    def line(points):
        pts = [px(*p) for p in points]
        draw.line(pts, fill=rgb, width=round(width), joint="curve")
        r = width / 2
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=rgb)

    for prim in ICONS[name]:
        kind = prim[0]
        if kind == "rect":
            _, x, y, w, h, r = prim
            draw.rounded_rectangle((x * unit, y * unit, (x + w) * unit, (y + h) * unit),
                                   radius=r * unit, outline=rgb, width=round(width))
        elif kind == "frect":
            _, x, y, w, h, r = prim
            draw.rounded_rectangle((x * unit, y * unit, (x + w) * unit, (y + h) * unit),
                                   radius=r * unit, fill=rgb)
        elif kind == "fcircle":
            _, cx, cy, r = prim
            draw.ellipse(((cx - r) * unit, (cy - r) * unit, (cx + r) * unit, (cy + r) * unit),
                         fill=rgb)
        elif kind == "circle":
            _, cx, cy, r = prim
            draw.ellipse(((cx - r) * unit, (cy - r) * unit, (cx + r) * unit, (cy + r) * unit),
                         outline=rgb, width=round(width))
        elif kind == "line":
            line(prim[1:])
        elif kind == "arc":
            _, cx, cy, r, a0, a1 = prim
            draw.arc(((cx - r) * unit, (cy - r) * unit, (cx + r) * unit, (cy + r) * unit),
                     a0, a1, fill=rgb, width=round(width))
        elif kind == "dot":
            _, x, y = prim
            r = width * 0.62
            cx, cy = px(x, y)
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgb)
    out = image.resize((size, size), Image.Resampling.LANCZOS)
    _cache[key] = out
    return out


def line_icon(name, color, size=20):
    """The icon as a CTkImage (crisp on high-DPI screens: rendered at 2x)."""
    return ctk.CTkImage(light_image=render(name, color, size * 2),
                        dark_image=render(name, color, size * 2), size=(size, size))
