import customtkinter as ctk

from ui.components.hero_section import HeroSection
from ui.components.scan_upload_card import ScanUploadCard
from ui.components.scan_result_card import ScanResultCard
from utils.qr_scanner import QRScanner, ScanError
from utils.screen_capture import ClipboardImageError, grab_clipboard_image


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