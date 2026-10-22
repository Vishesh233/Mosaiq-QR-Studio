import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons


class ActionButtons(ctk.CTkFrame):
    """Generate (primary, full width) and Save / Copy / Clear under the live preview."""

    def __init__(self, parent):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.generate_callback = None
        self.copy_callback = None
        self.save_callback = None
        self.clear_callback = None

        self.build_ui()

    # ==================================================

    def _secondary(self, text, command, column, text_color):
        theme = ThemeManager.get_theme()
        button = ctk.CTkButton(
            self,
            text=text,
            height=40,
            corner_radius=11,
            fg_color=theme["segment_bg"],
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=text_color,
            text_color_disabled=theme["text_muted"],
            font=("Segoe UI Semibold", 13),
            command=command,
        )
        button.grid(row=1, column=column, sticky="ew",
                    padx=(0 if column == 0 else 4, 0 if column == 2 else 4), pady=(8, 0))
        return button

    def build_ui(self):
        theme = ThemeManager.get_theme()
        self.grid_columnconfigure((0, 1, 2), weight=1, uniform="actions")

        self.generate_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('generate')}  Generate QR",
            height=44,
            corner_radius=11,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"],
            font=("Segoe UI Semibold", 14),
            command=self.on_generate
        )
        self.generate_btn.grid(row=0, column=0, columnspan=3, sticky="ew")

        self.save_btn = self._secondary(
            f"{icons.icon('save')}  Save", self.on_save, 0, theme["text_muted"])
        self.copy_btn = self._secondary(
            f"{icons.icon('copy')}  Copy", self.on_copy, 1, theme["text_muted"])
        self.clear_btn = self._secondary(
            f"{icons.icon('delete')}  Clear", self.on_clear, 2, theme["danger"])

        self.save_btn.configure(state="disabled")
        self.copy_btn.configure(state="disabled")

    # ==================================================

    def enable_export_buttons(self):

        for button in (self.save_btn, self.copy_btn):
            button.configure(state="normal", text_color=ThemeManager.get_theme()["text"])

    # ==================================================

    def disable_export_buttons(self):

        for button in (self.save_btn, self.copy_btn):
            button.configure(state="disabled", text_color=ThemeManager.get_theme()["text_muted"])

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.generate_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"]
        )

        for button in (self.save_btn, self.copy_btn, self.clear_btn):
            button.configure(
                fg_color=theme["segment_bg"],
                border_color=theme["border"],
                hover_color=theme["card_hover"],
                text_color_disabled=theme["text_muted"],
            )

        self.clear_btn.configure(text_color=theme["danger"])

        # Keep the enabled / disabled text colours.
        for button in (self.save_btn, self.copy_btn):
            disabled = str(button.cget("state")) == "disabled"
            button.configure(text_color=theme["text_muted"] if disabled else theme["text"])

    # ==================================================

    def set_generate_callback(self, callback):
        self.generate_callback = callback

    def set_copy_callback(self, callback):
        self.copy_callback = callback

    def set_save_callback(self, callback):
        self.save_callback = callback

    def set_clear_callback(self, callback):
        self.clear_callback = callback

    # ==================================================

    def on_generate(self):

        if self.generate_callback:
            self.generate_callback()

    def on_copy(self):

        if self.copy_callback:
            self.copy_callback()

    def on_save(self):

        if self.save_callback:
            self.save_callback()

    def on_clear(self):

        if self.clear_callback:
            self.clear_callback()
