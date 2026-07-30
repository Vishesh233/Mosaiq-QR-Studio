from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_H


class QRGenerator:
    """
    Reusable QR Code Generator.

    Responsibilities:
    - Generate QR Code
    - Apply custom colors
    - Embed optional logo
    - Return PIL Image

    No UI code should exist here.
    """

    def __init__(
        self,
        box_size=10,
        border=4,
        error_correction=ERROR_CORRECT_H,
    ):
        self.box_size = box_size
        self.border = border
        self.error_correction = error_correction

    # =====================================================

    def generate(
        self,
        data: str,
        qr_color="#000000",
        bg_color="#FFFFFF",
        logo_path=None,
    ):
        """
        Generate a QR Code.

        Parameters
        ----------
        data : str
            Text or URL.

        qr_color : str
            Foreground color.

        bg_color : str
            Background color.

        logo_path : str | None
            Optional logo image path.

        Returns
        -------
        PIL.Image.Image
        """

        if not data or not data.strip():
            raise ValueError("QR data cannot be empty.")

        qr = qrcode.QRCode(
            version=None,
            error_correction=self.error_correction,
            box_size=self.box_size,
            border=self.border,
        )

        qr.add_data(data)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color=qr_color,
            back_color=bg_color,
        ).convert("RGBA")

        if logo_path:
            image = self._add_logo(image, logo_path)

        return image

    # =====================================================

    def _add_logo(self, qr_image, logo_path):
        """
        Embed logo in the center of the QR.
        """

        logo = Image.open(logo_path).convert("RGBA")

        qr_width, qr_height = qr_image.size

        logo_size = qr_width // 5

        logo.thumbnail(
            (logo_size, logo_size),
            Image.Resampling.LANCZOS,
        )

        x = (qr_width - logo.width) // 2
        y = (qr_height - logo.height) // 2

        qr_image.paste(
            logo,
            (x, y),
            logo,
        )

        return qr_image

    # =====================================================

    @staticmethod
    def save(image, filepath):
        """
        Save generated QR image.
        """

        image.save(filepath)

    # =====================================================

    @staticmethod
    def resize(image, size=300):
        """
        Resize image for preview.
        """

        return image.resize(
            (size, size),
            Image.Resampling.LANCZOS,
        )