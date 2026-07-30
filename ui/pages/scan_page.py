import customtkinter as ctk

from ui.components.hero_section import HeroSection
from ui.components.scan_upload_card import ScanUploadCard
from ui.components.scan_result_card import ScanResultCard
from utils.qr_scanner import QRScanner


class ScanPage(ctk.CTkFrame):

    def __init__(self, parent):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.build_ui()
        self.upload_card.set_upload_callback(self.on_image_selected)

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
            title="Scan QR Codes",
            subtitle=(
                "Upload a QR code image to instantly decode URLs, "
                "plain text and other supported QR content." 
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

        result = QRScanner.decode(image_path)

        if result:
            self.result_card.set_result(result)
        else:
            self.result_card.set_result("No QR code found")

    def refresh_theme(self):

        if hasattr(self.hero, "refresh_theme"):
            self.hero.refresh_theme()

        if hasattr(self.upload_card, "refresh_theme"):
            self.upload_card.refresh_theme()

        if hasattr(self.result_card, "refresh_theme"):
            self.result_card.refresh_theme()