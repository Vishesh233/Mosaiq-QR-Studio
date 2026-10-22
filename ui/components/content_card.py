import customtkinter as ctk

from utils.theme_manager import ThemeManager
from ui.widgets import ModernEntry
from ui.components.type_forms import FORMS, style_segmented
from ui.widgets import ModernSegmented
from utils.qr_payloads import TYPE_NAMES


class ContentCard(ctk.CTkFrame):

    def __init__(self, parent):

        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            fg_color=theme["card"],
            corner_radius=16,
            border_width=1,
            border_color=theme["border"]
        )

        self.forms = {}
        self.active_type = TYPE_NAMES[0]

        self.build_ui()

    # ==================================================

    def build_ui(self):

        theme = ThemeManager.get_theme()

        content_frame = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        content_frame.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=18
        )

        self.title = ctk.CTkLabel(
            content_frame,
            text="Content",
            font=("Segoe UI Semibold", 16),
            text_color=theme["text"]
        )

        self.title.pack(anchor="w")

        # ---------------- Type + form ---------------- #

        self.type_selector = ModernSegmented(
            content_frame,
            values=list(TYPE_NAMES),
            command=self.set_type,
            height=34
        )

        style_segmented(self.type_selector)
        self.type_selector.set(self.active_type)
        self.type_selector.pack(fill="x", pady=(14, 16))

        self.form_holder = ctk.CTkFrame(
            content_frame,
            fg_color="transparent"
        )

        self.form_holder.pack(fill="x")

        for name, form_class in FORMS.items():
            self.forms[name] = form_class(self.form_holder)

        self.forms[self.active_type].pack(fill="x")

        # Kept for callers that fill the URL/Text box directly.
        self.url_entry = self.forms["URL / Text"].entry

        # ---------------- Filename ---------------- #

        self.label2 = ctk.CTkLabel(
            content_frame,
            text="OUTPUT FILE NAME",
            font=("Segoe UI", 11),
            text_color=theme["text_secondary"]
        )

        self.label2.pack(
            anchor="w",
            pady=(14, 5)
        )

        self.file_entry = ModernEntry(
            content_frame,
            placeholder="my_qr_code"
        )

        self.file_entry.pack(fill="x")

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

        self.label2.configure(
            text_color=theme["text_secondary"]
        )

        style_segmented(self.type_selector)

        for form in self.forms.values():
            form.refresh_theme()

        self.file_entry.refresh_theme()

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

    # ==================================================

    def get_filename(self):
        return self.file_entry.get().strip()

    # ==================================================

    def clear(self):

        for form in self.forms.values():
            form.clear()

        self.set_type(TYPE_NAMES[0])
        self.file_entry.delete(0, "end")