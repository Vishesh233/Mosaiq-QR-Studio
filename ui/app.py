import customtkinter as ctk

from ui.header import Header
from ui.navigation import Navigation
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

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            WINDOW_MIN_WIDTH,
            WINDOW_MIN_HEIGHT
        )

        self.root.configure(
            fg_color=theme["background"]
        )

        # ==========================
        # Header
        # ==========================

        self.header = Header(self.root)
        self.header.pack(fill="x")

        self.root.app = self

        # ==========================
        # Navigation
        # ==========================

        self.navigation = Navigation(self.root)
        self.navigation.pack(pady=(20, 15))

        # ==========================
        # Scrollable Body
        # ==========================

        self.body = ctk.CTkScrollableFrame(
            self.root,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=theme["primary"],
            scrollbar_button_hover_color=theme["primary_hover"]
        )

        self.body.pack(
            fill="both",
            expand=True,
            padx=0,
            pady=0
        )

        # ==========================
        # Pages
        # ==========================

        self.generate_page = GeneratePage(self.body)
        self.scan_page = ScanPage(self.body)

        self.generate_page.pack(
            fill="both",
            expand=True,
            pady=(10, 25)
        )

        # ==========================
        # Navigation Callbacks
        # ==========================

        self.navigation.set_generate_callback(
            self.show_generate_page
        )

        self.navigation.set_scan_callback(
            self.show_scan_page
        )

    def show_generate_page(self):

            self.scan_page.pack_forget()
            
            self.generate_page.pack(
                fill="both",
                expand=True,
                pady=(10, 25)
            )


    def show_scan_page(self):

            self.generate_page.pack_forget()

            self.scan_page.pack(
                fill="both",
                expand=True,
                pady=(10, 25)
            )

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.root.configure(
            fg_color=theme["background"]
        )

        self.body.configure(
            scrollbar_button_color=theme["primary"],
            scrollbar_button_hover_color=theme["primary_hover"]
        )

        # Header
        if hasattr(self.header, "refresh_theme"):
            self.header.refresh_theme()

        # Navigation
        if hasattr(self.navigation, "refresh_theme"):
            self.navigation.refresh_theme()

        # Generate Page
        if hasattr(self.generate_page, "refresh_theme"):
            self.generate_page.refresh_theme()

        # Scan Page
        if hasattr(self.scan_page, "refresh_theme"):
            self.scan_page.refresh_theme()

        self.root.update_idletasks()

        # Future
        #self.scan_page = ScanPage(self.body)

    # ==========================

    def run(self):

        self.root.mainloop()
