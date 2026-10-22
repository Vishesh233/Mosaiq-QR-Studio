import customtkinter as ctk

from ui.components.content_card import ContentCard
from ui.components.design_card import DesignCard
from ui.components.preview_card import PreviewCard
from ui.layout import CARD_GAP, TwoColumnPage
from utils import filenames
from utils.qr_generator import QRGenerator
from utils.clipboard import ClipboardManager
from tkinter import messagebox
from tkinter import filedialog


class GeneratePage(TwoColumnPage):

    def __init__(self, parent):

        super().__init__(parent)

        self.generator = QRGenerator()
        self.generated_image = None

        # Left column (scrolls): step 1 and step 2
        self.content_card = ContentCard(self.left)
        self.content_card.pack(fill="x", pady=(0, CARD_GAP))

        self.design_card = DesignCard(self.left)
        self.design_card.pack(fill="x")
        self.color_card = self.design_card.colours
        self.logo_card = self.design_card.logo

        # Right column (stays put): live preview with the buttons under it
        self.preview_card = PreviewCard(self.right)
        self.preview_card.pack(fill="both", expand=True)
        self.action_buttons = self.preview_card.actions

        self.action_buttons.set_generate_callback(self.generate_qr)
        self.action_buttons.set_clear_callback(self.clear_form)
        self.action_buttons.set_copy_callback(self.copy_qr)
        self.action_buttons.set_save_callback(self.save_qr)

    def generate_qr(self):

        # Get content
        try:
            data = self.content_card.get_content()
        except ValueError as e:
            messagebox.showwarning("Check Your Details", str(e))
            return

        try:

            image = self.generator.generate(
                data=data,
                qr_color=self.color_card.get_qr_color(),
                bg_color=self.color_card.get_bg_color(),
                logo_path=self.logo_card.get_logo_path()
            )

            self.generated_image = image

            self.preview_card.set_image(image)

            self.action_buttons.enable_export_buttons()

        except Exception as e:

            messagebox.showerror(
                "QR Generation Failed",
                str(e)
            )

    def clear_form(self):

        # Clear entries
        self.content_card.clear()

        # Reset logo
        self.logo_card.reset_logo()

        # Reset colors
        self.color_card.reset_colors()

        # Reset preview
        self.preview_card.clear_preview()

        # Remove generated image
        self.generated_image = None

        # Disable buttons
        self.action_buttons.disable_export_buttons()

    def copy_qr(self):

        if self.generated_image is None:

            messagebox.showwarning(
                "Nothing to Copy",
                "Please generate a QR code first."
            )

            return

        try:

            ClipboardManager.copy_image(
                self.generated_image
            )

            messagebox.showinfo(
                "Copied",
                "QR Code copied to clipboard."
            )

        except Exception as e:

            messagebox.showerror(
                "Copy Failed",
                str(e)
            )

    def save_qr(self):

        if self.generated_image is None:

            messagebox.showwarning(
                "Nothing to Save",
                "Please generate a QR code first."
            )
            return

        filepath = filedialog.asksaveasfilename(
            title="Save QR Code",
            initialfile=f"{self.content_card.default_filename_stem()}.png",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png")
            ]
        )

        if not filepath:
            return

        filepath = filenames.with_extension(filepath, ".png")

        try:

            self.generated_image.save(filepath)

            messagebox.showinfo(
                "Saved",
                "QR Code saved successfully."
            )

        except Exception as e:

            messagebox.showerror(
                "Save Failed",
                str(e)
            )

    def refresh_theme(self):

        super().refresh_theme()
        self.content_card.refresh_theme()
        self.design_card.refresh_theme()
        self.preview_card.refresh_theme()
