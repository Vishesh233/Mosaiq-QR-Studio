import os
import customtkinter as ctk

from tkinter import filedialog
from PIL import Image

from utils.theme_manager import ThemeManager


class LogoCard(ctk.CTkFrame):

    def __init__(self, parent):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            fg_color=theme["card"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border"]
        )

        self.logo_path = None
        self.logo_image = None

        self.build_ui()

    # ======================================================

    def build_ui(self):

        theme = ThemeManager.get_theme()

        # ==========================
        # Header
        # ==========================

        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(14, 8)
        )

        self.title = ctk.CTkLabel(
            header,
            text="🖼 Logo",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title.pack(side="left")

        self.optional = ctk.CTkLabel(
            header,
            text="Optional",
            font=("Segoe UI", 12),
            text_color=theme["text_secondary"]
        )

        self.optional.pack(side="left", padx=(8, 0))

        # ==========================
        # Upload Area
        # ==========================

        self.upload_frame = ctk.CTkFrame(
            self,
            height=120,
            fg_color=theme["entry"],
            corner_radius=14,
            border_width=1,
            border_color=theme["primary"]
        )

        self.upload_frame.pack(
            fill="x",
            padx=18,
            pady=(0, 16)
        )

        self.upload_frame.pack_propagate(False)

        self.upload_frame.bind(
            "<Button-1>",
            lambda e: self.choose_logo()
        )

        self.icon = ctk.CTkLabel(
            self.upload_frame,
            text="⬆",
            font=("Segoe UI", 28),
            text_color=theme["text"]
        )

        self.icon.pack(
            pady=(14, 6)
        )

        self.title_label = ctk.CTkLabel(
            self.upload_frame,
            text="Choose Logo",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title_label.pack()

        self.subtitle = ctk.CTkLabel(
            self.upload_frame,
            text="PNG, JPG up to 4 MB",
            font=("Segoe UI", 12),
            text_color=theme["text_secondary"]
        )

        self.subtitle.pack(
            pady=(2, 0)
        )

    # ======================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.title.configure(
            text_color=theme["text"]
        )

        self.optional.configure(
            text_color=theme["text_secondary"]
        )

        self.upload_frame.configure(
            fg_color=theme["entry"],
            border_color=theme["primary"]
        )

        self.icon.configure(
            text_color=theme["text"]
        )

        self.title_label.configure(
            text_color=theme["text"]
        )

        self.subtitle.configure(
            text_color=theme["text_secondary"]
        )

    # ======================================================

    def choose_logo(self):

        path = filedialog.askopenfilename(
            title="Select Logo",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg")
            ]
        )

        if not path:
            return

        self.logo_path = path

        image = Image.open(path)
        image.thumbnail((72, 72))

        self.logo_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=image.size
        )

        self.icon.configure(
            image=self.logo_image,
            text=""
        )

        filename = os.path.basename(path)

        if len(filename) > 20:
            filename = filename[:17] + "..."

        self.title_label.configure(
            text=filename
        )

        self.subtitle.pack_forget()

    # ======================================================

    def get_logo_path(self):
        return self.logo_path

    # ======================================================

    def reset_logo(self):

        self.logo_path = None
        self.logo_image = None

        self.icon.configure(
            image=None,
            text="⬆"
        )

        self.title_label.configure(
            text="Choose Logo"
        )

        self.subtitle.pack(
            pady=(4, 0)
        )