from config import DEFAULT_THEME


class ThemeManager:
    """
    Handles application themes.
    """

    THEMES = {

        # ==========================
        # MIDNIGHT (Current)
        # ==========================
        "Midnight": {

            "background": "#171717",
            "navbar": "#1E1E1E",

            "card": "#242424",
            "card_hover": "#2C2C2C",

            "primary": "#3B82F6",
            "primary_hover": "#2563EB",

            "success": "#10B981",
            "warning": "#F59E0B",
            "danger": "#EF4444",

            "text": "#FFFFFF",
            "text_secondary": "#A1A1AA",

            "border": "#343434",

            "entry": "#2A2A2A",
            "entry_border": "#3C3C3C",
        },

        # ==========================
        # CARBON
        # ==========================
        "Carbon": {

            "background": "#202020",
            "navbar": "#262626",

            "card": "#2D2D2D",
            "card_hover": "#363636",

            "primary": "#3B82F6",
            "primary_hover": "#2563EB",

            "success": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444",

            "text": "#FFFFFF",
            "text_secondary": "#B3B3B3",

            "border": "#404040",

            "entry": "#333333",
            "entry_border": "#4A4A4A",
        },

        # ==========================
        # DEEP NAVY
        # ==========================
        "Deep Navy": {

            "background": "#0F172A",
            "navbar": "#16213E",

            "card": "#1E293B",
            "card_hover": "#334155",

            "primary": "#60A5FA",
            "primary_hover": "#3B82F6",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F8FAFC",
            "text_secondary": "#CBD5E1",

            "border": "#334155",

            "entry": "#1E293B",
            "entry_border": "#475569",
        },

        # ==========================
        # AMOLED
        # ==========================
        "AMOLED": {

            "background": "#000000",
            "navbar": "#0A0A0A",

            "card": "#111111",
            "card_hover": "#1A1A1A",

            "primary": "#2563EB",
            "primary_hover": "#1D4ED8",

            "success": "#22C55E",
            "warning": "#F59E0B",
            "danger": "#EF4444",

            "text": "#FFFFFF",
            "text_secondary": "#9CA3AF",

            "border": "#222222",

            "entry": "#151515",
            "entry_border": "#2B2B2B",
        },
    }

    current_theme = DEFAULT_THEME

    @classmethod
    def set_theme(cls, theme_name: str):
        """Set active theme."""

        if theme_name in cls.THEMES:
            cls.current_theme = theme_name

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