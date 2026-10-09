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
        self._brand_icon = None
        self._brand_title = None
        self._version_label = None
        self._section_label = None
        self._footer_sep = None

        self.grid_propagate(False)
        self._build()

    # ------------------------------------------------------------------
    def _build(self):
        theme = ThemeManager.get_theme()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- Brand ----------------
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(22, 10))

        self._brand_mark = ctk.CTkFrame(
            brand, width=38, height=38, corner_radius=10,
            fg_color=theme["primary"],
        )
        self._brand_mark.grid(row=0, column=0)
        self._brand_mark.grid_propagate(False)
        self._brand_icon = ctk.CTkLabel(
            self._brand_mark, text=icons.icon("app"),
            font=icons.icon_font(20), text_color="#FFFFFF",
        )
        self._brand_icon.place(relx=0.5, rely=0.5, anchor="center")

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

        # ---------------- Footer (version / app info) ----------------
        self._footer_sep = ctk.CTkFrame(self, height=1, fg_color=theme["border"])
        self._footer_sep.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))

        self._version_label = ctk.CTkLabel(
            self,
            text=f"{APP_NAME}  ·  {APP_VERSION}",
            font=("Segoe UI", 10), text_color=theme["text_secondary"],
        )
        self._version_label.grid(row=3, column=0, sticky="w", padx=20, pady=(0, 16))

        self._refresh_active()

    # ------------------------------------------------------------------
    def _make_nav_item(self, parent, row, icon_name, label, command):
        theme = ThemeManager.get_theme()

        btn = ctk.CTkButton(
            parent,
            text=f"{icons.icon(icon_name)}   {label}",
            anchor="w",
            width=190, height=44,
            corner_radius=10,
            fg_color="transparent",
            text_color=theme["text_secondary"],
            hover_color=theme["card_hover"],
            border_width=0,
            font=("Segoe UI Semibold", 13),
            command=command,
        )
        btn.grid(row=row, column=0, sticky="ew", pady=3)
        return btn

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
            self._brand_mark.configure(fg_color=theme["primary"])
        if self._brand_icon is not None:
            self._brand_icon.configure(text_color="#FFFFFF")
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
