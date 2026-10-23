import webbrowser
import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons
from ui.layout import SectionCard, autohide_scrollbar, restyle_scrollable
from utils import qr_payloads

WAITING_TEXT = "Nothing yet — scan a QR to see it here."


class ScanResultCard(SectionCard):
    """Sticky "Result": type chip, the decoded title, its fields and the copy buttons.

    The buttons are pinned to the bottom; the decoded content scrolls above them, so a
    long text can never push a button out of the card.
    """

    def __init__(self, parent):
        super().__init__(parent, title="Result", dot=True)

        self.result = ""
        self.copy_callback = None
        self.action = None
        self.button_plan = []
        self.field_rows = []
        self._masked = []          # [(value label, real value)] for secret fields

        self.status_dot = self.badge
        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()
        body = self.body

        # ---------------- buttons (pinned to the bottom) ----------------
        self.buttons = ctk.CTkFrame(body, fg_color="transparent")
        self.buttons.pack(side="bottom", fill="x", pady=(12, 0))

        self.copy_label = f"{icons.icon('copy')}  Copy Result"

        self.copy_btn = ctk.CTkButton(
            self.buttons,
            text=self.copy_label,
            height=44,
            corner_radius=11,
            border_width=0,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            text_color=theme["on_primary"],
            state="disabled",
            command=lambda: self._press(0),
            font=("Segoe UI Semibold", 14)
        )
        self.copy_btn.pack(fill="x")
        self._style_copy_btn()

        # Extra copy button for smart types (UPI ID, WiFi password, ...);
        # packed only when the scanned code has such a value.
        self.action_btn = ctk.CTkButton(
            self.buttons,
            text="",
            height=40,
            corner_radius=11,
            border_width=1,
            fg_color=theme["segment_bg"],
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["text"],
            font=("Segoe UI Semibold", 13),
            command=lambda: self._press(1)
        )

        # ---------------- content (scrolls) ----------------
        self.scroll = ctk.CTkScrollableFrame(
            body, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            label_text_color=theme["text"], label_fg_color=theme["card"],
        )
        self.scroll.pack(side="top", fill="both", expand=True)
        autohide_scrollbar(self.scroll)

        self.status_chip = ctk.CTkLabel(
            self.scroll,
            text="Waiting",
            height=28,
            corner_radius=14,
            fg_color=theme["segment_bg"],
            text_color=theme["text_secondary"],
            padx=14,
            font=("Segoe UI Semibold", 12)
        )
        self.status_chip.pack(anchor="w", pady=(0, 12))

        self.result_box = ctk.CTkFrame(
            self.scroll,
            border_width=1,
            fg_color=theme["segment_bg"],
            border_color=theme["border"],
            corner_radius=12,
        )
        self.result_box.pack(fill="x")

        self.result_label = ctk.CTkLabel(
            self.result_box,
            text=WAITING_TEXT,
            justify="left",
            anchor="nw",
            wraplength=250,
            text_color=theme["text_secondary"],
            cursor="arrow",
            font=("Segoe UI", 14)
        )
        self.result_label.pack(fill="x", padx=14, pady=14)

        self.fields = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.fields.pack(fill="x", pady=(10, 0))

        self.scroll.bind("<Configure>", self._fit_wrap)

    # ==================================================

    # Chip label and icon per recognised kind.
    KIND_CHIPS = {
        "url": ("link", "URL Detected"),
        "text": ("text", "Plain Text"),
        "upi": ("text", "UPI Payment"),
        "wifi": ("text", "WiFi Network"),
        "contact": ("text", "Contact"),
        "email": ("text", "Email"),
        "sms": ("text", "SMS"),
    }
    SECRET_LABELS = ("Password",)

    def shown_text(self):
        """Everything the card shows as text (title and fields), for tests and accessibility."""
        lines = [self.result_label.cget("text")]
        for label, value in self.field_rows:
            lines.append(f"{label.cget('text')}: {value.cget('text')}")
        return "\n".join(lines)

    def set_result(self, text):

        self.result = text.strip()

        if not self.result:
            self.clear()
            return

        parsed = qr_payloads.parse(self.result)
        is_url = parsed.kind == "url"
        smart = parsed.kind not in ("url", "text")
        theme = ThemeManager.get_theme()

        self._clear_fields()

        # ----------------------------
        # Title (smart types show their title, then one row per field)
        # ----------------------------

        self.result_label.configure(
            text=parsed.title if smart else self.result,
            text_color=theme["primary"] if is_url else theme["text"],
            cursor="hand2" if is_url else "arrow",
            font=("Segoe UI Semibold", 16) if smart else ("Segoe UI", 14),
        )

        if smart:
            for label, value in parsed.fields:
                self._add_field(label, value)

        # ----------------------------
        # Status chip + box
        # ----------------------------

        icon_name, chip_text = self.KIND_CHIPS[parsed.kind]

        self.status_chip.configure(
            text=f"{icons.icon(icon_name)}  {chip_text}",
            fg_color=theme["segment_hover"],
            text_color=theme["primary"]
        )

        self.result_box.configure(
            border_color=theme["primary"] if (is_url or smart) else theme["border"]
        )
        self.status_dot.configure(fg_color=theme["success"])

        if is_url:
            self.result_label.bind("<Button-1>", self.open_result)
        else:
            self.result_label.unbind("<Button-1>")

        # ----------------------------
        # Buttons (the app never launches UPI or any other app by itself)
        # ----------------------------

        self._set_buttons(self._plan_buttons(parsed))
        self.action = parsed.action if smart else None   # the specific copy value

    # ==================================================

    def set_message(self, text):
        """Show a problem (no QR found, unreadable file) instead of a result."""

        self.clear()

        theme = ThemeManager.get_theme()

        self.result_label.configure(
            text=text,
            text_color=theme["text_secondary"]
        )

        self.status_chip.configure(
            text="Nothing decoded",
            fg_color=theme["segment_bg"],
            text_color=theme["danger"]
        )

        self.result_box.configure(border_color=theme["danger"])
        self.status_dot.configure(fg_color=theme["danger"])

    # ==================================================

    def _clear_fields(self):
        for child in self.fields.winfo_children():
            child.destroy()
        self.field_rows = []
        self._masked = []

    def _add_field(self, label_text, value_text):
        theme = ThemeManager.get_theme()
        row = ctk.CTkFrame(self.fields, fg_color=theme["segment_bg"], corner_radius=10,
                           border_width=1, border_color=theme["border"])
        row.pack(fill="x", pady=(0, 6))
        label = ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 12),
                             text_color=theme["text_secondary"], anchor="w")
        label.pack(side="left", padx=(12, 8), pady=9)
        secret = label_text in self.SECRET_LABELS and value_text
        shown = "•" * min(10, max(6, len(value_text))) if secret else value_text
        value = ctk.CTkLabel(row, text=shown, font=("Segoe UI Semibold", 12),
                             text_color=theme["text"], anchor="e", justify="right",
                             wraplength=170)
        value.pack(side="right", padx=(8, 12), pady=9)
        if secret:
            # Hidden until clicked, like a password box.
            self._masked.append((value, value_text))
            value.bind("<Button-1>", lambda _e, v=value, real=value_text: self._reveal(v, real))
            try:
                value.configure(cursor="hand2")
            except Exception:
                pass
        self.field_rows.append((label, value))

    def _reveal(self, label, real):
        hidden = label.cget("text") != real
        label.configure(text=real if hidden else "•" * min(10, max(6, len(real))))

    # ==================================================

    def _plan_buttons(self, parsed):
        """The buttons for a result: [(label, action, copies)], at most two.

        Every button does something different, and the generic "Copy Result"
        exists only when there is no more specific copy button:
          link    Open link, Copy link
          text    Copy Result
          smart   the specific value (Copy UPI ID, Copy password, ...), Copy raw text
                  (just Copy raw text when the code has no specific value)
        """
        raw = self.result
        copy = icons.icon("copy")

        if parsed.kind == "url":
            return [
                (f"{icons.icon('open')}  Open link", self.open_result, False),
                (f"{copy}  Copy link", lambda: self._copy(raw.strip()), True),
            ]

        if parsed.kind == "text":
            return [(f"{copy}  Copy Result", lambda: self._copy(raw), True)]

        plan = []
        if parsed.action:
            label, value = parsed.action
            plan.append((f"{copy}  {label}", lambda: self._copy(value), True))
        plan.append((f"{copy}  Copy raw text", lambda: self._copy(raw), True))
        return plan

    def _set_buttons(self, plan):
        """Show up to two buttons; the first is the primary one."""

        self._cancel_flashes()                   # a "Copied" timer must not put an old label back
        self.button_plan = plan
        self.action = None

        if not plan:
            self.copy_btn.configure(state="disabled", text=self.copy_label)
            self._style_copy_btn()
            self.action_btn.pack_forget()
            return

        self.copy_btn.configure(state="normal", text=plan[0][0])
        self._style_copy_btn()

        if len(plan) > 1:
            self.action_btn.configure(text=plan[1][0])
            if not self.action_btn.winfo_manager():
                self.action_btn.pack(fill="x", pady=(8, 0))
        else:
            self.action_btn.pack_forget()

    def _copy(self, value):
        self.clipboard_clear()
        self.clipboard_append(value)

    def _press(self, index):
        """A result button was clicked."""

        if index >= len(self.button_plan):
            return

        label, action, copies = self.button_plan[index]
        action()

        if copies:
            button = self.copy_btn if index == 0 else self.action_btn
            self._flash(button, label)

    def _flash(self, button, original_text):
        """Briefly confirm a copy on the button itself."""
        self._cancel_flashes()
        button.configure(text="Copied")
        self._flash_job = self.after(1200, lambda: self._unflash(button, original_text))

    def _unflash(self, button, original_text):
        self._flash_job = None
        button.configure(text=original_text)

    def _cancel_flashes(self):
        job = getattr(self, "_flash_job", None)
        if job is not None:
            self.after_cancel(job)
            self._flash_job = None

    # ==================================================

    def _fit_wrap(self, event=None):
        # Wrap long text at the width the scrolling area really has.
        scale = self._get_widget_scaling()
        width = int(self.scroll.winfo_width() / scale) - 76
        if width > 80 and abs(width - self.result_label.cget("wraplength")) > 2:
            self.result_label.configure(wraplength=width)

    # ==================================================

    def _style_copy_btn(self):
        """Primary when there is a result to copy, a quiet neutral button otherwise."""
        theme = ThemeManager.get_theme()
        if str(self.copy_btn.cget("state")) == "disabled":
            self.copy_btn.configure(
                fg_color=theme["segment_bg"],
                hover_color=theme["segment_bg"],
                text_color_disabled=theme["text_muted"],
            )
        else:
            self.copy_btn.configure(
                fg_color=theme["primary"],
                hover_color=theme["primary_hover"],
                text_color=theme["on_primary"],
            )

    # ==================================================

    def clear(self):

        self.result = ""
        theme = ThemeManager.get_theme()

        self._clear_fields()

        self.result_label.configure(
            text=WAITING_TEXT,
            text_color=theme["text_secondary"],
            cursor="arrow",
            font=("Segoe UI", 14),
        )

        self.status_chip.configure(
            text="Waiting",
            fg_color=theme["segment_bg"],
            text_color=theme["text_secondary"]
        )

        self.result_box.configure(border_color=theme["border"])
        self.status_dot.configure(fg_color=theme["text_muted"])

        self._set_buttons([])

        self.result_label.unbind("<Button-1>")

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

    def refresh_theme(self):

        super().refresh_theme()
        theme = ThemeManager.get_theme()

        restyle_scrollable(self.scroll, "card")
        self.result_box.configure(fg_color=theme["segment_bg"])
        self._style_copy_btn()
        self.action_btn.configure(
            fg_color=theme["segment_bg"],
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["text"]
        )

        # State colours (waiting / result / error) are re-applied from what is shown.
        if not self.result:
            self.clear_colours()
        else:
            self.set_result(self.result)

    def clear_colours(self):
        """Re-colour the empty or error state after a theme change (text is kept)."""
        theme = ThemeManager.get_theme()
        error = self.status_chip.cget("text") == "Nothing decoded"
        self.status_chip.configure(
            fg_color=theme["segment_bg"],
            text_color=theme["danger"] if error else theme["text_secondary"])
        self.result_label.configure(text_color=theme["text_secondary"])
        self.result_box.configure(border_color=theme["danger"] if error else theme["border"])
        self.status_dot.configure(
            fg_color=theme["danger"] if error else theme["text_muted"])
