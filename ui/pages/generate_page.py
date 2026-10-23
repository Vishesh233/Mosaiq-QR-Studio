import customtkinter as ctk

from ui.components.content_card import ContentCard
from ui.components.design_card import DesignCard
from ui.components.preview_card import PreviewCard
from ui.layout import CARD_GAP, TwoColumnPage
from utils import filenames, history_store, qr_export, self_check
from utils.app_log import get_logger
from utils.qr_generator import QRGenerator
from utils.qr_render import QRStyle
from utils.clipboard import ClipboardManager
from tkinter import messagebox
from tkinter import filedialog


class GeneratePage(TwoColumnPage):

    def __init__(self, parent):

        super().__init__(parent)

        self.generator = QRGenerator()
        self.generated_image = None
        self.generated_data = None          # the text behind generated_image
        self.generated_style = None         # the style and logo it was drawn with (for exports)
        self.generated_logo = None
        self._refresh_job = None
        self._checker = self_check.BackgroundCheck()
        self._check_job = None
        self._badge_type = ""

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
        self.logo_card.limit_provider = self.current_logo_limit

    def current_style(self):
        return self.design_card.get_style()

    def current_logo_limit(self):
        """The safe logo size for what is typed now; None while the content is not valid."""
        try:
            return self.generator.logo_limit(self.content_card.get_content())
        except ValueError:
            return None

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
        # The logo may not be larger than is safe for this code; the slider follows.
        self.logo_card.set_limit(self.generator.logo_limit(data))
        image = self.generator.generate(
            data=data,
            style=self.current_style(),
            logo_path=self.logo_card.get_logo_path(),
        )
        self.generated_image = image
        self.generated_data = data
        self.generated_style = self.current_style()
        self.generated_logo = self.logo_card.get_logo_path()
        self.preview_card.set_image(image, qr_export.pdf_pixels(self.generator, data))
        self.action_buttons.enable_export_buttons()
        self._begin_test_scan(image, data)

    # ------------------------------------------------------------------
    # Test scan: the app reads its own QR back and says so next to the preview
    # ------------------------------------------------------------------

    BADGES = {
        self_check.OK: ("ok", "✓  Scans correctly"),
        self_check.FAIL: ("warn", "⚠  May not scan"),
        self_check.UNAVAILABLE: ("info", "Test scan is not available on this PC"),
        self_check.ERROR: ("info", "Test scan could not run"),
    }

    def _begin_test_scan(self, image, data):
        self._badge_type = self.content_card.type_label()
        self.preview_card.set_badge("Checking the code…", "info")
        self._checker.start(image, data)
        if self._check_job is None:
            self._check_job = self.after(60, self._poll_test_scan)

    def _poll_test_scan(self):
        self._check_job = None
        outcome = self._checker.poll()
        if outcome is None:
            self._check_job = self.after(60, self._poll_test_scan)
            return
        kind, text = self.BADGES[outcome]
        if outcome == self_check.OK and self._badge_type:
            text += f"  ·  {self._badge_type}"
        self.preview_card.set_badge(text, kind)

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
            return

        self._remember(data)

    def _remember(self, data):
        """Keep the code that was just generated in the history (not live redraws)."""
        try:
            history_store.add_generated(
                self.content_card.active_type, data, self.content_card.get_fields(),
                self.generated_style, self.generated_logo, self.generated_image)
        except OSError:
            get_logger().exception("could not save the code to the history")

    # ------------------------------------------------------------------
    # From the History page
    # ------------------------------------------------------------------

    def open_entry(self, entry, remember=False):
        """Show a saved code: its form, look and picture. Nothing is saved unless ``remember``.

        A WiFi code saved without its password fills the form and asks for the password."""
        generated = entry["kind"] == history_store.GENERATED
        if generated:
            self.content_card.load(entry["type"], entry.get("fields") or {})
            self.design_card.load(QRStyle.from_dict(entry.get("style")), entry.get("logo") or None)
        else:
            self.content_card.load("URL / Text", {"url": entry["text"]})
            self.design_card.reset()
        if generated and entry.get("redacted"):
            self._reset_preview()
            messagebox.showwarning(
                "Password needed",
                "This WiFi code was saved without its password. Enter the password, "
                "then press Generate.")
            return
        try:
            self._show(entry["text"])
        except Exception as e:
            messagebox.showerror("QR Generation Failed", str(e))
            return
        if remember:
            self._remember(entry["text"])

    def regenerate_entry(self, entry):
        """Draw a saved code again and add it to the history as a new entry."""
        self.open_entry(entry, remember=True)

    def clear_form(self):

        # Clear entries
        self.content_card.clear()

        # Reset colours, style and logo
        self.design_card.reset()

        self._reset_preview()

    def _reset_preview(self):
        """Empty the preview and forget the generated code (the form is left as it is)."""
        if self._refresh_job is not None:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None
        # Forget a test scan still running
        self._checker.cancel()
        if self._check_job is not None:
            self.after_cancel(self._check_job)
            self._check_job = None
        self.preview_card.clear_preview()

        self.generated_image = None
        self.generated_data = None
        self.generated_style = None
        self.generated_logo = None

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

        fmt = self.preview_card.get_format()
        extension = qr_export.EXTENSIONS[fmt]

        filepath = filedialog.asksaveasfilename(
            title=f"Save QR Code as {fmt}",
            initialfile=f"{self.content_card.default_filename_stem()}{extension}",
            defaultextension=extension,
            filetypes=[qr_export.FILE_TYPES[fmt]]
        )

        if not filepath:
            return

        filepath = filenames.with_extension(filepath, extension)

        try:

            qr_export.export(filepath, fmt, self.generator, self.generated_data,
                             self.generated_style, self.generated_logo)

            messagebox.showinfo(
                "Saved",
                f"QR Code saved as {fmt}."
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
