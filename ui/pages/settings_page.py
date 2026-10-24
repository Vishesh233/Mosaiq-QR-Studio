import customtkinter as ctk
from tkinter import messagebox

from utils import history_store, settings_store, theme_transition
from utils.theme_manager import ThemeManager
from ui.layout import PAGE_PADX, autohide_scrollbar, restyle_scrollable


class SettingsPage(ctk.CTkFrame):
    """Settings, a page inside the main window: a live theme gallery, the intro preference, the
    animation switch and the history switches.

    Clicking a theme tile previews it on the whole window at once, with the liquid transition
    (nothing is written yet). The Cancel / Apply footer is always visible, whatever the window size.

    * **Apply** writes every setting to settings.json in one atomic write and returns to the page
      the user came from.
    * **Cancel** returns to what the page showed when it opened (the theme too, with the transition)
      and writes nothing.
    * Leaving by any other way (another page, closing the app) asks "Save changes?" when something was
      changed (the app does that, using ``has_changes`` / ``apply`` / ``discard``); it never reverts silently.
    """

    TILE_COLUMNS = 4
    CONTENT_MAX = 1000                  # px: the cards stop growing on very wide windows

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")

        self.app = app
        self._tiles = {}
        self._spare = PAGE_PADX
        self._original_theme = ThemeManager.get_current_theme()
        self._selected = self._original_theme

        self.splash_var = ctk.BooleanVar(value=bool(settings_store.get("splash_enabled", True)))
        self.animate_var = ctk.BooleanVar(value=bool(settings_store.get(theme_transition.SETTING_KEY, True)))
        self.animate_var.trace_add(
            "write", lambda *_: setattr(theme_transition, "ENABLED_OVERRIDE", bool(self.animate_var.get())))
        self.history_var = ctk.BooleanVar(value=history_store.enabled())
        self.wifi_var = ctk.BooleanVar(value=history_store.save_wifi_passwords())
        self._saved = self.values()          # what the page showed when it opened

        self._build_ui()
        self._refresh_selection()
        self._update_history_count()

    # ======================================================

    def _build_ui(self):
        theme = ThemeManager.get_theme()

        # The footer is packed first, so it stays visible however small the window is; the body scrolls above it.
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=PAGE_PADX, pady=(8, 20))
        self.body = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"], label_fg_color=theme["background"])
        self.body.pack(fill="both", expand=True)
        autohide_scrollbar(self.body)

        self.content = ctk.CTkFrame(self.body, fg_color="transparent")
        self.content.pack(fill="x", padx=(PAGE_PADX, PAGE_PADX))
        self.bind("<Configure>", self._limit_width, add="+")

        # ---------------- Theme gallery ---------------- #

        self._section("THEME", pady=(4, 8))

        grid = ctk.CTkFrame(self.content, fg_color="transparent")
        grid.pack(fill="x")
        for col in range(self.TILE_COLUMNS):
            grid.grid_columnconfigure(col, weight=1, uniform="tiles")
        for index, name in enumerate(ThemeManager.get_theme_names()):
            tile = self._make_tile(grid, name)
            tile.grid(row=index // self.TILE_COLUMNS, column=index % self.TILE_COLUMNS,
                      padx=6, pady=6, sticky="nsew")
            self._tiles[name] = tile

        # ---------------- Startup ---------------- #

        self._section("STARTUP", pady=(22, 8))
        startup = self._card()
        self._switch_row(startup, "Intro animation",
                         "Play the cinematic splash when the app starts.", self.splash_var, last=True)

        # ---------------- Appearance ---------------- #

        self._section("APPEARANCE", pady=(22, 8))
        appearance = self._card()
        self._switch_row(appearance, "Animate theme changes",
                         "A liquid ink transition when the theme changes. Off, or with Windows "
                         "animations off, the theme changes at once.", self.animate_var, last=True)

        # ---------------- History ---------------- #

        self._section("HISTORY", pady=(22, 8))
        history = self._card()
        self._switch_row(history, "Save history",
                         "Keep the codes you generate and scan on this PC.", self.history_var)
        self._switch_row(history, "Save WiFi passwords in history",
                         "Off by default. When off, WiFi codes are kept without their password "
                         "and without a picture.", self.wifi_var)
        clear_row = ctk.CTkFrame(history, fg_color="transparent")
        clear_row.pack(fill="x", padx=18, pady=(10, 14))
        self.history_count = ctk.CTkLabel(
            clear_row, text="", font=("Segoe UI", 12), text_color=theme["text_secondary"])
        self.history_count.pack(side="left")
        self.clear_button = ctk.CTkButton(
            clear_row, text="Clear history", width=130, height=34, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=theme["border"],
            hover_color=theme["card_hover"], text_color=theme["danger"],
            text_color_disabled=theme["text_muted"], command=self._clear_history)
        self.clear_button.pack(side="right")
        ctk.CTkFrame(self.content, height=12, fg_color="transparent").pack()

        # ---------------- Footer buttons ---------------- #

        self.cancel_button = ctk.CTkButton(
            self.footer, text="Cancel", width=120, height=40, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=theme["border"],
            hover_color=theme["card_hover"], text_color=theme["text"], command=self.cancel)
        self.cancel_button.pack(side="right")
        self.apply_button = ctk.CTkButton(
            self.footer, text="Apply", width=120, height=40, corner_radius=10,
            fg_color=theme["primary"], hover_color=theme["primary_hover"],
            text_color=theme["on_primary"], font=("Segoe UI Semibold", 13), command=self.apply_and_close)
        self.apply_button.pack(side="right", padx=(0, 12))

    def _limit_width(self, event):
        """Keep the content at most CONTENT_MAX px wide: the spare room goes to the right margin.
        Measured on the page (its width does not depend on its content), applied once things settle."""
        if event.widget is not self:
            return
        width = event.width / self._get_widget_scaling()
        spare = max(PAGE_PADX, round(width - 2 * PAGE_PADX - 24 - self.CONTENT_MAX))      # 24: the scrollbar
        if spare != self._spare:
            self._spare = spare
            self.after_idle(lambda: self.content.pack_configure(padx=(PAGE_PADX, self._spare)))

    def _card(self):
        theme = ThemeManager.get_theme()
        card = ctk.CTkFrame(self.content, fg_color=theme["card"], corner_radius=12,
                            border_width=1, border_color=theme["border"])
        card.pack(fill="x")
        return card

    def _switch_row(self, parent, title, subtitle, variable, last=False):
        theme = ThemeManager.get_theme()
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(14, 14 if last else 0))
        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text_col, text=title, anchor="w", font=("Segoe UI Semibold", 14),
                     text_color=theme["text"]).pack(fill="x")
        ctk.CTkLabel(text_col, text=subtitle, anchor="w", justify="left", wraplength=640,
                     font=("Segoe UI", 12), text_color=theme["text_secondary"]).pack(fill="x")
        ctk.CTkSwitch(
            row, text="", variable=variable, onvalue=True, offvalue=False, width=52,
            progress_color=theme["primary"], button_color=theme["text"],
            button_hover_color=theme["text_secondary"], fg_color=theme["scrollbar"],
            text_color=theme["text"]).pack(side="right", padx=(12, 0))

    def _section(self, text, pady=(0, 8)):
        ctk.CTkLabel(
            self.content, text=text, font=("Segoe UI Semibold", 11),
            text_color=ThemeManager.get_theme()["text_secondary"],
        ).pack(anchor="w", padx=4, pady=pady)

    def _update_history_count(self):
        count = history_store.count()
        self.history_count.configure(text=f"{count} saved" if count else "No saved codes")
        self.clear_button.configure(state="normal" if count else "disabled")

    def _clear_history(self):
        count = history_store.count()
        if not messagebox.askyesno(
                "Clear history",
                f"Remove all {count} saved codes and their previews from this PC?\n\n"
                f"This cannot be undone."):
            return
        history_store.clear()
        self.app.history_page.refresh()
        self._update_history_count()

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

    def refresh_theme(self):
        """The window changed theme: restyle what the generic pass does not know about."""
        restyle_scrollable(self.body, "background")
        self._refresh_selection()

    def load(self):
        """The page is being opened: show what is saved now, with the active theme selected."""
        self._original_theme = ThemeManager.get_current_theme()
        self._selected = self._original_theme
        self._reset_switches()
        self._saved = self.values()
        self._refresh_selection()
        self._update_history_count()
        # While the page is open its animation switch decides at once (before it is applied).
        theme_transition.ENABLED_OVERRIDE = bool(self.animate_var.get())

    def unload(self):
        """The page is being left."""
        theme_transition.ENABLED_OVERRIDE = None

    def _reset_switches(self):
        self.splash_var.set(bool(settings_store.get("splash_enabled", True)))
        self.animate_var.set(bool(settings_store.get(theme_transition.SETTING_KEY, True)))
        self.history_var.set(history_store.enabled())
        self.wifi_var.set(history_store.save_wifi_passwords())

    def preview_theme(self, theme_name):
        """Show ``theme_name`` on the whole window right away, with the transition (not saved yet)."""
        if theme_name == self._selected:
            return
        self._selected = theme_name
        self._refresh_selection()
        self.app.change_theme(theme_name)

    def values(self):
        """Every setting this page edits, as it stands now (the keys of settings.json)."""
        return {
            "theme": self._selected,
            "splash_enabled": bool(self.splash_var.get()),
            theme_transition.SETTING_KEY: bool(self.animate_var.get()),
            history_store.KEY_ENABLED: bool(self.history_var.get()),
            history_store.KEY_WIFI_PASSWORDS: bool(self.wifi_var.get()),
        }

    def has_changes(self):
        return self.values() != self._saved

    def apply(self):
        """Write all settings (one atomic write). A failed write is shown and the page keeps the
        choices as they are. Returns True when saved."""
        try:
            settings_store.update(self.values())
        except settings_store.SettingsWriteError as e:
            messagebox.showerror("Could not save settings", str(e))
            return False
        ThemeManager.set_theme(self._selected, persist=False)       # already on disk
        self._original_theme = self._selected
        self._saved = self.values()
        self.app.history_page.refresh()
        return True

    def apply_and_close(self):
        """The Apply button: save, then go back to the page the user came from."""
        if self.apply():
            self.app.close_settings()

    def discard(self, then=None):
        """Back to what the page showed when it opened: the switches, and the theme with the
        transition. ``then`` (leaving the page) runs as part of that change, so the new look is the page
        the user lands on."""
        def restore():
            self._selected = self._original_theme
            self._reset_switches()
            self._saved = self.values()          # nothing differs from what is saved now
            self._refresh_selection()
            if then is not None:
                then()

        if ThemeManager.get_current_theme() != self._original_theme:
            self.app.change_theme(self._original_theme, also=restore)
        else:
            restore()

    def cancel(self):
        """The Cancel button: discard the changes and go back."""
        self.discard(then=self.app.close_settings)
