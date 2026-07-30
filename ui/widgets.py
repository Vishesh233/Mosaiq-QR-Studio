import customtkinter as ctk

from utils.theme_manager import ThemeManager


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
            placeholder_text_color=theme["text_secondary"],
            font=("Segoe UI", 14)
        )

    # ================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["entry"],
            border_color=theme["entry_border"],
            text_color=theme["text"],
            placeholder_text_color=theme["text_secondary"]
        )