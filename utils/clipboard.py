import time
from io import BytesIO

from PIL import Image
import win32clipboard


class ClipboardManager:

    @staticmethod
    def copy_image(image):
        """
        Copy PIL Image to Windows clipboard.
        """

        output = BytesIO()

        bmp = image.convert("RGB")
        bmp.save(output, "BMP")

        data = output.getvalue()[14:]

        output.close()

        ClipboardManager._open()

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(
                win32clipboard.CF_DIB,
                data
            )
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def _open(attempts=40, pause=0.05):
        """OpenClipboard, retrying: another program (clipboard manager, remote
        desktop) may hold the clipboard for a moment. Raises after ~2 s."""

        for attempt in range(attempts):
            try:
                win32clipboard.OpenClipboard()
                return
            except win32clipboard.error:
                if attempt == attempts - 1:
                    raise
                time.sleep(pause)
