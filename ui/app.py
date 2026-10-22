import customtkinter as ctk
import traceback

from ui.header import Header
from ui.sidebar import Sidebar
from ui.pages.generate_page import GeneratePage
from ui.pages.scan_page import ScanPage
from ui.splash import Splash, splash_disabled
from ui.brand_logo import apply_window_icon
from ui.dnd_support import create_root

from config import (
    APP_NAME,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
)

from utils import settings_store
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
            "Create a custom QR code: link, text, UPI, WiFi, contact, email or SMS.",
        ),
        "scan": (
            "Scan QR Code",
            "Decode a QR code from an image, the camera, the clipboard or the screen.",
        ),
    }

    def __init__(self):
        # The theme chosen last time (Settings or the intro's palette chips).
        ThemeManager.load_saved()
        theme = ThemeManager.get_theme()

        # ==========================
        # Theme
        # ==========================

        ctk.set_appearance_mode(ThemeManager.get_mode())
        ctk.set_default_color_theme("blue")

        # ==========================
        # Window
        # ==========================

        # dnd_error is None when files can be dropped onto the Scan page.
        self.root, self.dnd_error = create_root()
        self.root.title(APP_NAME)
        apply_window_icon(self.root)
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
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"],
            label_fg_color=theme["background"],
        )
        self.body.grid(row=1, column=0, sticky="nsew")

        # ==========================
        # Pages
        # ==========================

        self.generate_page = GeneratePage(self.body)
        self.scan_page = ScanPage(self.body)
        self.scan_page.enable_drop(self.dnd_error)

        self.generate_page.pack(fill="both", expand=True, padx=28, pady=(10, 25))

        # ==========================
        # Navigation wiring
        # ==========================

        self.sidebar.set_generate_callback(self.show_generate_page)
        self.sidebar.set_scan_callback(self.show_scan_page)

        # Set the initial top bar copy to match the default page.
        self._apply_screen_meta("generate")

        # Closing the window must release the camera before the app exits.
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ==================================================

    def close(self):
        self.scan_page.shutdown()
        self.root.destroy()

    # ==================================================

    def _apply_screen_meta(self, key):
        title, subtitle = self.SCREEN_META.get(key, ("", ""))
        self.header.set_title(title, subtitle)

    def show_generate_page(self):
        self.scan_page.on_hide()
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

        ThemeManager.apply_mode(self.root)
        # Generic pass first: every widget colour that belongs to the previous
        # theme moves to the same token of the new one (covers any widget a
        # component's own refresh_theme does not know about).
        ThemeManager.retheme_tree(self.root)

        self.root.configure(fg_color=theme["background"])
        self.sidebar.refresh_theme()
        self.header.refresh_theme()
        self.body.configure(
            fg_color="transparent",
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"],
            label_fg_color=theme["background"],
        )

        # Header / Navigation
        self.header.refresh_theme()

        # Pages (each cascades to its components defensively)
        if hasattr(self.generate_page, "refresh_theme"):
            self.generate_page.refresh_theme()
        if hasattr(self.scan_page, "refresh_theme"):
            self.scan_page.refresh_theme()

        self.root.update_idletasks()

    # ==================================================

    def _maximize(self):
        """Fill the available screen work area (respects the Windows taskbar).

        Uses the reliable Windows ``state("zoomed")`` first, then falls back to
        ``-zoomed`` / a manual work-area geometry. Safe on any platform.
        """
        root = self.root
        try:
            root.update_idletasks()
        except Exception:
            pass
        # Primary: native "zoomed" window state (Windows maximized).
        try:
            root.state("zoomed")
            return
        except Exception:
            pass
        # Fallback 1: -zoomed attribute.
        try:
            root.attributes("-zoomed", True)
            return
        except Exception:
            pass
        # Fallback 2: size to the usable work area manually.
        try:
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            root.geometry(f"{sw}x{sh - 48}+0+0")  # leave room for a taskbar
        except Exception:
            pass

    def run(self, show_splash: bool = True):
        """Enter the Tk main loop, playing the cinematic intro first.

        The splash is a borderless ``Toplevel`` owned by the real root window,
        so no second application window is ever created. The main window is
        withdrawn before it can map on-screen, maximized, then deiconified
        exactly once when the intro finishes (or immediately if the intro is
        disabled / unavailable). Honors ``QRSTUDIO_NO_SPLASH=1`` /
        ``--no-splash`` / ``--fast`` via :func:`ui.splash.splash_disabled`.
        """
        use_splash = (bool(show_splash) and not splash_disabled()
                      and bool(settings_store.get("splash_enabled", True)))

        # Hide the real window before the mainloop maps it, so the opening
        # frame is pure AMOLED black with no title-bar flash.
        try:
            self.root.withdraw()
        except Exception:
            pass

        started = [False]

        def _on_intro_palette(palette):
            # A palette chip on the intro also picks the matching app theme
            # (remembered); it is applied before the main window is revealed.
            ThemeManager.set_theme(ThemeManager.theme_for_palette(palette))

        def _show_main():
            if ThemeManager.needs_retheme():
                self.refresh_theme()
            # Maximize first, then reveal: the very first mapped frame is
            # already full-screen (no small window before maximization).
            self._maximize()
            try:
                self.root.deiconify()
            except Exception:
                pass
            try:
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass

        if not use_splash:
            # Reveal from an after() callback (see below): maximizing before
            # mainloop() was undone by CustomTkinter's title-bar prelude, so
            # the window opened un-maximized.
            self.root.after(0, _show_main)
            self.root.mainloop()
            return

        splash = None
        try:
            splash = Splash(on_done=_show_main,
                            palette=ThemeManager.splash_palette(),
                            on_palette=_on_intro_palette)
            started[0] = splash.start(self.root)
        except Exception:
            # Never swallow this silently — a bare `except` here is what hid
            # the original crash (Scene.__init__ raised on every launch and the
            # splash simply never started, with no traceback anywhere).
            traceback.print_exc()
            started[0] = False
            if splash is not None:
                try:
                    splash.stop()
                except Exception:
                    pass
        if not started[0]:
            # Splash could not start — never trap the user on a withdrawn
            # window. Reveal from an after() callback: CustomTkinter's
            # CTk.mainloop() prelude hides the root once to recolour the
            # Windows title bar and only re-maps it itself when withdraw() was
            # NOT called before the first show (we do call it, to keep the root
            # hidden behind the intro). Revealing before mainloop() therefore
            # got undone, leaving the app permanently invisible.
            self.root.after(0, _show_main)
        self.root.mainloop()
