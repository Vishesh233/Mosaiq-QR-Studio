import customtkinter as ctk
from tkinter.colorchooser import askcolor

from utils.theme_manager import ThemeManager
from ui import icons


class ColorCard(ctk.CTkFrame):

    def __init__(self, parent):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            fg_color=theme["card"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border"]
        )

        self.qr_color = "#000000"
        self.bg_color = "#FFFFFF"

        self.build_ui()

    # =====================================================

    def build_ui(self):

        theme = ThemeManager.get_theme()

        # ---------------- Header ----------------

        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.pack(
            fill="x",
            padx=18,
            pady=(14, 8)
        )

        self.icon = ctk.CTkLabel(
            header,
            text=icons.icon("theme"),
            font=icons.icon_font(16),
            text_color=theme["primary"]
        )

        self.icon.pack(side="left")

        self.title = ctk.CTkLabel(
            header,
            text="Color Customization",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title.pack(side="left", padx=(8, 0))

        # ---------------- Body ----------------

        body = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        body.pack(
            fill="x",
            padx=18,
            pady=(0, 14)
        )

        body.grid_columnconfigure((0, 1), weight=1)

        self.create_color_picker(
            body,
            column=0,
            title="QR COLOR",
            color_type="qr"
        )

        self.create_color_picker(
            body,
            column=1,
            title="BACKGROUND COLOR",
            color_type="bg"
        )

    # =====================================================

    def create_color_picker(
        self,
        parent,
        column,
        title,
        color_type
    ):

        theme = ThemeManager.get_theme()

        frame = ctk.CTkFrame(
            parent,
            fg_color="transparent"
        )

        frame.grid(
            row=0,
            column=column,
            sticky="w",
            padx=(0, 18)
        )

        label = ctk.CTkLabel(
            frame,
            text=title,
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        label.pack(anchor="w")

        row = ctk.CTkFrame(
            frame,
            fg_color="transparent"
        )

        row.pack(anchor="w", pady=(6, 0))

        preview = ctk.CTkButton(
            row,
            width=34,
            height=34,
            text="",
            corner_radius=17,
            fg_color=self.qr_color if color_type == "qr" else self.bg_color,
            hover=False,
            command=lambda: self.choose_color(color_type)
        )

        preview.pack(side="left")

        text_frame = ctk.CTkFrame(
            row,
            fg_color="transparent"
        )

        text_frame.pack(side="left", padx=(10, 0))

        hex_label = ctk.CTkLabel(
            text_frame,
            text=self.qr_color if color_type == "qr" else self.bg_color,
            font=("Segoe UI Semibold", 14),
            text_color=theme["text"]
        )

        hex_label.pack(anchor="w")

        click_label = ctk.CTkLabel(
            text_frame,
            text="Click to change",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        click_label.pack(anchor="w")

        if color_type == "qr":
            self.qr_preview = preview
            self.qr_hex = hex_label
            self.qr_label = label
            self.qr_click = click_label
        else:
            self.bg_preview = preview
            self.bg_hex = hex_label
            self.bg_label = label
            self.bg_click = click_label

    # =====================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.icon.configure(
            text_color=theme["primary"]
        )

        self.title.configure(
            text_color=theme["text"]
        )

        self.qr_label.configure(
            text_color=theme["text_secondary"]
        )

        self.bg_label.configure(
            text_color=theme["text_secondary"]
        )

        self.qr_hex.configure(
            text_color=theme["text"]
        )

        self.bg_hex.configure(
            text_color=theme["text"]
        )

        self.qr_click.configure(
            text_color=theme["text_secondary"]
        )

        self.bg_click.configure(
            text_color=theme["text_secondary"]
        )

    # =====================================================

    def choose_color(self, color_type):

        color = askcolor()[1]

        if color is None:
            return

        if color_type == "qr":

            self.qr_color = color

            self.qr_preview.configure(
                fg_color=color
            )

            self.qr_hex.configure(
                text=color.upper()
            )

        else:

            self.bg_color = color

            self.bg_preview.configure(
                fg_color=color
            )

            self.bg_hex.configure(
                text=color.upper()
            )

    # =====================================================

    def get_qr_color(self):
        return self.qr_color

    def get_bg_color(self):
        return self.bg_color

    # =====================================================

    def reset_colors(self):

        self.qr_color = "#000000"
        self.bg_color = "#FFFFFF"

        self.qr_preview.configure(
            fg_color=self.qr_color
        )

        self.bg_preview.configure(
            fg_color=self.bg_color
        )

        self.qr_hex.configure(
            text=self.qr_color
        )

        self.bg_hex.configure(
            text=self.bg_color
        )