from PIL import Image
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from qrcode.exceptions import DataOverflowError

from utils import qr_render
from utils.qr_render import QRStyle


class QRGenerator:
    """
    Reusable QR Code Generator.

    Responsibilities:
    - Generate QR Code (module shapes, eye shapes, gradient, colours)
    - Embed optional logo
    - Return PIL Image

    No UI code should exist here. Drawing lives in utils/qr_render.py.
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

    def matrix(self, data: str):
        """The QR as rows of bools (quiet zone not included), and its version number."""

        if not data or not data.strip():
            raise ValueError("QR data cannot be empty.")

        qr = qrcode.QRCode(
            version=None,
            error_correction=self.error_correction,
            box_size=self.box_size,
            border=0,
        )

        qr.add_data(data)

        try:
            qr.make(fit=True)
        except (DataOverflowError, ValueError) as e:
            # qrcode reports "too big even for version 40" as either one.
            raise ValueError(
                "There is too much data for one QR code. "
                "Shorten the text and try again."
            ) from e

        return qr.get_matrix(), qr.version

    # =====================================================

    def generate(
        self,
        data: str,
        qr_color="#000000",
        bg_color="#FFFFFF",
        logo_path=None,
        style: QRStyle = None,
    ):
        """
        Generate a QR Code.

        Parameters
        ----------
        data : str
            Text or URL.

        qr_color, bg_color : str
            Foreground / background colour (ignored when ``style`` is given).

        logo_path : str | None
            Optional logo image path.

        style : QRStyle | None
            Shapes, gradient, colours and logo size.

        Returns
        -------
        PIL.Image.Image
        """

        style = style or QRStyle(fg=qr_color, bg=bg_color)
        matrix, _version = self.matrix(data)

        logo = Image.open(logo_path) if logo_path else None
        try:
            return qr_render.render(
                matrix, style, box_size=self.box_size, border=self.border, logo=logo
            )
        finally:
            if logo is not None:
                logo.close()

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
