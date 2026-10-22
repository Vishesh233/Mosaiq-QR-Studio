import customtkinter as ctk

from ui.dialogs.color_picker import pick_color
from ui.widgets import IconTileRow, ModernSegmented
from utils.qr_render import QRStyle
from utils.theme_manager import ThemeManager

DEFAULT_GRADIENT_END = "#1E3A8A"

MODULE_TILES = (("square", "shape_square", "Square"),
                ("rounded", "shape_rounded", "Rounded"),
                ("dots", "shape_dots", "Dots"))
EYE_TILES = (("square", "eye_square", "Square"),
             ("rounded", "eye_rounded", "Rounded"))
GRADIENT_VALUES = (("none", "None"), ("linear", "Linear"), ("radial", "Radial"))


class StyleCard(ctk.CTkFrame):
    """Style tab of the Design card: module shape, eye shape and gradient."""

    def __init__(self, parent):

        super().__init__(parent, fg_color="transparent")

        self.module_shape = "square"
        self.eye_shape = "square"
        self.gradient = "none"
        self.gradient_end = DEFAULT_GRADIENT_END
        self.change_callback = None

        theme = ThemeManager.get_theme()
        self.grid_columnconfigure(0, weight=3, uniform="style")
        self.grid_columnconfigure(1, weight=2, uniform="style")
        self._captions = []

        self._caption("MODULE SHAPE", 0, 0)
        self.module_tiles = IconTileRow(self, MODULE_TILES, command=self._module_picked, height=60)
        self.module_tiles.grid(row=1, column=0, sticky="ew", padx=(0, 12), pady=(4, 12))
        self.module_tiles.set(self.module_shape)

        self._caption("EYE SHAPE", 0, 1)
        self.eye_tiles = IconTileRow(self, EYE_TILES, command=self._eye_picked, height=60)
        self.eye_tiles.grid(row=1, column=1, sticky="ew", pady=(4, 12))
        self.eye_tiles.set(self.eye_shape)

        self._caption("GRADIENT", 2, 0)
        gradient_row = ctk.CTkFrame(self, fg_color="transparent")
        gradient_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self.gradient_selector = ModernSegmented(
            gradient_row, values=[label for _v, label in GRADIENT_VALUES],
            command=self._gradient_picked, height=32)
        self.gradient_selector.set("None")
        self.gradient_selector.pack(side="left")

        # The end colour of the gradient (its start is the QR colour); only with a gradient.
        self.end_swatch = ctk.CTkFrame(
            gradient_row, width=30, height=30, corner_radius=8, border_width=1,
            border_color=theme["border"], fg_color=self.gradient_end)
        self.end_swatch._theme_skip = True        # shows the user's colour
        self.end_label = ctk.CTkLabel(gradient_row, text=self.gradient_end,
                                      font=("Segoe UI Semibold", 12), text_color=theme["text"])
        self.end_hint = ctk.CTkLabel(gradient_row, text="end colour · click to edit",
                                     font=("Segoe UI", 11), text_color=theme["text_secondary"])
        for widget in (self.end_swatch, self.end_label, self.end_hint):
            widget.bind("<Button-1>", lambda _e: self.choose_end_color())
            widget.configure(cursor="hand2")

    def _caption(self, text, row, column):
        label = ctk.CTkLabel(self, text=text, font=("Segoe UI", 11), anchor="w",
                             text_color=ThemeManager.get_theme()["text_secondary"])
        label.grid(row=row, column=column, sticky="w")
        self._captions.append(label)

    # ------------------------------------------------------------------

    def _notify(self):
        if self.change_callback:
            self.change_callback()

    def _module_picked(self, value):
        self.module_shape = value
        self._notify()

    def _eye_picked(self, value):
        self.eye_shape = value
        self._notify()

    def _gradient_picked(self, label):
        self.gradient = next(v for v, text in GRADIENT_VALUES if text == label)
        self._show_end_colour()
        self._notify()

    def _show_end_colour(self):
        if self.gradient == "none":
            for widget in (self.end_swatch, self.end_label, self.end_hint):
                widget.pack_forget()
        elif not self.end_swatch.winfo_manager():
            self.end_swatch.pack(side="left", padx=(16, 8))
            self.end_label.pack(side="left")
            self.end_hint.pack(side="left", padx=(8, 0))

    def choose_end_color(self):
        color = pick_color(self, self.gradient_end, "Gradient end colour")
        if color is not None:
            self.set_style(gradient_end=color)

    # ------------------------------------------------------------------

    def set_style(self, module_shape=None, eye_shape=None, gradient=None, gradient_end=None):
        """Show (and use) new values; ``None`` leaves that value as it is."""
        if module_shape is not None:
            self.module_shape = module_shape
            self.module_tiles.set(module_shape)
        if eye_shape is not None:
            self.eye_shape = eye_shape
            self.eye_tiles.set(eye_shape)
        if gradient is not None:
            self.gradient = gradient
            self.gradient_selector.set(dict(GRADIENT_VALUES)[gradient])
            self._show_end_colour()
        if gradient_end is not None:
            self.gradient_end = gradient_end.upper()
            self.end_swatch.configure(fg_color=self.gradient_end)
            self.end_label.configure(text=self.gradient_end)
        self._notify()

    def reset(self):
        self.set_style("square", "square", "none", DEFAULT_GRADIENT_END)

    def apply_to(self, style: QRStyle):
        """``style`` with this tab's choices filled in."""
        return style.with_(module_shape=self.module_shape, eye_shape=self.eye_shape,
                           gradient=self.gradient, fg2=self.gradient_end)

    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        for label in self._captions:
            label.configure(text_color=theme["text_secondary"])
        self.module_tiles.apply_theme()
        self.eye_tiles.apply_theme()
        self.gradient_selector.apply_theme()
        self.end_swatch.configure(border_color=theme["border"])
        self.end_label.configure(text_color=theme["text"])
        self.end_hint.configure(text_color=theme["text_secondary"])
