"""Render the splash as a project thumbnail / social preview (dev-only).

Uses the real splash renderer. Each still is laid out at a compact CSS size
(so the QR and wordmark fill the frame), rendered supersampled and
downscaled to the output size for clean edges.
A thumbnail shows the assembled QR and the full-brightness wordmark together,
which the animation itself never does (the title dims while the QR is on
screen), so the title opacity is held at 1 for these stills.

Run:  .venv\\Scripts\\python.exe ui\\_splash_thumbnail.py
Writes PNGs into assets/thumbnail/.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import ui.splash as sp  # noqa: E402

OUT_DIR = os.path.join(ROOT, "assets", "thumbnail")

# t = 3.3 s: QR assembled, scan bar crossing it.
# (file name, layout w, layout h, supersample, output w, output h, palette, t ms)
SHOTS = (
    ("qr-studio-splash-1920x1080.png", 1280, 720, 3, 1920, 1080, "Aqua Mint", 3300),
    ("qr-studio-splash-1920x1080-ultraviolet.png", 1280, 720, 3, 1920, 1080, "Ultraviolet", 3300),
    ("qr-studio-splash-1920x1080-ember.png", 1280, 720, 3, 1920, 1080, "Ember", 3300),
    # GitHub's recommended social preview size (2:1).
    ("qr-studio-social-1280x640.png", 1280, 640, 2, 1280, 640, "Aqua Mint", 3300),
)


def render_still(w, h, palette, t_ms, ss=2, size=None):
    """One frame laid out at (w, h) CSS px, rendered at ``ss``x, resized to ``size``."""
    scene = sp.Scene(w, h, ss=ss, palette=palette)
    out = np.empty((scene.ph, scene.pw, 3), np.float32)
    u8 = np.empty((scene.ph, scene.pw, 3), np.uint8)
    title_alpha = sp.title_alpha
    sp.title_alpha = lambda _t: 1.0          # wordmark at full brightness
    try:
        sp.render_frame_into(scene, out, u8, t_ms, t_ms)
    finally:
        sp.title_alpha = title_alpha
    img = Image.fromarray(u8, "RGB")
    size = size or (w, h)
    return img.resize(size, Image.LANCZOS) if img.size != size else img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, w, h, ss, ow, oh, palette, t in SHOTS:
        path = os.path.join(OUT_DIR, name)
        render_still(w, h, palette, t, ss=ss, size=(ow, oh)).save(path, optimize=True)
        print("wrote", path)


if __name__ == "__main__":
    main()
