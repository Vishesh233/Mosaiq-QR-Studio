"""History page: the codes generated and scanned before, with Open / Copy / Re-generate / Delete."""
import datetime
import os

import customtkinter as ctk
from PIL import Image

from ui.layout import CARD_GAP, CARD_PAD, Card, SectionCard, TwoColumnPage, autohide_scrollbar
from ui.line_icons import line_icon
from ui.widgets import ModernSegmented
from utils import history_store, qr_payloads
from utils.qr_generator import QRGenerator
from utils.qr_render import QRStyle
from utils.theme_manager import ThemeManager

PAGE_SIZE = 40
THUMB = 48
PREVIEW = 200

# icon per QR type name
TYPE_ICONS = {"URL / Text": "url", "UPI Payment": "upi", "WiFi": "wifi",
              "Contact": "contact", "Email": "email", "SMS": "sms"}
KIND_TYPES = {"url": "URL / Text", "text": "URL / Text", "upi": "UPI Payment", "wifi": "WiFi",
              "contact": "Contact", "email": "Email", "sms": "SMS"}
FILTERS = ("All", "Generated", "Scanned")


def type_for_kind(parsed_kind):
    """The QR type name for what the scanner recognised (url, upi, wifi ...)."""
    return KIND_TYPES.get(parsed_kind, "URL / Text")


def describe(entry):
    """(title, subtitle) of an entry for the list."""
    parsed = qr_payloads.parse(entry["text"])
    if parsed.kind in ("url", "text"):
        flat = " ".join(entry["text"].split())
        title = flat if len(flat) <= 56 else flat[:53] + "…"
    else:
        title = parsed.title
    try:
        when = datetime.datetime.fromisoformat(entry["created"]).strftime("%d %b %Y, %H:%M")
    except ValueError:
        when = entry["created"]
    kind = "Generated" if entry["kind"] == history_store.GENERATED else "Scanned"
    return title, f"{entry['type']}  ·  {kind}  ·  {when}"


class HistoryRow(ctk.CTkFrame):

    def __init__(self, parent, entry, thumb, on_select):
        theme = ThemeManager.get_theme()
        super().__init__(parent, fg_color=theme["segment_bg"], corner_radius=12,
                         border_width=1, border_color=theme["border"])
        self.entry = entry
        self._on_select = on_select
        self._thumb = thumb                         # kept: a label raises if its image is collected

        self.picture = ctk.CTkLabel(self, text="", image=thumb, width=THUMB, height=THUMB,
                                    text_color=theme["text"])
        self.picture.pack(side="left", padx=(12, 12), pady=10)
        texts = ctk.CTkFrame(self, fg_color="transparent")
        texts.pack(side="left", fill="x", expand=True, pady=10)
        title, subtitle = describe(entry)
        self.title = ctk.CTkLabel(texts, text=title, anchor="w", font=("Segoe UI Semibold", 13),
                                  text_color=theme["text"])
        self.title.pack(fill="x")
        self.subtitle = ctk.CTkLabel(texts, text=subtitle, anchor="w", font=("Segoe UI", 11),
                                     text_color=theme["text_secondary"])
        self.subtitle.pack(fill="x")

        for widget in (self, self.picture, texts, self.title, self.subtitle):
            widget.bind("<Button-1>", lambda _e: self._on_select(self.entry["id"]))
        self.configure(cursor="hand2")

    def set_selected(self, selected):
        theme = ThemeManager.get_theme()
        self.configure(border_color=theme["primary"] if selected else theme["border"],
                       fg_color=theme["segment_hover"] if selected else theme["segment_bg"])

    def refresh_theme(self, selected):
        theme = ThemeManager.get_theme()
        self.set_selected(selected)
        self.title.configure(text_color=theme["text"])
        self.subtitle.configure(text_color=theme["text_secondary"])


class HistoryPage(TwoColumnPage):

    def __init__(self, parent, on_open=None, on_regenerate=None):
        super().__init__(parent)
        theme = ThemeManager.get_theme()
        self.on_open = on_open
        self.on_regenerate = on_regenerate
        self._entries = []
        self._rows = {}
        self._selected = None
        self._filter = "All"
        self._shown = PAGE_SIZE
        self._images = []
        self._detail_image = None
        self._generator = QRGenerator()

        # ---------------- left: filter, list ----------------
        bar = ctk.CTkFrame(self.left, fg_color="transparent")
        bar.pack(fill="x", pady=(0, CARD_GAP))
        self.filter = ModernSegmented(bar, values=list(FILTERS), command=self._filter_changed, height=32)
        self.filter.set("All")
        self.filter.pack(side="left")
        self.count_label = ctk.CTkLabel(bar, text="", font=("Segoe UI", 12),
                                        text_color=theme["text_secondary"])
        self.count_label.pack(side="right")

        self.notice = ctk.CTkLabel(self.left, text="", anchor="w", justify="left", wraplength=520,
                                   font=("Segoe UI", 12), text_color=theme["warning"])
        self.list_holder = ctk.CTkFrame(self.left, fg_color="transparent")
        self.list_holder.pack(fill="x")
        self.empty = Card(self.left)
        self.empty_label = ctk.CTkLabel(
            self.empty, text="", font=("Segoe UI", 13), justify="center",
            text_color=theme["text_secondary"])
        self.empty_label.pack(padx=CARD_PAD, pady=40)
        self.more_button = ctk.CTkButton(
            self.left, text="Show more", height=36, corner_radius=10, fg_color=theme["segment_bg"],
            border_width=1, border_color=theme["border"], hover_color=theme["card_hover"],
            text_color=theme["text"], font=("Segoe UI", 12), command=self._show_more)

        # ---------------- right: details ----------------
        self.details = SectionCard(self.right, title="Details", dot=True)
        self.details.pack(fill="both", expand=True)
        body = self.details.body
        self.buttons = ctk.CTkFrame(body, fg_color="transparent")
        self.buttons.pack(side="bottom", fill="x", pady=(12, 0))
        self.open_btn = self._button(self.buttons, "Open", primary=True, command=self._open)
        self.open_btn.pack(fill="x")
        row = ctk.CTkFrame(self.buttons, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        row.grid_columnconfigure((0, 1, 2), weight=1, uniform="hist")
        self.copy_btn = self._button(row, "Copy", command=self._copy)
        self.copy_btn.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.regen_btn = self._button(row, "Re-generate", command=self._regenerate)
        self.regen_btn.grid(row=0, column=1, sticky="ew", padx=4)
        self.delete_btn = self._button(row, "Delete", command=self._delete, danger=True)
        self.delete_btn.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        self.preview_box = ctk.CTkFrame(body, fg_color=theme["segment_bg"], corner_radius=12,
                                        border_width=1, border_color=theme["border"], height=PREVIEW + 24)
        self.preview_box.pack(side="top", fill="x")
        self.preview_box.pack_propagate(False)
        self.preview = ctk.CTkLabel(self.preview_box, text="", text_color=theme["text"],
                                    font=("Segoe UI", 12), justify="center", wraplength=260)
        self.preview.place(relx=0.5, rely=0.5, anchor="center")
        self.detail_title = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=300,
                                         font=("Segoe UI Semibold", 15), text_color=theme["text"])
        self.detail_title.pack(fill="x", pady=(12, 0))
        self.detail_meta = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=300,
                                        font=("Segoe UI", 12), text_color=theme["text_secondary"])
        self.detail_meta.pack(fill="x", pady=(2, 0))
        self.detail_note = ctk.CTkLabel(body, text="", anchor="w", justify="left", wraplength=300,
                                        font=("Segoe UI", 12), text_color=theme["warning"])
        self.detail_note.pack(fill="x", pady=(8, 0))

        self.refresh()

    # ------------------------------------------------------------------ helpers

    def _button(self, parent, text, primary=False, danger=False, command=None):
        theme = ThemeManager.get_theme()
        return ctk.CTkButton(
            parent, text=text, height=44 if primary else 38, corner_radius=11,
            fg_color=theme["primary"] if primary else theme["segment_bg"],
            hover_color=theme["primary_hover"] if primary else theme["card_hover"],
            text_color=theme["on_primary"] if primary else (theme["danger"] if danger else theme["text"]),
            border_width=0 if primary else 1, border_color=theme["border"],
            text_color_disabled=theme["text_muted"],
            font=("Segoe UI Semibold", 14 if primary else 12), command=command)

    def _thumbnail(self, entry):
        path = history_store.thumbnail_path(entry)
        if path:
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB")
                image.thumbnail((THUMB * 2, THUMB * 2))
                return ctk.CTkImage(light_image=image, dark_image=image, size=(THUMB, THUMB))
            except OSError:
                pass            # a damaged preview shows the type icon instead
        icon = TYPE_ICONS.get(entry["type"], "url")
        return line_icon(icon, ThemeManager.get_theme()["text_secondary"], 26)

    # ------------------------------------------------------------------ list

    def refresh(self):
        """Reload the entries from disk and redraw the list."""
        self._entries = history_store.entries()
        if self._selected not in {e["id"] for e in self._entries}:
            self._selected = None
        self._draw_list()
        self._show_details()

    def _visible(self):
        if self._filter == "All":
            return self._entries
        kind = history_store.GENERATED if self._filter == "Generated" else history_store.SCANNED
        return [e for e in self._entries if e["kind"] == kind]

    def _draw_list(self):
        for child in self.list_holder.winfo_children():
            child.destroy()
        self._rows = {}
        self._images = []
        visible = self._visible()
        self.count_label.configure(text=f"{len(visible)} of {len(self._entries)} codes"
                                   if self._filter != "All" else f"{len(self._entries)} codes")

        if not history_store.enabled():
            self.notice.configure(text="History is switched off, so new codes are not being saved. "
                                       "Turn it on in Settings.")
            self.notice.pack(fill="x", pady=(0, CARD_GAP), before=self.list_holder)
        else:
            self.notice.pack_forget()

        if not visible:
            self.empty_label.configure(
                text="No history yet.\nCodes you generate or scan appear here."
                if not self._entries else "Nothing in this filter.")
            self.empty.pack(fill="x")
            self.more_button.pack_forget()
            return
        self.empty.pack_forget()

        for entry in visible[:self._shown]:
            thumb = self._thumbnail(entry)
            self._images.append(thumb)
            row = HistoryRow(self.list_holder, entry, thumb, self.select)
            row.pack(fill="x", pady=(0, 8))
            row.set_selected(entry["id"] == self._selected)
            self._rows[entry["id"]] = row
        if len(visible) > self._shown:
            self.more_button.configure(text=f"Show more ({len(visible) - self._shown} left)")
            self.more_button.pack(fill="x", pady=(4, 0))
        else:
            self.more_button.pack_forget()

    def _show_more(self):
        self._shown += PAGE_SIZE
        self._draw_list()

    def _filter_changed(self, value):
        self._filter = value
        self._shown = PAGE_SIZE
        self._draw_list()

    def select(self, entry_id):
        self._selected = entry_id
        for key, row in self._rows.items():
            row.set_selected(key == entry_id)
        self._show_details()

    # ------------------------------------------------------------------ details

    def selected_entry(self):
        return next((e for e in self._entries if e["id"] == self._selected), None)

    def _show_details(self):
        entry = self.selected_entry()
        has = entry is not None
        for button in (self.open_btn, self.copy_btn, self.regen_btn, self.delete_btn):
            button.configure(state="normal" if has else "disabled")
        self.detail_note.configure(text="")
        if not has:
            self._set_preview(None, "Select a code to see it here.")
            self.detail_title.configure(text="")
            self.detail_meta.configure(text="")
            return
        title, subtitle = describe(entry)
        self.detail_title.configure(text=title)
        self.detail_meta.configure(text=subtitle)
        self.open_btn.configure(text="Open in Generate" if entry["kind"] == history_store.GENERATED
                                else "Open in Scan")
        if entry.get("redacted"):
            self._set_preview(None, "No picture is saved for this WiFi code,\n"
                                    "because its picture contains the password.")
            self.detail_note.configure(text="The password was not saved. Enter it again to "
                                            "generate the code.")
            return
        try:
            image = self._render(entry)
        except (OSError, ValueError) as e:
            self._set_preview(None, f"The preview could not be drawn: {e}")
            return
        image.thumbnail((PREVIEW, PREVIEW))
        self._set_preview(ctk.CTkImage(light_image=image, dark_image=image, size=image.size), "")

    def _set_preview(self, image, text):
        """Show ``image`` (a CTkImage or None) and ``text`` in the detail preview. The old image
        stays alive until the label has switched: Tk raises when a shown image is freed first."""
        previous, self._detail_image = self._detail_image, image
        # CustomTkinter leaves the old picture on the Tk label when image is None (and Tk then
        # raises once that picture is freed), so the Tk label is emptied first.
        self.preview._label.configure(image="")
        self.preview.configure(image=image, text=text)
        del previous

    def _render(self, entry):
        style = QRStyle.from_dict(entry.get("style"))
        logo = entry.get("logo") or None
        if logo and not os.path.exists(logo):
            logo = None                         # the logo file has been moved or deleted
        return self._generator.generate(entry["text"], style=style, logo_path=logo)

    # ------------------------------------------------------------------ actions

    def _open(self):
        entry = self.selected_entry()
        if entry is not None and self.on_open:
            self.on_open(entry)

    def _regenerate(self):
        entry = self.selected_entry()
        if entry is not None and self.on_regenerate:
            self.on_regenerate(entry)

    def _copy(self):
        entry = self.selected_entry()
        if entry is None:
            return
        self.clipboard_clear()
        self.clipboard_append(entry["text"])
        self.copy_btn.configure(text="Copied")
        self.after(1200, lambda: self.copy_btn.configure(text="Copy"))

    def _delete(self):
        entry = self.selected_entry()
        if entry is None:
            return
        history_store.delete(entry["id"])
        self._selected = None
        self.refresh()

    # ------------------------------------------------------------------ theme

    def refresh_theme(self):
        super().refresh_theme()
        theme = ThemeManager.get_theme()
        self.filter.apply_theme()
        self.count_label.configure(text_color=theme["text_secondary"])
        self.notice.configure(text_color=theme["warning"])
        self.empty.refresh_theme()
        self.empty_label.configure(text_color=theme["text_secondary"])
        self.more_button.configure(fg_color=theme["segment_bg"], border_color=theme["border"],
                                   hover_color=theme["card_hover"], text_color=theme["text"])
        self.details.refresh_theme()
        self.preview_box.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
        self.preview.configure(text_color=theme["text"])
        self.detail_title.configure(text_color=theme["text"])
        self.detail_meta.configure(text_color=theme["text_secondary"])
        self.detail_note.configure(text_color=theme["warning"])
        self.open_btn.configure(fg_color=theme["primary"], hover_color=theme["primary_hover"],
                                text_color=theme["on_primary"])
        for button, danger in ((self.copy_btn, False), (self.regen_btn, False), (self.delete_btn, True)):
            button.configure(fg_color=theme["segment_bg"], hover_color=theme["card_hover"],
                             border_color=theme["border"],
                             text_color=theme["danger"] if danger else theme["text"])
        for key, row in self._rows.items():
            row.refresh_theme(key == self._selected)
        self.refresh()
