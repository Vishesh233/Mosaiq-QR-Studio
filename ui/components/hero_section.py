import customtkinter as ctk

from utils.theme_manager import ThemeManager


class HeroSection(ctk.CTkFrame):

    def __init__(
        self,
        parent,
        title="⚡ Generate Beautiful QR Codes",
        subtitle="Create custom QR codes with logos, colors, and export options."
    ):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.title_text = title
        self.subtitle_text = subtitle

        self.build_ui()

    def build_ui(self):

        theme = ThemeManager.get_theme()

        self.title = ctk.CTkLabel(
            self,
            text=self.title_text,
            font=("Segoe UI Semibold", 28),
            text_color=theme["text"],
            anchor="w"
        )

        self.title.pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            self,
            text=self.subtitle_text,
            font=("Segoe UI", 14),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=650,
            anchor="w"
        )

        self.subtitle.pack(
            anchor="w",
            pady=(8, 0)
        )

    # ==================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.title.configure(
            text_color=theme["text"]
        )

        self.subtitle.configure(
            text_color=theme["text_secondary"]
        )