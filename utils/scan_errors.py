class ScanError(Exception):
    """The input could not be read as an image (not the same as "no QR in it")."""


class ScannerUnavailable(ScanError):
    """Scanning cannot run on this PC (OpenCV failed to load). The message is for the user."""
