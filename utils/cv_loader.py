"""Lazy, guarded access to OpenCV.

OpenCV (scanning and the webcam) is only loaded the first time it is needed, so the
rest of the app (Generate, themes, the intro) never depends on it. If it cannot be
loaded, for example on Windows N editions without the Media Feature Pack (mf.dll is
missing), load() raises ScannerUnavailable with a message for the user, and the
cause is written to the error log.
"""
import threading

from utils.app_log import get_logger
from utils.scan_errors import ScannerUnavailable

MEDIA_PACK_MESSAGE = (
    "Scanning needs the Windows Media Feature Pack. "
    "Install it from Settings → Apps → Optional features."
)

_lock = threading.Lock()
_module = None
_failure = None


def load():
    """Return the cv2 module, importing it on first use. Raises ScannerUnavailable."""
    global _module, _failure

    if _module is not None:
        return _module
    if _failure is not None:
        raise _failure

    with _lock:
        if _module is not None:
            return _module
        if _failure is not None:
            raise _failure

        try:
            import cv2
        except (ImportError, OSError) as e:
            get_logger().error("OpenCV could not be loaded: %s", e, exc_info=True)
            if "DLL load failed" in str(e):
                message = MEDIA_PACK_MESSAGE
            else:
                message = (
                    "Scanning could not start because a required component failed "
                    "to load. Details are in mosaiq.log next to the app settings."
                )
            _failure = ScannerUnavailable(message)
            raise _failure from e

        _module = cv2
        return _module


def available():
    """True when scanning can run (loads OpenCV if it has not been loaded yet)."""
    try:
        load()
    except ScannerUnavailable:
        return False
    return True


def reset_for_tests():
    global _module, _failure
    _module = None
    _failure = None
