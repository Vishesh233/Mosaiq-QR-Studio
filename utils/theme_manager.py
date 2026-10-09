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

            "background": "#0B0D12",
            "navbar": "#0E1219",
            "panel": "#121620",
            "panel_alt": "#171C27",

            "card": "#121620",
            "card_hover": "#1B2130",

            "primary": "#7C6CFF",
            "primary_hover": "#6F5DF0",
            "accent": "#36D7E8",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F3F5F8",
            "text_secondary": "#9AA4B2",

            "border": "#282F3D",

            "entry": "#0E1219",
            "entry_border": "#2C3444",
        },

        # ==========================
        # CARBON
        # ==========================
        "Carbon": {

            "background": "#0A0C10",
            "navbar": "#101319",
            "panel": "#14181F",
            "panel_alt": "#191E26",

            "card": "#14181F",
            "card_hover": "#1E242E",

            "primary": "#7C6CFF",
            "primary_hover": "#6F5DF0",
            "accent": "#36D7E8",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F3F5F8",
            "text_secondary": "#9AA4B2",

            "border": "#272E3A",

            "entry": "#0D1015",
            "entry_border": "#2A313D",
        },

        # ==========================
        # DEEP NAVY
        # ==========================
        "Deep Navy": {

            "background": "#0A0E1A",
            "navbar": "#0E1424",
            "panel": "#111a2e",
            "panel_alt": "#16203a",

            "card": "#111A2E",
            "card_hover": "#1A2542",

            "primary": "#6C8CFF",
            "primary_hover": "#5B7AF0",
            "accent": "#36D7E8",

            "success": "#34D399",
            "warning": "#FBBF24",
            "danger": "#F87171",

            "text": "#F3F5F8",
            "text_secondary": "#9AA4B2",

            "border": "#22304D",

            "entry": "#0C1220",
            "entry_border": "#25324C",
        },

        # ==========================
        # AMOLED
        # ==========================
        "AMOLED": {

            "background": "#000000",
            "navbar": "#07080B",
            "panel": "#0C0E12",
            "panel_alt": "#11141A",

            "card": "#0C0E12",
            "card_hover": "#161A21",

            "primary": "#7C6CFF",
            "primary_hover": "#6F5DF0",
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