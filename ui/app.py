import customtkinter as ctk
import traceback

from ui.header import Header
from ui.sidebar import Sidebar
from ui.pages.generate_page import GeneratePage
from ui.pages.scan_page import ScanPage
from ui.pages.history_page import HistoryPage
from ui.pages.bulk_page import BulkPage
from ui.pages.settings_page import SettingsPage
from ui.dialogs import save_changes
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

from utils import app_log, settings_store, window_guard
from utils.theme_transition import ThemeTransition
from utils.theme_manager import ThemeManager


class QRCodeStudioApp:
    """Application shell: fixed left sidebar + top bar + scrollable workspace.

    Pages: Generate, Scan, History, Bulk Create and Settings (a page in this window, so the
    theme transition covers all of it). Theme changes go through ``change_theme``.
    """

    # Per-screen top bar copy (kept next to routing for a single source).
    SCREEN_META = {
        "generate": (
            "Generate QR Code",
            "Pick a type, fill the details, style it, then save.",
        ),
        "scan": (
            "Scan a QR code",
            "Decode links, text, UPI, WiFi, contacts, email and SMS.",
        ),
        "history": (
            "History",
            "Codes you generated and scanned on this PC.",
        ),
        "bulk": (
            "Bulk Create",
            "Make many QR codes at once from a CSV file.",
        ),
        "settings": (
            "Settings",
            "Personalise how Mosaiq looks. Themes preview instantly.",
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

        # An error inside a button or timer callback must never vanish (a windowed exe has no
        # console): it goes to mosaiq.log, and to stderr when there is one.
        self.root.report_callback_exception = self._report_callback_exception

        # The liquid blob transition for live theme changes (never at start-up).
        self.theme_transition = ThemeTransition(
            self.root, windows=self._transition_windows,
            accent=lambda: ThemeManager.get_theme()["primary"])

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

        # Body: pages fill it and scroll (or not) on their own.
        self.body = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew")

        # ==========================
        # Pages
        # ==========================

        self.generate_page = GeneratePage(self.body)
        self.scan_page = ScanPage(self.body)
        self.scan_page.enable_drop(self.dnd_error)
        self.history_page = HistoryPage(self.body, on_open=self.open_history_entry,
                                        on_regenerate=self.regenerate_history_entry)

        self.bulk_page = BulkPage(self.body, style_provider=self._generate_look)
        self.settings_page = SettingsPage(self.body, app=self)

        self._pages = {"generate": self.generate_page, "scan": self.scan_page,
                       "history": self.history_page, "bulk": self.bulk_page,
                       "settings": self.settings_page}
        self._current_page = None
        self._page_theme = {key: ThemeManager.get_current_theme() for key in self._pages}   # the theme each page shows
        self._page_dirty = set()          # pages hidden while the Dark / Light mode flipped: CustomTkinter redrew their canvases
        self._refreshing = False
        self._refresh_again = False
        self._settings_return = "generate"      # where Apply / Cancel go back to
        self._switch_page("generate")

        # ==========================
        # Navigation wiring
        # ==========================

        self.sidebar.add_nav_item("generate", "Generate", "generate", self.show_generate_page)
        self.sidebar.add_nav_item("scan", "Scan QR", "scan", self.show_scan_page)
        self.sidebar.add_nav_item("history", "History", "history", self.show_history_page)
        self.sidebar.add_nav_item("bulk", "Bulk Create", "bulk", self.show_bulk_page)
        self.sidebar.add_nav_item("settings", "Settings", "settings", self.show_settings_page, bottom=True)

        # Closing the window must release the camera before the app exits.
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ==================================================

    def close(self):
        if self._current_page == "settings" and self.settings_page.has_changes():
            choice = save_changes.ask_save_changes(self.root)
            if choice == "cancel" or (choice == "save" and not self.settings_page.apply()):
                return                      # stay (a failed save has shown its error)
            # "Don't save": nothing was written, and the window is closing anyway.
        self.scan_page.shutdown()
        self.bulk_page.shutdown()
        self.root.destroy()

    # ==================================================

    def _apply_screen_meta(self, key):
        title, subtitle = self.SCREEN_META.get(key, ("", ""))
        self.header.set_title(title, subtitle)

    def _show_page(self, key):
        """Go to a page. Leaving Settings with unsaved changes asks "Save changes?" first."""
        if self._current_page == "settings" and key != "settings" and self.settings_page.has_changes():
            self._leave_settings(key)
            return
        self._switch_page(key)

    def _leave_settings(self, key):
        choice = save_changes.ask_save_changes(self.root)
        if choice == "save" and self.settings_page.apply():
            self._switch_page(key)
        elif choice == "discard":
            # The old theme comes back with the transition, and the page switch is part of that change.
            self.settings_page.discard(then=lambda: self._switch_page(key))
        else:                               # Cancel (or a failed save, which has shown its error): stay
            self.sidebar.set_active("settings")

    def _page_up_to_date(self, key):
        """A page that was hidden while the theme changed is recoloured now (from the theme it shows), so a
        change only pays for the page on screen. Does nothing for a page that is already current."""
        current = ThemeManager.get_current_theme()
        shown = self._page_theme[key]
        if shown == current and key not in self._page_dirty:
            return
        page = self._pages[key]
        if shown != current:
            ThemeManager.retheme_tree(page, old=shown)
        if hasattr(page, "refresh_theme"):
            page.refresh_theme()
        self._page_theme[key] = current
        self._page_dirty.discard(key)

    def ensure_themed(self):
        """Bring every page up to date (what showing each of them would do)."""
        for key in self._pages:
            self._page_up_to_date(key)

    def _switch_page(self, key):
        """Show one page (and its title); leaving Scan always releases the camera."""
        self._page_up_to_date(key)
        if self._current_page == "scan" and key != "scan":
            self.scan_page.on_hide()
        if self._current_page == "settings" and key != "settings":
            self.settings_page.unload()
        for name, page in self._pages.items():
            if name != key:
                page.pack_forget()
        self._pages[key].pack(fill="both", expand=True)
        self._current_page = key
        self.sidebar.set_active(key)
        self._apply_screen_meta(key)

    def show_generate_page(self):
        self._show_page("generate")

    def show_scan_page(self):
        self._show_page("scan")

    def show_bulk_page(self):
        self._page_up_to_date("bulk")
        self.bulk_page._update_summary()          # the look may have changed on Generate
        self._show_page("bulk")

    def _generate_look(self):
        """The style and logo chosen on the Generate page (Bulk Create uses them)."""
        gp = self.generate_page
        return gp.current_style(), gp.logo_card.get_logo_path()

    def show_settings_page(self):
        self._page_up_to_date("settings")
        if self._current_page != "settings":
            self._settings_return = self._current_page
            self.settings_page.load()
        self._show_page("settings")

    def close_settings(self):
        """Back to the page Settings was opened from (after Apply or Cancel)."""
        self._show_page(self._settings_return)

    def show_history_page(self):
        self._page_up_to_date("history")
        self.history_page.refresh()
        self._show_page("history")

    def open_history_entry(self, entry):
        """Open a saved code where it belongs: generated ones in Generate, scanned ones in Scan."""
        if entry["kind"] == "generated":
            self.show_generate_page()
            self.generate_page.open_entry(entry)
        else:
            self.show_scan_page()
            self.scan_page.show_saved(entry["text"])

    def regenerate_history_entry(self, entry):
        """Generate a saved code again (and keep it as a new history entry)."""
        self.show_generate_page()
        self.generate_page.regenerate_entry(entry)

    # ==================================================

    @staticmethod
    def _report_callback_exception(exc_type, exc, tb):
        app_log.get_logger().error("Unhandled error in a callback", exc_info=(exc_type, exc, tb))
        traceback.print_exception(exc_type, exc, tb)

    def _transition_windows(self):
        """The window the transition covers: the main window, Settings page included."""
        return [self.root]

    def change_theme(self, name, also=None):
        """Switch to theme ``name`` live (nothing is saved) with the blob transition. ``also`` is
        called as part of the change, before the new look is photographed (leaving a page)."""
        def change():
            ThemeManager.set_theme(name, persist=False)
            self.refresh_theme()
            if also is not None:
                also()
        self.theme_transition.run(change)

    def refresh_theme(self):
        """Re-apply the active theme across the shell, pages and components.

        It always runs to the end: a part that fails is logged and the other parts are still
        refreshed (the first error is raised afterwards), and a change requested while this runs is
        applied right after, so the window never keeps colours of two themes."""
        if self._refreshing:
            self._refresh_again = True
            return
        self._refreshing = True
        failures = []

        def step(label, action):
            try:
                action()
            except Exception as e:
                app_log.get_logger().exception("Theme refresh failed in %s", label)
                failures.append(e)

        try:
            for _attempt in range(3):           # a change that arrives meanwhile is applied by the next round
                self._refresh_again = False
                mode = ctk.get_appearance_mode()
                step("the window mode", lambda: ThemeManager.apply_mode(self.root))
                if ctk.get_appearance_mode() != mode:
                    # CustomTkinter redraws every widget when the mode flips, the hidden pages' scroll canvases
                    # from the colours of that moment: those pages are recoloured when they are shown.
                    self._page_dirty.update(key for key in self._pages if key != self._current_page)
                # Generic pass first: every widget colour that belongs to the previous theme moves to
                # the same token of the new one (covers any widget a component's own refresh_theme
                # does not know about).
                hidden = [page for key, page in self._pages.items() if key != self._current_page]
                step("the generic pass", lambda: ThemeManager.retheme_tree(self.root, skip=hidden))
                step("the window", lambda: self.root.configure(fg_color=ThemeManager.get_theme()["background"]))
                step("the sidebar", self.sidebar.refresh_theme)
                step("the header", self.header.refresh_theme)
                shown = self._current_page         # only the page on screen now; the others follow when they are shown
                if shown is not None and hasattr(self._pages[shown], "refresh_theme"):
                    step(f"the {shown} page", self._pages[shown].refresh_theme)
                if shown is not None:
                    self._page_theme[shown] = ThemeManager.get_current_theme()
                self.root.update_idletasks()
                if not (self._refresh_again or ThemeManager.needs_retheme()):
                    break
        finally:
            self._refreshing = False
        if failures:
            raise failures[0]

    # ==================================================

    def verify_visible(self):
        """A window outside every monitor, minimized or hidden shows only in the taskbar:
        bring it back (and note it in the log)."""
        try:
            action = window_guard.ensure_visible(self.root)
        except Exception:
            app_log.get_logger().exception("window visibility check failed")
            return "error"
        if action != "ok":
            app_log.get_logger().warning("main window was not visible at start (%s); moved back", action)
        return action

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
                app_log.get_logger().exception("could not raise the main window")
            # Whatever happened above, make sure it can be seen once Windows has placed it.
            self.root.after(400, self.verify_visible)

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
            app_log.get_logger().exception("the intro could not start")
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
