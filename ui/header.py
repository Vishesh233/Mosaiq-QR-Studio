import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui.dialogs.settings_dialog import SettingsDialog
from ui import icons


class Header(ctk.CTkFrame):
    """Premium top bar: contextual screen title/subtitle + actions.

    Keeps the original settings entry point (open_settings) and the settings
    button, and adds a live title/subtitle driven by the active screen.
    """

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            height=64,
            corner_radius=0,
            fg_color=theme["navbar"],
        )

        self.pack_propagate(False)

        self._title_label = None
        self._subtitle_label = None
        self._settings_btn = None
        self._sep = None

        self._build()

    # ==================================================
    def _build(self):
        theme = ThemeManager.get_theme()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- Left: title + subtitle ----------------
        text_col = ctk.CTkFrame(self, fg_color="transparent")
        text_col.grid(row=0, column=0, sticky="w", padx=(28, 0))

        self._title_label = ctk.CTkLabel(
            text_col,
            text="Generate QR Code",
            font=("Segoe UI Semibold", 20),
            text_color=theme["text"],
        )
        self._title_label.grid(row=0, column=0, sticky="w")

        self._subtitle_label = ctk.CTkLabel(
            text_col,
            text="Create a custom QR code from a URL or text.",
            font=("Segoe UI", 12),
            text_color=theme["text_secondary"],
        )
        self._subtitle_label.grid(row=1, column=0, sticky="w")

        # ---------------- Right: actions ----------------
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(0, 24))

        self._settings_btn = ctk.CTkButton(
            actions,
            text=icons.icon("settings"),
            width=40, height=40,
            corner_radius=10,
            fg_color="transparent",
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
            font=icons.icon_font(17),
            command=self.open_settings,
        )
        self._settings_btn.grid(row=0, column=0, padx=(0, 8))

        # Bottom hairline divider
        self._sep = ctk.CTkFrame(self, height=1, fg_color=theme["border"])
        self._sep.place(relx=0, rely=1.0, anchor="sw", relwidth=1.0)

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
        self.configure(fg_color=theme["navbar"])
        if self._title_label is not None:
            self._title_label.configure(text_color=theme["text"])
        if self._subtitle_label is not None:
            self._subtitle_label.configure(text_color=theme["text_secondary"])
        if self._settings_btn is not None:
            self._settings_btn.configure(
                hover_color=theme["card_hover"],
                text_color=theme["text_secondary"],
            )
        if self._sep is not None:
            self._sep.configure(fg_color=theme["border"])
