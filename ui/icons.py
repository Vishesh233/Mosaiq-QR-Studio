"""Central icon registry for QR Code Studio v2.

Icons use the Windows "Segoe MDL2 Assets" glyph set (ships with Windows 10/11),
so there are NO external icon/image dependencies. If the font is unavailable,
callers fall back to clean text labels so the UI never breaks.

Glyph codes are Segoe MDL2 Assets Private Use Area codepoints.
"""
import tkinter
import tkinter.font as tkfont

from config import FONT_ICON

# Logical name -> (MDL2 glyph, plain-text fallback)
ICONS = {
    "generate": ("\uE71E", "Generate"),
    "scan": ("\uEC4E", "Scan"),
    "settings": ("\uE713", "Settings"),
    "theme": ("\uE790", "Theme"),
    "copy": ("\uE8C8", "Copy"),
    "save": ("\uE74E", "Save"),
    "delete": ("\uE74D", "Delete"),
    "link": ("\uE71B", "Link"),
    "text": ("\uE8C0", "Text"),
    "upload": ("\uE898", "Upload"),
    "image": ("\uEB9F", "Image"),
    "open": ("\uE8A7", "Open"),
    "check": ("\uE73E", "OK"),
    "info": ("\uE946", "Info"),
    "app": ("\uE71D", "QR"),
}

_PROBE_ROOT = None
_font_available = None


def _existing_root():
    """Return an already-created default Tk root, if any (no new root made)."""
    return getattr(tkinter, "_default_root", None)


def _get_probe_root():
    """Return a root usable for font probing.

    Prefers an already-created default root (e.g. the app's CTk window) so we
    never create a second Tk root alongside the real application window.
    """
    global _PROBE_ROOT
    existing = _existing_root()
    if existing is not None:
        return existing
    if _PROBE_ROOT is None:
        try:
            _PROBE_ROOT = tkinter.Tk()
            _PROBE_ROOT.withdraw()
        except Exception:
            _PROBE_ROOT = False  # sentinel: could not create
    return _PROBE_ROOT or None


def has_icons():
    """True if the MDL2 icon font is available on this machine."""
    global _font_available
    if _font_available is not None:
        return _font_available
    root = _get_probe_root()
    if root is None:
        _font_available = False
        return _font_available
    try:
        _font_available = FONT_ICON in set(tkfont.families(root))
    except Exception:
        _font_available = False
    return _font_available


def icon_font(size=16):
    """Return a font tuple for an icon glyph of the given point size."""
    return (FONT_ICON, size)


def glyph(name):
    """Return the MDL2 glyph for a logical icon name ('' if unknown)."""
    return ICONS.get(name, ("", ""))[0]


def icon(name):
    """Return the display string for an icon.

    Uses the MDL2 glyph when the font is available; otherwise returns the
    plain-text fallback so the control remains understandable.
    """
    g, text = ICONS.get(name, ("", ""))
    if has_icons() and g:
        return g
    return text

