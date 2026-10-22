import customtkinter as ctk
from ui.dialogs.color_picker import pick_color
from utils.theme_manager import ThemeManager


class ColorCard(ctk.CTkFrame):
    """Colours tab of the Design card: QR colour and background colour swatches."""

    DEFAULT_QR = "#000000"
    DEFAULT_BG = "#FFFFFF"

    def __init__(self, parent):

        super().__init__(parent, fg_color="transparent")

        self.qr_color = self.DEFAULT_QR
        self.bg_color = self.DEFAULT_BG
        self.change_callback = None

        self.grid_columnconfigure((0, 1), weight=1, uniform="swatch")

        self.qr_card, self.qr_preview, self.qr_hex, self.qr_caption = self._swatch(
            0, "qr", "QR colour · click to edit")
        self.bg_card, self.bg_preview, self.bg_hex, self.bg_caption = self._swatch(
            1, "bg", "Background · click to edit")

    # =====================================================

    def _swatch(self, column, color_type, caption):

        theme = ThemeManager.get_theme()
        color = self.qr_color if color_type == "qr" else self.bg_color

        card = ctk.CTkFrame(
            self, fg_color=theme["segment_bg"], corner_radius=11,
            border_width=1, border_color=theme["border"],
        )
        card.grid(row=0, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0))

        preview = ctk.CTkFrame(
            card, width=30, height=30, corner_radius=8,
            border_width=1, border_color=theme["border"], fg_color=color,
        )
        # Shows the user's colour, never a theme token.
        preview._theme_skip = True
        preview.pack(side="left", padx=(10, 10), pady=10)

        texts = ctk.CTkFrame(card, fg_color="transparent")
        texts.pack(side="left", fill="x", pady=8)

        hex_label = ctk.CTkLabel(texts, text=color, anchor="w",
                                 font=("Segoe UI Semibold", 13), text_color=theme["text"])
        hex_label.pack(anchor="w")
        caption_label = ctk.CTkLabel(texts, text=caption, anchor="w",
                                     font=("Segoe UI", 11), text_color=theme["text_secondary"])
        caption_label.pack(anchor="w")

        for widget in (card, preview, texts, hex_label, caption_label):
            widget.bind("<Button-1>", lambda _e, t=color_type: self.choose_color(t))
        try:
            card.configure(cursor="hand2")
        except Exception:
            pass
        return card, preview, hex_label, caption_label

    # =====================================================

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        for card, preview, hex_label, caption in (
            (self.qr_card, self.qr_preview, self.qr_hex, self.qr_caption),
            (self.bg_card, self.bg_preview, self.bg_hex, self.bg_caption),
        ):
            card.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
            # The swatch shows the user's colour; only its border follows the theme.
            preview.configure(border_color=theme["border"])
            hex_label.configure(text_color=theme["text"])
            caption.configure(text_color=theme["text_secondary"])

    # =====================================================

    def choose_color(self, color_type):

        current = self.qr_color if color_type == "qr" else self.bg_color
        title = "QR colour" if color_type == "qr" else "Background colour"
        color = pick_color(self, current, title)

        if color is None:
            return

        if color_type == "qr":
            self.set_colors(qr=color)
        else:
            self.set_colors(bg=color)

    # =====================================================

    def set_colors(self, qr=None, bg=None):
        """Show (and use) new colours; ``None`` leaves that colour as it is."""

        if qr is not None:
            self.qr_color = qr.upper()
            self.qr_preview.configure(fg_color=self.qr_color)
            self.qr_hex.configure(text=self.qr_color)

        if bg is not None:
            self.bg_color = bg.upper()
            self.bg_preview.configure(fg_color=self.bg_color)
            self.bg_hex.configure(text=self.bg_color)

        if self.change_callback:
            self.change_callback()

    def get_qr_color(self):
        return self.qr_color

    def get_bg_color(self):
        return self.bg_color

    def reset_colors(self):
        self.set_colors(qr=self.DEFAULT_QR, bg=self.DEFAULT_BG)
