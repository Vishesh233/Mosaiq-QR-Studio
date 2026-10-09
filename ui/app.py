import customtkinter as ctk

from ui.header import Header
from ui.sidebar import Sidebar
from ui.pages.generate_page import GeneratePage
from ui.pages.scan_page import ScanPage

from config import (
    APP_NAME,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
)

from utils.theme_manager import ThemeManager


class QRCodeStudioApp:
    """Application shell: fixed left sidebar + top bar + scrollable workspace.

    Behaviour is unchanged from v2: two pages (Generate / Scan), the same
    generator/scanner integration, and the same theme refresh propagation.
    Only the surrounding layout is redesigned.
    """

    # Per-screen top bar copy (kept next to routing for a single source).
    SCREEN_META = {
        "generate": (
            "Generate QR Code",
            "Create a custom QR code from a URL or text.",
        ),
        "scan": (
            "Scan QR Code",
            "Decode a QR code from an image file.",
        ),
    }

    def __init__(self):
        theme = ThemeManager.get_theme()

        # ==========================
        # Theme
        # ==========================

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # ==========================
        # Window
        # ==========================

        self.root = ctk.CTk()
        self.root.title(APP_NAME)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(fg_color=theme["background"])

        # App reference for dialogs (unchanged contract).
        self.root.app = self

        # Root grid: sidebar | main
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # ==========================
        # Sidebar
        # ==========================

        self.sidebar = Sidebar(self.root)
        self.sidebar.grid(row=0, column=0, sticky="nsw")

        # ==========================
        # Main column (top bar + scrollable body)
        # ==========================

        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.header = Header(main)
        self.header.grid(row=0, column=0, sticky="ew")

        # Scrollable Body
        self.body = ctk.CTkScrollableFrame(
            main,
            fg_color="transparent",
            corner_radius=0,
        )
        self.body.grid(row=1, column=0, sticky="nsew")

        # ==========================
        # Pages
        # ==========================

        self.generate_page = GeneratePage(self.body)
        self.scan_page = ScanPage(self.body)

        self.generate_page.pack(fill="both", expand=True, padx=28, pady=(10, 25))

        # ==========================
        # Navigation wiring
        # ==========================

        self.sidebar.set_generate_callback(self.show_generate_page)
        self.sidebar.set_scan_callback(self.show_scan_page)

        # Set the initial top bar copy to match the default page.
        self._apply_screen_meta("generate")

    # ==================================================

    def _apply_screen_meta(self, key):
        title, subtitle = self.SCREEN_META.get(key, ("", ""))
        self.header.set_title(title, subtitle)

    def show_generate_page(self):
        self.scan_page.pack_forget()
        self.generate_page.pack(fill="both", expand=True, padx=28, pady=(10, 25))
        self._apply_screen_meta("generate")

    def show_scan_page(self):
        self.generate_page.pack_forget()
        self.scan_page.pack(fill="both", expand=True, padx=28, pady=(10, 25))
        self._apply_screen_meta("scan")

    # ==================================================

    def refresh_theme(self):
        """Re-apply the active theme across the shell, pages and components."""
        theme = ThemeManager.get_theme()

        self.root.configure(fg_color=theme["background"])
        self.sidebar.refresh_theme()
        self.header.refresh_theme()
        self.body.configure(fg_color="transparent")

        # Header / Navigation
        self.header.refresh_theme()

        # Pages (each cascades to its components defensively)
        if hasattr(self.generate_page, "refresh_theme"):
            self.generate_page.refresh_theme()
        if hasattr(self.scan_page, "refresh_theme"):
            self.scan_page.refresh_theme()

        self.root.update_idletasks()

    # ==================================================

    def run(self):
        self.root.mainloop()
