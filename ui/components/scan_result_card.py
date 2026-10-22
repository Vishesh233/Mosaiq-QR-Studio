import tkinter
import webbrowser
import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui import icons
from utils import qr_payloads


class ScanResultCard(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            corner_radius=16,
            border_width=1,
            fg_color=theme["card"],
            border_color=theme["border"],
            width=380
        )

        self.result = ""
        self.copy_callback = None
        self.action = None
        self.button_plan = []

        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()

        # The card's height follows its content (nothing is ever cut off, in
        # any state); this empty strip keeps the width at 380 px.
        self.width_keeper = ctk.CTkFrame(
            self, width=340, height=0, fg_color="transparent"
        )
        self.width_keeper.pack(padx=20)

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
            fg_color=theme["success"],
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
        # Wrap at the width the label really gets: the fixed wraplength was
        # wider than the box, so long URLs ran past its edge and were clipped.
        self.result_label.bind("<Configure>", self._fit_result_wrap)

        # ----------------------------
        # Copy Button
        # ----------------------------

        self.copy_label = f"{icons.icon('copy')}  Copy Result"

        self.copy_btn = ctk.CTkButton(
            self,
            text=self.copy_label,
            width=200,
            height=46,
            corner_radius=12,
            border_width=0,
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            border_color=theme["border"],
            text_color=theme["on_primary"],
            state="disabled",
            command=lambda: self._press(0),
            font=("Segoe UI Semibold", 14)
        )

        self.copy_btn.pack(
            anchor="center",
            pady=(18, 16)
        )
        self._style_copy_btn()

        # Extra copy button for smart types (UPI ID, WiFi password, ...);
        # packed only when the scanned code has such a value.
        self.action_btn = ctk.CTkButton(
            self,
            text="",
            width=200,
            height=40,
            corner_radius=12,
            border_width=1,
            fg_color="transparent",
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["primary"],
            font=("Segoe UI Semibold", 13),
            command=lambda: self._press(1)
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

        for index, tip in enumerate(tips):

            row = ctk.CTkFrame(
                self.tips_frame,
                fg_color="transparent"
            )

            row.pack(
                anchor="w",
                padx=16,
                pady=(1, 12 if index == len(tips) - 1 else 1)
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

    def set_result(self, text):

        self.result = text.strip()

        if not self.result:
            self.clear()
            return

        parsed = qr_payloads.parse(self.result)
        is_url = parsed.kind == "url"
        smart = parsed.kind not in ("url", "text")
        theme = ThemeManager.get_theme()

        # ----------------------------
        # Result Text (smart types show their readable fields)
        # ----------------------------

        self.result_label.configure(
            text=parsed.readable if smart else self.result,
            text_color=theme["primary"] if is_url else theme["text"],
            cursor="hand2" if is_url else "arrow"
        )

        self.result_box.configure(
            height=min(260, 70 + 24 * (1 + len(parsed.fields))) if smart else 128
        )

        # ----------------------------
        # Icon + Status Chip
        # ----------------------------

        icon_name, chip_text = self.KIND_CHIPS[parsed.kind]

        self.icon.configure(
            text=icons.icon(icon_name),
            text_color=theme["primary"] if is_url else theme["text"]
        )

        self.status_chip.configure(
            text=f"{icons.icon(icon_name)}  {chip_text}",
            fg_color=theme["card_hover"],
            text_color=theme["primary"] if is_url else theme["text"]
        )

        self.result_box.configure(
            border_color=theme["primary"] if (is_url or smart) else theme["border"]
        )

        if is_url:
            self.result_label.bind("<Button-1>", self.open_result)
            self.icon.bind("<Button-1>", self.open_result)
        else:
            self.result_label.unbind("<Button-1>")
            self.icon.unbind("<Button-1>")

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
            fg_color=theme["entry"],
            text_color=theme["danger"]
        )

        self.result_box.configure(border_color=theme["danger"])

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
            if not self.action_btn.winfo_ismapped():
                self.action_btn.pack(after=self.copy_btn, pady=(0, 14))
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
        button.configure(text="Copied")
        self.after(1200, lambda: button.configure(text=original_text))

    # ==================================================

    def _fit_result_wrap(self, event):
        # The label's canvas fills the space pack gives it; its inner text
        # label only reports the size of the current text.
        if not isinstance(event.widget, tkinter.Canvas):
            return
        width = int(event.width / self.result_label._get_widget_scaling()) - 8
        if width > 40 and abs(width - self.result_label.cget("wraplength")) > 2:
            self.result_label.configure(wraplength=width)

    # ==================================================

    def _style_copy_btn(self):
        """Primary when there is a result to copy, a quiet neutral button otherwise."""
        theme = ThemeManager.get_theme()
        if str(self.copy_btn.cget("state")) == "disabled":
            self.copy_btn.configure(
                fg_color=theme["card_hover"],
                hover_color=theme["card_hover"],
                text_color_disabled=theme["text_secondary"],
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
            border_color=theme["border"],
            height=128
        )

        self._set_buttons([])

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

        self._style_copy_btn()

        self.action_btn.configure(
            hover_color=theme["card_hover"],
            border_color=theme["border"],
            text_color=theme["primary"]
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