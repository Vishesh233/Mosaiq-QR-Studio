import customtkinter as ctk

from utils import settings_store
from utils.theme_manager import ThemeManager
from ui import icons
from ui.brand_logo import apply_window_icon


class SettingsDialog(ctk.CTkToplevel):
    """Appearance settings: a live theme gallery and the intro preference.

    Clicking a theme tile previews it on the whole app immediately; Apply keeps
    it (and remembers it for the next launch), Cancel or closing the window
    restores the theme that was active when the dialog opened.
    """

    TILE_COLUMNS = 4

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent
        self._original_theme = ThemeManager.get_current_theme()
        self._selected = self._original_theme
        self._tiles = {}

        self.title("Settings")
        apply_window_icon(self)
        self.geometry("760x660")
        self.resizable(False, False)

        # Modal behaviour + clean focus return to the parent window.
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.splash_var = ctk.BooleanVar(
            value=bool(settings_store.get("splash_enabled", True))
        )

        self._build_ui()
        self._refresh_selection()

    # ======================================================

    def _find_app(self):
        """Walk up the widget tree to locate the QRCodeStudioApp instance.

        The app stores itself on the root window as ``root.app``. Because the
        header now lives inside an intermediate frame, we search ancestors for
        an ``app`` attribute rather than assuming a fixed parent depth.
        """
        widget = self.parent
        while widget is not None:
            app = getattr(widget, "app", None)
            if app is not None:
                return app
            widget = getattr(widget, "master", None)
        return getattr(self.winfo_toplevel(), "app", None)

    def _build_ui(self):
        theme = ThemeManager.get_theme()

        self.container = ctk.CTkFrame(self, fg_color=theme["background"], bg_color=theme["background"], corner_radius=0)
        self.container.pack(fill="both", expand=True)

        # ---------------- Title ---------------- #

        title_row = ctk.CTkFrame(self.container, fg_color="transparent")
        title_row.pack(anchor="w", padx=30, pady=(24, 2))

        ctk.CTkLabel(
            title_row,
            text=icons.icon("settings"),
            font=icons.icon_font(22),
            text_color=theme["primary"],
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            title_row,
            text="Settings",
            font=("Segoe UI Semibold", 22),
            text_color=theme["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            self.container,
            text="Personalise how Mosaiq looks. Themes preview instantly.",
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"],
        ).pack(anchor="w", padx=30, pady=(0, 18))

        # ---------------- Theme gallery ---------------- #

        self._section("THEME")

        grid = ctk.CTkFrame(self.container, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        for col in range(self.TILE_COLUMNS):
            grid.grid_columnconfigure(col, weight=1, uniform="tiles")

        for index, name in enumerate(ThemeManager.get_theme_names()):
            tile = self._make_tile(grid, name)
            tile.grid(row=index // self.TILE_COLUMNS, column=index % self.TILE_COLUMNS,
                      padx=6, pady=6, sticky="nsew")
            self._tiles[name] = tile

        # ---------------- Startup ---------------- #

        self._section("STARTUP", pady=(22, 8))

        startup = ctk.CTkFrame(
            self.container, fg_color=theme["card"], corner_radius=12,
            border_width=1, border_color=theme["border"],
        )
        startup.pack(fill="x", padx=30)

        text_col = ctk.CTkFrame(startup, fg_color="transparent")
        text_col.pack(side="left", padx=18, pady=14)
        ctk.CTkLabel(
            text_col, text="Intro animation",
            font=("Segoe UI Semibold", 14), text_color=theme["text"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            text_col, text="Play the cinematic splash when the app starts.",
            font=("Segoe UI", 12), text_color=theme["text_secondary"],
        ).pack(anchor="w")

        ctk.CTkSwitch(
            startup, text="", variable=self.splash_var,
            onvalue=True, offvalue=False, width=52,
            progress_color=theme["primary"],
            button_color=theme["text"],
            button_hover_color=theme["text_secondary"],
            fg_color=theme["scrollbar"],
            text_color=theme["text"],
        ).pack(side="right", padx=18)

        # ---------------- Bottom Buttons ---------------- #

        button_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=30, pady=24)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120, height=40, corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text"],
            command=self.cancel,
        ).pack(side="right")

        ctk.CTkButton(
            button_frame,
            text="Apply",
            width=120, height=40, corner_radius=10,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"],
            font=("Segoe UI Semibold", 13),
            command=self.apply,
        ).pack(side="right", padx=(0, 12))

    def _section(self, text, pady=(0, 8)):
        ctk.CTkLabel(
            self.container, text=text,
            font=("Segoe UI Semibold", 11),
            text_color=ThemeManager.get_theme()["text_secondary"],
        ).pack(anchor="w", padx=30, pady=pady)

    # ------------------------------------------------------

    def _make_tile(self, parent, name):
        """A clickable card with a miniature of the theme's own colours."""
        theme = ThemeManager.get_theme()
        t = ThemeManager.THEMES[name]

        tile = ctk.CTkFrame(
            parent, fg_color=theme["card"], corner_radius=14,
            border_width=2, border_color=theme["border"],
        )

        # Miniature app: sidebar, a card, a primary button and accent dots.
        # It shows another theme's colours, so the live re-theme skips it.
        mini = ctk.CTkFrame(tile, height=86, fg_color=t["background"], corner_radius=10)
        mini._theme_skip = True
        mini.pack(fill="x", padx=10, pady=(10, 8))
        mini.pack_propagate(False)

        side = ctk.CTkFrame(mini, width=26, fg_color=t["navbar"], corner_radius=8)
        side.pack(side="left", fill="y", padx=(6, 0), pady=6)
        for color in (t["primary"], t["text_secondary"], t["text_secondary"]):
            ctk.CTkFrame(side, width=12, height=4, corner_radius=2, fg_color=color).pack(pady=(6, 0))

        card = ctk.CTkFrame(mini, fg_color=t["card"], corner_radius=8,
                            border_width=1, border_color=t["border"])
        card.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        ctk.CTkFrame(card, height=5, width=54, corner_radius=2,
                     fg_color=t["text"]).pack(anchor="w", padx=8, pady=(9, 0))
        ctk.CTkFrame(card, height=4, width=38, corner_radius=2,
                     fg_color=t["text_secondary"]).pack(anchor="w", padx=8, pady=(5, 0))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=(9, 0))
        ctk.CTkFrame(row, height=14, width=40, corner_radius=7,
                     fg_color=t["primary"]).pack(side="left")
        ctk.CTkFrame(row, height=8, width=8, corner_radius=4,
                     fg_color=t["accent"]).pack(side="left", padx=(6, 0))

        label_row = ctk.CTkFrame(tile, fg_color="transparent")
        label_row.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkLabel(
            label_row, text=name, font=("Segoe UI Semibold", 13),
            text_color=theme["text"],
        ).pack(side="left")
        ctk.CTkLabel(
            label_row, text=t["mode"], font=("Segoe UI", 11),
            text_color=theme["text_secondary"],
        ).pack(side="right")

        self._bind_click(tile, lambda _e, n=name: self.preview_theme(n))
        return tile

    def _bind_click(self, widget, callback):
        widget.bind("<Button-1>", callback, add="+")
        try:
            widget.configure(cursor="hand2")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_click(child, callback)

    def _refresh_selection(self):
        theme = ThemeManager.get_theme()
        for name, tile in self._tiles.items():
            tile.configure(
                border_color=theme["primary"] if name == self._selected else theme["border"]
            )

    # ======================================================

    def _apply_live(self, name):
        ThemeManager.set_theme(name, persist=False)
        app = self._find_app()
        if app:
            app.refresh_theme()
        else:
            ThemeManager.retheme_tree(self)

    def preview_theme(self, theme_name):
        """Show ``theme_name`` on the whole app right away (not saved yet)."""
        if theme_name == self._selected:
            return
        self._selected = theme_name
        self._apply_live(theme_name)
        self._refresh_selection()
        # Switching between Dark and Light makes CustomTkinter hide and re-show
        # windows to recolour their title bars, which can drop this dialog
        # behind the main window; bring it back once that has settled.
        self._restore_front()
        self.after(150, self._restore_front)

    def _restore_front(self):
        try:
            if self.state() == "withdrawn":
                self.deiconify()
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def apply(self):
        ThemeManager.set_theme(self._selected)
        settings_store.set("splash_enabled", bool(self.splash_var.get()))
        self.destroy()

    def cancel(self):
        if ThemeManager.get_current_theme() != self._original_theme:
            self._apply_live(self._original_theme)
        ThemeManager.set_theme(self._original_theme)
        self.destroy()
