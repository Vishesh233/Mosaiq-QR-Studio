"""Left navigation sidebar.

Fixed-width sidebar: brand, icon + label navigation with an accent bar on the active item,
and a compact footer (current theme + Settings). Navigation entries are added by the app
with ``add_nav_item`` so a page only appears once it exists.
"""
import customtkinter as ctk

from config import APP_SHORT_NAME, APP_VERSION, SIDEBAR_WIDTH
from utils.theme_manager import ThemeManager
from ui import icons
from ui.brand_logo import logo_ctk_image
from ui.line_icons import line_icon
from ui.widgets import ThemeDot


class Sidebar(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=theme["navbar"],
        )

        self.active_tab = "generate"
        self._nav_callbacks = {}
        self._nav_icons = {}

        # Refs kept so we can restyle everything on theme change.
        self._nav_buttons = {}
        self._indicators = {}
        self._brand_mark = None
        self._brand_title = None
        self._brand_sub = None
        self._section_label = None
        self._footer_sep = None
        self._theme_dot = None
        self._theme_name_label = None
        self._settings_link = None

        self.grid_propagate(False)
        self._build()

    # ------------------------------------------------------------------
    def _brand_logo_image(self):
        """Cached premium brand mark (kept alive on self for Tk)."""
        try:
            img = logo_ctk_image(size=38)
        except Exception:
            return None
        self._brand_logo_ref = img
        return img

    # ------------------------------------------------------------------
    def _build(self):
        theme = ThemeManager.get_theme()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- Brand ----------------
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(24, 16))

        self._brand_mark = ctk.CTkLabel(
            brand, text="",
            image=self._brand_logo_image(),
            fg_color="transparent",
            text_color=theme["text"],
        )
        self._brand_mark.grid(row=0, column=0)

        text_col = ctk.CTkFrame(brand, fg_color="transparent")
        text_col.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self._brand_title = ctk.CTkLabel(
            text_col, text=APP_SHORT_NAME.upper(),
            font=("Segoe UI Semibold", 14), text_color=theme["text"],
        )
        self._brand_title.grid(row=0, column=0, sticky="w")
        self._brand_sub = ctk.CTkLabel(
            text_col, text=f"QR Studio  ·  {APP_VERSION}",
            font=("Segoe UI", 11), text_color=theme["text_secondary"],
        )
        self._brand_sub.grid(row=1, column=0, sticky="w")

        # ---------------- Nav section ----------------
        self._nav_wrap = ctk.CTkFrame(self, fg_color="transparent")
        self._nav_wrap.grid(row=1, column=0, sticky="new", pady=(8, 0))
        self._nav_wrap.grid_columnconfigure(0, weight=1)

        self._section_label = ctk.CTkLabel(
            self._nav_wrap, text="WORKSPACE",
            font=("Segoe UI Semibold", 10), text_color=theme["text_secondary"],
        )
        self._section_label.grid(row=0, column=0, sticky="w", padx=24, pady=(0, 8))

        # ---------------- Footer: theme name + Settings ----------------
        self._footer_sep = ctk.CTkFrame(self, height=1, fg_color=theme["border"])
        self._footer_sep.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        footer.grid_columnconfigure(1, weight=1)

        self._theme_dot = ThemeDot(footer)
        self._theme_dot.grid(row=0, column=0, padx=(0, 4))
        self._theme_name_label = ctk.CTkLabel(
            footer, text=ThemeManager.get_current_theme(),
            font=("Segoe UI", 11), text_color=theme["text_secondary"],
        )
        self._theme_name_label.grid(row=0, column=1, sticky="w")
        self._settings_link = ctk.CTkButton(
            footer, text=f"{icons.icon('settings')}  Settings",
            font=("Segoe UI", 11), width=0, height=28, corner_radius=8,
            fg_color="transparent", hover_color=theme["card_hover"],
            text_color=theme["text_secondary"], command=self._open_settings,
        )
        self._settings_link.grid(row=0, column=2, sticky="e")

    # ------------------------------------------------------------------
    def add_nav_item(self, key, label, icon_name, callback):
        """Add a navigation entry (icon + label). Order of calls = order on screen."""
        theme = ThemeManager.get_theme()
        self._nav_callbacks[key] = callback
        self._nav_icons[key] = icon_name
        row = len(self._nav_buttons) + 1

        item = ctk.CTkFrame(self._nav_wrap, fg_color="transparent")
        item.grid(row=row, column=0, sticky="ew", pady=2)
        item.grid_columnconfigure(1, weight=1)

        # Accent bar on the sidebar's left edge for the active item.
        bar = ctk.CTkFrame(item, width=3, height=26, corner_radius=2, fg_color="transparent")
        bar.grid(row=0, column=0, padx=(0, 11))
        self._indicators[key] = bar

        btn = ctk.CTkButton(
            item,
            text=f"  {label}",
            image=line_icon(icon_name, theme["text_secondary"], 18),
            compound="left",
            anchor="w",
            height=40,
            corner_radius=10,
            fg_color="transparent",
            text_color=theme["text_secondary"],
            hover_color=theme["card_hover"],
            border_width=0,
            font=("Segoe UI Semibold", 13),
            command=lambda k=key: self.navigate(k),
        )
        btn.grid(row=0, column=1, sticky="ew", padx=(0, 14))
        self._nav_buttons[key] = btn
        self._refresh_active()

    # ------------------------------------------------------------------
    def _open_settings(self):
        app = getattr(self.winfo_toplevel(), "app", None)
        if app is not None:
            app.header.open_settings()

    def navigate(self, key):
        """A click on a nav item: highlight it and open its page."""
        self.set_active(key)
        callback = self._nav_callbacks.get(key)
        if callback:
            callback()

    def set_active(self, tab):
        self.active_tab = tab
        self._refresh_active()

    def _refresh_active(self):
        theme = ThemeManager.get_theme()
        for key, bar in self._indicators.items():
            bar.configure(fg_color=theme["primary"] if key == self.active_tab else "transparent")
        for key, btn in self._nav_buttons.items():
            active = key == self.active_tab
            color = theme["text"] if active else theme["text_secondary"]
            btn.configure(
                fg_color=theme["segment_hover"] if active else "transparent",
                hover_color=theme["segment_hover"] if active else theme["card_hover"],
                text_color=color,
                image=line_icon(self._nav_icons[key], theme["primary"] if active else color, 18),
            )

    # ------------------------------------------------------------------
    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        self.configure(fg_color=theme["navbar"])
        if self._brand_mark is not None:
            try:
                img = self._brand_logo_image()
                if img is not None:
                    self._brand_mark.configure(image=img)
            except Exception:
                pass
        self._brand_title.configure(text_color=theme["text"])
        self._brand_sub.configure(text_color=theme["text_secondary"])
        self._section_label.configure(text_color=theme["text_secondary"])
        self._footer_sep.configure(fg_color=theme["border"])
        self._theme_name_label.configure(
            text=ThemeManager.get_current_theme(), text_color=theme["text_secondary"])
        self._theme_dot.refresh_theme()          # blends to the new colour with a spreading ring
        self._settings_link.configure(
            hover_color=theme["card_hover"], text_color=theme["text_secondary"])
        self._refresh_active()
