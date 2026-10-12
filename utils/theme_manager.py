from config import DEFAULT_THEME
from utils import settings_store


# Widget options that can carry a theme colour (CustomTkinter names).
_COLOR_OPTIONS = (
    "fg_color", "bg_color", "border_color", "text_color", "hover_color",
    "button_color", "button_hover_color", "dropdown_fg_color",
    "dropdown_hover_color", "dropdown_text_color", "placeholder_text_color",
    "progress_color", "scrollbar_button_color", "scrollbar_button_hover_color",
    "text_color_disabled", "selected_color", "selected_hover_color",
    "unselected_color", "unselected_hover_color", "checkmark_color",
)


def _dwm_title_bar(window, dark):
    """Recolour a window's Windows title bar in place (no-op elsewhere)."""
    try:
        import ctypes
        import sys
        from ctypes import wintypes

        if not sys.platform.startswith("win"):
            return
        user32 = ctypes.WinDLL("user32")
        dwmapi = ctypes.WinDLL("dwmapi")
        user32.GetParent.argtypes = (wintypes.HWND,)
        user32.GetParent.restype = wintypes.HWND
        user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT)
        dwmapi.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD,
                                                 ctypes.c_void_p, wintypes.DWORD)
        hwnd = user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE: 20, or 19 before Windows 10 20H1.
        if dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)) != 0:
            dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(value), ctypes.sizeof(value))
        # Repaint the frame: NOSIZE | NOMOVE | NOZORDER | NOACTIVATE | FRAMECHANGED.
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
    except Exception:
        pass


class ThemeManager:
    """
    Handles application themes.

    Every theme is a flat dict of colour tokens plus three settings:
    ``mode`` (CustomTkinter appearance, "Dark" / "Light"), ``on_primary``
    (text on primary buttons) and ``splash`` (the intro palette that matches
    the theme). Within one theme every colour value is unique, which lets
    :meth:`retheme_tree` map any widget colour back to its token.
    """

    THEMES = {

        # ==========================
        # MIDNIGHT (default)
        # ==========================
        "Midnight": {
            "mode": "Dark",
            "splash": "Aqua Mint",

            "background": "#0B0D12",
            "navbar": "#0E1219",
            "panel": "#141925",
            "panel_alt": "#171C27",

            "card": "#121620",
            "card_hover": "#1B2130",

            "primary": "#7C6CFF",
            "primary_hover": "#6F5DF0",
            "on_primary": "#FFFFFF",
            "accent": "#36D7E8",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F3F5F8",
            "text_secondary": "#9AA4B2",

            "border": "#282F3D",

            "entry": "#0D1118",
            "entry_border": "#2C3444",
        },

        # ==========================
        # GRAPHITE — neutral, blue accent
        # ==========================
        "Graphite": {
            "mode": "Dark",
            "splash": "Aqua Mint",

            "background": "#0A0A0B",
            "navbar": "#0F0F11",
            "panel": "#18181B",
            "panel_alt": "#1C1C20",

            "card": "#131315",
            "card_hover": "#1E1E22",

            "primary": "#3B82F6",
            "primary_hover": "#2563EB",
            "on_primary": "#FFFFFF",
            "accent": "#60A5FA",

            "success": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444",

            "text": "#FAFAFA",
            "text_secondary": "#A1A1AA",

            "border": "#27272A",

            "entry": "#0C0C0E",
            "entry_border": "#303036",
        },

        # ==========================
        # AMOLED — true black
        # ==========================
        "AMOLED": {
            "mode": "Dark",
            "splash": "Aqua Mint",

            "background": "#000000",
            "navbar": "#07080B",
            "panel": "#0E1015",
            "panel_alt": "#11141A",

            "card": "#0C0E12",
            "card_hover": "#161A21",

            "primary": "#7C6CFF",
            "primary_hover": "#6F5DF0",
            "on_primary": "#FFFFFF",
            "accent": "#36D7E8",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F3F5F8",
            "text_secondary": "#9AA4B2",

            "border": "#1E2330",

            "entry": "#05060A",
            "entry_border": "#232936",
        },

        # ==========================
        # AQUA MINT — matches the splash palette
        # ==========================
        "Aqua Mint": {
            "mode": "Dark",
            "splash": "Aqua Mint",

            "background": "#060A0E",
            "navbar": "#0A1117",
            "panel": "#0F1920",
            "panel_alt": "#122029",

            "card": "#0D161C",
            "card_hover": "#13212A",

            "primary": "#22D3EE",
            "primary_hover": "#4FE3F6",
            "on_primary": "#04161A",
            "accent": "#6EE7B7",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#E6F6F8",
            "text_secondary": "#86A9AF",

            "border": "#17363C",

            "entry": "#081016",
            "entry_border": "#1D3C44",
        },

        # ==========================
        # ULTRAVIOLET — matches the splash palette
        # ==========================
        "Ultraviolet": {
            "mode": "Dark",
            "splash": "Ultraviolet",

            "background": "#08060F",
            "navbar": "#0D0A18",
            "panel": "#130F23",
            "panel_alt": "#171229",

            "card": "#110D1F",
            "card_hover": "#1A1530",

            "primary": "#A78BFA",
            "primary_hover": "#B9A3FB",
            "on_primary": "#14092B",
            "accent": "#F472B6",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#FB7185",

            "text": "#F1ECFF",
            "text_secondary": "#A69CC4",

            "border": "#2A2342",

            "entry": "#0B0816",
            "entry_border": "#31294D",
        },

        # ==========================
        # EMBER — matches the splash palette
        # ==========================
        "Ember": {
            "mode": "Dark",
            "splash": "Ember",

            "background": "#0D0806",
            "navbar": "#140D0A",
            "panel": "#1B130F",
            "panel_alt": "#211712",

            "card": "#18110D",
            "card_hover": "#241A14",

            "primary": "#FB923C",
            "primary_hover": "#FDA75F",
            "on_primary": "#1C0D04",
            "accent": "#F43F5E",

            "success": "#34D399",
            "warning": "#FDE047",
            "danger": "#F87171",

            "text": "#FBEFE6",
            "text_secondary": "#B59C8C",

            "border": "#3A2A21",

            "entry": "#110B08",
            "entry_border": "#45322A",
        },

        # ==========================
        # EMERALD
        # ==========================
        "Emerald": {
            "mode": "Dark",
            "splash": "Aqua Mint",

            "background": "#07100C",
            "navbar": "#0B1611",
            "panel": "#101F18",
            "panel_alt": "#13241C",

            "card": "#0E1B15",
            "card_hover": "#16281F",

            "primary": "#10B981",
            "primary_hover": "#34D399",
            "on_primary": "#03140D",
            "accent": "#5EEAD4",

            "success": "#4ADE80",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#ECFDF5",
            "text_secondary": "#8FB5A5",

            "border": "#1F3A2E",

            "entry": "#09140F",
            "entry_border": "#244536",
        },

        # ==========================
        # DAYLIGHT — light theme
        # ==========================
        "Daylight": {
            "mode": "Light",
            "splash": "Aqua Mint",

            "background": "#F4F6FA",
            "navbar": "#F9FAFC",
            "panel": "#EEF1F6",
            "panel_alt": "#E6EAF2",

            "card": "#FEFEFE",
            "card_hover": "#F1F5F9",

            "primary": "#4F46E5",
            "primary_hover": "#4338CA",
            "on_primary": "#FFFFFF",
            "accent": "#0891B2",

            "success": "#16A34A",
            "warning": "#D97706",
            "danger": "#DC2626",

            "text": "#0F172A",
            "text_secondary": "#64748B",

            "border": "#E2E8F0",

            "entry": "#F8FAFC",
            "entry_border": "#CBD5E1",
        },
    }

    # Non-colour keys of a theme.
    META_KEYS = ("mode", "splash")

    current_theme = DEFAULT_THEME
    _applied = DEFAULT_THEME   # the theme the widgets currently show

    @classmethod
    def load_saved(cls):
        """Activate the theme saved in the settings file (if any)."""
        name = settings_store.get("theme", DEFAULT_THEME)
        cls.current_theme = name if name in cls.THEMES else DEFAULT_THEME
        cls._applied = cls.current_theme

    @classmethod
    def set_theme(cls, theme_name: str, persist: bool = True):
        """Set active theme (and remember it unless ``persist`` is False)."""

        if theme_name in cls.THEMES:
            cls.current_theme = theme_name
            if persist:
                settings_store.set("theme", theme_name)

    @classmethod
    def get_theme(cls):
        """Return active theme dictionary."""

        return cls.THEMES[cls.current_theme]

    @classmethod
    def get_color(cls, key: str):
        """Return a single color from active theme."""

        return cls.THEMES[cls.current_theme].get(key)

    @classmethod
    def get_theme_names(cls):
        """Return all available theme names."""

        return list(cls.THEMES.keys())

    @classmethod
    def get_current_theme(cls):
        """Return current theme name."""

        return cls.current_theme

    @classmethod
    def get_mode(cls, theme_name=None):
        """CustomTkinter appearance mode ("Dark" / "Light") of a theme."""
        return cls.THEMES[theme_name or cls.current_theme]["mode"]

    @classmethod
    def splash_palette(cls):
        """Intro palette that matches the active theme."""
        return cls.get_theme()["splash"]

    @classmethod
    def theme_for_palette(cls, palette):
        """App theme to switch to when a palette is chosen on the intro."""
        if cls.get_theme()["splash"] == palette:
            return cls.current_theme
        return palette if palette in cls.THEMES else cls.current_theme

    @classmethod
    def apply_mode(cls, root):
        """Switch CustomTkinter's Dark/Light mode without any window flashing.

        CustomTkinter recolours Windows title bars by hiding and re-showing
        every window, which flashes the screen and can drop dialogs behind the
        main window. The switch runs with that disabled, and the title bars are
        then recoloured in place through DWM.
        """
        import customtkinter as ctk

        mode = cls.get_mode()
        if ctk.get_appearance_mode() == mode:
            return
        classes = (ctk.CTk, ctk.CTkToplevel)
        saved = [c._deactivate_windows_window_header_manipulation for c in classes]
        for c in classes:
            c._deactivate_windows_window_header_manipulation = True
        try:
            ctk.set_appearance_mode(mode)
        finally:
            for c, value in zip(classes, saved):
                c._deactivate_windows_window_header_manipulation = value

        # Dialogs can hang anywhere in the tree (e.g. under the header).
        windows, stack = [root], list(root.winfo_children())
        while stack:
            widget = stack.pop()
            if isinstance(widget, ctk.CTkToplevel):
                windows.append(widget)
            stack.extend(widget.winfo_children())
        for window in windows:
            _dwm_title_bar(window, dark=(mode == "Dark"))

    @classmethod
    def needs_retheme(cls):
        """True if the widgets still show a different theme than the active one."""
        return cls._applied != cls.current_theme

    @classmethod
    def retheme_tree(cls, root):
        """Recolour every widget under ``root`` from the shown theme to the active one.

        Each colour option holding a token value of the previously applied
        theme is set to the same token of the active theme, so components that
        never wrote a ``refresh_theme`` (or missed a widget) still follow the
        theme. Widgets showing user data or other themes' colours set
        ``_theme_skip = True`` and are left alone, together with their children.
        """
        old = cls.THEMES[cls._applied]
        new = cls.get_theme()
        mapping = {}
        for key, value in old.items():
            if key not in cls.META_KEYS:
                mapping[value.upper()] = new[key]
        cls._applied = cls.current_theme
        if not mapping:
            return

        stack = [root]
        while stack:
            widget = stack.pop()
            if getattr(widget, "_theme_skip", False):
                continue
            changes = {}
            for opt in _COLOR_OPTIONS:
                try:
                    value = widget.cget(opt)
                except Exception:
                    continue
                if isinstance(value, str):
                    target = mapping.get(value.upper())
                    if target is not None and target.upper() != value.upper():
                        changes[opt] = target
            if changes:
                try:
                    widget.configure(**changes)
                except Exception:
                    for opt, value in changes.items():
                        try:
                            widget.configure(**{opt: value})
                        except Exception:
                            pass
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass
