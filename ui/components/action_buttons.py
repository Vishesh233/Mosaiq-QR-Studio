import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons


class ActionButtons(ctk.CTkFrame):

    def __init__(self, parent):
        
        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.generate_callback = None
        self.copy_callback = None
        self.save_callback = None
        self.clear_callback = None

        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # ---------------- Generate ---------------- #

        self.generate_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('generate')}  Generate QR",
            width=150,
            height=48,
            corner_radius=12,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color="#FFFFFF",
            font=("Segoe UI Semibold", 13),
            command=self.on_generate
        )

        self.generate_btn.grid(
            row=0,
            column=0,
            padx=(0, 10),
            sticky="ew"
        )

        # ---------------- Copy ---------------- #

        self.copy_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('copy')}  Copy",
            width=110,
            height=48,
            corner_radius=12,
            fg_color=theme["card"],
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
            font=("Segoe UI Semibold", 13),
            state="disabled",
            command=self.on_copy
        )

        self.copy_btn.grid(
            row=0,
            column=1,
            padx=(0, 10),
            sticky="ew"
        )

        # ---------------- Save ---------------- #

        self.save_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('save')}  Save As",
            width=120,
            height=48,
            corner_radius=12,
            fg_color=theme["card"],
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
            font=("Segoe UI Semibold", 13),
            state="disabled",
            command=self.on_save
        )

        self.save_btn.grid(
            row=0,
            column=2,
            padx=(0, 10),
            sticky="ew"
        )

        # ---------------- Clear ---------------- #

        self.clear_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('delete')}  Clear",
            width=110,
            height=48,
            corner_radius=12,
            fg_color="transparent",
            border_width=1,
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["danger"],
            font=("Segoe UI Semibold", 13),
            command=self.on_clear
        )

        self.clear_btn.grid(
            row=0,
            column=3,
            sticky="ew"
        )

    # ==================================================

    def enable_export_buttons(self):

        self.copy_btn.configure(
            state="normal",
            text_color=ThemeManager.get_theme()["text"]
        )

        self.save_btn.configure(
            state="normal",
            text_color=ThemeManager.get_theme()["text"]
        )

    # ==================================================

    def disable_export_buttons(self):

        self.copy_btn.configure(
            state="disabled",
            text_color=ThemeManager.get_theme()["text_secondary"]
        )

        self.save_btn.configure(
            state="disabled",
            text_color=ThemeManager.get_theme()["text_secondary"]
        )

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.generate_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"]
        )

        self.copy_btn.configure(
            fg_color=theme["card"],
            border_color=theme["border"],
            hover_color=theme["card_hover"]
        )

        self.save_btn.configure(
            fg_color=theme["card"],
            border_color=theme["border"],
            hover_color=theme["card_hover"]
        )

        self.clear_btn.configure(
            border_color=theme["border"],
            hover_color=theme["card_hover"],
            text_color=theme["danger"]
        )

        # Preserve enabled/disabled text colors
        if str(self.copy_btn.cget("state")) == "disabled":
            self.copy_btn.configure(text_color=theme["text_secondary"])
        else:
            self.copy_btn.configure(text_color=theme["text"])

        if str(self.save_btn.cget("state")) == "disabled":
            self.save_btn.configure(text_color=theme["text_secondary"])
        else:
            self.save_btn.configure(text_color=theme["text"])

    # ==================================================

    def set_generate_callback(self, callback):
        self.generate_callback = callback

    def set_copy_callback(self, callback):
        self.copy_callback = callback

    def set_save_callback(self, callback):
        self.save_callback = callback

    def set_clear_callback(self, callback):
        self.clear_callback = callback

    # ==================================================

    def on_generate(self):

        if self.generate_callback:
            self.generate_callback()

    def on_copy(self):

        if self.copy_callback:
            self.copy_callback()

    def on_save(self):

        if self.save_callback:
            self.save_callback()

    def on_clear(self):

        if self.clear_callback:
            self.clear_callback()