"""Quick, advisory checks of a QR style (no UI, never blocks generating)."""
from collections import namedtuple

from utils import colors

MIN_CONTRAST = 3.0

LOW_CONTRAST_TEXT = "These colours may not scan. Try more contrast."
INVERTED_TEXT = "Light codes on a dark background do not scan in every app."
GOOD_TEXT = "Good contrast — this will scan well"

# level: "good" (green) or "warn" (amber)
Check = namedtuple("Check", "level text worst_ratio")


def dark_samples(style):
    """The colours the dark parts of the code take: the gradient's ends and points between."""
    if style.gradient == "none" or style.fg == style.fg2:
        return [style.fg]
    return [colors.blend(style.fg, style.fg2, t) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]


def check_style(style):
    """Advice for ``style``: too little contrast (any part of a gradient included), a light
    code on a dark background, or all good."""
    samples = dark_samples(style)
    worst = min(colors.contrast_ratio(color, style.bg) for color in samples)
    if worst < MIN_CONTRAST:
        return Check("warn", LOW_CONTRAST_TEXT, worst)
    bg_light = colors.relative_luminance(style.bg)
    if all(colors.relative_luminance(color) > bg_light for color in samples):
        return Check("warn", INVERTED_TEXT, worst)
    return Check("good", GOOD_TEXT, worst)
