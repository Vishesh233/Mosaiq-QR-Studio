"""Saving a QR as PNG, SVG or PDF (no new dependencies).

* PNG  the image as it is shown.
* SVG  vector, written from the same drawing primitives as the PNG (utils/qr_render.layout), so
       shapes, colours, gradient and logo match; the logo is embedded as a PNG data URI.
* PDF  a single page holding a high-resolution picture (Pillow's PDF writer): at least
       2000 px, so it prints sharply. It is not vector.

The QR's text is never written into the file as text (SVG has no <title>/<desc>).
"""
import base64
import io
import math

from PIL import Image

from utils import qr_render
from utils.qr_render import QRStyle

FORMATS = ("PNG", "SVG", "PDF")
EXTENSIONS = {"PNG": ".png", "SVG": ".svg", "PDF": ".pdf"}
FILE_TYPES = {
    "PNG": ("PNG Image", "*.png"),
    "SVG": ("SVG Vector Image", "*.svg"),
    "PDF": ("PDF Document", "*.pdf"),
}
MIN_PDF_PIXELS = 2000
PDF_DPI = 300


# ------------------------------------------------------------------------------ SVG

def _num(value):
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _rounded_rect_path(x, y, w, h, r, corners):
    """Path data of a rectangle with the chosen corners rounded (radius ``r``)."""
    tl, tr, br, bl = corners
    r = min(r, w / 2, h / 2)
    n = _num
    d = [f"M{n(x + (r if tl else 0))} {n(y)}"]
    d.append(f"H{n(x + w - (r if tr else 0))}")
    if tr:
        d.append(f"A{n(r)} {n(r)} 0 0 1 {n(x + w)} {n(y + r)}")
    d.append(f"V{n(y + h - (r if br else 0))}")
    if br:
        d.append(f"A{n(r)} {n(r)} 0 0 1 {n(x + w - r)} {n(y + h)}")
    d.append(f"H{n(x + (r if bl else 0))}")
    if bl:
        d.append(f"A{n(r)} {n(r)} 0 0 1 {n(x)} {n(y + h - r)}")
    d.append(f"V{n(y + (r if tl else 0))}")
    if tl:
        d.append(f"A{n(r)} {n(r)} 0 0 1 {n(x + r)} {n(y)}")
    d.append("Z")
    return "".join(d)


def _circle_path(cx, cy, r):
    n = _num
    return (f"M{n(cx - r)} {n(cy)}A{n(r)} {n(r)} 0 1 0 {n(cx + r)} {n(cy)}"
            f"A{n(r)} {n(r)} 0 1 0 {n(cx - r)} {n(cy)}Z")


def _fill_definition(style, total):
    """(<defs> markup, fill value) for the dark parts."""
    if style.gradient == "none" or style.fg == style.fg2:
        return "", style.fg
    stops = (f'<stop offset="0" stop-color="{style.fg}"/>'
             f'<stop offset="1" stop-color="{style.fg2}"/>')
    if style.gradient == "linear":
        gradient = (f'<linearGradient id="fill" gradientUnits="userSpaceOnUse" '
                    f'x1="0" y1="0" x2="{total}" y2="{total}">{stops}</linearGradient>')
    else:
        gradient = (f'<radialGradient id="fill" gradientUnits="userSpaceOnUse" '
                    f'cx="{_num(total / 2)}" cy="{_num(total / 2)}" '
                    f'r="{_num(total * math.sqrt(0.5))}">{stops}</radialGradient>')
    return f"<defs>{gradient}</defs>", "url(#fill)"


def build_svg(matrix, style, box_size=10, border=4, logo=None):
    """The QR as SVG text. ``logo`` is an optional PIL image placed in the middle."""
    total = len(matrix) + 2 * border
    px = total * box_size
    eye = qr_render.eye_geometry(style.eye_shape)
    defs, fill = _fill_definition(style, total)

    modules, eyes = [], []
    for prim in qr_render.layout(matrix, border, style):
        kind = prim[0]
        if kind == "rect":
            _, x, y, w, h, r, corners = prim
            modules.append(_rounded_rect_path(x, y, w, h, r, corners) if r > 0
                           else f"M{_num(x)} {_num(y)}h{_num(w)}v{_num(h)}h-{_num(w)}z")
        elif kind == "circle":
            _, cx, cy, r = prim
            modules.append(_circle_path(cx, cy, r))
        elif kind == "eye":
            _, x, y = prim
            on = (True,) * 4
            # even-odd: the 7x7 ring minus the 5x5 hole, plus the 3x3 centre
            eyes.append(_rounded_rect_path(x, y, 7, 7, eye["outer"], on if eye["outer"] else (False,) * 4)
                        + _rounded_rect_path(x + 1, y + 1, 5, 5, eye["hole"], on if eye["hole"] else (False,) * 4)
                        + _rounded_rect_path(x + 2, y + 2, 3, 3, eye["centre"], on if eye["centre"] else (False,) * 4))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{px}" height="{px}" viewBox="0 0 {total} {total}" '
        f'shape-rendering="geometricPrecision">',
        defs,
        f'<rect width="{total}" height="{total}" fill="{style.bg}"/>',
        f'<path fill="{fill}" d="{"".join(modules)}"/>',
        f'<path fill="{fill}" fill-rule="evenodd" d="{"".join(eyes)}"/>',
    ]
    if logo is not None:
        parts.append(_logo_markup(logo, style, len(matrix), box_size, border))
    parts.append("</svg>")
    return "\n".join(p for p in parts if p) + "\n"


def _logo_markup(logo, style, size, box_size, border):
    """The clear patch and the logo, positioned exactly as in the PNG."""
    left, top, side = qr_render.logo_box(style, size, box_size, border)
    original = logo.convert("RGBA")
    shown = original.copy()
    shown.thumbnail((side, side), Image.Resampling.LANCZOS)    # the size the PNG draws it at
    pad = max(2, int(round(side * qr_render.LOGO_PAD)))
    cx, cy = left + side // 2, top + side // 2
    half_w, half_h = shown.width // 2 + pad, shown.height // 2 + pad
    u = box_size
    patch = (f'<rect x="{_num((cx - half_w) / u)}" y="{_num((cy - half_h) / u)}" '
             f'width="{_num(2 * half_w / u)}" height="{_num(2 * half_h / u)}" '
             f'rx="{_num(max(2, pad) / u)}" fill="{style.bg}"/>')

    # Embed the logo at up to four times the size shown: sharp when zoomed, but not huge.
    embedded = original.copy()
    embedded.thumbnail((side * 4, side * 4), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    embedded.save(buffer, "PNG", optimize=True)
    data = base64.b64encode(buffer.getvalue()).decode("ascii")
    image = (f'<image x="{_num((cx - shown.width // 2) / u)}" y="{_num((cy - shown.height // 2) / u)}" '
             f'width="{_num(shown.width / u)}" height="{_num(shown.height / u)}" '
             f'preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,{data}"/>')
    return patch + "\n" + image


# ------------------------------------------------------------------------------ files

def export(path, fmt, generator, data, style: QRStyle, logo_path=None):
    """Write the QR for ``data`` to ``path`` in format ``fmt`` ("PNG", "SVG" or "PDF")."""
    fmt = fmt.upper()
    if fmt not in FORMATS:
        raise ValueError(f"Unknown export format: {fmt}")

    if fmt == "PNG":
        generator.generate(data, style=style, logo_path=logo_path).save(path, "PNG")
        return

    matrix, version = generator.matrix(data)
    safe = qr_render.max_logo_scale(version)
    if style.logo_scale > safe:
        style = style.with_(logo_scale=safe)
    logo = Image.open(logo_path) if logo_path else None
    try:
        if fmt == "SVG":
            svg = build_svg(matrix, style, generator.box_size, generator.border, logo)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(svg)
        else:
            total = len(matrix) + 2 * generator.border
            box = max(generator.box_size, math.ceil(MIN_PDF_PIXELS / total))
            image = qr_render.render(matrix, style, box_size=box, border=generator.border, logo=logo)
            image.convert("RGB").save(path, "PDF", resolution=PDF_DPI)
    finally:
        if logo is not None:
            logo.close()


def pdf_pixels(generator, data):
    """Width in pixels of the picture a PDF export of ``data`` contains."""
    matrix, _version = generator.matrix(data)
    total = len(matrix) + 2 * generator.border
    return total * max(generator.box_size, math.ceil(MIN_PDF_PIXELS / total))
