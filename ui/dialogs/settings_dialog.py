import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons


class SettingsDialog(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent

        self.title("Settings")
        self.geometry("520x560")
        self.resizable(False, False)

        # Modal behaviour + clean focus return to the parent window.
        self.transient(parent)
        self.grab_set()

        self.theme_var = ctk.StringVar(
            value=ThemeManager.get_current_theme()
        )

        self._build_ui()

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

        # ---------------- Main Container ---------------- #

        self.container = ctk.CTkFrame(
            self,
            fg_color=theme["background"],
            corner_radius=0
        )
        self.container.pack(fill="both", expand=True)

        # ---------------- Title ---------------- #

        title_row = ctk.CTkFrame(self.container, fg_color="transparent")
        title_row.pack(anchor="w", padx=30, pady=(25, 10))

        ctk.CTkLabel(
            title_row,
            text=icons.icon("settings"),
            font=icons.icon_font(24),
            text_color=theme["primary"],
        ).pack(side="left", padx=(0, 12))

        self.title_label = ctk.CTkLabel(
            title_row,
            text="Settings",
            font=("Segoe UI Semibold", 22),
            text_color=theme["text"]
        )
        self.title_label.pack(side="left")

        # ---------------- Appearance ---------------- #

        self.appearance_label = ctk.CTkLabel(
            self.container,
            text="Appearance",
            font=("Segoe UI Semibold", 15),
            text_color=theme["text"]
        )
        self.appearance_label.pack(anchor="w", padx=30, pady=(15, 8))

        self.theme_label = ctk.CTkLabel(
            self.container,
            text="Theme",
            font=("Segoe UI", 13),
            text_color=theme["text_secondary"]
        )
        self.theme_label.pack(anchor="w", padx=30)

        self.theme_menu = ctk.CTkOptionMenu(
            self.container,
            values=ThemeManager.get_theme_names(),
            variable=self.theme_var,
            width=240,
            height=38,
            corner_radius=10,
            fg_color=theme["card"],
            button_color=theme["primary"],
            button_hover_color=theme["primary_hover"],
            dropdown_fg_color=theme["panel"],
            dropdown_hover_color=theme["card_hover"],
            dropdown_text_color=theme["text"],
            text_color=theme["text"],
            command=self.preview_theme
        )
        self.theme_menu.pack(anchor="w", padx=30, pady=(8, 25))

        # ---------------- Preview Card ---------------- #

        self.preview = ctk.CTkFrame(
            self.container,
            fg_color=theme["card"],
            corner_radius=14,
            border_width=1,
            border_color=theme["border"]
        )
        self.preview.pack(fill="x", padx=30)

        self.preview_title = ctk.CTkLabel(
            self.preview,
            text="Preview",
            font=("Segoe UI Semibold", 15),
            text_color=theme["text"]
        )
        self.preview_title.pack(anchor="w", padx=20, pady=(18, 10))

        self.sample_entry = ctk.CTkEntry(
            self.preview,
            placeholder_text="Sample Entry",
            height=38,
            corner_radius=10,
            fg_color=theme["entry"],
            border_color=theme["entry_border"],
            text_color=theme["text"],
        )
        self.sample_entry.pack(fill="x", padx=20)

        self.sample_button = ctk.CTkButton(
            self.preview,
            text="Sample Button",
            width=160,
            height=38,
            corner_radius=10,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color="#FFFFFF",
        )
        self.sample_button.pack(padx=20, pady=20)

        # ---------------- Bottom Buttons ---------------- #

        button_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        button_frame.pack(side="bottom", fill="x", padx=30, pady=25)

        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120,
            height=40,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text"],
            command=self.destroy
        )
        self.cancel_btn.pack(side="right")

        self.apply_btn = ctk.CTkButton(
            button_frame,
            text="Apply",
            width=120,
            height=40,
            corner_radius=10,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color="#FFFFFF",
            command=self.apply_theme
        )
        self.apply_btn.pack(side="right", padx=(0, 12))

    # ======================================================

    def preview_theme(self, theme_name):

        theme = ThemeManager.THEMES[theme_name]

        self.container.configure(fg_color=theme["background"])
        self.title_label.configure(text_color=theme["text"])
        self.appearance_label.configure(text_color=theme["text"])
        self.theme_label.configure(text_color=theme["text_secondary"])

        self.preview.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )
        self.preview_title.configure(text_color=theme["text"])

        self.theme_menu.configure(
            fg_color=theme["card"],
            button_color=theme["primary"],
            button_hover_color=theme["primary_hover"],
            dropdown_fg_color=theme["panel"],
            dropdown_hover_color=theme["card_hover"],
            text_color=theme["text"],
        )

        self.cancel_btn.configure(
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text"],
        )

        self.sample_entry.configure(
            fg_color=theme["entry"],
            border_color=theme["entry_border"],
            text_color=theme["text"]
        )

        self.sample_button.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"]
        )

        self.apply_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"]
        )

    # ======================================================

    def apply_theme(self):

        ThemeManager.set_theme(self.theme_var.get())

        app = self._find_app()
        if app:
            app.refresh_theme()

        self.destroy()
