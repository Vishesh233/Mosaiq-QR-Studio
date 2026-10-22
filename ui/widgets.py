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
                text_color=theme["on_primary"] if value == selected else theme["text"]
            )
