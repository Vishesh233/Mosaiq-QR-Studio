import webbrowser
import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons


class ScanResultCard(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            corner_radius=16,
            border_width=1,
            fg_color=theme["card"],
            border_color=theme["border"],
            width=380,
            height=520
        )

        self.pack_propagate(False)

        self.result = ""
        self.copy_callback = None

        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()

        # ----------------------------
        # Title
        # ----------------------------
        self.header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        self.header.pack(
            anchor="w",
            padx=20,
            pady=(20, 12)
        )

        self.status_dot = ctk.CTkFrame(
            self.header,
            width=12,
            height=12,
            fg_color="#22C55E",
            corner_radius=6
        )

        self.status_dot.pack(
            side="left",
            padx=(0, 10),
        )

        self.title = ctk.CTkLabel(
            self.header,
            text="Decoded Result",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title.pack(
            side="left",
        )

        self.divider = ctk.CTkFrame(
            self,
            height=1,
            fg_color=theme["border"]
        )

        self.divider.pack(fill="x", padx=20, pady=(0, 18))

        # ----------------------------
        # Status Chip
        # ----------------------------

        self.status_chip = ctk.CTkLabel(
            self,
            text="Waiting",
            height=34,
            corner_radius=17,
            fg_color=theme["entry"],
            text_color=theme["text_secondary"],
            padx=18,
            font=("Segoe UI Semibold", 12)
        )

        self.status_chip.pack(
            anchor="w",
            padx=20
        )

        # ----------------------------
        # Result Box
        # ----------------------------

        self.result_box = ctk.CTkFrame(
            self,
            border_width=1,
            fg_color=theme["entry"],
            border_color=theme["border"],
            corner_radius=14,
            height=128
        )

        self.result_box.pack(
            fill="x",
            padx=20,
            pady=(18, 20)
        )

        self.result_box.pack_propagate(False)

        # ----------------------------
        # Content Frame
        # ----------------------------

        self.content = ctk.CTkFrame(
            self.result_box,
            fg_color="transparent"
        )

        self.content.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=18
        )

        # ----------------------------
        # Icon
        # ----------------------------

        self.icon = ctk.CTkLabel(
            self.content,
            text=icons.icon("text"),
            width=24,
            font=icons.icon_font(20),
            text_color=theme["text_secondary"]
        )

        self.icon.pack(
            side="left",
            anchor="n",
            padx=(0, 14)
        )

        # ----------------------------
        # Result Label
        # ----------------------------

        self.result_label = ctk.CTkLabel(
            self.content,
            text="Upload a QR image to see decoded result.",
            justify="left",
            anchor="nw",
            wraplength=320,
            text_color=theme["text_secondary"],
            cursor="arrow",
            font=("Segoe UI", 14)
        )

        self.result_label.pack(
            side="left",
            fill="both",
            expand=True
        )

        # ----------------------------
        # Copy Button
        # ----------------------------

        self.copy_btn = ctk.CTkButton(
            self,
            text=f"{icons.icon('copy')}  Copy Result",
            width=200,
            height=46,
            corner_radius=12,
            border_width=0,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            border_color=theme["border"],
            text_color="#FFFFFF",
            state="disabled",
            command=self.on_copy,
            font=("Segoe UI Semibold", 14)
        )

        self.copy_btn.pack(
            anchor="center",
            pady=(18, 16)
        )

        self.divider2 = ctk.CTkFrame(
            self,
            height=1,
            fg_color=theme["border"]
        )

        self.divider2.pack(
            fill="x",
            padx=20,
            pady=(0, 16)
        )

        self.tips_frame = ctk.CTkFrame(
            self,
            fg_color=theme["entry"],
            corner_radius=12,
            border_width=1,
            border_color=theme["border"],
        )

        self.tips_frame.pack(
            fill="x",
            padx=20,
            pady=(0, 12)
        )

        self.tips_title = ctk.CTkLabel(
            self.tips_frame,
            text="TIPS",
            font=("Segoe UI Semibold", 13),
            text_color=theme["text"]
        )

        self.tips_title.pack(
            anchor="w",
            padx=16,
            pady=(8, 4)
        )

        self.tip_bullets = []
        self.tip_labels = []

        tips = [
            "Use high-resolution images",
            "Ensure good contrast in the QR",
            "Avoid cropped or blurry images"
        ]

        for tip in tips:

            row = ctk.CTkFrame(
                self.tips_frame,
                fg_color="transparent"
            )

            row.pack(
                anchor="w",
                padx=16,
                pady=1
            )

            bullet = ctk.CTkLabel(
                row,
                text="•",
                text_color=theme["primary"],
                font=("Segoe UI Bold", 16)
            )

            bullet.pack(side="left")
            self.tip_bullets.append(bullet)

            text = ctk.CTkLabel(
                row,
                text=tip,
                text_color=theme["text_secondary"],
                font=("Segoe UI", 13)
            )

            text.pack(side="left", padx=(8, 0))
            self.tip_labels.append(text)
        

    # ==================================================

    def set_result(self, text):

        self.result = text.strip()

        if not self.result:
            self.clear()
            return

        is_url = (
            "www." in self.result.lower()
            or self.result.lower().startswith(("http://", "https://"))
        )

        # ----------------------------
        # Result Text
        # ----------------------------

        self.result_label.configure(
            text= self.result,
            text_color=theme["primary"],
            cursor="hand2"
)

        # ----------------------------
        # Icon
        # ----------------------------

        self.icon.configure(
            text=icons.icon("link") if is_url else icons.icon("text"),
            text_color=theme["primary"] if is_url else theme["text"]
        )

        # ----------------------------
        # Status Chip
        # ----------------------------

        if is_url:

            self.status_chip.configure(
                text=f"{icons.icon('link')}  URL Detected",
                fg_color=theme["card_hover"],
                text_color=theme["primary"]
            )

            self.result_box.configure(
                border_color=theme["primary"]
            )

            self.result_label.bind(
                "<Button-1>",
                self.open_result
            )

            self.icon.bind(
                "<Button-1>",
                self.open_result
            )

        else:

            self.status_chip.configure(
                text=f"{icons.icon('text')}  Plain Text",
                fg_color=theme["card_hover"],
                text_color=theme["text"]
            )

            self.result_box.configure(
                border_color=theme["border"]
            )

            self.result_label.unbind("<Button-1>")
            self.icon.unbind("<Button-1>")

        self.copy_btn.configure(
            state="normal"
        )

    # ==================================================

    def clear(self):

        self.result = ""
        theme = ThemeManager.get_theme()
        self.icon.configure(
            text=icons.icon("text"),
            text_color=theme["text_secondary"]
        )

        self.result_label.configure(
            text="Upload a QR image to see decoded result.",
            text_color=theme["text_secondary"],
            cursor="arrow"
        )

        self.status_chip.configure(
            text="Waiting",
            fg_color=theme["entry"],
            text_color=theme["text_secondary"]
        )

        self.result_box.configure(
            border_color=theme["border"]
        )

        self.copy_btn.configure(
            state="disabled"
        )

        self.result_label.unbind("<Button-1>")
        self.icon.unbind("<Button-1>")

    # ==================================================

    def open_result(self, event=None):

        url = self.result.strip()

        if url.lower().startswith("www."):
            url = "https://" + url

        if url.lower().startswith(("http://", "https://")):
            webbrowser.open(url)

    # ==================================================

    def get_result(self):
        return self.result

    # ==================================================

    def set_copy_callback(self, callback):
        self.copy_callback = callback

    # ==================================================

    def on_copy(self):

        if not self.result:
            return

        self.clipboard_clear()
        self.clipboard_append(self.result)

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.title.configure(
            text_color=theme["text"]
        )

        self.divider.configure(
            fg_color=theme["border"]
        )

        self.divider2.configure(
            fg_color=theme["border"]
        )

        self.tips_frame.configure(
            fg_color=theme["entry"],
            border_color=theme["border"]
        )

        self.tips_title.configure(
            text_color=theme["text"]
        )

        for bullet in self.tip_bullets:
            bullet.configure(text_color=theme["primary"])

        for label in self.tip_labels:
            label.configure(text_color=theme["text_secondary"])

        self.copy_btn.configure(
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            border_color=theme["border"],
            text_color="#FFFFFF"
        )

        if not self.result:
            self.status_chip.configure(
                fg_color=theme["entry"],
                text_color=theme["text_secondary"]
            )

            self.result_box.configure(
                fg_color=theme["entry"],
                border_color=theme["border"]
            )

            self.result_label.configure(
                text_color=theme["text_secondary"]
            )

            self.icon.configure(
                text_color=theme["text_secondary"]
            )