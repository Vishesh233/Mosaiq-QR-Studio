import customtkinter as ctk

from utils import filenames
from ui.components.type_forms import FORMS
from ui.layout import SectionCard
from ui.widgets import IconTileRow
from utils.qr_payloads import TYPE_NAMES

# (type name, icon, tile caption)
TYPE_TILES = (
    ("URL / Text", "url", "URL / Text"),
    ("UPI Payment", "upi", "UPI"),
    ("WiFi", "wifi", "WiFi"),
    ("Contact", "contact", "Contact"),
    ("Email", "email", "Email"),
    ("SMS", "sms", "SMS"),
)


# Short names for the "Scans correctly · ..." badge.
TYPE_LABELS = {
    "URL / Text": "URL / text", "UPI Payment": "UPI payment", "WiFi": "WiFi",
    "Contact": "contact", "Email": "email", "SMS": "SMS",
}


class ContentCard(SectionCard):
    """Step 1: pick the QR type (icon tiles) and fill in its form."""

    def __init__(self, parent):

        super().__init__(parent, title="Content", step=1)

        self.forms = {}
        self.active_type = TYPE_NAMES[0]

        self.type_selector = IconTileRow(self.body, TYPE_TILES, command=self.set_type)
        self.type_selector.set(self.active_type)
        self.type_selector.pack(fill="x", pady=(0, 16))

        self.form_holder = ctk.CTkFrame(self.body, fg_color="transparent")
        self.form_holder.pack(fill="x")

        for name, form_class in FORMS.items():
            self.forms[name] = form_class(self.form_holder)

        self.forms[self.active_type].pack(fill="x")

        # Kept for callers that fill the URL/Text box directly.
        self.url_entry = self.forms["URL / Text"].entry

    # ==================================================

    def set_type(self, name):

        self.forms[self.active_type].pack_forget()
        self.active_type = name
        self.type_selector.set(name)
        self.forms[name].pack(fill="x")

    # ==================================================

    def get_content(self):
        """Text to encode for the selected type. Raises ValueError (user message)."""
        return self.forms[self.active_type].payload()

    def get_fields(self):
        """The selected type's form values, by key (for the history)."""
        return self.forms[self.active_type].values()

    def load(self, type_name, values):
        """Select ``type_name`` and fill its form with saved ``values``."""
        if type_name not in self.forms:
            raise ValueError(f"Unknown QR type: {type_name}")
        self.set_type(type_name)
        self.forms[type_name].fill(values)

    def type_label(self):
        """The selected type as shown in the test-scan badge, e.g. "UPI payment"."""
        return TYPE_LABELS.get(self.active_type, self.active_type)

    def default_filename_stem(self):
        """Suggested name for the Save dialog, from the selected type (e.g. 'upi_qr')."""
        return filenames.default_stem(self.active_type)

    # ==================================================

    def clear(self):

        for form in self.forms.values():
            form.clear()

    # ==================================================

    def refresh_theme(self):

        super().refresh_theme()
        self.type_selector.apply_theme()

        for form in self.forms.values():
            form.refresh_theme()
