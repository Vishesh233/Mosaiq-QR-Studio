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
        self.generated_data = None          # the text behind generated_image
        self._refresh_job = None

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

        # Changing a colour, shape or the logo updates a QR that is already showing.
        self.design_card.change_callback = self.on_design_changed

    def current_style(self):
        return self.design_card.get_style()

    def on_design_changed(self):
        """Redraw the preview with the new design (same text) shortly after the last change."""
        if self.generated_data is None:
            return
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(120, self._redraw_preview)

    def _redraw_preview(self):
        self._refresh_job = None
        if self.generated_data is None:
            return
        try:
            self._show(self.generated_data)
        except Exception as e:
            messagebox.showerror("QR Generation Failed", str(e))

    def _show(self, data):
        image = self.generator.generate(
            data=data,
            style=self.current_style(),
            logo_path=self.logo_card.get_logo_path(),
        )
        self.generated_image = image
        self.generated_data = data
        self.preview_card.set_image(image)
        self.action_buttons.enable_export_buttons()

    def generate_qr(self):

        # Get content
        try:
            data = self.content_card.get_content()
        except ValueError as e:
            messagebox.showwarning("Check Your Details", str(e))
            return

        try:

            self._show(data)

        except Exception as e:

            messagebox.showerror(
                "QR Generation Failed",
                str(e)
            )

    def clear_form(self):

        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

        # Clear entries
        self.content_card.clear()

        # Reset colours, style and logo
        self.design_card.reset()

        # Reset preview
        self.preview_card.clear_preview()

        # Remove generated image
        self.generated_image = None
        self.generated_data = None

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
