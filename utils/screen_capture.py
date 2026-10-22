"""Image sources for scanning that are not files on disk: the clipboard and the screen."""

import ctypes
import os

from PIL import Image, ImageGrab

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


class ClipboardImageError(Exception):
    """The clipboard holds no usable image (message is meant for the user)."""


def grab_clipboard_image():
    """Return the image on the clipboard as a PIL image.

    Handles a copied bitmap (Snipping Tool, Print Screen, "Copy image") and an
    image file copied in Explorer. Raises ClipboardImageError otherwise.
    """
    try:
        data = ImageGrab.grabclipboard()
    except OSError as e:
        raise ClipboardImageError(f"Could not read the clipboard: {e}") from e

    if isinstance(data, Image.Image):
        return data

    if isinstance(data, list):
        for path in data:
            if os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS:
                try:
                    with Image.open(path) as opened:
                        return opened.copy()
                except OSError as e:
                    raise ClipboardImageError(
                        f"The copied file is not a readable image: {e}"
                    ) from e
        raise ClipboardImageError(
            "The clipboard has files, but none of them is an image "
            "(PNG, JPG, WEBP or BMP)."
        )

    raise ClipboardImageError(
        "There is no image on the clipboard. Copy a QR code first, for "
        "example with Windows Snipping Tool (Win + Shift + S), then paste."
    )


# ==================================================
# Screen capture (used by the region selector)
# ==================================================

MIN_REGION = 8   # smaller selections are treated as an accidental click


def virtual_screen_origin():
    """Top-left of the whole desktop (negative when a monitor is left of / above the main one)."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)


def grab_virtual_screen():
    """Capture every monitor. Returns (RGB image, (left, top) of the desktop)."""
    try:
        image = ImageGrab.grab(all_screens=True)
    except OSError as e:
        raise ClipboardImageError(f"Could not capture the screen: {e}") from e
    return image.convert("RGB"), virtual_screen_origin()


def region_to_crop(rect, shown_size, image_size):
    """Map a rectangle dragged on the overlay to a crop box of the screenshot.

    rect:       (x0, y0, x1, y1) in overlay pixels, any corner order
    shown_size: (width, height) of the overlay as Windows really made it
    image_size: (width, height) of the screenshot

    The two sizes differ when Windows scales the overlay (DPI virtualisation,
    125% / 150% displays); the box is scaled back to screenshot pixels.
    Returns (left, top, right, bottom) or None when the area is too small.
    """
    x0, y0, x1, y1 = rect
    sx = image_size[0] / shown_size[0]
    sy = image_size[1] / shown_size[1]

    left = max(0, int(round(min(x0, x1) * sx)))
    right = min(image_size[0], int(round(max(x0, x1) * sx)))
    top = max(0, int(round(min(y0, y1) * sy)))
    bottom = min(image_size[1], int(round(max(y0, y1) * sy)))

    if right - left < MIN_REGION or bottom - top < MIN_REGION:
        return None
    return left, top, right, bottom
