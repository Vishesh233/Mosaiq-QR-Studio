import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui.dialogs.settings_dialog import SettingsDialog
from ui.layout import GRID, PAGE_PADX
from ui import icons


class Header(ctk.CTkFrame):
    """Page title + subtitle on the shared left edge, and the Settings button.

    ``set_title`` is driven by the active page.
    """

    HEIGHT = 12 * GRID

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            height=self.HEIGHT,
            corner_radius=0,
            fg_color=theme["background"],
        )

        self.pack_propagate(False)

        self._title_label = None
        self._subtitle_label = None
        self._settings_btn = None

        self._build()

    # ==================================================
    def _build(self):
        theme = ThemeManager.get_theme()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- Left: title + subtitle ----------------
        text_col = ctk.CTkFrame(self, fg_color="transparent")
        text_col.grid(row=0, column=0, sticky="w", padx=(PAGE_PADX, 0))

        self._title_label = ctk.CTkLabel(
            text_col,
            text="Generate QR Code",
            font=("Segoe UI Semibold", 24),
            text_color=theme["text"],
            anchor="w",
        )
        self._title_label.grid(row=0, column=0, sticky="w")

        self._subtitle_label = ctk.CTkLabel(
            text_col,
            text="",
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"],
            anchor="w",
        )
        self._subtitle_label.grid(row=1, column=0, sticky="w")

        # ---------------- Right: settings ----------------
        self._settings_btn = ctk.CTkButton(
            self,
            text=icons.icon("settings"),
            width=5 * GRID, height=5 * GRID,
            corner_radius=10,
            border_width=1,
            border_color=theme["border"],
            fg_color=theme["card"],
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
            font=icons.icon_font(16),
            command=self.open_settings,
        )
        self._settings_btn.grid(row=0, column=1, sticky="e", padx=(0, PAGE_PADX))

    # ==================================================
    def set_title(self, title, subtitle=""):
        if self._title_label is not None:
            self._title_label.configure(text=title)
        if self._subtitle_label is not None:
            self._subtitle_label.configure(text=subtitle)

    # ==================================================
    def open_settings(self):
        SettingsDialog(self)

    # ==================================================
    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        self.configure(fg_color=theme["background"])
        self._title_label.configure(text_color=theme["text"])
        self._subtitle_label.configure(text_color=theme["text_secondary"])
        self._settings_btn.configure(
            fg_color=theme["card"],
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
        )
