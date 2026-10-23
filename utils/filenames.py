"""File names for saved QR codes: defaults per type and safe handling of anything typed.

Pure functions (no UI), so the Save dialog, Bulk Create and the tests share one behaviour.
"""
import os
import re

# Default stem (name without extension) per QR type shown in the Save dialog.
DEFAULT_STEMS = {
    "URL / Text": "url_qr",
    "UPI Payment": "upi_qr",
    "WiFi": "wifi_qr",
    "Contact": "contact_qr",
    "Email": "email_qr",
    "SMS": "sms_qr",
}
FALLBACK_STEM = "qr_code"

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DOT_RUN = re.compile(r"\.{2,}")
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_STEM = 100


def default_stem(type_name):
    """Default file name (without extension) for a QR type, e.g. 'upi_qr'."""
    return DEFAULT_STEMS.get(type_name, FALLBACK_STEM)


def safe_stem(name, fallback=FALLBACK_STEM):
    """A usable file name stem for anything the user typed.

    Illegal characters become '_'; empty names, names made only of dots/spaces and
    Windows device names (CON, NUL, COM1 ...) fall back to ``fallback``.
    """
    stem = _ILLEGAL.sub("_", str(name or "")).strip().rstrip(". ")
    if not stem or stem.split(".")[0].upper() in _RESERVED:
        return fallback
    return _DOT_RUN.sub("_", stem)[:MAX_STEM]               # no ".." left, even without slashes


def with_extension(path, extension):
    """``path`` ending in ``extension`` ('.png'); an existing different one is kept as typed
    only when it is the chosen extension, otherwise the extension is appended."""
    extension = extension.lower()
    if os.path.splitext(path)[1].lower() == extension:
        return path
    return path + extension
