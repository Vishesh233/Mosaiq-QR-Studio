import cv2
import numpy as np
from PIL import Image


class ScanError(Exception):
    """The input could not be read as an image (not the same as "no QR in it")."""


class QRScanner:

    @staticmethod
    def decode(image_path):
        """Decode the QR code in an image file.

        Returns the text, or None when the image holds no readable QR code.
        Raises ScanError when the file cannot be read as an image.
        """
        try:
            raw = np.fromfile(image_path, dtype=np.uint8)
        except OSError as e:
            raise ScanError(f"Could not read the file: {e.strerror or e}") from e

        # imdecode (not imread) so paths with non-ASCII characters work.
        image = cv2.imdecode(raw, cv2.IMREAD_COLOR) if raw.size else None

        if image is None:
            raise ScanError("This file is not a readable image.")

        return QRScanner.decode_image(image)

    @staticmethod
    def decode_image(image, thorough=True):
        """Decode a QR code from a PIL image or a BGR/grayscale ndarray.

        thorough=False tries the frame as-is only (used per camera frame).
        Returns the text, or None when no QR code is found.
        """
        gray = QRScanner._to_gray(image)
        detector = cv2.QRCodeDetector()

        for candidate in QRScanner._candidates(gray, thorough):
            data, points, _ = detector.detectAndDecode(candidate)
            if points is not None and data:
                return data

        return None

    # ==================================================

    @staticmethod
    def _to_gray(image):

        if isinstance(image, Image.Image):
            if image.mode in ("RGBA", "LA", "P"):
                rgba = image.convert("RGBA")
                flat = Image.new("RGB", rgba.size, "white")
                flat.paste(rgba, mask=rgba.getchannel("A"))
                image = flat
            array = np.asarray(image.convert("L"))
            return np.ascontiguousarray(array)

        if image.ndim == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        return image

    @staticmethod
    def _candidates(gray, thorough):

        yield gray

        if not thorough:
            return

        height, width = gray.shape[:2]
        longest = max(height, width)

        # A quiet zone is required; screenshots are often cropped tight.
        pad = max(20, longest // 8)
        yield cv2.copyMakeBorder(
            gray, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255
        )

        if longest < 1000:
            yield cv2.resize(
                gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
            )

        if longest > 1600:
            scale = 1200 / longest
            yield cv2.resize(
                gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
            )

        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        yield binary
