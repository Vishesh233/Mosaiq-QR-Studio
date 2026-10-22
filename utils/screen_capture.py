"""Image sources for scanning that are not files on disk: the clipboard and the screen."""

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
