import customtkinter as ctk
from PIL import Image

from ui.components.action_buttons import ActionButtons
from ui.layout import SectionCard
from utils.theme_manager import ThemeManager


class PreviewCard(SectionCard):
    """Sticky "Live Preview": the QR, a status badge, a few facts and the action buttons.

    The QR box takes whatever height is left, so the buttons below it are always visible.
    """

    MIN_QR = 96
    MAX_QR = 320

    def __init__(self, parent):
        super().__init__(parent, title="Live Preview", dot=True)

        self.ctk_image = None
        self.image_label = None
        self._source = None
        self._shown_size = None
        self._fit_job = None

        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()
        body = self.body

        # ---- bottom-up (pack gives the first-packed widgets their space first) ----
        self.actions = ActionButtons(body)
        self.actions.pack(side="bottom", fill="x")

        self.meta = ctk.CTkFrame(body, fg_color="transparent")
        self.meta.pack(side="bottom", fill="x", pady=(14, 14))
        self.meta.grid_columnconfigure((0, 1, 2), weight=1, uniform="meta")
        self._meta_tiles = []
        self.format_label = self._meta_tile(0, "FORMAT", "PNG")
        self.resolution_label = self._meta_tile(1, "SIZE", "—")
        self.correction_label = self._meta_tile(2, "ERROR CORR.", "H")

        self.badge = ctk.CTkLabel(
            body, text="", height=26, corner_radius=13,
            font=("Segoe UI", 12), padx=12,
            fg_color=theme["segment_bg"], text_color=theme["success"],
        )   # shown by set_badge(); hidden while there is nothing to say

        # ---- the QR box fills the rest ----
        self.preview_box = ctk.CTkFrame(
            body, fg_color=theme["segment_bg"], corner_radius=14,
            border_width=1, border_color=theme["border"], height=120,
        )
        self.preview_box.pack(side="top", fill="both", expand=True)
        self.preview_box.pack_propagate(False)
        self.preview_box.bind("<Configure>", self._schedule_fit)

        self.placeholder = ctk.CTkLabel(
            self.preview_box,
            text="Your QR code appears here.\nFill in the details and press Generate.",
            justify="center",
            text_color=theme["text_secondary"],
            font=("Segoe UI", 13)
        )
        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _meta_tile(self, column, caption, value):
        theme = ThemeManager.get_theme()
        tile = ctk.CTkFrame(self.meta, fg_color=theme["segment_bg"], corner_radius=10,
                            border_width=1, border_color=theme["border"])
        tile.grid(row=0, column=column, sticky="ew",
                  padx=(0 if column == 0 else 4, 0 if column == 2 else 4))
        small = ctk.CTkLabel(tile, text=caption, font=("Segoe UI", 10),
                             text_color=theme["text_secondary"])
        small.pack(pady=(7, 0))
        big = ctk.CTkLabel(tile, text=value, font=("Segoe UI Semibold", 13),
                           text_color=theme["text"])
        big.pack(pady=(0, 7))
        self._meta_tiles.append((tile, small, big))
        return big

    # ==================================================

    def set_badge(self, text, kind="ok"):
        """Status line under the QR ("Scans correctly ..."); ``None`` hides it.

        kind: "ok" (green), "warn" (amber) or "info" (muted).
        """
        theme = ThemeManager.get_theme()
        if not text:
            self.badge.pack_forget()
            return
        color = {"ok": theme["success"], "warn": theme["warning"]}.get(kind, theme["text_secondary"])
        self.badge.configure(text=text, text_color=color)
        if not self.badge.winfo_manager():
            self.badge.pack(side="bottom", pady=(0, 10), after=self.meta)

    # ==================================================

    def set_image(self, image):
        """
        Display generated QR image inside preview.
        """

        self.placeholder.place_forget()

        # Save writes this same image, so this is the saved PNG's size.
        self.resolution_label.configure(text=f"{image.width} px")

        self._source = image.copy()
        self._shown_size = None
        self._show()

    def _schedule_fit(self, _event=None):
        if self._source is None or self._fit_job is not None:
            return
        self._fit_job = self.after(60, self._fit_now)

    def _fit_now(self):
        self._fit_job = None
        self._show()

    def _target_size(self):
        box = min(self.preview_box.winfo_width(), self.preview_box.winfo_height())
        scale = self._get_widget_scaling()
        side = int(box / scale) - 32
        return max(self.MIN_QR, min(self.MAX_QR, side))

    def _show(self):
        if self._source is None:
            return
        side = self._target_size()
        if side == self._shown_size and self.image_label is not None:
            return
        self._shown_size = side

        preview = self._source.copy()
        preview.thumbnail((side * 2, side * 2), Image.Resampling.LANCZOS)

        self.ctk_image = ctk.CTkImage(
            light_image=preview, dark_image=preview, size=(side, side)
        )

        if self.image_label is None:
            self.image_label = ctk.CTkLabel(
                self.preview_box, text="", image=self.ctk_image,
                text_color=ThemeManager.get_color("text"),
            )
            self.image_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.image_label.configure(image=self.ctk_image)

    # ==================================================

    def clear_preview(self):
        """
        Restore placeholder and remove QR preview.
        """

        if self.image_label is not None:
            self.image_label.destroy()
            self.image_label = None

        self._source = None
        self._shown_size = None
        self.ctk_image = None
        self.resolution_label.configure(text="—")
        self.set_badge(None)

        self.placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def refresh_theme(self):

        super().refresh_theme()
        theme = ThemeManager.get_theme()

        self.preview_box.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
        self.placeholder.configure(text_color=theme["text_secondary"])
        self.badge.configure(fg_color=theme["segment_bg"])
        for tile, small, big in self._meta_tiles:
            tile.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
            small.configure(text_color=theme["text_secondary"])
            big.configure(text_color=theme["text"])
        self.actions.refresh_theme()
