import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui.widgets import ModernEntry


class ContentCard(ctk.CTkFrame):

    def __init__(self, parent):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            fg_color=theme["card"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border"],
            height=250
        )

        self.pack_propagate(False)

        self.build_ui()

    # ==================================================

    def build_ui(self):

        theme = ThemeManager.get_theme()

        content_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        content_frame.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=18
        )

        self.title = ctk.CTkLabel(
            content_frame,
            text="🔗  Content",
            font=("Segoe UI", 18, "bold"),
            text_color=theme["text"]
        )

        self.title.pack(anchor="w")

        # ---------------- URL ---------------- #

        self.label1 = ctk.CTkLabel(
            content_frame,
            text="WEBSITE URL OR TEXT",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        self.label1.pack(
            anchor="w",
            pady=(16, 5)
        )

        self.url_entry = ModernEntry(
            content_frame,
            placeholder="https://example.com"
        )

        self.url_entry.pack(fill="x")

        # ---------------- Filename ---------------- #

        self.label2 = ctk.CTkLabel(
            content_frame,
            text="OUTPUT FILE NAME",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        self.label2.pack(
            anchor="w",
            pady=(14, 5)
        )

        self.file_entry = ModernEntry(
            content_frame,
            placeholder="my_qr_code"
        )

        self.file_entry.pack(fill="x")

    # ==================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.title.configure(
            text_color=theme["text"]
        )

        self.label1.configure(
            text_color=theme["text_secondary"]
        )

        self.label2.configure(
            text_color=theme["text_secondary"]
        )

        self.url_entry.refresh_theme()
        self.file_entry.refresh_theme()

        # ModernEntry refresh baad me add karenge

    # ==================================================

    def get_content(self):
        return self.url_entry.get().strip()

    # ==================================================

    def get_filename(self):
        return self.file_entry.get().strip()

    # ==================================================

    def clear(self):

        self.url_entry.delete(0, "end")
        self.file_entry.delete(0, "end")