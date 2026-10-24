import math
import tkinter

import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui.line_icons import line_icon


class ModernCard(ctk.CTkFrame):

    def __init__(self, parent, width=None, height=None):

        theme = ThemeManager.get_theme()

        kwargs = {
            "fg_color": theme["card"],
            "corner_radius": 16,
            "border_width": 1,
            "border_color": theme["border"]
        }

        if width is not None:
            kwargs["width"] = width

        if height is not None:
            kwargs["height"] = height

        super().__init__(parent, **kwargs)

        self.pack_propagate(False)

    # ================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )


# ====================================================


class ModernEntry(ctk.CTkEntry):

    def __init__(self, parent, placeholder=""):

        self.placeholder = placeholder

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            height=42,
            corner_radius=12,
            border_width=1,
            border_color=theme["entry_border"],
            fg_color=theme["entry"],
            text_color=theme["text"],
            placeholder_text=placeholder,
            placeholder_text_color=theme["text_muted"],
            font=("Segoe UI", 14)
        )

    # ================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["entry"],
            border_color=theme["entry_border"],
            text_color=theme["text"],
            placeholder_text_color=theme["text_muted"]
        )


# ====================================================


class ModernSegmented(ctk.CTkSegmentedButton):
    """Segmented button that follows the theme tokens.

    CustomTkinter gives every segment one text colour; here the selected segment
    uses ``on_primary`` (readable on the primary fill in every theme) and the
    others use ``text``.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.apply_theme()

    def set(self, value, *args, **kwargs):
        super().set(value, *args, **kwargs)
        self._colour_segments()

    def apply_theme(self):
        theme = ThemeManager.get_theme()
        self.configure(
            bg_color=theme["card"],
            fg_color=theme["segment_bg"],
            selected_color=theme["primary"],
            selected_hover_color=theme["primary_hover"],
            unselected_color=theme["segment_bg"],
            unselected_hover_color=theme["segment_hover"],
            text_color=theme["text"],
            text_color_disabled=theme["text_muted"],
            font=("Segoe UI", 12),
            corner_radius=10,
        )
        self._colour_segments()

    def _colour_segments(self):
        theme = ThemeManager.get_theme()
        selected = self.get()
        for value, button in self._buttons_dict.items():
            button.configure(
                # the segments' own background is what shows at their rounded corners: it must be the strip's colour
                # (CustomTkinter leaves its grey default there until something re-themes the control)
                bg_color=theme["segment_bg"],
                text_color=theme["on_primary"] if value == selected else theme["text"]
            )


# ====================================================


class IconTile(ctk.CTkFrame):
    """An icon over a caption. A selectable type tile, or a plain button.

    ``configure(command=...)``, ``invoke()`` and ``set_selected()`` mirror a button.
    """

    def __init__(self, parent, icon_name, text, command=None, height=64, icon_size=20):
        theme = ThemeManager.get_theme()
        super().__init__(
            parent, height=height, corner_radius=11, border_width=1,
            fg_color=theme["segment_bg"], border_color=theme["border"],
        )
        self._command = command
        self._icon_name = icon_name
        self._icon_size = icon_size
        self._selected = False
        self._hover = False
        self.pack_propagate(False)

        self._icon = ctk.CTkLabel(self, text="", fg_color="transparent",
                                  text_color=theme["text"])
        self._icon.pack(pady=(10, 2))
        self._text = ctk.CTkLabel(self, text=text, font=("Segoe UI", 12),
                                  fg_color="transparent")
        self._text.pack()

        for widget in (self, self._icon, self._text):
            widget.bind("<Button-1>", self._clicked)
            widget.bind("<Enter>", lambda _e: self._set_hover(True))
            widget.bind("<Leave>", lambda _e: self.after(20, self._check_hover))
        try:
            self.configure(cursor="hand2")
        except Exception:
            pass
        self._paint()

    # ---- button-like API ----
    def configure(self, require_redraw=False, **kwargs):
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if kwargs or require_redraw:
            super().configure(require_redraw=require_redraw, **kwargs)

    def cget(self, attribute_name):
        if attribute_name == "command":
            return self._command
        return super().cget(attribute_name)

    def invoke(self):
        if self._command:
            self._command()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._paint()

    def set_text(self, text):
        self._text.configure(text=text)

    # ---- internals ----
    def _clicked(self, _event=None):
        self.invoke()

    def _set_hover(self, hover):
        if hover != self._hover:
            self._hover = hover
            self._paint()

    def _check_hover(self):
        try:
            x, y = self.winfo_pointerxy()
            inside = str(self.winfo_containing(x, y) or "").startswith(str(self))
        except Exception:
            inside = False
        self._set_hover(inside)

    def _paint(self):
        theme = ThemeManager.get_theme()
        if self._selected:
            fg, border = theme["segment_hover"], theme["primary"]
            text_color, icon_color = theme["text"], theme["primary"]
        else:
            fg = theme["card_hover"] if self._hover else theme["segment_bg"]
            border = theme["border"]
            text_color = theme["text"] if self._hover else theme["text_secondary"]
            icon_color = text_color
        super().configure(fg_color=fg, border_color=border)
        self._text.configure(text_color=text_color)
        self._icon.configure(image=line_icon(self._icon_name, icon_color, self._icon_size))

    def apply_theme(self):
        self._paint()


class IconTileRow(ctk.CTkFrame):
    """A row of equal IconTiles where exactly one is selected (like a segmented control)."""

    def __init__(self, parent, items, command=None, height=68):
        super().__init__(parent, fg_color="transparent")
        self._command = command
        self._value = None
        self.tiles = {}
        for column, (value, icon_name, caption) in enumerate(items):
            self.grid_columnconfigure(column, weight=1, uniform="tiles")
            tile = IconTile(self, icon_name, caption, height=height,
                            command=lambda v=value: self._picked(v))
            tile.grid(row=0, column=column, sticky="ew",
                      padx=(0 if column == 0 else 4, 0 if column == len(items) - 1 else 4))
            self.tiles[value] = tile

    def _picked(self, value):
        self.set(value)
        if self._command:
            self._command(value)

    def set(self, value):
        self._value = value
        for key, tile in self.tiles.items():
            tile.set_selected(key == value)

    def get(self):
        return self._value

    def apply_theme(self):
        for tile in self.tiles.values():
            tile.apply_theme()


# ====================================================


def mix_colors(a, b, k):
    """Blend hex colour ``a`` towards ``b`` by ``k`` (0..1)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    parts = [int(a[i:i + 2], 16) + (int(b[i:i + 2], 16) - int(a[i:i + 2], 16)) * k
             for i in (0, 2, 4)]
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(p))) for p in parts)


class DashedZone(ctk.CTkFrame):
    """A rounded, dashed outline around its content (CustomTkinter has no dashed border).

    Put content into ``self.inner``; ``set_solid(True)`` turns the dashes into a solid line
    (e.g. once a file has been chosen).
    """

    RADIUS = 14

    def __init__(self, parent, height=300):
        theme = ThemeManager.get_theme()
        super().__init__(parent, fg_color="transparent", height=height)
        self.pack_propagate(False)
        self._solid = False

        # tkinter.Canvas is not themed by retheme_tree, so apply_theme() paints it.
        self.canvas = tkinter.Canvas(self, highlightthickness=0, bd=0, bg=theme["card"])
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.canvas.bind("<Configure>", self._redraw)

        self.inner = ctk.CTkFrame(self, fg_color="transparent")
        self.inner.place(relx=0.5, rely=0.5, anchor="center")

    def set_solid(self, solid):
        self._solid = bool(solid)
        self._redraw()

    def apply_theme(self):
        self.canvas.configure(bg=ThemeManager.get_theme()["card"])
        self._redraw()

    def _redraw(self, _event=None):
        theme = ThemeManager.get_theme()
        canvas = self.canvas
        canvas.delete("outline")
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 20 or h < 20:
            return
        pad, r = 2, self.RADIUS
        x0, y0, x1, y1 = pad, pad, w - pad, h - pad
        points = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
                  x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0, x0 + r, y0]
        color = theme["primary"] if self._solid else mix_colors(
            theme["primary"], theme["card"], 0.45)
        canvas.create_line(*points, smooth=True, width=1.5, fill=color,
                           dash=() if self._solid else (6, 5), tags="outline")

    def bind_click(self, callback):
        """Make the whole zone (and everything inside it) clickable."""
        for widget in (self, self.canvas, self.inner):
            widget.bind("<Button-1>", lambda _e: callback())
        try:
            self.canvas.configure(cursor="hand2")
        except Exception:
            pass


class StatusDot(tkinter.Canvas):
    """The dot in front of a card title: a small lit lamp. Idle (the card is empty) it is a dull core with
    a faint halo; once the card holds a result it is bright, with a strong soft glow around it. The change
    fades over about 180 ms. There is no outline or ring anywhere: the glow is a smooth radial falloff
    (see ui.glow).

    ``set_active(True/False)``; ``active`` tells the current state. A change redraws one small cached image.
    """

    SIZE = 28                       # logical px
    CORE = 4.2                      # radius of the dot
    GLOW_IDLE = (4.6, 0.14)         # (spread in px, strength) while dim
    GLOW_LIT = (7.4, 0.95)          # ... and when bright
    HOT = 0.40                      # how far the middle of the lit core goes towards white
    STEPS = 6
    STEP_MS = 30

    def __init__(self, parent):
        theme = ThemeManager.get_theme()
        self._scale = self._scaling_of(parent)
        side = round(self.SIZE * self._scale)
        super().__init__(parent, width=side, height=side, bg=theme["card"],
                         highlightthickness=0, bd=0)
        self.active = False
        self._level = 0.0            # 0 = dim, 1 = bright (moves during the fade)
        self._job = None
        self._photo = None
        self._draw()

    @staticmethod
    def _scaling_of(widget):
        top = widget.winfo_toplevel()
        return top._get_window_scaling() if hasattr(top, "_get_window_scaling") else 1.0

    # ------------------------------------------------------------------ colours

    @staticmethod
    def colours(theme):
        """(dim, bright, surface) for a theme dictionary."""
        return theme["text_muted"], theme["success"], theme["card"]

    def current_look(self):
        """(core colour, glow spread px, glow strength, hot) for the level being shown."""
        from utils import colors
        dim, bright, _surface = self.colours(ThemeManager.get_theme())
        level = self._level
        spread = self.GLOW_IDLE[0] + (self.GLOW_LIT[0] - self.GLOW_IDLE[0]) * level
        strength = self.GLOW_IDLE[1] + (self.GLOW_LIT[1] - self.GLOW_IDLE[1]) * level
        hot = self.HOT * level if ThemeManager.get_mode() == "Dark" else 0.0     # a white-hot middle only shows on a dark card
        return colors.blend(dim, bright, level), spread, strength, hot

    # ------------------------------------------------------------------ drawing

    def _draw(self):
        from ui import glow
        colour, spread, strength, hot = self.current_look()
        surface = self.colours(ThemeManager.get_theme())[2]
        scale = self._scale
        side = round(self.SIZE * scale)
        self._photo = glow.photo(side, surface, colour, self.CORE * scale, spread * scale, strength, hot)
        self.delete("all")
        self.create_image(side / 2, side / 2, image=self._photo)

    def set_active(self, active):
        """Bright with glow (a result is showing) or dim (empty, cleared, invalid)."""
        active = bool(active)
        if active == self.active and self._job is None:
            return
        self.active = active
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if not self.winfo_ismapped():            # nothing to watch: no animation needed
            self._level = 1.0 if active else 0.0
            self._draw()
            return
        self._fade()

    def _fade(self):
        target = 1.0 if self.active else 0.0
        step = 1.0 / self.STEPS
        if abs(self._level - target) <= step / 2:
            self._level = target
            self._job = None
        else:
            self._level += step if target > self._level else -step
            self._job = self.after(self.STEP_MS, self._fade)
        self._draw()

    def refresh_theme(self):
        """Follow a theme change (a Canvas is not recoloured by the generic theme pass)."""
        self._scale = self._scaling_of(self)
        side = round(self.SIZE * self._scale)
        self.configure(width=side, height=side, bg=ThemeManager.get_theme()["card"])
        self._draw()


class ThemeDot(tkinter.Canvas):
    """The dot in front of the theme name in the sidebar footer: a lit lamp in the theme's accent colour
    with a strong soft glow and no outline. When the theme changes it blends from the old colour to the new
    one while the glow swells and settles again (about 350 ms)."""

    SIZE = 32                # logical px
    CORE = 4.6
    GLOW = (7.0, 0.9)        # (spread in px, strength) at rest
    SWELL = (4.0, 0.1)       # how much more the glow spreads / strengthens at the height of a change
    HOT = 0.40
    STEPS = 10
    STEP_MS = 35

    def __init__(self, parent):
        theme = ThemeManager.get_theme()
        self._scale = StatusDot._scaling_of(parent)
        side = round(self.SIZE * self._scale)
        super().__init__(parent, width=side, height=side, bg=theme["navbar"],
                         highlightthickness=0, bd=0)
        self._from = theme["primary"]
        self._to = theme["primary"]
        self._t = 1.0
        self._job = None
        self._photo = None
        self._draw()

    def current_look(self):
        """(core colour, glow spread px, glow strength, hot) as drawn now."""
        from utils import colors
        swell = math.sin(math.pi * self._t) if self._t < 1.0 else 0.0
        return (colors.blend(self._from, self._to, self._t), self.GLOW[0] + self.SWELL[0] * swell,
                min(1.0, self.GLOW[1] + self.SWELL[1] * swell), self.HOT if ThemeManager.get_mode() == "Dark" else 0.0)

    def _draw(self):
        from ui import glow
        colour, spread, strength, hot = self.current_look()
        scale = self._scale
        side = round(self.SIZE * scale)
        self._photo = glow.photo(side, ThemeManager.get_theme()["navbar"], colour, self.CORE * scale,
                                 spread * scale, strength, hot)
        self.delete("all")
        self.create_image(side / 2, side / 2, image=self._photo)

    def refresh_theme(self):
        """Show the active theme's colours, animated when the dot is on screen."""
        from utils import colors
        theme = ThemeManager.get_theme()
        self._scale = StatusDot._scaling_of(self)
        side = round(self.SIZE * self._scale)
        self.configure(width=side, height=side, bg=theme["navbar"])
        shown = colors.blend(self._from, self._to, self._t)
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        self._from, self._to = shown, theme["primary"]
        if shown.upper() == theme["primary"].upper() or not self.winfo_ismapped():
            self._from, self._t = self._to, 1.0
            self._draw()
            return
        self._t = 0.0
        self._step()

    def _step(self):
        self._t = min(1.0, self._t + 1.0 / self.STEPS)
        self._draw()
        if self._t < 1.0:
            self._job = self.after(self.STEP_MS, self._step)
        else:
            self._job = None
            self._from = self._to
