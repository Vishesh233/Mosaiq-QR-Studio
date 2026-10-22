"""Shared page layout: one left edge, an 8 px spacing grid and a sticky right column.

Every page (Generate, Scan, History, Bulk Create) is built on these pieces so the title,
the subtitle and the cards start on the same x and the spacing is the same everywhere.
"""
import customtkinter as ctk

from utils.theme_manager import ThemeManager

# ---- the 8 px grid -------------------------------------------------------
GRID = 8
PAGE_PADX = 4 * GRID           # 32: left edge shared by title, subtitle and cards
PAGE_PADY = 2 * GRID           # 16
COLUMN_GAP = 3 * GRID          # 24 between the two columns
CARD_GAP = 2 * GRID            # 16 between stacked cards
CARD_PAD = 20                  # inside a card
CARD_RADIUS = 14
RIGHT_COLUMN_WIDTH = 46 * GRID  # 368


def autohide_scrollbar(scrollable):
    """Show a CTkScrollableFrame's scrollbar only while its content overflows."""

    def update(_event=None):
        try:
            canvas, bar = scrollable._parent_canvas, scrollable._scrollbar
            overflow = scrollable.winfo_reqheight() > canvas.winfo_height() + 1
            shown = bool(bar.winfo_manager())
            if overflow and not shown:
                bar.grid()
            elif not overflow and shown:
                bar.grid_remove()
        except Exception:      # the widget is being destroyed
            pass

    def schedule(_event=None):
        scrollable.after_idle(update)

    scrollable.bind("<Configure>", schedule, add="+")
    scrollable._parent_canvas.bind("<Configure>", schedule, add="+")


def restyle_scrollable(scrollable, label_bg):
    """Re-apply the theme to a CTkScrollableFrame (its inner canvas needs a nudge too)."""
    theme = ThemeManager.get_theme()
    scrollable.configure(
        fg_color="transparent",
        scrollbar_button_color=theme["scrollbar"],
        scrollbar_button_hover_color=theme["scrollbar_hover"],
        label_text_color=theme["text"], label_fg_color=theme[label_bg],
    )


class Card(ctk.CTkFrame):
    """A rounded, bordered surface."""

    def __init__(self, parent, **kwargs):
        theme = ThemeManager.get_theme()
        super().__init__(
            parent,
            fg_color=theme["card"],
            corner_radius=CARD_RADIUS,
            border_width=1,
            border_color=theme["border"],
            **kwargs,
        )

    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        self.configure(fg_color=theme["card"], border_color=theme["border"])


class SectionCard(Card):
    """A card with a title row: a numbered step badge (or a status dot) and a title.

    Content goes into ``self.body``.
    """

    def __init__(self, parent, title, step=None, dot=False, **kwargs):
        super().__init__(parent, **kwargs)
        theme = ThemeManager.get_theme()

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=CARD_PAD, pady=(CARD_PAD, GRID + 4))

        self.badge = None
        if step is not None:
            self.badge = ctk.CTkLabel(
                head, text=str(step), width=22, height=22, corner_radius=7,
                fg_color=theme["segment_hover"], text_color=theme["primary"],
                font=("Segoe UI Semibold", 12),
            )
            self.badge.pack(side="left", padx=(0, GRID))
        elif dot:
            self.badge = ctk.CTkFrame(head, width=10, height=10, corner_radius=5,
                                      fg_color=theme["primary"])
            self.badge.pack(side="left", padx=(2, GRID + 2))

        self.title_label = ctk.CTkLabel(
            head, text=title, font=("Segoe UI Semibold", 15), text_color=theme["text"],
        )
        self.title_label.pack(side="left")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=CARD_PAD, pady=(0, CARD_PAD))

    def refresh_theme(self):
        super().refresh_theme()
        theme = ThemeManager.get_theme()
        self.title_label.configure(text_color=theme["text"])
        if isinstance(self.badge, ctk.CTkLabel):
            self.badge.configure(fg_color=theme["segment_hover"], text_color=theme["primary"])
        elif self.badge is not None:
            self.badge.configure(fg_color=theme["primary"])


class TwoColumnPage(ctk.CTkFrame):
    """Left column that scrolls, right column that stays put.

    ``self.left`` (a scrollable frame) holds the cards that can be taller than the window;
    ``self.right`` is fixed, so its buttons are never scrolled out of view.
    """

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        theme = ThemeManager.get_theme()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"], label_fg_color=theme["background"],
        )
        self.left.grid(row=0, column=0, sticky="nsew",
                       padx=(PAGE_PADX, COLUMN_GAP - GRID), pady=(0, PAGE_PADY))
        autohide_scrollbar(self.left)

        self.right = ctk.CTkFrame(self, width=RIGHT_COLUMN_WIDTH, fg_color="transparent")
        self.right.grid(row=0, column=1, sticky="ns", padx=(0, PAGE_PADX), pady=(0, PAGE_PADY))
        self.right.grid_propagate(False)
        self.right.pack_propagate(False)

    def refresh_theme(self):
        restyle_scrollable(self.left, "background")
