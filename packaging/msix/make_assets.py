"""Write the MSIX image assets (Store logo, tiles, Start / taskbar icons).

Usage:  python packaging/msix/make_assets.py <output Assets folder>

Everything is rendered from ui/brand_logo.py. Windows picks the scale- and
targetsize- variants through the resources.pri that build_msix.ps1 generates.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from ui.brand_logo import render_app_icon  # noqa: E402

SCALES = (100, 125, 150, 200, 400)
# Sizes Windows asks for in the taskbar, Start, Alt+Tab and title bars.
TARGET_SIZES = (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256)


def tile(width, height, icon_size):
    """The icon centred on a transparent tile."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = render_app_icon(icon_size)
    canvas.alpha_composite(icon, ((width - icon_size) // 2, (height - icon_size) // 2))
    return canvas


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    count = 0

    def save(img, name):
        nonlocal count
        img.save(os.path.join(out_dir, name))
        count += 1

    for scale in SCALES:
        f = scale / 100
        save(render_app_icon(round(50 * f)), "StoreLogo.scale-%d.png" % scale)
        save(render_app_icon(round(44 * f)), "Square44x44Logo.scale-%d.png" % scale)
        side = round(150 * f)
        save(tile(side, side, round(side * 0.66)), "Square150x150Logo.scale-%d.png" % scale)
        save(tile(round(310 * f), side, round(side * 0.66)), "Wide310x150Logo.scale-%d.png" % scale)

    # The icon brings its own plate, so the unplated (taskbar) variants for
    # dark and light themes are the same image.
    for size in TARGET_SIZES:
        icon = render_app_icon(size)
        for suffix in ("", "_altform-unplated", "_altform-lightunplated"):
            save(icon, "Square44x44Logo.targetsize-%d%s.png" % (size, suffix))

    print("wrote %d assets to %s" % (count, out_dir))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
