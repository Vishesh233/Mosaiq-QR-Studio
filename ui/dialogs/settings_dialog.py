import customtkinter as ctk

from utils.theme_manager import ThemeManager


class SettingsDialog(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent

        self.title("Settings")
        self.geometry("500x520")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()

        self.theme_var = ctk.StringVar(
            value=ThemeManager.get_current_theme()
        )

        self._build_ui()

    # ======================================================

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

        self.title_label = ctk.CTkLabel(
            self.container,
            text="⚙ Settings",
            font=("Segoe UI", 24, "bold"),
            text_color=theme["text"]
        )
        self.title_label.pack(
            anchor="w",
            padx=30,
            pady=(25, 10)
        )

        # ---------------- Appearance ---------------- #

        self.appearance_label = ctk.CTkLabel(
            self.container,
            text="Appearance",
            font=("Segoe UI", 18, "bold"),
            text_color=theme["text"]
        )
        self.appearance_label.pack(
            anchor="w",
            padx=30,
            pady=(15, 8)
        )

        self.theme_label = ctk.CTkLabel(
            self.container,
            text="Theme",
            font=("Segoe UI", 14),
            text_color=theme["text_secondary"]
        )
        self.theme_label.pack(
            anchor="w",
            padx=30
        )

        self.theme_menu = ctk.CTkOptionMenu(
            self.container,
            values=ThemeManager.get_theme_names(),
            variable=self.theme_var,
            width=220,
            command=self.preview_theme
        )

        self.theme_menu.pack(
            anchor="w",
            padx=30,
            pady=(8, 25)
        )

        # ---------------- Preview Card ---------------- #

        self.preview = ctk.CTkFrame(
            self.container,
            fg_color=theme["card"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border"]
        )

        self.preview.pack(
            fill="x",
            padx=30
        )

        self.preview_title = ctk.CTkLabel(
            self.preview,
            text="Preview",
            font=("Segoe UI", 18, "bold"),
            text_color=theme["text"]
        )

        self.preview_title.pack(
            anchor="w",
            padx=20,
            pady=(18, 10)
        )

        self.sample_entry = ctk.CTkEntry(
            self.preview,
            placeholder_text="Sample Entry"
        )

        self.sample_entry.pack(
            fill="x",
            padx=20
        )

        self.sample_button = ctk.CTkButton(
            self.preview,
            text="Sample Button"
        )

        self.sample_button.pack(
            padx=20,
            pady=20
        )

        # ---------------- Bottom Buttons ---------------- #

        button_frame = ctk.CTkFrame(
            self.container,
            fg_color="transparent"
        )

        button_frame.pack(
            side="bottom",
            fill="x",
            padx=30,
            pady=25
        )

        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color=theme["border"],
            command=self.destroy
        )

        self.cancel_btn.pack(
            side="right"
        )

        self.apply_btn = ctk.CTkButton(
            button_frame,
            text="Apply",
            width=120,
            command=self.apply_theme
        )

        self.apply_btn.pack(
            side="right",
            padx=(0, 12)
        )

    # ======================================================

    def preview_theme(self, theme_name):

        theme = ThemeManager.THEMES[theme_name]

        self.container.configure(
            fg_color=theme["background"]
        )

        self.title_label.configure(
            text_color=theme["text"]
        )

        self.appearance_label.configure(
            text_color=theme["text"]
        )

        self.theme_label.configure(
            text_color=theme["text_secondary"]
        )

        self.preview.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.preview_title.configure(
            text_color=theme["text"]
        )

        self.cancel_btn.configure(
            border_color=theme["border"]
        )

        self.sample_entry.configure(
            fg_color=theme["entry"],
            border_color=theme["border"],
            text_color=theme["text"]
        )

        self.sample_button.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"]
        )

    def apply_theme(self):

        ThemeManager.set_theme(
            self.theme_var.get()
        )

        app = getattr(self.parent.master, "app", None)

        if app:
            app.refresh_theme()

        self.destroy()