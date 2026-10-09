import customtkinter as ctk

from ui.widgets import ModernEntry
from ui.components.hero_section import HeroSection
from ui.components.content_card import ContentCard
from ui.components.preview_card import PreviewCard
from ui.components.logo_card import LogoCard
from ui.components.color_card import ColorCard
from ui.components.action_buttons import ActionButtons
from utils.qr_generator import QRGenerator
from utils.clipboard import ClipboardManager
from tkinter import messagebox
from tkinter import filedialog



class GeneratePage(ctk.CTkFrame):

    def __init__(self, parent):

        super().__init__(
            parent,
            fg_color="transparent"
        )

        self.generator = QRGenerator()
        self.generated_image = None

        # ==========================
        # Main Container
        # ==========================

        container = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        container.grid_columnconfigure(0, weight=3)
        container.grid_columnconfigure(1, weight=2)

        container.pack(
            anchor="center",
            padx=(90,40),
            pady=10,
            fill="both",
            expand=True,
            
        )

        # Left Side

        self.left = ctk.CTkFrame(
            container,
            width=800,
            fg_color="transparent"
        )

        self.left.pack(
            side="left",
            fill="both",
            padx=(0,18),
            expand=True
        )

        # ==========================================
        # HERO SECTION
        # ==========================================

        self.hero = HeroSection(
            self.left,
            title="Design your QR code",
            subtitle="Enter your content, then customize colors and add a logo."
        )

        self.hero.pack(
            fill="x",
            pady=(0, 16),
        )

        # ==========================================
        # CONTENT CARD
        # ==========================================

        self.content_card = ContentCard(self.left)

        self.content_card.pack(
            fill="x",
            pady=(0, 16)
        )
        content_frame = ctk.CTkFrame(
            self.content_card,
            fg_color="transparent"
        )

        content_frame.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=18
        )

        title = ctk.CTkLabel(
            content_frame,
            text="🔗  Content",
            font=("Segoe UI", 18, "bold")
        )

        title.pack(anchor="w")

        label1 = ctk.CTkLabel(
            content_frame,
            text="WEBSITE URL OR TEXT",
            font=("Segoe UI", 11),
            text_color="#9CA3AF"
        )

        label1.pack(anchor="w", pady=(16,5))

        self.url_entry = ModernEntry(
            content_frame,
            placeholder="https://example.com"
        )

        self.url_entry.pack(fill="x")

        label2 = ctk.CTkLabel(
            content_frame,
            text="OUTPUT FILE NAME",
            font=("Segoe UI", 11),
            text_color="#9CA3AF"
        )

        label2.pack(anchor="w", pady=(14,5))

        self.file_entry = ModernEntry(
            content_frame,
            placeholder="my_qr_code"
            )

        self.file_entry.pack(fill="x")

        self.logo_card = LogoCard(self.left)

        self.logo_card.pack(
            fill="x",
            pady=(0,16)
        )

        self.color_card = ColorCard(self.left)
        self.color_card.pack(fill="x", pady=(0, 16))
        self.action_buttons = ActionButtons(self.left)

        self.action_buttons.pack(
            fill="x",
            pady=(0, 0)
        )   

        self.action_buttons.set_generate_callback(self.generate_qr)
        self.action_buttons.set_clear_callback(self.clear_form)
        self.action_buttons.set_copy_callback(self.copy_qr)
        self.action_buttons.set_save_callback(self.save_qr)

            # Right Side

        self.right = ctk.CTkFrame(
            container,
            width=400,
            fg_color="transparent"
        )

        self.right.pack(
            side="left",
            fill="y",
            padx=(8,0)
        )

        self.preview_card = PreviewCard(self.right)

        self.preview_card.pack(
            fill="x",
            pady=(60, 0)
        )

    def generate_qr(self):

        # Get content
        data = self.content_card.get_content()

        if not data:
            messagebox.showwarning(
                "Missing Content",
                "Please enter a URL or text."
            )
            return

        try:

            image = self.generator.generate(
                data=data,
                qr_color=self.color_card.get_qr_color(),
                bg_color=self.color_card.get_bg_color(),
                logo_path=self.logo_card.get_logo_path()
            )

            self.generated_image = image

            self.preview_card.set_image(image)

            self.action_buttons.enable_export_buttons()

        except Exception as e:

            messagebox.showerror(
                "QR Generation Failed",
                str(e)
            )

    def clear_form(self):

        # Clear entries
        self.content_card.clear()

        # Reset logo
        self.logo_card.reset_logo()

        # Reset colors
        self.color_card.reset_colors()

        # Reset preview
        self.preview_card.clear_preview()

        # Remove generated image
        self.generated_image = None

        # Disable buttons
        self.action_buttons.disable_export_buttons()

    def copy_qr(self):

        if self.generated_image is None:

            messagebox.showwarning(
                "Nothing to Copy",
                "Please generate a QR code first."
            )

            return

        try:

            ClipboardManager.copy_image(
                self.generated_image
            )

            messagebox.showinfo(
                "Copied",
                "QR Code copied to clipboard."
            )

        except Exception as e:

            messagebox.showerror(
                "Copy Failed",
                str(e)
            )

    def save_qr(self):

        if self.generated_image is None:

            messagebox.showwarning(
                "Nothing to Save",
                "Please generate a QR code first."
            )
            return

        filename = self.content_card.get_filename()

        if not filename:
            filename = "qr_code"

        if filename.lower().endswith(".png"):
            filename = filename[:-4]

        filepath = filedialog.asksaveasfilename(
            title="Save QR Code",
            initialfile=f"{filename}.png",
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png")
            ]
        )

        if not filepath:
            return

        try:

            self.generated_image.save(filepath)

            messagebox.showinfo(
                "Saved",
                "QR Code saved successfully."
            )

        except Exception as e:

            messagebox.showerror(
                "Save Failed",
                str(e)
            )

    def refresh_theme(self):

        if hasattr(self.hero, "refresh_theme"):
            self.hero.refresh_theme()

        if hasattr(self.content_card, "refresh_theme"):
            self.content_card.refresh_theme()

        if hasattr(self.logo_card, "refresh_theme"):
            self.logo_card.refresh_theme()

        if hasattr(self.color_card, "refresh_theme"):
            self.color_card.refresh_theme()

        if hasattr(self.action_buttons, "refresh_theme"):
            self.action_buttons.refresh_theme()

        if hasattr(self.preview_card, "refresh_theme"):
            self.preview_card.refresh_theme()