"""Left navigation sidebar for QR Code Studio v2.

Premium fixed-width sidebar with branding, icon+label navigation, an active
state, hover feedback, and a version footer. Preserves the original
navigation callback API (set_generate_callback / set_scan_callback) so the
application shell wiring is unchanged.
"""
import customtkinter as ctk

from config import APP_NAME, APP_VERSION, SIDEBAR_WIDTH
from utils.theme_manager import ThemeManager
from ui import icons
from ui.brand_logo import logo_ctk_image


class Sidebar(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            width=SIDEBAR_WIDTH,
            corner_radius=0,
            fg_color=theme["navbar"],
        )

        self.generate_callback = None
        self.scan_callback = None
        self.active_tab = "generate"

        # Refs kept so we can restyle the active item on theme change.
        self._nav_buttons = {}
        self._brand_mark = None
        self._brand_title = None
        self._version_label = None
        self._section_label = None
        self._footer_sep = None
        self._indicators = {}
        self._theme_dots = {}
        self._theme_name_label = None
        self._theme_label = None

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
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 10))

        self._brand_mark = ctk.CTkLabel(
            brand, text="",
            image=self._brand_logo_image(),
            fg_color="transparent",
        )
        self._brand_mark.grid(row=0, column=0)

        text_col = ctk.CTkFrame(brand, fg_color="transparent")
        text_col.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self._brand_title = ctk.CTkLabel(
            text_col, text="QR CODE STUDIO",
            font=("Segoe UI Semibold", 14), text_color=theme["text"],
        )
        self._brand_title.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            text_col, text=APP_VERSION,
            font=("Segoe UI", 11), text_color=theme["text_secondary"],
        ).grid(row=1, column=0, sticky="w")

        # ---------------- Nav section ----------------
        nav_wrap = ctk.CTkFrame(self, fg_color="transparent")
        nav_wrap.grid(row=1, column=0, sticky="nsw", padx=14, pady=(10, 0))

        self._section_label = ctk.CTkLabel(
            nav_wrap, text="WORKSPACE",
            font=("Segoe UI Semibold", 10), text_color=theme["text_secondary"],
        )
        self._section_label.grid(row=0, column=0, sticky="w", padx=8, pady=(0, 8))

        self._nav_buttons["generate"] = self._make_nav_item(
            nav_wrap, row=1, icon_name="generate", label="Generate",
            command=self.on_generate,
        )
        self._nav_buttons["scan"] = self._make_nav_item(
            nav_wrap, row=2, icon_name="scan", label="Scan QR",
            command=self.on_scan,
        )

        # ---------------- Quick theme switcher ----------------
        self._build_theme_switcher(row=2)

        # ---------------- Footer (version / app info) ----------------
        self._footer_sep = ctk.CTkFrame(self, height=1, fg_color=theme["border"])
        self._footer_sep.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 12))

        self._version_label = ctk.CTkLabel(
            self,
            text=f"{APP_NAME}  ·  {APP_VERSION}",
            font=("Segoe UI", 10), text_color=theme["text_secondary"],
        )
        self._version_label.grid(row=4, column=0, sticky="w", padx=20, pady=(0, 16))

        self._refresh_active()

    # ------------------------------------------------------------------
    def _make_nav_item(self, parent, row, icon_name, label, command):
        theme = ThemeManager.get_theme()

        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.grid(row=row, column=0, sticky="ew", pady=3)
        # Accent bar shown next to the active item.
        self._indicators[icon_name] = ctk.CTkFrame(
            item, width=4, height=24, corner_radius=2, fg_color="transparent",
        )
        self._indicators[icon_name].grid(row=0, column=0, padx=(0, 6))

        btn = ctk.CTkButton(
            item,
            text=f"{icons.icon(icon_name)}   {label}",
            anchor="w",
            width=184, height=44,
            corner_radius=10,
            fg_color="transparent",
            text_color=theme["text_secondary"],
            hover_color=theme["card_hover"],
            border_width=0,
            font=("Segoe UI Semibold", 13),
            command=command,
        )
        btn.grid(row=0, column=1, sticky="ew")
        return btn

    # ------------------------------------------------------------------
    def _build_theme_switcher(self, row):
        """THEME section: one dot per theme, coloured with its primary."""
        theme = ThemeManager.get_theme()

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", padx=22, pady=(0, 16))

        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x", pady=(0, 8))
        self._theme_label = ctk.CTkLabel(
            head, text="THEME",
            font=("Segoe UI Semibold", 10), text_color=theme["text_secondary"],
        )
        self._theme_label.pack(side="left")
        self._theme_name_label = ctk.CTkLabel(
            head, text=ThemeManager.get_current_theme(),
            font=("Segoe UI Semibold", 11), text_color=theme["text"],
        )
        self._theme_name_label.pack(side="right")

        # Each dot is a tiny swatch of its theme: the theme's own background
        # with its primary in the middle, so light and dark themes (and themes
        # sharing an accent) read differently at a glance; hovering shows the
        # name. The dots show other themes' colours: the live re-theme skips them.
        dots = ctk.CTkFrame(box, fg_color="transparent")
        dots._theme_skip = True
        dots.pack(fill="x")
        names = ThemeManager.get_theme_names()
        per_row = 4
        for index, name in enumerate(names):
            t = ThemeManager.THEMES[name]
            dot = ctk.CTkFrame(
                dots, width=34, height=34, corner_radius=17,
                fg_color=t["background"], border_width=2, border_color=theme["border"],
            )
            dot.grid(row=index // per_row, column=index % per_row,
                     padx=(0, 9), pady=(0, 8))
            dot.grid_propagate(False)
            core = ctk.CTkFrame(dot, width=14, height=14, corner_radius=7,
                                fg_color=t["primary"], bg_color=t["background"])
            core.place(relx=0.5, rely=0.5, anchor="center")
            for widget in (dot, core):
                widget.bind("<Button-1>", lambda _e, n=name: self._pick_theme(n))
                widget.bind("<Enter>", lambda _e, n=name: self._show_theme_name(n))
                widget.bind("<Leave>", lambda _e: self._show_theme_name(None))
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass
            self._theme_dots[name] = dot
        self._refresh_theme_switcher()

    def _show_theme_name(self, name):
        """Name of the hovered theme (with its mode), or the active one."""
        if self._theme_name_label is None:
            return
        if name is None:
            self._theme_name_label.configure(text=ThemeManager.get_current_theme())
        else:
            self._theme_name_label.configure(
                text="%s · %s" % (name, ThemeManager.THEMES[name]["mode"]))

    def _refresh_theme_switcher(self):
        theme = ThemeManager.get_theme()
        current = ThemeManager.get_current_theme()
        if self._theme_label is not None:
            self._theme_label.configure(text_color=theme["text_secondary"])
        if self._theme_name_label is not None:
            self._theme_name_label.configure(text=current, text_color=theme["text"])
        for name, dot in self._theme_dots.items():
            # A ring in the primary colour marks the active theme.
            dot.configure(
                border_color=theme["primary"] if name == current else theme["border"],
                border_width=3 if name == current else 2,
                bg_color=theme["navbar"],
            )

    def _pick_theme(self, name):
        if name == ThemeManager.get_current_theme():
            return
        ThemeManager.set_theme(name)
        app = getattr(self.winfo_toplevel(), "app", None)
        if app is not None:
            app.refresh_theme()
        else:
            self.refresh_theme()

    # ------------------------------------------------------------------
    def set_generate_callback(self, callback):
        self.generate_callback = callback

    def set_scan_callback(self, callback):
        self.scan_callback = callback

    # ------------------------------------------------------------------
    def on_generate(self):
        self.set_active("generate")
        if self.generate_callback:
            self.generate_callback()

    def on_scan(self):
        self.set_active("scan")
        if self.scan_callback:
            self.scan_callback()

    # ------------------------------------------------------------------
    def set_active(self, tab):
        self.active_tab = tab
        self._refresh_active()

    def _refresh_active(self):
        theme = ThemeManager.get_theme()
        for name, bar in self._indicators.items():
            bar.configure(fg_color=theme["primary"] if name == self.active_tab else "transparent")
        for name, btn in self._nav_buttons.items():
            if name == self.active_tab:
                btn.configure(
                    fg_color=theme["card"],
                    text_color=theme["text"],
                    border_width=0,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme["text_secondary"],
                    border_width=0,
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
        if self._brand_title is not None:
            self._brand_title.configure(text_color=theme["text"])
        if self._version_label is not None:
            self._version_label.configure(text_color=theme["text_secondary"])
        if self._section_label is not None:
            self._section_label.configure(text_color=theme["text_secondary"])
        if self._footer_sep is not None:
            self._footer_sep.configure(fg_color=theme["border"])
        for btn in self._nav_buttons.values():
            btn.configure(hover_color=theme["card_hover"])
        self._refresh_active()
        self._refresh_theme_switcher()
