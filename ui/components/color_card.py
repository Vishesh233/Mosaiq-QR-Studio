import customtkinter as ctk
import numpy as np
from PIL import Image

from ui.dialogs.color_picker import pick_color
from utils import colors, qr_presets
from utils.theme_manager import ThemeManager


def _chip_image(style, size=40):
    """A little picture of a preset's colours: its gradient, or the solid QR colour."""
    a = np.array(colors.hex_to_rgb(style.fg), dtype=np.float32)
    b = np.array(colors.hex_to_rgb(style.fg2 if style.gradient != "none" else style.fg),
                 dtype=np.float32)
    axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
    t = (axis[None, :] + axis[:, None]) / 2.0
    pixels = a[None, None, :] + (b - a)[None, None, :] * t[:, :, None]
    return Image.fromarray(np.clip(pixels + 0.5, 0, 255).astype("uint8"))


class PresetRow(ctk.CTkFrame):
    """One-click colour + style combinations."""

    def __init__(self, parent, command):
        super().__init__(parent, fg_color="transparent")
        self._command = command
        self._frames = {}
        self._captions = {}
        self._images = []           # kept: a label raises TclError if its CTkImage is collected
        theme = ThemeManager.get_theme()
        for column, preset in enumerate(qr_presets.PRESETS):
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.grid(row=0, column=column, padx=(0, 10))
            frame = ctk.CTkFrame(holder, width=48, height=48, corner_radius=12,
                                 border_width=2, border_color=theme["card"],
                                 fg_color=theme["card"])
            frame.pack()
            frame.pack_propagate(False)
            image = ctk.CTkImage(light_image=_chip_image(preset.style),
                                 dark_image=_chip_image(preset.style), size=(38, 38))
            self._images.append(image)
            chip = ctk.CTkLabel(frame, text="", image=image, corner_radius=10,
                                text_color=theme["text"])
            chip.place(relx=0.5, rely=0.5, anchor="center")
            caption = ctk.CTkLabel(holder, text=preset.name, font=("Segoe UI", 11),
                                   text_color=theme["text_secondary"])
            caption.pack(pady=(4, 0))
            for widget in (frame, chip, caption, holder):
                widget.bind("<Button-1>", lambda _e, n=preset.name: self._command(n))
            self._frames[preset.name] = frame
            self._captions[preset.name] = caption

    def set_selected(self, name):
        theme = ThemeManager.get_theme()
        for key, frame in self._frames.items():
            frame.configure(border_color=theme["primary"] if key == name else theme["card"])
            self._captions[key].configure(
                text_color=theme["text"] if key == name else theme["text_secondary"])
        self._selected = name

    def refresh_theme(self):
        self.set_selected(getattr(self, "_selected", None))
        theme = ThemeManager.get_theme()
        for frame in self._frames.values():
            frame.configure(fg_color=theme["card"])


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

        self.preset_label = ctk.CTkLabel(
            self, text="PRESETS", font=("Segoe UI", 11), anchor="w",
            text_color=ThemeManager.get_theme()["text_secondary"])
        self.preset_label.grid(row=0, column=0, columnspan=2, sticky="w")
        self.preset_row = PresetRow(self, command=self._preset_clicked)
        self.preset_row.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        self.preset_callback = None

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
        card.grid(row=2, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0))

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

    def _preset_clicked(self, name):
        if self.preset_callback:
            self.preset_callback(name)

    def refresh_theme(self):

        theme = ThemeManager.get_theme()
        self.preset_label.configure(text_color=theme["text_secondary"])
        self.preset_row.refresh_theme()

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
