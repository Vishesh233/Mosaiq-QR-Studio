"""Small input forms, one per QR type, shown inside the Content card.

Every form exposes:
    payload()        -> the text to encode (raises ValueError with a user message)
    clear()          -> empty the inputs
    refresh_theme()  -> re-apply the active theme
"""

import customtkinter as ctk

from utils import qr_payloads as payloads
from utils.theme_manager import ThemeManager
from ui.widgets import ModernEntry, ModernSegmented


class ModernText(ctk.CTkTextbox):
    """Multi-line input styled like ModernEntry."""

    def __init__(self, parent, height=72):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            height=height,
            corner_radius=12,
            border_width=1,
            border_color=theme["entry_border"],
            fg_color=theme["entry"],
            text_color=theme["text"],
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"],
            font=("Segoe UI", 14),
            wrap="word"
        )

    def get_text(self):
        return self.get("1.0", "end-1c").strip()

    def clear(self):
        self.delete("1.0", "end")

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["entry"],
            border_color=theme["entry_border"],
            text_color=theme["text"],
            scrollbar_button_color=theme["scrollbar"],
            scrollbar_button_hover_color=theme["scrollbar_hover"]
        )


def style_segmented(button):
    """Re-apply the active theme to a ModernSegmented button."""
    button.apply_theme()


class _Field(ctk.CTkFrame):
    """A caption above an entry (or multi-line text) box."""

    def __init__(self, parent, caption, placeholder="", multiline=False,
                 show=None):

        super().__init__(parent, fg_color="transparent")

        theme = ThemeManager.get_theme()

        self.label = ctk.CTkLabel(
            self,
            text=caption,
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        self.label.pack(anchor="w", pady=(0, 5))

        if multiline:
            self.widget = ModernText(self)
        else:
            self.widget = ModernEntry(self, placeholder=placeholder)
            if show:
                self.widget.configure(show=show)

        self.widget.pack(fill="x")

        self.multiline = multiline

    def get(self):
        if self.multiline:
            return self.widget.get_text()
        return self.widget.get().strip()

    def clear(self):
        if self.multiline:
            self.widget.clear()
        else:
            self.widget.delete(0, "end")

    def refresh_theme(self):
        theme = ThemeManager.get_theme()
        self.label.configure(text_color=theme["text_secondary"])
        self.widget.refresh_theme()


class _Form(ctk.CTkFrame):

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.columnconfigure(0, weight=1, uniform="col")
        self.columnconfigure(1, weight=1, uniform="col")
        self.fields = []

    def add(self, field, row, column=0, span=1):
        field.grid(
            row=row,
            column=column,
            columnspan=span,
            sticky="ew",
            padx=(0, 12) if column == 0 and span == 1 else 0,
            pady=(0, 12)
        )
        self.fields.append(field)
        return field

    def clear(self):
        for field in self.fields:
            field.clear()

    def refresh_theme(self):
        for field in self.fields:
            field.refresh_theme()


# ==================================================


class UrlForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)
        self.entry_field = self.add(
            _Field(self, "WEBSITE URL OR TEXT", "https://example.com"),
            0, 0, 2
        )
        self.entry = self.entry_field.widget

    def payload(self):
        text = self.entry_field.get()
        if not text:
            raise ValueError("Please enter a URL or text.")
        return text


class UpiForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)
        self.upi_id = self.add(_Field(self, "UPI ID", "name@bank"), 0, 0)
        self.payee = self.add(_Field(self, "PAYEE NAME", "Name shown to the payer"), 0, 1)
        self.amount = self.add(_Field(self, "AMOUNT (OPTIONAL)", "e.g. 250.00"), 1, 0)
        self.note = self.add(_Field(self, "NOTE (OPTIONAL)", "e.g. Rent"), 1, 1)

    def payload(self):
        return payloads.build_upi(
            self.upi_id.get(), self.payee.get(),
            self.amount.get(), self.note.get()
        )


class WifiForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)

        theme = ThemeManager.get_theme()

        self.ssid = self.add(_Field(self, "NETWORK NAME (SSID)", "MyNetwork"), 0, 0)
        self.password = self.add(_Field(self, "PASSWORD", show="•"), 0, 1)

        options = ctk.CTkFrame(self, fg_color="transparent")
        options.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.security_label = ctk.CTkLabel(
            options,
            text="SECURITY",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )
        self.security_label.pack(side="left", padx=(0, 10))

        self.security = ModernSegmented(
            options,
            values=list(payloads.WIFI_SECURITY),
            command=self._security_changed
        )
        self.security.set("WPA")
        style_segmented(self.security)
        self.security.pack(side="left", padx=(0, 22))

        self.hidden = ctk.CTkCheckBox(
            options,
            text="Hidden network",
            font=("Segoe UI", 12),
            text_color=theme["text"],
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            border_color=theme["entry_border"],
            checkmark_color=theme["on_primary"]
        )
        self.hidden.pack(side="left", padx=(0, 22))

        self.show_password = ctk.CTkCheckBox(
            options,
            text="Show password",
            font=("Segoe UI", 12),
            text_color=theme["text"],
            fg_color=theme["primary"],
            hover_color=theme["primary_hover"],
            border_color=theme["entry_border"],
            checkmark_color=theme["on_primary"],
            command=self._toggle_password
        )
        self.show_password.pack(side="left")

    def _toggle_password(self):
        shown = bool(self.show_password.get())
        self.password.widget.configure(show="" if shown else "•")

    def _security_changed(self, value):
        state = "disabled" if value == "None" else "normal"
        self.password.widget.configure(state=state)

    def payload(self):
        return payloads.build_wifi(
            self.ssid.get(),
            self.password.widget.get(),
            self.security.get(),
            bool(self.hidden.get())
        )

    def clear(self):
        super().clear()
        self.hidden.deselect()
        self.show_password.deselect()
        self.security.set("WPA")
        self._security_changed("WPA")
        self._toggle_password()

    def refresh_theme(self):
        super().refresh_theme()
        theme = ThemeManager.get_theme()
        self.security_label.configure(text_color=theme["text_secondary"])
        style_segmented(self.security)
        for box in (self.hidden, self.show_password):
            box.configure(
                text_color=theme["text"],
                fg_color=theme["primary"],
                hover_color=theme["primary_hover"],
                border_color=theme["entry_border"],
                checkmark_color=theme["on_primary"]
            )


class ContactForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)
        self.name = self.add(_Field(self, "FULL NAME", "Asha Verma"), 0, 0)
        self.phone = self.add(_Field(self, "PHONE", "+91 98765 43210"), 0, 1)
        self.email = self.add(_Field(self, "EMAIL", "asha@example.com"), 1, 0)
        self.organisation = self.add(_Field(self, "ORGANISATION", "Company name"), 1, 1)

    def payload(self):
        return payloads.build_vcard(
            self.name.get(), self.phone.get(),
            self.email.get(), self.organisation.get()
        )


class EmailForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)
        self.to = self.add(_Field(self, "TO", "name@example.com"), 0, 0)
        self.subject = self.add(_Field(self, "SUBJECT (OPTIONAL)", "Subject"), 0, 1)
        self.body = self.add(_Field(self, "MESSAGE (OPTIONAL)", multiline=True), 1, 0, 2)

    def payload(self):
        return payloads.build_email(
            self.to.get(), self.subject.get(), self.body.get()
        )


class SmsForm(_Form):

    def __init__(self, parent):
        super().__init__(parent)
        self.number = self.add(_Field(self, "PHONE NUMBER", "+91 98765 43210"), 0, 0, 2)
        self.message = self.add(_Field(self, "MESSAGE (OPTIONAL)", multiline=True), 1, 0, 2)

    def payload(self):
        return payloads.build_sms(self.number.get(), self.message.get())


FORMS = {
    "URL / Text": UrlForm,
    "UPI Payment": UpiForm,
    "WiFi": WifiForm,
    "Contact": ContactForm,
    "Email": EmailForm,
    "SMS": SmsForm,
}
