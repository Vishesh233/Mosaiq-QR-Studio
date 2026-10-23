"""Where the user's own folders are (Windows keeps Documents wherever the user moved it,
for example into OneDrive)."""
import ctypes
import os
import sys
from ctypes import wintypes

from utils.app_log import get_logger

_FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


class _Guid(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


def documents_folder():
    """The user's Documents folder; ``~\\Documents`` when Windows cannot say."""
    fallback = os.path.join(os.path.expanduser("~"), "Documents")
    if not sys.platform.startswith("win"):
        return fallback
    try:
        guid = _Guid()
        ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(_FOLDERID_DOCUMENTS), ctypes.byref(guid))
        path = ctypes.c_wchar_p()
        ctypes.oledll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path))
        try:
            return path.value or fallback
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    except OSError:
        get_logger().exception("could not ask Windows for the Documents folder")
        return fallback
