import os
import customtkinter as ctk

from tkinter import filedialog
from PIL import Image

from utils.theme_manager import ThemeManager
from ui import icons

class ScanUploadCard(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            corner_radius=16,
            border_width=1,
            fg_color=theme["card"],
            border_color=theme["border"],
            width=760,
            height=520
        )

        self.image_path = None
        self.preview_image = None
        self.preview_label = None
        self.upload_callback = None

        self.build_ui()

    # ======================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()

        # ---------------- Header ---------------- #

        self.header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.header.pack(
            fill="x",
            padx=20,
            pady=(18, 10)
        )

        self.title = ctk.CTkLabel(
            self.header,
            text="Scan Image",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title.pack(side="left")

        # ---------------- Upload Area ---------------- #

        self.upload_frame = ctk.CTkFrame(
            self,
            height=390,
            width=690,
            corner_radius=16,
            border_width=1,
            fg_color=theme["entry"],
            border_color=theme["primary"]
        )

        self.upload_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 20)
        )

        self.upload_frame.pack_propagate(False)

        self.upload_frame.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        # Placeholder

        self.placeholder = ctk.CTkFrame(
            self.upload_frame,
            fg_color="transparent"
        )

        self.placeholder.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        self.placeholder.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        self.icon = ctk.CTkLabel(
            self.placeholder,
            text=icons.icon("image"),
            font=icons.icon_font(52),
            text_color=theme["primary"]
        )

        self.icon.pack(
            pady=(15, 10)
        )

        self.icon.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        self.title_label = ctk.CTkLabel(
            self.placeholder,
            text="Drop your QR Image Here",
            font=("Segoe UI Semibold", 18),
            text_color=theme["text"]
        )

        self.title_label.pack()

        self.title_label.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        self.subtitle = ctk.CTkLabel(
            self.placeholder,
            text="Drag & drop or click to browse",
            font=("Segoe UI", 12),
            text_color=theme["text_secondary"]
        )

        self.subtitle.pack(
            pady=(5, 15)
        )

        self.subtitle.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        self.browse_button = ctk.CTkButton(
            self.placeholder,
            text="Browse Image",
            width=170,
            height=42,
            corner_radius=12,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"],
            command=self.choose_image
        )

        self.browse_button.pack(
            pady=(10, 0)
        )

        self.supported_label = ctk.CTkLabel(
            self.placeholder,
            text="PNG • JPG • JPEG • WEBP",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        self.supported_label.pack(
            pady=(15, 0)
        )

    # ======================================================

    def choose_image(self):

        path = filedialog.askopenfilename(
            title="Select QR Image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.webp *.bmp")
            ]
        )

        if not path:
            return

        self.image_path = path

        self.show_preview()

        if self.upload_callback:
            self.upload_callback(path)

    # ======================================================

    def show_preview(self):

        # Remove old preview if exists
        if self.preview_label is not None:
            self.preview_label.destroy()
            self.preview_label = None

        try:
            image = Image.open(self.image_path).copy()
            image.thumbnail((190, 190))

        except Exception:
            return

        self.preview_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=image.size
        )

        # Hide upload icon only
        self.icon.pack_forget()

        # Show preview
        self.preview_label = ctk.CTkLabel(
            self.placeholder,
            text="",
            image=self.preview_image,
            fg_color="transparent"
        )

        self.preview_label.pack(
            pady=(15, 10)
        )

        self.preview_label.bind(
            "<Button-1>",
            lambda e: self.choose_image()
        )

        filename = os.path.basename(self.image_path)

        if len(filename) > 28:
            filename = filename[:25] + "..."

        self.title_label.configure(
            text=filename
        )

        self.subtitle.configure(
            text="Click 'Replace Image' to choose another QR code"
        )

        self.browse_button.configure(
            text="Replace Image"
        )

        theme = ThemeManager.get_theme()


        self.upload_frame.configure(
            border_color=theme["primary"]
        )

        if not hasattr(self, "clear_button"):

            self.clear_button = ctk.CTkButton(
                self,
                text=f"{icons.icon('delete')}  Clear Image",
                width=180,
                height=42,
                corner_radius=12,
                fg_color="transparent",
                border_width=1,
                hover_color=theme["card_hover"],
                border_color=theme["border"],
                text_color=theme["danger"],
                command=self.clear
            )

            self.clear_button.pack(
                anchor="w",
                padx=20,
                pady=(10, 0)
            )

    # ======================================================

    def clear(self):

        self.image_path = None
        self.preview_image = None

        # Remove preview
        if self.preview_label is not None:
            self.preview_label.destroy()
            self.preview_label = None

        # Bring upload icon back
        self.icon.pack(
            pady=(15, 10)
        )

        self.title_label.configure(
            text="Drop your QR Image Here"
        )

        self.subtitle.configure(
            text="Drag & drop or click to browse"
        )

        self.browse_button.configure(
            text="Browse Image"
        )

        theme = ThemeManager.get_theme()

        self.upload_frame.configure(
            border_color=theme["border"]
        )

        if hasattr(self, "clear_button"):
            self.clear_button.destroy()
            del self.clear_button


    # ======================================================

    def get_image_path(self):
        return self.image_path


    # ======================================================

    def set_upload_callback(self, callback):
        self.upload_callback = callback


    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.upload_frame.configure(
            fg_color=theme["entry"],
            border_color=theme["primary"] if self.image_path else theme["border"]
        )


        self.title.configure(
            text_color=theme["text"]
        )

        self.title_label.configure(
            text_color=theme["text"]
        )

        self.subtitle.configure(
            text_color=theme["text_secondary"]
        )

        self.icon.configure(
            text_color=theme["primary"]
        )

        self.supported_label.configure(
            text_color=theme["text_secondary"]
        )

        self.browse_button.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"]
        )

        if hasattr(self, "clear_button"):
            self.clear_button.configure(
                hover_color=theme["card_hover"],
                border_color=theme["border"],
                text_color=theme["danger"]
            )