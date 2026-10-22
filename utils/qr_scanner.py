import time

import numpy as np
from PIL import Image

from utils import cv_loader
from utils.scan_errors import ScanError, ScannerUnavailable  # noqa: F401  (re-exported)

# OpenCV is loaded on first use (cv_loader.load()), not when the app starts, and a
# failure to load it surfaces as ScannerUnavailable instead of crashing the app.


# ----------------------------------------------------------------------
# Decoding recipes. Real-world QR codes are often light-on-dark (dark-mode
# payment apps), blurred (a webcam looking at a phone) or drawn with dotted
# modules, and OpenCV's default detector only handles dark-on-light. Each
# recipe is (name, preparation, detector); the detector returns the text.
# ----------------------------------------------------------------------

def _invert(gray):
    return cv_loader.load().bitwise_not(gray)


def _sharpen(gray):
    cv2 = cv_loader.load()
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    return cv2.addWeighted(gray, 2.0, blurred, -1.0, 0)


def _adaptive(gray):
    cv2 = cv_loader.load()
    # The block size follows the image so it spans roughly one QR module row.
    block = max(21, (max(gray.shape[:2]) // 32) | 1)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, 8
    )


def _plain(gray):
    return gray


RECIPES = (
    # (name, prepare, detector)  -- ordered by how often they win and how cheap they are
    ("aruco", _plain, "aruco"),
    ("aruco inverted", _invert, "aruco"),
    ("threshold inverted", lambda g: _adaptive(_invert(g)), "classic"),
    ("threshold", _adaptive, "classic"),
    ("aruco inverted sharpened", lambda g: _sharpen(_invert(g)), "aruco"),
    ("aruco sharpened", _sharpen, "aruco"),
    ("classic", _plain, "classic"),
    ("classic inverted", _invert, "classic"),
)

# Recipes a live camera cycles through (the slow "classic" ones are left out).
CAMERA_RECIPES = 6

_reported = set()


class QRScanner:

    @staticmethod
    def decode(image_path):
        """Decode the QR code in an image file.

        Returns the text, or None when the image holds no readable QR code.
        Raises ScanError when the file cannot be read as an image, and
        ScannerUnavailable when OpenCV cannot be loaded on this PC.
        """
        cv2 = cv_loader.load()

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
    def decode_image(image, thorough=True, variant=None, budget=6.0):
        """Decode a QR code from a PIL image or a BGR/grayscale ndarray.

        thorough=True   tries every recipe on several versions of the image
                        (stills: files, clipboard, screen region).
        variant=n       tries only recipe n (modulo CAMERA_RECIPES); a camera
                        loop passes a counter so each frame costs one attempt.
        budget          seconds a thorough scan may take before giving up (a
                        picture with QR-like patterns that never decode can
                        make every recipe slow).
        Returns the text, or None when no QR code is found. Raises
        ScannerUnavailable when OpenCV cannot be loaded on this PC.
        """
        cv2 = cv_loader.load()
        gray = QRScanner._to_gray(image)
        deadline = time.perf_counter() + budget

        if variant is not None:
            recipes = [RECIPES[variant % CAMERA_RECIPES]]
            images = [gray]
        elif thorough:
            recipes = RECIPES
            images = QRScanner._candidates(gray)
        else:
            recipes = RECIPES[:1]
            images = [gray]

        detectors = {}

        for candidate in images:
            for name, prepare, kind in recipes:
                if time.perf_counter() > deadline:
                    return None
                if kind not in detectors:
                    detectors[kind] = (
                        cv2.QRCodeDetectorAruco() if kind == "aruco"
                        else cv2.QRCodeDetector()
                    )
                text = QRScanner._try(name, prepare, detectors[kind], candidate)
                if text:
                    return text

        return None

    # ==================================================

    @staticmethod
    def _try(name, prepare, detector, gray):

        cv2 = cv_loader.load()

        try:
            data, points, _ = detector.detectAndDecode(prepare(gray))
        except cv2.error as e:
            # OpenCV raises on some degenerate inputs; that only means this
            # recipe found nothing. Say so once per message, never silently.
            message = str(e).strip().splitlines()[-1][:120]
            if (name, message) not in _reported:
                _reported.add((name, message))
                print(f"[QRScanner] {name}: {message}")
            return None

        return data if data and points is not None else None

    @staticmethod
    def _to_gray(image):

        cv2 = cv_loader.load()

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
    def _candidates(gray):
        """The image itself, then versions that help hard cases."""

        cv2 = cv_loader.load()

        yield gray

        height, width = gray.shape[:2]
        longest = max(height, width)

        # A quiet zone is required; screenshots are often cropped tight. Pad
        # with white (dark-on-light codes) and with black (light-on-dark).
        # (Skipped for very large images, where it only adds seconds.)
        pad = max(20, longest // 8)
        for shade in (255, 0):
            if longest <= 2000:
                yield cv2.copyMakeBorder(
                    gray, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=shade
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
