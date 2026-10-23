# ==========================
# APP INFO
# ==========================

APP_NAME = "Mosaiq QR Studio"
APP_SHORT_NAME = "Mosaiq"         # where space is tight (sidebar brand)
APP_VERSION = "v2.2"

# Settings folder under %APPDATA%. Keeps the pre-rebrand name on purpose so
# existing installs keep their saved theme / intro preference.
SETTINGS_DIR_NAME = "QR Code Studio"

# ==========================
# WINDOW
# ==========================

# Generous default that still fits common 1366x768 / 1440x900 laptops.
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 820

WINDOW_MIN_WIDTH = 1080
WINDOW_MIN_HEIGHT = 680

# ==========================
# APPEARANCE
# ==========================

DEFAULT_THEME = "Midnight"

# ==========================
# TYPOGRAPHY (single source of truth)
# ==========================
# Segoe UI ships with Windows; kept as the primary family. The premium icon
# glyphs come from "Segoe MDL2 Assets" (also ships with Windows 10/11).

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_SEMIBOLD = "Segoe UI Semibold"
FONT_ICON = "Segoe MDL2 Assets"

# ==========================
# PREMIUM DARK DESIGN TOKENS
# ==========================
# Reference palette for the redesigned shell. The live, switchable palettes
# live in utils/theme_manager.py (keys are consumed across the UI). These
# constants document the design system and are used by the app shell.

# Surfaces
BG = "#0B0D12"            # deep charcoal background
PANEL = "#121620"         # elevated panel
PANEL_ALT = "#171C27"     # secondary elevated panel
BORDER = "#282F3D"        # subtle 1px borders

# Text
TEXT = "#F3F5F8"          # primary text
TEXT_SECONDARY = "#9AA4B2"  # secondary text

# Accents
PRIMARY = "#7C6CFF"       # electric violet / indigo
PRIMARY_HOVER = "#6F5DF0"
ACCENT_CYAN = "#36D7E8"   # secondary accent (used sparingly)

# Status
SUCCESS = "#34D399"
WARNING = "#FBBF24"
DANGER = "#F87171"

# ==========================
# BACKWARD-COMPATIBLE ALIASES
# ==========================
# Older names kept so any code referencing them keeps working.

BACKGROUND = BG
CARD = PANEL
CARD_HOVER = PANEL_ALT
NAVBAR = PANEL
ENTRY = "#0E1219"
ENTRY_BORDER = BORDER

# ==========================
# SHAPE / SPACING
# ==========================

CARD_RADIUS = 12
CONTROL_RADIUS = 10
BUTTON_HEIGHT = 42
SIDEBAR_WIDTH = 232
TOPBAR_HEIGHT = 64

# ==========================
# PREVIEW
# ==========================

QR_PREVIEW = 300
