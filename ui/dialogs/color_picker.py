"""Theme-matched colour picker: saturation/value square, hue slider, HEX and RGB fields,
recent colours and presets. Replaces the old Windows colour dialog.

    colour = pick_color(parent, initial="#000000", title="QR colour")   # "#RRGGBB" or None
"""
import colorsys
import time
import tkinter

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from ui.brand_logo import apply_window_icon
from utils import colors
from utils.app_log import get_logger
from utils.theme_manager import ThemeManager

SV_WIDTH, SV_HEIGHT, HUE_HEIGHT = 376, 188, 16


class ColorPickerDialog(ctk.CTkToplevel):

    def __init__(self, parent, initial="#000000", title="Pick a colour"):
        super().__init__(parent)

        self.result = None
        self.initial = colors.parse_color(initial) or "#000000"
        self._h, self._s, self._v = 0.0, 0.0, 0.0
        self._hex = self.initial
        self._updating = False
        self._sv_photo = None
        self._hue_photo = None
        scale = self._get_window_scaling()
        self._sv_w, self._sv_h = int(SV_WIDTH * scale), int(SV_HEIGHT * scale)
        self._hue_h = int(HUE_HEIGHT * scale)

        theme = ThemeManager.get_theme()
        self.title(title)
        apply_window_icon(self)
        self.resizable(False, False)
        self.configure(fg_color=theme["background"])
        self.transient(parent.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self._build(theme)
        self.set_color(self.initial)

        self.update_idletasks()
        self._center_on(parent.winfo_toplevel())
        self._grab_when_visible()
        self.bind("<Escape>", lambda _e: self.cancel())
        self.bind("<Return>", lambda _e: self.apply())

    # ======================================================

    def _grab_when_visible(self):
        """Make the dialog modal once it is on screen (grab_set needs a viewable window).

        Waits at most two seconds: a dialog that never appears must not hang the app.
        """
        deadline = time.time() + 2.0
        while not self.winfo_viewable() and time.time() < deadline:
            self.update()
            time.sleep(0.02)
        if self.winfo_viewable():
            self.grab_set()
        else:
            get_logger().warning("Colour picker did not become visible; opened without a grab")

    def _center_on(self, window):
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        x = window.winfo_rootx() + max(0, (window.winfo_width() - width) // 2)
        y = window.winfo_rooty() + max(0, (window.winfo_height() - height) // 3)
        self.geometry(f"+{x}+{y}")

    def _label(self, parent, text):
        return ctk.CTkLabel(parent, text=text, font=("Segoe UI", 11), anchor="w",
                            text_color=ThemeManager.get_theme()["text_secondary"])

    def _build(self, theme):
        outer = ctk.CTkFrame(self, fg_color=theme["background"], corner_radius=0)
        outer.pack(fill="both", expand=True, padx=20, pady=18)

        # ---------------- saturation / value square ----------------
        self.sv_canvas = tkinter.Canvas(
            outer, width=self._sv_w, height=self._sv_h, highlightthickness=1,
            highlightbackground=theme["border"], bd=0, cursor="crosshair",
            bg=theme["card"])
        self.sv_canvas.pack()
        self._sv_item = self.sv_canvas.create_image(0, 0, anchor="nw")
        self._sv_ring = self.sv_canvas.create_oval(0, 0, 0, 0, outline="#FFFFFF", width=2)
        self._sv_ring_in = self.sv_canvas.create_oval(0, 0, 0, 0, outline="#000000", width=1)
        self.sv_canvas.bind("<Button-1>", self._sv_drag)
        self.sv_canvas.bind("<B1-Motion>", self._sv_drag)

        # ---------------- hue slider ----------------
        self.hue_canvas = tkinter.Canvas(
            outer, width=self._sv_w, height=self._hue_h, highlightthickness=1,
            highlightbackground=theme["border"], bd=0, cursor="hand2", bg=theme["card"])
        self.hue_canvas.pack(pady=(12, 0))
        self._hue_item = self.hue_canvas.create_image(0, 0, anchor="nw")
        self._hue_marker = self.hue_canvas.create_rectangle(
            0, 0, 0, 0, outline="#FFFFFF", width=2)
        self.hue_canvas.bind("<Button-1>", self._hue_drag)
        self.hue_canvas.bind("<B1-Motion>", self._hue_drag)
        self._render_hue_bar()

        # ---------------- preview + value fields ----------------
        row = ctk.CTkFrame(outer, fg_color="transparent")
        row.pack(fill="x", pady=(16, 0))

        preview = ctk.CTkFrame(row, fg_color="transparent")
        preview.pack(side="left")
        self.current_label = self._label(preview, "CURRENT → NEW")
        self.current_label.pack(anchor="w")
        swatches = ctk.CTkFrame(preview, fg_color="transparent")
        swatches.pack(anchor="w", pady=(4, 0))
        self.old_swatch = ctk.CTkFrame(swatches, width=52, height=44, corner_radius=8,
                                       border_width=1, border_color=theme["border"],
                                       fg_color=self.initial)
        self.old_swatch.pack(side="left")
        self.new_swatch = ctk.CTkFrame(swatches, width=52, height=44, corner_radius=8,
                                       border_width=1, border_color=theme["border"],
                                       fg_color=self.initial)
        self.new_swatch.pack(side="left", padx=(6, 0))
        for swatch in (self.old_swatch, self.new_swatch):
            swatch._theme_skip = True        # shows the user's colour, never a theme token
        self.old_swatch.bind("<Button-1>", lambda _e: self.set_color(self.initial))
        self.old_swatch.configure(cursor="hand2")

        fields = ctk.CTkFrame(row, fg_color="transparent")
        fields.pack(side="right", padx=(24, 0))

        hex_box = ctk.CTkFrame(fields, fg_color="transparent")
        hex_box.pack(side="left", padx=(0, 8))
        self.hex_label = self._label(hex_box, "HEX")
        self.hex_label.pack(anchor="w")
        self.hex_entry = self._entry(hex_box, 88)
        self.hex_entry.pack(pady=(4, 0))
        self.hex_entry.bind("<KeyRelease>", self._hex_typed)

        self.rgb_entries = []
        for name in ("R", "G", "B"):
            box = ctk.CTkFrame(fields, fg_color="transparent")
            box.pack(side="left", padx=(0, 6))
            self._label(box, name).pack(anchor="w")
            entry = self._entry(box, 44)
            entry.pack(pady=(4, 0))
            entry.bind("<KeyRelease>", self._rgb_typed)
            self.rgb_entries.append(entry)

        self.error_label = ctk.CTkLabel(outer, text="", anchor="w", height=16,
                                        font=("Segoe UI", 11), text_color=theme["danger"])
        self.error_label.pack(fill="x", pady=(6, 0))

        # ---------------- recent colours ----------------
        self._label(outer, "RECENT").pack(anchor="w", pady=(6, 4))
        self.recent_row = ctk.CTkFrame(outer, fg_color="transparent", height=28)
        self.recent_row.pack(fill="x")
        self._fill_swatches(self.recent_row, colors.load_recent(), empty="Colours you use appear here.")

        # ---------------- presets ----------------
        self._label(outer, "PRESETS").pack(anchor="w", pady=(12, 4))
        presets = ctk.CTkFrame(outer, fg_color="transparent")
        presets.pack(fill="x")
        self._fill_swatches(presets, colors.PRESET_COLORS, per_row=12)

        # ---------------- buttons ----------------
        buttons = ctk.CTkFrame(outer, fg_color="transparent")
        buttons.pack(fill="x", pady=(18, 0))
        ctk.CTkButton(
            buttons, text="Apply", width=110, height=38, corner_radius=10,
            fg_color=theme["primary"], hover_color=theme["primary_hover"],
            text_color=theme["on_primary"], font=("Segoe UI Semibold", 13),
            command=self.apply).pack(side="right")
        ctk.CTkButton(
            buttons, text="Cancel", width=100, height=38, corner_radius=10,
            fg_color="transparent", border_width=1, border_color=theme["border"],
            hover_color=theme["card_hover"], text_color=theme["text"],
            font=("Segoe UI", 13), command=self.cancel).pack(side="right", padx=(0, 10))

    def _entry(self, parent, width):
        theme = ThemeManager.get_theme()
        return ctk.CTkEntry(
            parent, width=width, height=34, corner_radius=9, border_width=1,
            border_color=theme["entry_border"], fg_color=theme["entry"],
            text_color=theme["text"], placeholder_text_color=theme["text_muted"],
            font=("Segoe UI", 13), justify="center")

    def _fill_swatches(self, holder, items, per_row=10, empty=""):
        theme = ThemeManager.get_theme()
        if not items and empty:
            ctk.CTkLabel(holder, text=empty, font=("Segoe UI", 11),
                         text_color=theme["text_muted"]).pack(anchor="w")
            return
        for index, color in enumerate(items):
            button = ctk.CTkButton(
                holder, text="", width=26, height=26, corner_radius=7,
                border_width=1, border_color=theme["border"], fg_color=color,
                hover=False, command=lambda c=color: self.set_color(c))
            button._theme_skip = True
            button.grid(row=index // per_row, column=index % per_row, padx=(0, 6), pady=(0, 6))

    # ======================================================
    # State
    # ======================================================

    @property
    def color(self):
        """The colour currently shown, "#RRGGBB"."""
        return self._hex

    def set_color(self, color, source=None):
        """Show ``color`` (any accepted spelling); returns False if it is not a colour.

        ``source`` ("hex" / "rgb") names the field the user is typing in, which is left alone.
        """
        parsed = colors.parse_color(color)
        if parsed is None:
            return False
        r, g, b = colors.hex_to_rgb(parsed)
        h, s, v = colors.rgb_to_hsv(r, g, b)
        if s > 1e-6 and v > 1e-6:
            hue_changed = abs(h - self._h) > 1e-6
            self._h = h
        else:
            hue_changed = False             # greys and black keep the hue where it was
        self._s, self._v = s, v
        self._hex = parsed
        self._refresh(hue_changed=hue_changed, source=source)
        return True

    def _set_from_hsv(self, h=None, s=None, v=None):
        if h is not None:
            self._h = min(1.0, max(0.0, h))
        if s is not None:
            self._s = min(1.0, max(0.0, s))
        if v is not None:
            self._v = min(1.0, max(0.0, v))
        self._hex = colors.rgb_to_hex(*colors.hsv_to_rgb(self._h, self._s, self._v))
        self._refresh(hue_changed=h is not None)

    # ======================================================
    # Drawing
    # ======================================================

    def _refresh(self, hue_changed, source=None):
        if hue_changed or self._sv_photo is None:
            self._render_sv()
        x = self._s * (self._sv_w - 1)
        y = (1.0 - self._v) * (self._sv_h - 1)
        self.sv_canvas.coords(self._sv_ring, x - 7, y - 7, x + 7, y + 7)
        self.sv_canvas.coords(self._sv_ring_in, x - 8, y - 8, x + 8, y + 8)
        hx = self._h * (self._sv_w - 1)
        self.hue_canvas.coords(self._hue_marker, hx - 3, 0, hx + 3, self._hue_h)

        self.new_swatch.configure(fg_color=self._hex)
        self._updating = True
        try:
            if source != "hex":
                self._write(self.hex_entry, self._hex)
            if source != "rgb":
                for entry, value in zip(self.rgb_entries, colors.hex_to_rgb(self._hex)):
                    self._write(entry, str(value))
        finally:
            self._updating = False
        self._mark_valid(True)

    @staticmethod
    def _write(entry, text):
        if entry.get() != text:
            entry.delete(0, "end")
            entry.insert(0, text)

    def _render_sv(self):
        base = np.array(colorsys.hsv_to_rgb(self._h, 1.0, 1.0)) * 255.0
        s = np.linspace(0.0, 1.0, self._sv_w)[None, :, None]
        v = np.linspace(1.0, 0.0, self._sv_h)[:, None, None]
        pixels = ((1.0 - s) * 255.0 + s * base) * v
        image = Image.fromarray(pixels.astype("uint8"))
        self._sv_photo = ImageTk.PhotoImage(image, master=self)
        self.sv_canvas.itemconfigure(self._sv_item, image=self._sv_photo)

    def _render_hue_bar(self):
        hues = np.linspace(0.0, 1.0, self._sv_w, endpoint=True)
        row = np.array([colorsys.hsv_to_rgb(h, 1.0, 1.0) for h in hues]) * 255.0
        pixels = np.repeat(row[None, :, :], self._hue_h, axis=0)
        image = Image.fromarray(pixels.astype("uint8"))
        self._hue_photo = ImageTk.PhotoImage(image, master=self)
        self.hue_canvas.itemconfigure(self._hue_item, image=self._hue_photo)

    # ======================================================
    # Input
    # ======================================================

    def _sv_drag(self, event):
        s = min(1.0, max(0.0, event.x / (self._sv_w - 1)))
        v = 1.0 - min(1.0, max(0.0, event.y / (self._sv_h - 1)))
        self._set_from_hsv(s=s, v=v)

    def _hue_drag(self, event):
        self._set_from_hsv(h=min(1.0, max(0.0, event.x / (self._sv_w - 1))))

    def _hex_typed(self, _event=None):
        if self._updating:
            return
        parsed = colors.parse_color(self.hex_entry.get())
        if parsed is None:
            self._mark_valid(False, "Enter a colour like #0E7490.")
            return
        self.set_color(parsed, source="hex")

    def _rgb_typed(self, _event=None):
        if self._updating:
            return
        values = []
        for entry in self.rgb_entries:
            text = entry.get().strip()
            if not text.isdigit() or not 0 <= int(text) <= 255:
                self._mark_valid(False, "R, G and B are numbers from 0 to 255.")
                return
            values.append(int(text))
        self.set_color(colors.rgb_to_hex(*values), source="rgb")

    def _mark_valid(self, ok, message=""):
        theme = ThemeManager.get_theme()
        border = theme["entry_border"] if ok else theme["danger"]
        for entry in (self.hex_entry, *self.rgb_entries):
            entry.configure(border_color=border)
        self.error_label.configure(text="" if ok else message)

    # ======================================================

    def apply(self):
        self.result = self._hex
        colors.remember(self._hex)
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()


def pick_color(parent, initial="#000000", title="Pick a colour"):
    """Open the picker and wait; the chosen "#RRGGBB", or None when cancelled."""
    dialog = ColorPickerDialog(parent, initial=initial, title=title)
    parent.wait_window(dialog)
    return dialog.result
