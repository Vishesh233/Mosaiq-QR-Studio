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

        win32clipboard.OpenClipboard()

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(
                win32clipboard.CF_DIB,
                data
            )
        finally:
            win32clipboard.CloseClipboard()