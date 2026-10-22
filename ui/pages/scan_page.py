import os
import traceback

import customtkinter as ctk

from ui.components.hero_section import HeroSection
from ui.components.scan_upload_card import ScanUploadCard
from ui.components.scan_result_card import ScanResultCard
from utils.qr_scanner import QRScanner, ScanError
from PIL import Image

from ui.region_selector import RegionSelector
from utils.screen_capture import IMAGE_EXTENSIONS
from utils.camera_scanner import CameraScanner, CvFrameSource
from utils.screen_capture import (
    ClipboardImageError, grab_clipboard_image, grab_virtual_screen
)
from utils.theme_manager import ThemeManager


class ScanPage(ctk.CTkFrame):

    NOT_FOUND = (
        "No QR code found in this image. Try a sharper or closer picture."
    )

    def __init__(self, parent):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.build_ui()
        self.upload_card.set_upload_callback(self.on_image_selected)
        self.upload_card.paste_button.configure(
            command=self.paste_from_clipboard
        )
        self.upload_card.region_button.configure(
            command=self.scan_screen_region
        )
        self.region_selector = None
        self._window_state = "normal"
        self.drop_enabled = False

        # Camera: the scanner runs on its own thread; poll_id is the after() id
        # of the UI-side poll. camera_factory exists so tests can supply a fake.
        self.camera = None
        self.camera_factory = CvFrameSource.open
        self._camera_poll_id = None
        self._last_camera_frame = None
        self.upload_card.camera_button.configure(command=self.start_camera)
        self.upload_card.camera_stop_button.configure(command=self.stop_camera)
        self.upload_card.camera_settings_button.configure(
            command=self.open_camera_settings
        )
        # Ctrl+V pastes an image while this page is showing. The Generate page
        # has text entries, so the shortcut must stay inert there.
        self.winfo_toplevel().bind("<Control-v>", self._on_ctrl_v, add="+")

    # ==================================================

    def build_ui(self):

        # ---------------- Hero ---------------- #

        hero_wrapper = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        hero_wrapper.pack(
            fill="x",
            padx=(185, 0),   
            pady=(10, 25)
        )


        self.hero = HeroSection(
            hero_wrapper,
            title="Scan a QR code",
            subtitle=(
                "Upload or paste an image to decode links, text, "
                "UPI, WiFi, contacts, email and SMS."
            ),
            
        )

        self.hero.pack(
            anchor="w",
            fill="x",
            pady=(0, 12)
        )

        # ---------------- Main Layout ---------------- #

        self.content = ctk.CTkFrame(
            self,
            fg_color="transparent",
            width=1320,
            height=560
        )

        self.content.pack(
            anchor="center",
            pady=(0, 10),
        )

        # Left Card

        self.upload_card = ScanUploadCard(self.content)

        self.upload_card.pack(
            side="left",
            padx=(0, 28)
        )

        # Right Card

        self.result_card = ScanResultCard(self.content)

        self.result_card.pack(
            side="left",
            padx=(12, 0)
        )

    # ==================================================

    def on_image_selected(self, image_path):

        self.stop_camera()

        if not image_path:
            self.result_card.clear()
            return

        try:
            result = QRScanner.decode(image_path)
        except ScanError as e:
            self.result_card.set_message(str(e))
            return

        if result:
            self.result_card.set_result(result)
        else:
            self.result_card.set_message(self.NOT_FOUND)

    # ==================================================
    # Camera
    # ==================================================

    def start_camera(self):

        if self.camera is not None:
            return

        self.result_card.clear()
        self.upload_card.show_camera_view("Starting camera...")

        self.camera = CameraScanner(source_factory=self.camera_factory)
        self.camera.start()
        self._camera_poll_id = self.after(33, self._poll_camera)

    def _poll_camera(self):

        self._camera_poll_id = None

        if self.camera is None:
            return

        frame, events = self.camera.poll()

        if frame is not None:
            self._last_camera_frame = frame
            self.upload_card.show_camera_frame(frame)

        for kind, value in events:

            if kind == "running":
                self.upload_card.set_camera_status(
                    "Hold a QR code in front of the camera."
                )

            elif kind == "found":
                self._camera_found(value)
                return

            elif kind == "error":
                self._camera_failed(value)
                return

            elif kind == "stopped":
                self.stop_camera()
                return

        self._camera_poll_id = self.after(33, self._poll_camera)

    def _camera_found(self, text):

        captured = self._last_camera_frame
        self.stop_camera()

        if captured is not None:
            self.upload_card.show_image(Image.fromarray(captured), "Camera capture")

        self.result_card.set_result(text)

    def _camera_failed(self, message):

        self._release_camera()
        self.upload_card.show_camera_error(message)
        self.result_card.set_message("The camera could not be used.")

    def _release_camera(self):
        """Stop the worker and make sure the camera is released (no UI changes)."""

        if self._camera_poll_id is not None:
            self.after_cancel(self._camera_poll_id)
            self._camera_poll_id = None

        if self.camera is not None:
            self.camera.stop()
            self.camera = None

        self._last_camera_frame = None

    def stop_camera(self):
        """Stop the camera and go back to the image area. Safe to call any time."""

        self._release_camera()
        self.upload_card.hide_camera_view()

    def open_camera_settings(self):

        try:
            os.startfile("ms-settings:privacy-webcam")
        except OSError as e:
            self.upload_card.set_camera_status(
                f"Could not open Settings: {e}", error=True
            )

    def on_hide(self):
        """The Scan tab is being left: never keep the camera running."""
        self.stop_camera()

    def shutdown(self):
        """The app is closing."""
        self.stop_camera()

    # ==================================================
    # Drag & drop
    # ==================================================

    def enable_drop(self, unavailable_reason):
        """Accept image files dropped on this page (None = drag & drop works)."""

        self.drop_enabled = unavailable_reason is None
        self.upload_card.set_drop_hint(self.drop_enabled)

        if not self.drop_enabled:
            return

        from tkinterdnd2 import DND_FILES

        # OLE hands a drop to the nearest registered parent window, so one
        # registration covers every widget on the page, including ones
        # created later (preview, camera view).
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):

        paths = self.winfo_toplevel().tk.splitlist(event.data)
        self.scan_dropped_files(list(paths))
        return event.action

    def scan_dropped_files(self, paths):

        images = [
            p for p in paths
            if os.path.splitext(p)[1].lower() in IMAGE_EXTENSIONS
        ]

        if not images:
            self.stop_camera()
            self.result_card.set_message(
                "That is not an image file. Drop a PNG, JPG, WEBP or BMP."
            )
            return

        self.stop_camera()
        self.upload_card.load_path(images[0])

    def _on_ctrl_v(self, event=None):

        if self.winfo_ismapped():
            self.paste_from_clipboard()

    def paste_from_clipboard(self):

        self.stop_camera()

        try:
            image = grab_clipboard_image()
        except ClipboardImageError as e:
            self.result_card.set_message(str(e))
            return

        self.upload_card.show_image(image, "Pasted image")
        self.scan_image(image)

    # How long the main window gets to disappear before the screen is grabbed.
    HIDE_DELAY_MS = 350

    def scan_screen_region(self):
        """Hide the app, freeze the screen, let the user drag around a QR code."""

        if self.region_selector is not None:
            return

        self.stop_camera()
        self.region_selector = "starting"
        root = self.winfo_toplevel()
        self._window_state = root.state()      # "zoomed" when maximized
        root.withdraw()
        root.after(self.HIDE_DELAY_MS, self._begin_region_select)

    def _begin_region_select(self):

        root = self.winfo_toplevel()

        try:
            screenshot, origin = grab_virtual_screen()
            self.region_selector = RegionSelector(
                root, screenshot, origin, self._end_region_select,
                accent=ThemeManager.get_theme()["primary"]
            )
        except Exception as e:
            # The window is hidden at this point: always bring it back.
            traceback.print_exc()
            self._end_region_select(None, f"Screen capture failed: {e}")

    def _end_region_select(self, image, message):

        self.region_selector = None
        root = self.winfo_toplevel()
        root.deiconify()
        if self._window_state == "zoomed":
            root.state("zoomed")               # deiconify alone drops maximize
        root.lift()
        root.focus_force()

        if image is not None:
            self.upload_card.show_image(image, "Screen region")
            self.scan_image(image)
        elif message:
            self.result_card.set_message(message)

    def scan_image(self, image):
        """Decode a PIL image (clipboard, screen region, drop) into the result panel."""

        result = QRScanner.decode_image(image)

        if result:
            self.result_card.set_result(result)
        else:
            self.result_card.set_message(self.NOT_FOUND)

    def refresh_theme(self):

        if hasattr(self.hero, "refresh_theme"):
            self.hero.refresh_theme()

        if hasattr(self.upload_card, "refresh_theme"):
            self.upload_card.refresh_theme()

        if hasattr(self.result_card, "refresh_theme"):
            self.result_card.refresh_theme()