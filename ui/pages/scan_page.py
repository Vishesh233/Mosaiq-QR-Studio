import traceback

import customtkinter as ctk

from ui.components.hero_section import HeroSection
from ui.components.scan_upload_card import ScanUploadCard
from ui.components.scan_result_card import ScanResultCard
from utils.qr_scanner import QRScanner, ScanError
from ui.region_selector import RegionSelector
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

    def _on_ctrl_v(self, event=None):

        if self.winfo_ismapped():
            self.paste_from_clipboard()

    def paste_from_clipboard(self):

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