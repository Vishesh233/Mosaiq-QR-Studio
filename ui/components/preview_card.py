import customtkinter as ctk
from PIL import Image
from utils.theme_manager import ThemeManager


class PreviewCard(ctk.CTkFrame):

    def __init__(self, parent):
        theme = ThemeManager.get_theme()

        super().__init__(
            parent,
            corner_radius=16,
            border_width=1,
            fg_color=theme["card"],
            border_color=theme["border"],
            width=400,
            height=560
        )

        self.pack_propagate(False)

        self.ctk_image = None
        self.image_label = None

        self.build_ui()

    # ==================================================

    def build_ui(self):
        theme = ThemeManager.get_theme()
        # ---------- Title ----------
        header = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        header.pack(
            fill="x",
            padx=20,
            pady=(20, 12)
        )

        title_row = ctk.CTkFrame(
            header,
            fg_color="transparent"
        )

        title_row.pack(anchor="w")

        dot = ctk.CTkFrame(
            title_row,
            width=10,
            height=10,
            fg_color=theme["primary"],
            corner_radius=5
        )

        dot.pack(
            side="left",
            padx=(0,8)
        )

        title = ctk.CTkLabel(
            title_row,
            text="QR Preview",
            font=("Segoe UI Semibold", 18),
            text_color=theme["text"]
        )

        title.pack(side="left")

        divider = ctk.CTkFrame(
            header,
            height=1,
            fg_color=theme["border"]
        )

        divider.pack(fill="x")
            

        # ---------- Preview Area ----------

        self.preview_box = ctk.CTkFrame(
            self,
            fg_color=theme["entry"],
            corner_radius=14,
            height=285
        )

        self.preview_box.pack(
            fill="x",
            padx=20
        )

        self.preview_box.pack_propagate(False)

        self.placeholder = ctk.CTkLabel(
            self.preview_box,
            text="QR Preview\n\nEnter a URL and Click Generate",
            justify="center",
            text_color=theme["text_secondary"],
            font=("Segoe UI", 15)
        )

        self.placeholder.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

        # ---------- Info Card ----------

        info = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        info.pack(
            fill="x",
            padx=20,
            pady=(18, 20)
        )

        title = ctk.CTkLabel(
            info,
            text="QR Information",
            font=("Segoe UI Semibold", 15),
            text_color=theme["text"]
        )

        title.pack(anchor="w", pady=(0, 10))

        info_box = ctk.CTkFrame(
            info,
            fg_color="transparent",
            corner_radius=14,
            border_width=1,
            border_color=theme["border"]
        )

        info_box.pack(fill="x")

        rows = [
            ("Format", "PNG"),
            ("Error Correction", "H"),
            ("Resolution", "1200 × 1200 px")
        ]

        for index, (left, right) in enumerate(rows):

            row = ctk.CTkFrame(
                info_box,
                fg_color="transparent"
            )

            row.pack(
                fill="x",
                padx=18,
                pady=10
            )

            left_frame = ctk.CTkFrame(
                row,
                fg_color="transparent"
            )

            left_frame.pack(side="left")

            dot = ctk.CTkFrame(
                left_frame,
                width=6,
                height=6,
                fg_color=theme["primary"],
                corner_radius=3
            )

            dot.pack(side="left", padx=(0, 12), pady=(6, 0))

            ctk.CTkLabel(
                left_frame,
                text=left,
                font=("Segoe UI", 13),
                text_color=theme["text_secondary"]
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=right,
                font=("Segoe UI Semibold", 13)
            ).pack(side="right")

            if index < len(rows) - 1:

                divider = ctk.CTkFrame(
                    info_box,
                    height=1,
                    fg_color=theme["border"]
                )

                divider.pack(fill="x", padx=18)

    # ==================================================

    def set_image(self, image):
        """
        Display generated QR image inside preview.
        """

        # Hide placeholder
        self.placeholder.place_forget()

        # Resize image for preview
        preview = image.copy()
        preview.thumbnail(
            (260, 260),
            Image.Resampling.LANCZOS
        )

        # Convert to CTkImage
        self.ctk_image = ctk.CTkImage(
            light_image=preview,
            dark_image=preview,
            size=preview.size
        )

        # Create image label once
        if self.image_label is None:

            self.image_label = ctk.CTkLabel(
                self.preview_box,
                text="",
                image=self.ctk_image
            )

            self.image_label.place(
                relx=0.5,
                rely=0.5,
                anchor="center"
            )

        else:

            self.image_label.configure(
                image=self.ctk_image
            )

    # ==================================================

    def clear_preview(self):
        """
        Restore placeholder and remove QR preview.
        """

        if self.image_label is not None:
            self.image_label.destroy()
            self.image_label = None

        self.ctk_image = None

        self.placeholder.place(
            relx=0.5,
            rely=0.5,
            anchor="center"
        )

    def refresh_theme(self):

        theme = ThemeManager.get_theme()

        self.configure(
            fg_color=theme["card"],
            border_color=theme["border"]
        )

        self.preview_box.configure(
            fg_color=theme["entry"]
        )

        self.placeholder.configure(
            text_color=theme["text_secondary"]
        )