import customtkinter as ctk

from utils.theme_manager import ThemeManager


class HeroSection(ctk.CTkFrame):
    """Subtle in-page section heading (title + supporting subtitle).

    The global screen title now lives in the top bar; this component provides
    a lighter, secondary heading within a page when a page wants one.
    """

    def __init__(
        self,
        parent,
        title="Generate Beautiful QR Codes",
        subtitle="Create custom QR codes with logos, colors, and export options.",
    ):
        super().__init__(parent, fg_color="transparent")

        self.title_text = title
        self.subtitle_text = subtitle

        self.build_ui()

    def build_ui(self):
        theme = ThemeManager.get_theme()

        self.title = ctk.CTkLabel(
            self,
            text=self.title_text,
            font=("Segoe UI Semibold", 20),
            text_color=theme["text"],
            anchor="w",
        )
        self.title.pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            self,
            text=self.subtitle_text,
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"],
            justify="left",
            wraplength=680,
            anchor="w",
        )
        self.subtitle.pack(anchor="w", pady=(4, 0))

    # ==================================================

    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        self.title.configure(text_color=theme["text"])
        self.subtitle.configure(text_color=theme["text_secondary"])
