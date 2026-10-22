import os
import customtkinter as ctk

from tkinter import filedialog
from PIL import Image

from utils.theme_manager import ThemeManager
from ui import icons
from ui.layout import CARD_PAD, Card
from ui.line_icons import line_icon
from ui.widgets import DashedZone, IconTile

ZONE_HEIGHT = 320
TIPS = ("Use a sharp image", "Good contrast helps", "Avoid cropped codes")


class ScanUploadCard(Card):
    """Source tiles (Image, Camera, Screen region, Paste), a big drop zone and a tips line."""

    def __init__(self, parent):
        super().__init__(parent)

        self.image_path = None
        self.has_content = False
        self.preview_image = None
        self.preview_label = None
        self.upload_callback = None
        self.idle_title = "Select a QR image"
        self.idle_subtitle = "Click to browse your files"

        self.build_ui()

    # ======================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()

        # ---------------- Source tiles ---------------- #

        self.tiles = ctk.CTkFrame(self, fg_color="transparent")
        self.tiles.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, 14))
        self.tiles.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="sources")

        self.image_button = IconTile(self.tiles, "image", "Image", height=64,
                                     command=self.choose_image)
        self.camera_button = IconTile(self.tiles, "camera", "Camera", height=64)
        self.region_button = IconTile(self.tiles, "screen", "Screen region", height=64)
        self.paste_button = IconTile(self.tiles, "paste", "Paste · Ctrl+V", height=64)
        for column, tile in enumerate((self.image_button, self.camera_button,
                                       self.region_button, self.paste_button)):
            tile.grid(row=0, column=column, sticky="ew",
                      padx=(0 if column == 0 else 5, 0 if column == 3 else 5))
        self.image_button.set_selected(True)

        # ---------------- Drop zone ---------------- #

        self.upload_frame = DashedZone(self, height=ZONE_HEIGHT)
        self.upload_frame.pack(fill="x", padx=CARD_PAD)
        self.upload_frame.bind_click(self.choose_image)

        self.placeholder = self.upload_frame.inner

        self.icon = ctk.CTkLabel(self.placeholder, text="", text_color=theme["text"],
                                 image=self._upload_icon())
        self.icon.pack(pady=(0, 8))

        self.title_label = ctk.CTkLabel(
            self.placeholder,
            text=self.idle_title,
            font=("Segoe UI Semibold", 18),
            text_color=theme["text"]
        )
        self.title_label.pack()

        self.subtitle = ctk.CTkLabel(
            self.placeholder,
            text=self.idle_subtitle,
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"]
        )
        self.subtitle.pack(pady=(4, 14))

        self.browse_button = ctk.CTkButton(
            self.placeholder,
            text="Browse Image",
            height=40,
            width=160,
            corner_radius=11,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"],
            font=("Segoe UI Semibold", 13),
            command=self.choose_image
        )
        self.browse_button.pack()

        self.supported_label = ctk.CTkLabel(
            self.placeholder,
            text="PNG · JPG · JPEG · WEBP · BMP",
            font=("Segoe UI", 12),
            text_color=theme["text_secondary"]
        )
        self.supported_label.pack(pady=(14, 0))

        for widget in (self.icon, self.title_label, self.subtitle, self.supported_label):
            widget.bind("<Button-1>", lambda _e: self.choose_image())

        # ---------------- Tips ---------------- #

        self.tips = ctk.CTkFrame(self, fg_color="transparent")
        self.tips.pack(fill="x", padx=CARD_PAD, pady=(12, CARD_PAD))
        self.tip_labels = []
        for tip in TIPS:
            label = ctk.CTkLabel(
                self.tips, text=f"•  {tip}", font=("Segoe UI", 12),
                text_color=theme["text_secondary"])
            label.pack(side="left", padx=(0, 18))
            self.tip_labels.append(label)

        self.build_camera_view()

    def _upload_icon(self):
        # Kept on self: a label raises TclError if its CTkImage is garbage-collected.
        self._upload_icon_ref = line_icon("upload", ThemeManager.get_theme()["primary"], 48)
        return self._upload_icon_ref

    # ======================================================
    # Camera view (replaces the drop zone while the camera runs)
    # ======================================================

    def build_camera_view(self):
        theme = ThemeManager.get_theme()

        self.camera_frame = ctk.CTkFrame(
            self,
            height=ZONE_HEIGHT,
            corner_radius=14,
            border_width=1,
            fg_color=theme["segment_bg"],
            border_color=theme["primary"]
        )

        self.camera_frame.pack_propagate(False)

        self.camera_label = None

        self.camera_status = ctk.CTkLabel(
            self.camera_frame,
            text="",
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"],
            wraplength=560,
            justify="center"
        )

        self.camera_buttons = ctk.CTkFrame(
            self.camera_frame,
            fg_color="transparent"
        )

        self.camera_stop_button = ctk.CTkButton(
            self.camera_buttons,
            text="Stop Camera",
            width=150,
            height=40,
            corner_radius=11,
            fg_color="transparent",
            border_width=1,
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["danger"]
        )

        self.camera_stop_button.pack(side="left", padx=6)

        self.camera_settings_button = ctk.CTkButton(
            self.camera_buttons,
            text="Open Camera Settings",
            width=190,
            height=40,
            corner_radius=11,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"]
        )

        self.camera_image = None
        self.camera_visible = False

    def show_camera_view(self, status):
        """Swap the drop zone for the live camera area."""

        self.clear()

        self.upload_frame.pack_forget()
        self.camera_visible = True
        self.image_button.set_selected(False)
        self.camera_button.set_selected(True)

        # A fresh label each time: a CTkLabel keeps a reference to its last
        # CTkImage and raises TclError if that image was freed meanwhile.
        if self.camera_label is not None:
            self.camera_label.destroy()

        self.camera_label = ctk.CTkLabel(
            self.camera_frame,
            text="",
            fg_color="transparent",
            text_color=ThemeManager.get_color("text"),
        )

        self.camera_buttons.pack(side="bottom", pady=(0, 16))
        self.camera_label.pack(pady=(16, 6))
        self.camera_status.pack(pady=(0, 10))
        self.camera_settings_button.pack_forget()
        self.camera_stop_button.configure(text="Stop Camera")

        self.camera_frame.pack(
            after=self.tiles,
            fill="x",
            padx=CARD_PAD,
        )

        self.camera_image = None
        self.set_camera_status(status)

    def set_camera_status(self, text, error=False):
        theme = ThemeManager.get_theme()
        self.camera_status.configure(
            text=text,
            text_color=theme["danger"] if error else theme["text_secondary"]
        )

    def show_camera_frame(self, rgb):
        """Show one preview frame (RGB ndarray) in the camera area."""

        if self.camera_label is None:
            return

        frame = Image.fromarray(rgb)
        frame.thumbnail((440, 230))

        self.camera_image = ctk.CTkImage(
            light_image=frame,
            dark_image=frame,
            size=frame.size
        )

        self.camera_label.configure(image=self.camera_image)

    def show_camera_error(self, text):
        """Replace the preview with a message and a shortcut to the privacy settings."""

        if self.camera_label is not None:
            self.camera_label.destroy()
            self.camera_label = None
        self.camera_image = None
        self.set_camera_status(text, error=True)
        self.camera_stop_button.configure(text="Close")
        self.camera_settings_button.pack(side="left", padx=6)

    def hide_camera_view(self):

        if not self.camera_visible:
            return

        self.camera_visible = False
        self.camera_button.set_selected(False)
        self.image_button.set_selected(True)
        self.camera_frame.pack_forget()
        if self.camera_label is not None:
            self.camera_label.destroy()
            self.camera_label = None
        self.camera_status.pack_forget()
        self.camera_buttons.pack_forget()
        self.upload_frame.pack(
            after=self.tiles,
            fill="x",
            padx=CARD_PAD,
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

        self.load_path(path)

    # ======================================================

    def load_path(self, path):
        """Use an image file (chosen in the dialog or dropped onto the card)."""

        self.image_path = path

        self.show_preview()

        if self.upload_callback:
            self.upload_callback(path)

    def set_drop_hint(self, enabled):
        """Mention drag & drop in the idle text when it is available."""

        if enabled:
            self.idle_title = "Drop a QR image here"
            self.idle_subtitle = "or click to browse your files"
        else:
            self.idle_title = "Select a QR image"
            self.idle_subtitle = "Click to browse your files"

        if not self.has_content and not self.camera_visible:
            self.title_label.configure(text=self.idle_title)
            self.subtitle.configure(text=self.idle_subtitle)

    # ======================================================

    def show_preview(self):
        """Preview the chosen file (self.image_path)."""

        name = os.path.basename(self.image_path)

        try:
            image = Image.open(self.image_path).copy()
        except (OSError, Image.DecompressionBombError) as e:
            # cv2 may still decode it; only the preview is unavailable.
            print(f"[ScanUploadCard] no preview for {name}: {e}")
            image = None

        self._render_preview(image, name)

    # ======================================================

    def show_image(self, image, name):
        """Preview an image that is not a file (clipboard, screen region)."""

        self.image_path = None
        self._render_preview(image.copy(), name)

    # ======================================================

    def _render_preview(self, image, name):

        self.has_content = True

        # Remove old preview if exists
        if self.preview_label is not None:
            self.preview_label.destroy()
            self.preview_label = None

        # Hide the upload icon only
        self.icon.pack_forget()

        if image is not None:

            image.thumbnail((170, 170))

            self.preview_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=image.size
            )

            # Show preview
            self.preview_label = ctk.CTkLabel(
                self.placeholder,
                text="",
                text_color=ThemeManager.get_color("text"),
                image=self.preview_image,
                fg_color="transparent"
            )

            self.preview_label.pack(
                pady=(0, 8),
                before=self.title_label
            )

            self.preview_label.bind(
                "<Button-1>",
                lambda e: self.choose_image()
            )

        if len(name) > 28:
            name = name[:25] + "..."

        self.title_label.configure(
            text=name
        )

        self.subtitle.configure(
            text="Click 'Replace Image' to choose another QR code"
        )

        self.browse_button.configure(
            text="Replace Image"
        )

        self.upload_frame.set_solid(True)

        theme = ThemeManager.get_theme()

        if not hasattr(self, "clear_button"):

            self.clear_button = ctk.CTkButton(
                self,
                text=f"{icons.icon('delete')}  Clear Image",
                width=150,
                height=36,
                corner_radius=11,
                fg_color="transparent",
                border_width=1,
                hover_color=theme["card_hover"],
                border_color=theme["border"],
                text_color=theme["danger"],
                font=("Segoe UI", 12),
                command=self.clear
            )

            self.clear_button.pack(
                anchor="w",
                padx=CARD_PAD,
                pady=(12, 0),
                before=self.tips
            )

    # ======================================================

    def clear(self):

        self.image_path = None
        self.has_content = False
        self.preview_image = None

        # Remove preview
        if self.preview_label is not None:
            self.preview_label.destroy()
            self.preview_label = None

        # Bring the upload icon back
        self.icon.pack(
            pady=(0, 8),
            before=self.title_label
        )

        self.title_label.configure(
            text=self.idle_title
        )

        self.subtitle.configure(
            text=self.idle_subtitle
        )

        self.browse_button.configure(
            text="Browse Image"
        )

        self.upload_frame.set_solid(False)

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

        super().refresh_theme()
        theme = ThemeManager.get_theme()

        self.upload_frame.apply_theme()

        self.title_label.configure(
            text_color=theme["text"]
        )

        self.subtitle.configure(
            text_color=theme["text_secondary"]
        )

        self.icon.configure(image=self._upload_icon())

        self.supported_label.configure(
            text_color=theme["text_secondary"]
        )

        for label in self.tip_labels:
            label.configure(text_color=theme["text_secondary"])

        self.browse_button.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"]
        )

        for tile in (self.image_button, self.camera_button,
                     self.region_button, self.paste_button):
            tile.apply_theme()

        self.camera_frame.configure(
            fg_color=theme["segment_bg"],
            border_color=theme["primary"]
        )
        self.camera_stop_button.configure(
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["danger"]
        )
        self.camera_settings_button.configure(
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
