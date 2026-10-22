import os
import customtkinter as ctk

from tkinter import filedialog
from PIL import Image

from utils.theme_manager import ThemeManager
from ui.line_icons import line_icon


class LogoCard(ctk.CTkFrame):
    """Logo tab of the Design card: choose an image to place in the middle of the QR."""

    def __init__(self, parent):

        super().__init__(parent, fg_color="transparent")

        self.logo_path = None
        self.logo_image = None
        self.change_callback = None

        self.build_ui()

    # ======================================================

    def build_ui(self):

        theme = ThemeManager.get_theme()

        self.upload_frame = ctk.CTkFrame(
            self,
            height=96,
            fg_color=theme["segment_bg"],
            corner_radius=11,
            border_width=1,
            border_color=theme["border"],
        )
        self.upload_frame.pack(fill="x")
        self.upload_frame.pack_propagate(False)

        row = ctk.CTkFrame(self.upload_frame, fg_color="transparent")
        row.place(relx=0.5, rely=0.5, anchor="center")

        self.icon = ctk.CTkLabel(row, text="", width=56, height=56,
                                 text_color=theme["text"],
                                 image=self._placeholder_icon())
        self.icon.pack(side="left", padx=(0, 14))

        texts = ctk.CTkFrame(row, fg_color="transparent")
        texts.pack(side="left")

        self.title_label = ctk.CTkLabel(
            texts, text="Choose logo", anchor="w",
            font=("Segoe UI Semibold", 14), text_color=theme["text"],
        )
        self.title_label.pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            texts, text="PNG, JPG up to 4 MB. Shown in the middle of the QR.", anchor="w",
            font=("Segoe UI", 12), text_color=theme["text_secondary"],
        )
        self.subtitle.pack(anchor="w")

        self.remove_button = ctk.CTkButton(
            row, text="Remove", width=80, height=32, corner_radius=9,
            fg_color="transparent", border_width=1, border_color=theme["border"],
            hover_color=theme["card_hover"], text_color=theme["danger"],
            font=("Segoe UI", 12), command=self.reset_logo,
        )

        for widget in (self.upload_frame, row, self.icon, texts, self.title_label, self.subtitle):
            widget.bind("<Button-1>", lambda _e: self.choose_logo())
        try:
            self.upload_frame.configure(cursor="hand2")
        except Exception:
            pass

    def _placeholder_icon(self):
        # Kept on self: a label raises TclError if its CTkImage is garbage-collected.
        self._placeholder_ref = line_icon("image", ThemeManager.get_theme()["primary"], 28)
        return self._placeholder_ref

    # ======================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.upload_frame.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
        self.title_label.configure(text_color=theme["text"])
        self.subtitle.configure(text_color=theme["text_secondary"])
        self.remove_button.configure(
            border_color=theme["border"], hover_color=theme["card_hover"],
            text_color=theme["danger"])
        if self.logo_path is None:
            self.icon.configure(image=self._placeholder_icon())

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

        self.set_logo(path)

    def set_logo(self, path):
        """Use the image at ``path`` as the logo."""

        image = Image.open(path)
        image.thumbnail((56, 56))

        self.logo_path = path
        self.logo_image = ctk.CTkImage(
            light_image=image,
            dark_image=image,
            size=image.size
        )

        self.icon.configure(image=self.logo_image)

        filename = os.path.basename(path)

        if len(filename) > 28:
            filename = filename[:25] + "..."

        self.title_label.configure(text=filename)
        self.subtitle.configure(text="Click to choose another image")
        self.remove_button.pack(side="left", padx=(18, 0))

        if self.change_callback:
            self.change_callback()

    # ======================================================

    def get_logo_path(self):
        return self.logo_path

    # ======================================================

    def reset_logo(self):

        self.logo_path = None
        self.logo_image = None

        self.icon.configure(image=self._placeholder_icon())
        self.title_label.configure(text="Choose logo")
        self.subtitle.configure(text="PNG, JPG up to 4 MB. Shown in the middle of the QR.")
        self.remove_button.pack_forget()

        if self.change_callback:
            self.change_callback()
