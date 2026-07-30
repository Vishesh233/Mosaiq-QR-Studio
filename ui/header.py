import customtkinter as ctk

from config import (
    APP_NAME,
    APP_VERSION,
)

from utils.theme_manager import ThemeManager
from ui.dialogs.settings_dialog import SettingsDialog


class Header(ctk.CTkFrame):

    def __init__(self, parent):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            fg_color=theme["navbar"],
            height=52,
            corner_radius=0
        )

        self.pack_propagate(False)

        # ---------------- Logo ---------------- #

        self.logo = ctk.CTkLabel(
            self,
            text="▣",
            font=("Segoe UI", 22),
            text_color=theme["primary"]
        )

        self.logo.pack(
            side="left",
            padx=(18, 10)
        )

        # ---------------- App Name ---------------- #

        self.title = ctk.CTkLabel(
            self,
            text=APP_NAME,
            font=("Segoe UI", 16, "bold"),
            text_color=theme["text"]
        )

        self.title.pack(side="left")

        # ---------------- Version Badge ---------------- #

        self.version = ctk.CTkLabel(
            self,
            text=APP_VERSION,
            width=40,
            height=22,
            fg_color=theme["card"],
            corner_radius=8,
            font=("Segoe UI", 10),
            text_color=theme["text_secondary"]
        )

        self.version.pack(
            side="left",
            padx=(10, 0)
        )

        # ---------------- Right Side ---------------- #

        self.right_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.right_frame.pack(
            side="right",
            padx=15
        )

        # ---------------- Settings ---------------- #

        self.settings_btn = ctk.CTkButton(
            self.right_frame,
            text="⚙",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=theme["card"],
            command=self.open_settings
        )

        self.settings_btn.pack(
            side="left",
            padx=5
        )

        # ---------------- Theme ---------------- #

        self.theme_btn = ctk.CTkButton(
            self.right_frame,
            text="☀",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=theme["card"]
        )

        self.theme_btn.pack(
            side="left",
            padx=5
        )

    # ==================================================

    def open_settings(self):
        SettingsDialog(self)

    # ==================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["navbar"]
        )

        self.logo.configure(
            text_color=theme["primary"]
        )

        self.title.configure(
            text_color=theme["text"]
        )

        self.version.configure(
            fg_color=theme["card"],
            text_color=theme["text_secondary"]
        )

        self.settings_btn.configure(
            hover_color=theme["card"]
        )

        self.theme_btn.configure(
            hover_color=theme["card"]
        )