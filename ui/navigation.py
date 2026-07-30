import customtkinter as ctk

from utils.theme_manager import ThemeManager


class Navigation(ctk.CTkFrame):

    def __init__(self, parent):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        theme = ThemeManager.get_theme()

        self.generate_callback = None
        self.scan_callback = None

        # Track active tab
        self.active_tab = "generate"

        # ==========================
        # Outer Capsule
        # ==========================

        self.container = ctk.CTkFrame(
            self,
            width=220,
            height=50,
            fg_color=theme["card"],
            corner_radius=25
        )

        self.container.pack()
        self.container.pack_propagate(False)

        # ==========================
        # Generate Button
        # ==========================

        self.generate_btn = ctk.CTkButton(
            self.container,
            text="⚡  Generate",
            width=110,
            height=34,
            corner_radius=18,
            fg_color=theme["primary"],
            hover_color=theme["primary"],
            text_color=theme["text"],
            command=self.on_generate
        )

        self.generate_btn.pack(
            side="left",
            padx=(8, 4),
            pady=8
        )

        # ==========================
        # Scan Button
        # ==========================

        self.scan_btn = ctk.CTkButton(
            self.container,
            text=" Scan QR",
            width=110,
            height=34,
            corner_radius=18,
            fg_color="transparent",
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"],
            command=self.on_scan
        )

        self.scan_btn.pack(
            side="left",
            padx=(4, 8),
            pady=8
        )

    # ==================================================

    def set_generate_callback(self, callback):
        self.generate_callback = callback

    def set_scan_callback(self, callback):
        self.scan_callback = callback

    # ==================================================

    def on_generate(self):

        theme = ThemeManager.get_theme()

        self.active_tab = "generate"

        self.generate_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary"],
            text_color=theme["text"]
        )

        self.scan_btn.configure(
            fg_color="transparent",
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"]
        )

        if self.generate_callback:
            self.generate_callback()

    # ==================================================

    def on_scan(self):

        theme = ThemeManager.get_theme()

        self.active_tab = "scan"

        self.scan_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary"],
            text_color=theme["text"]
        )

        self.generate_btn.configure(
            fg_color="transparent",
            hover_color=theme["card_hover"],
            text_color=theme["text_secondary"]
        )

        if self.scan_callback:
            self.scan_callback()

    # ==================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.container.configure(
            fg_color=theme["card"]
        )

        if self.active_tab == "generate":

            self.generate_btn.configure(
                fg_color=theme["primary"],
                hover_color=theme["primary"],
                text_color=theme["text"]
            )

            self.scan_btn.configure(
                fg_color="transparent",
                hover_color=theme["card_hover"],
                text_color=theme["text_secondary"]
            )

        else:

            self.scan_btn.configure(
                fg_color=theme["primary"],
                hover_color=theme["primary"],
                text_color=theme["text"]
            )

            self.generate_btn.configure(
                fg_color="transparent",
                hover_color=theme["card_hover"],
                text_color=theme["text_secondary"]
            )