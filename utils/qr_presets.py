"""Ready-made colour + style combinations, one click each."""
from collections import namedtuple

from utils.qr_render import QRStyle

Preset = namedtuple("Preset", "name style")

# Every preset is dark on a light background with a clear contrast, and decodes with the
# plain scanner (checked by _design_features_test.py).
PRESETS = (
    Preset("Classic", QRStyle(fg="#000000", bg="#FFFFFF")),
    Preset("Ocean", QRStyle(module_shape="rounded", eye_shape="rounded", gradient="linear",
                            fg="#0E7490", fg2="#1E3A8A", bg="#FFFFFF")),
    Preset("Midnight", QRStyle(module_shape="dots", eye_shape="rounded", gradient="linear",
                               fg="#1E1B4B", fg2="#6D28D9", bg="#FFFFFF")),
    Preset("Sunset", QRStyle(module_shape="rounded", eye_shape="rounded", gradient="linear",
                             fg="#9A3412", fg2="#EA580C", bg="#FFFFFF")),
    Preset("Mint", QRStyle(module_shape="rounded", eye_shape="square", gradient="linear",
                           fg="#064E3B", fg2="#059669", bg="#FFFFFF")),
    Preset("Berry", QRStyle(module_shape="dots", eye_shape="rounded", gradient="radial",
                            fg="#9D174D", fg2="#DB2777", bg="#FFFFFF")),
    Preset("Forest", QRStyle(module_shape="square", eye_shape="rounded", gradient="linear",
                             fg="#14532D", fg2="#3F7D58", bg="#F7FBF5")),
    Preset("Mono", QRStyle(module_shape="rounded", eye_shape="square", gradient="linear",
                           fg="#111827", fg2="#4B5563", bg="#FFFFFF")),
)

_BY_NAME = {p.name: p for p in PRESETS}


def get(name):
    return _BY_NAME[name]


def matching(style):
    """The name of the preset whose look ``style`` has (logo size ignored), or None."""
    for preset in PRESETS:
        ps = preset.style
        if (ps.module_shape, ps.eye_shape, ps.fg, ps.bg) == (
                style.module_shape, style.eye_shape, style.fg, style.bg) and (
                (ps.gradient, ps.fg2) == (style.gradient, style.fg2)
                or (ps.gradient == "none" and style.gradient == "none")):
            return preset.name
    return None
