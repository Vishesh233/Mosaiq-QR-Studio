import os

import customtkinter as ctk

from ui.components.color_card import ColorCard
from ui.components.logo_card import LogoCard
from ui.components.style_card import StyleCard
from ui.layout import SectionCard
from ui.widgets import ModernSegmented
from utils import qr_checks, qr_presets
from utils.qr_render import QRStyle
from utils.theme_manager import ThemeManager


class DesignCard(SectionCard):
    """Step 2: tabs (Colours / Style / Logo) that style the QR, with a contrast hint."""

    def __init__(self, parent):

        super().__init__(parent, title="Design", step=2)

        self.change_callback = None

        self.tabs = ModernSegmented(
            self.body, values=["Colours", "Style", "Logo"], command=self.show_tab, height=32,
        )
        self.tabs.pack(anchor="w", pady=(0, 12))

        # The panes live in their own holder so the hint stays below whichever is showing.
        self.pane_holder = ctk.CTkFrame(self.body, fg_color="transparent")
        self.pane_holder.pack(fill="x")
        self.panes = {
            "Colours": ColorCard(self.pane_holder),
            "Style": StyleCard(self.pane_holder),
            "Logo": LogoCard(self.pane_holder),
        }
        self.colours = self.panes["Colours"]
        self.style = self.panes["Style"]
        self.logo = self.panes["Logo"]
        for pane in self.panes.values():
            pane.change_callback = self._changed
        self.colours.preset_callback = self.apply_preset

        self.hint = ctk.CTkLabel(
            self.body, text="", anchor="w", font=("Segoe UI", 12),
            text_color=ThemeManager.get_theme()["success"])
        self.hint.pack(fill="x", pady=(12, 0))

        self._active = None
        self.show_tab("Colours")
        self._update_state()

    # ------------------------------------------------------------------

    def _changed(self):
        self._update_state()
        if self.change_callback:
            self.change_callback()

    def _update_state(self):
        """Highlight the matching preset and show the contrast advice."""
        style = self.get_style()
        self.colours.preset_row.set_selected(qr_presets.matching(style))
        check = qr_checks.check_style(style)
        theme = ThemeManager.get_theme()
        dot = "●  "
        self.hint.configure(
            text=dot + check.text,
            text_color=theme["success"] if check.level == "good" else theme["warning"])
        self.last_check = check

    def show_tab(self, name):
        if self._active is not None:
            self.panes[self._active].pack_forget()
        self._active = name
        self.tabs.set(name)
        self.panes[name].pack(fill="x")
        if name == "Logo":
            self.logo.refresh_limit()

    def apply_preset(self, name):
        """Set colours and style from a preset (the logo is kept); one preview refresh."""
        preset = qr_presets.get(name).style
        callback, self.change_callback = self.change_callback, None
        try:
            self.colours.set_colors(qr=preset.fg, bg=preset.bg)
            self.style.set_style(module_shape=preset.module_shape, eye_shape=preset.eye_shape,
                                 gradient=preset.gradient, gradient_end=preset.fg2)
        finally:
            self.change_callback = callback
        self._changed()

    def get_style(self):
        """The QRStyle chosen in the tabs."""
        base = QRStyle(fg=self.colours.get_qr_color(), bg=self.colours.get_bg_color(),
                       logo_scale=self.logo.get_logo_scale())
        return self.style.apply_to(base)

    def load(self, style, logo_path=None):
        """Show a saved look: colours, shapes, gradient, logo and logo size (one preview refresh).
        A logo file that is gone is dropped."""
        callback, self.change_callback = self.change_callback, None
        try:
            self.colours.set_colors(qr=style.fg, bg=style.bg)
            self.style.set_style(module_shape=style.module_shape, eye_shape=style.eye_shape,
                                 gradient=style.gradient, gradient_end=style.fg2)
            if logo_path and os.path.exists(logo_path):
                self.logo.set_logo(logo_path)
                self.logo.set_scale(style.logo_scale)
            else:
                self.logo.reset_logo()
        finally:
            self.change_callback = callback
        self._update_state()

    def reset(self):
        """Back to black on white, plain shapes, no logo (one preview refresh)."""
        callback, self.change_callback = self.change_callback, None
        try:
            self.colours.reset_colors()
            self.style.reset()
            self.logo.reset_logo()
        finally:
            self.change_callback = callback
        self._update_state()

    def refresh_theme(self):
        super().refresh_theme()
        self.tabs.apply_theme()
        for pane in self.panes.values():
            pane.refresh_theme()
        self._update_state()
