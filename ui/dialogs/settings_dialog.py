import tkinter

import customtkinter as ctk
from tkinter import messagebox

from utils import history_store, settings_store, theme_transition
from utils.theme_manager import ThemeManager
from ui import icons
from ui.layout import autohide_scrollbar, restyle_scrollable
from ui.brand_logo import apply_window_icon


def dialog_size(screen_width, screen_height, scaling):
    """(width, height) in logical px that fits a screen of ``screen_*`` physical px at ``scaling``
    (1.25 = 125 %), leaving room for the title bar and the taskbar. The Apply / Cancel footer is
    packed first, so it stays visible however small the dialog is."""
    width = max(520, min(760, int(screen_width / scaling) - 60))
    height = max(420, min(990, int(screen_height / scaling) - 130))
    return width, height


def dialog_position(parent_rect, work_areas, size_px):
    """(x, y) in physical px for a dialog of ``size_px`` = (width, height): centred over the parent
    window, then moved so that the WHOLE dialog is inside the work area of the monitor the parent is
    on (so its Apply / Cancel footer can never be below the bottom of the screen).
    ``parent_rect`` is (left, top, right, bottom); ``work_areas`` the monitors' usable rectangles.
    Returns None when the parent is on no monitor (then the system places the dialog)."""
    centre_x = (parent_rect[0] + parent_rect[2]) / 2
    centre_y = (parent_rect[1] + parent_rect[3]) / 2
    area = next((a for a in work_areas if a[0] <= centre_x < a[2] and a[1] <= centre_y < a[3]), None)
    if area is None:
        return None
    width, height = size_px
    x = min(max(round(centre_x - width / 2), area[0]), max(area[0], area[2] - width))
    y = min(max(round(centre_y - height / 2), area[1]), max(area[1], area[3] - height))
    return x, y


def ask_save_changes(parent):
    """"Save changes?" with [Save] [Don't save] [Cancel]. Returns "save", "discard" or "cancel"."""
    theme = ThemeManager.get_theme()
    box = ctk.CTkToplevel(parent)
    box.title("Settings")
    apply_window_icon(box)
    box.configure(fg_color=theme["background"])
    box.resizable(False, False)
    box.transient(parent)
    answer = {"value": "cancel"}

    def choose(value):
        answer["value"] = value
        box.destroy()

    ctk.CTkLabel(box, text="Save changes?", font=("Segoe UI Semibold", 17),
                 text_color=theme["text"]).pack(anchor="w", padx=26, pady=(24, 4))
    ctk.CTkLabel(box, text="You changed some settings. Save them before closing?",
                 font=("Segoe UI", 13), text_color=theme["text_secondary"],
                 wraplength=380, justify="left").pack(anchor="w", padx=26)
    row = ctk.CTkFrame(box, fg_color="transparent")
    row.pack(fill="x", padx=26, pady=(22, 22))
    ctk.CTkButton(row, text="Save", width=110, height=38, corner_radius=10,
                  fg_color=theme["primary"], hover_color=theme["primary_hover"],
                  text_color=theme["on_primary"], font=("Segoe UI Semibold", 13),
                  command=lambda: choose("save")).pack(side="right")
    ctk.CTkButton(row, text="Don't save", width=110, height=38, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=theme["border"],
                  hover_color=theme["card_hover"], text_color=theme["text"],
                  command=lambda: choose("discard")).pack(side="right", padx=(0, 10))
    ctk.CTkButton(row, text="Cancel", width=90, height=38, corner_radius=10,
                  fg_color="transparent", border_width=1, border_color=theme["border"],
                  hover_color=theme["card_hover"], text_color=theme["text"],
                  command=lambda: choose("cancel")).pack(side="right", padx=(0, 10))
    box.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
    box.bind("<Escape>", lambda _e: choose("cancel"))
    box.update_idletasks()
    box.geometry(f"{max(box.winfo_reqwidth(), 440)}x{box.winfo_reqheight()}")
    box.after(50, box.grab_set)
    parent.wait_window(box)
    return answer["value"]


class SettingsDialog(ctk.CTkToplevel):
    """Settings: a live theme gallery, the intro preference and the history switches.

    Clicking a theme tile previews it on the whole app immediately (nothing is written yet).

    * **Apply** writes every setting to settings.json in one atomic write and closes.
    * **Cancel** returns to what the dialog showed when it opened (the theme too) and writes nothing.
    * Closing with **X** asks "Save changes?" when something was changed, and closes straight away
      when nothing was; it never reverts silently.
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
        width, height = dialog_size(self.winfo_screenwidth(), self.winfo_screenheight(),
                                    self._get_window_scaling())
        position = self._position(width, height)
        self.geometry(f"{width}x{height}" + (f"+{position[0]}+{position[1]}" if position else ""))
        self.resizable(False, False)

        # Modal behaviour + clean focus return to the parent window.
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_requested)
        self.bind("<Escape>", lambda _e: self.close_requested())

        self.splash_var = ctk.BooleanVar(
            value=bool(settings_store.get("splash_enabled", True))
        )

        self.animate_var = ctk.BooleanVar(value=bool(settings_store.get(theme_transition.SETTING_KEY, True)))
        # While this dialog is open the switch decides at once (before it is applied).
        theme_transition.ENABLED_OVERRIDE = bool(self.animate_var.get())
        self.animate_var.trace_add(
            "write", lambda *_: setattr(theme_transition, "ENABLED_OVERRIDE", bool(self.animate_var.get())))
        self.history_var = ctk.BooleanVar(value=history_store.enabled())
        self.wifi_var = ctk.BooleanVar(value=history_store.save_wifi_passwords())
        self._saved = self.values()          # what the dialog showed when it opened

        self._build_ui()
        self._refresh_selection()
        self._update_history_count()

    # ======================================================

    def _position(self, width, height):
        """Where the dialog goes: on screen, over the main window (see ``dialog_position``)."""
        from utils import window_guard
        try:
            rect = (self.parent.winfo_toplevel().winfo_rootx(), self.parent.winfo_toplevel().winfo_rooty(),
                    self.parent.winfo_toplevel().winfo_rootx() + self.parent.winfo_toplevel().winfo_width(),
                    self.parent.winfo_toplevel().winfo_rooty() + self.parent.winfo_toplevel().winfo_height())
            scaling = self._get_window_scaling()
            return dialog_position(rect, window_guard.work_areas(), (round(width * scaling), round(height * scaling)))
        except tkinter.TclError:
            return None

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

        # Bottom buttons first so they stay visible; everything else scrolls above them.
        self.footer = ctk.CTkFrame(self.container, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=30, pady=(8, 20))
        button_frame = self.footer
        self.body = ctk.CTkScrollableFrame(
            self.container, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"], label_fg_color=theme["background"])
        self.body.pack(fill="both", expand=True)
        autohide_scrollbar(self.body)

        # ---------------- Title ---------------- #

        title_row = ctk.CTkFrame(self.body, fg_color="transparent")
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
            self.body,
            text="Personalise how Mosaiq looks. Themes preview instantly.",
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"],
        ).pack(anchor="w", padx=30, pady=(0, 18))

        # ---------------- Theme gallery ---------------- #

        self._section("THEME")

        grid = ctk.CTkFrame(self.body, fg_color="transparent")
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
            self.body, fg_color=theme["card"], corner_radius=12,
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

        # ---------------- Appearance ---------------- #

        self._section("APPEARANCE", pady=(22, 8))
        appearance = ctk.CTkFrame(
            self.body, fg_color=theme["card"], corner_radius=12,
            border_width=1, border_color=theme["border"],
        )
        appearance.pack(fill="x", padx=30)
        self._switch_row(appearance, "Animate theme changes",
                         "A liquid ink transition when the theme changes. Off, or with Windows "
                         "animations off, the theme changes at once.", self.animate_var)
        ctk.CTkFrame(appearance, height=14, fg_color="transparent").pack()

        # ---------------- History ---------------- #

        self._section("HISTORY", pady=(22, 8))
        history = ctk.CTkFrame(
            self.body, fg_color=theme["card"], corner_radius=12,
            border_width=1, border_color=theme["border"],
        )
        history.pack(fill="x", padx=30)
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

        # ---------------- Bottom Buttons ---------------- #

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

    def _switch_row(self, parent, title, subtitle, variable):
        theme = ThemeManager.get_theme()
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(14, 0))
        text_col = ctk.CTkFrame(row, fg_color="transparent")
        text_col.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text_col, text=title, anchor="w", font=("Segoe UI Semibold", 14),
                     text_color=theme["text"]).pack(fill="x")
        ctk.CTkLabel(text_col, text=subtitle, anchor="w", justify="left", wraplength=470,
                     font=("Segoe UI", 12), text_color=theme["text_secondary"]).pack(fill="x")
        ctk.CTkSwitch(
            row, text="", variable=variable, onvalue=True, offvalue=False, width=52,
            progress_color=theme["primary"], button_color=theme["text"],
            button_hover_color=theme["text_secondary"], fg_color=theme["scrollbar"],
            text_color=theme["text"]).pack(side="right", padx=(12, 0))

    def _update_history_count(self):
        count = history_store.count()
        self.history_count.configure(
            text=f"{count} saved" if count else "No saved codes")
        self.clear_button.configure(state="normal" if count else "disabled")

    def _clear_history(self):
        count = history_store.count()
        if not messagebox.askyesno(
                "Clear history",
                f"Remove all {count} saved codes and their previews from this PC?\n\n"
                f"This cannot be undone."):
            return
        history_store.clear()
        app = self._find_app()
        if app is not None and hasattr(app, "history_page"):
            app.history_page.refresh()
        self._update_history_count()

    def _section(self, text, pady=(0, 8)):
        ctk.CTkLabel(
            self.body, text=text,
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
        app = self._find_app()
        restyle = lambda: restyle_scrollable(self.body, "background")
        if app is not None and hasattr(app, "change_theme"):
            app.change_theme(name, also=restyle)       # with the blob transition on the windows
            return
        ThemeManager.set_theme(name, persist=False)
        if app is not None:
            app.refresh_theme()
        else:
            ThemeManager.retheme_tree(self)
        restyle()

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

    def destroy(self):
        theme_transition.ENABLED_OVERRIDE = None
        super().destroy()

    def values(self):
        """Every setting this dialog edits, as it stands now (the keys of settings.json)."""
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
        """Write all settings (one atomic write) and close. A failed write is shown and the dialog
        stays open with the choices intact. Returns True when saved."""
        try:
            settings_store.update(self.values())
        except settings_store.SettingsWriteError as e:
            messagebox.showerror("Could not save settings", str(e))
            return False
        ThemeManager.set_theme(self._selected, persist=False)       # already on disk
        app = self._find_app()
        if app is not None and hasattr(app, "history_page"):
            app.history_page.refresh()
        self.destroy()
        return True

    def cancel(self):
        """Back to what was set when the dialog opened (the theme too). Writes nothing."""
        if ThemeManager.get_current_theme() != self._original_theme:
            self._apply_live(self._original_theme)
        self.destroy()

    def close_requested(self):
        """The X button (or Escape): ask only if something changed."""
        if not self.has_changes():
            self.cancel()
            return
        choice = ask_save_changes(self)
        if choice == "save":
            self.apply()
        elif choice == "discard":
            self.cancel()
        # "cancel": stay in the dialog
