"""A lit dot: a crisp core and a soft radial glow, drawn with Pillow (no outline, no ring).

Both status dots (the card title dot and the sidebar's theme dot) use ``render``. The image already holds
the surface colour behind the dot, so it sits on any Canvas of that colour without transparency tricks.
The glow falls off smoothly (a Gaussian) from the core outwards: there is no edge to see anywhere, and the
core's own edge is anti-aliased (drawn at 4x and scaled down).
"""
import functools
import math

from PIL import Image, ImageTk

from utils import colors

SUPERSAMPLE = 4


@functools.lru_cache(maxsize=512)
def render(side, surface, colour, core, glow_radius, strength, hot=0.0):
    """The dot as an RGB PIL image of ``side`` x ``side`` px.

    ``core`` is the radius of the bright dot and ``glow_radius`` the spread of the glow (both in px),
    ``strength`` (0..1) how much of ``colour`` the glow shows right at the core, ``hot`` (0..1) how
    much the very middle of the core goes towards white (a lit lamp is brightest in its centre).
    """
    big = side * SUPERSAMPLE
    # 0 in the middle, 255 in the corners: the distance to a corner is big / 2 * sqrt(2)
    gradient = Image.radial_gradient("L").resize((big, big), Image.Resampling.BILINEAR)

    def radius_px(value):
        return value / 255.0 * (big / 2.0) * math.sqrt(2) / SUPERSAMPLE

    core_mask = gradient.point([255 if radius_px(v) <= core else 0 for v in range(256)])
    # The falloff is lowered so that it reaches exactly zero at the edge of the image: no square shows.
    floor = math.exp(-((side / 2.0) / glow_radius) ** 2)
    glow_mask = gradient.point([int(255 * min(1.0, strength * max(0.0, math.exp(-(radius_px(v) / glow_radius) ** 2) - floor)
                                              / (1.0 - floor))) for v in range(256)])
    hot_mask = gradient.point([int(255 * hot * max(0.0, 1.0 - radius_px(v) / core) ** 1.6) if radius_px(v) <= core else 0
                               for v in range(256)])

    base = Image.new("RGB", (big, big), surface)
    lit = Image.composite(Image.new("RGB", (big, big), colour), base, glow_mask)            # surface -> colour, smoothly
    middle = Image.composite(Image.new("RGB", (big, big), "#FFFFFF"), Image.new("RGB", (big, big), colour), hot_mask)
    image = Image.composite(middle, lit, core_mask)
    return image.resize((side, side), Image.Resampling.BOX)           # BOX: no overshoot, so no halo line at the core edge


def photo(side, surface, colour, core, glow_radius, strength, hot=0.0):
    """``render`` as a Tk image (the caller keeps a reference)."""
    return ImageTk.PhotoImage(render(side, surface.upper(), colour.upper(), round(core, 2), round(glow_radius, 2),
                                     round(strength, 3), round(hot, 3)))


def glow_at(distance, glow_radius, strength):
    """How much of the colour the glow shows ``distance`` px from the middle (what ``render`` draws)."""
    return min(1.0, strength * math.exp(-(distance / glow_radius) ** 2))


def edge_colour(surface, colour, core, glow_radius, strength):
    """The colour right at the edge of the core, where the glow is strongest."""
    return colors.blend(surface, colour, glow_at(core, glow_radius, strength))
