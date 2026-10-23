"""Bulk Create page: a CSV in, a folder of QR codes out (progress, cancel, no frozen window)."""
import os

import customtkinter as ctk
from tkinter import filedialog, messagebox

from ui.layout import CARD_GAP, CARD_PAD, SectionCard, TwoColumnPage
from ui.widgets import ModernSegmented
from utils import bulk_csv, bulk_runner, qr_export, settings_store
from utils.qr_generator import QRGenerator
from utils.theme_manager import ThemeManager

FOLDER_KEY = "bulk_folder"
TABLE_PAGE = 100
COLUMNS = (("#", 44), ("Type", 96), ("File name", 170), ("Content", 0), ("Result", 230))


class BulkPage(TwoColumnPage):

    def __init__(self, parent, style_provider=None):
        """``style_provider()`` -> (QRStyle, logo path or None): the look chosen on Generate."""
        super().__init__(parent)
        theme = ThemeManager.get_theme()
        self.style_provider = style_provider
        self.rows = []
        self.csv_path = ""
        self.job = None
        self._poll_job = None
        self._table_limit = TABLE_PAGE
        self._errors_only = False
        self.folder = settings_store.get(FOLDER_KEY, "") or ""

        # ======================= left: step 1 file, step 2 output =======================
        self.file_card = SectionCard(self.left, title="CSV file", step=1)
        self.file_card.pack(fill="x", pady=(0, CARD_GAP))
        body = self.file_card.body

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")
        self.choose_btn = self._button(top, "Choose CSV…", self.choose_csv, primary=True, width=150)
        self.choose_btn.pack(side="left")
        self.sample_btn = self._button(top, "Download sample CSV", self.download_sample, width=190)
        self.sample_btn.pack(side="left", padx=(10, 0))

        self.file_label = ctk.CTkLabel(
            body, text="No file chosen. Columns: type, content, filename, and the fields of each "
                       "type. The first line is the header.",
            anchor="w", justify="left", wraplength=560, font=("Segoe UI", 12),
            text_color=theme["text_secondary"])
        self.file_label.pack(fill="x", pady=(12, 0))

        self.table_bar = ctk.CTkFrame(body, fg_color="transparent")
        self.table_filter = ModernSegmented(self.table_bar, values=["All rows", "Errors only"],
                                            command=self._filter_table, height=30)
        self.table_filter.set("All rows")
        self.table_filter.pack(side="left")
        self.table_info = ctk.CTkLabel(self.table_bar, text="", font=("Segoe UI", 12),
                                       text_color=theme["text_secondary"])
        self.table_info.pack(side="right")
        self.table = ctk.CTkFrame(body, fg_color=theme["segment_bg"], corner_radius=12,
                                  border_width=1, border_color=theme["border"])
        self.more_btn = self._button(body, "Show more rows", self._more_rows, width=160)

        self.output_card = SectionCard(self.left, title="Output", step=2)
        self.output_card.pack(fill="x")
        out = self.output_card.body
        ctk.CTkLabel(out, text="SAVE IN FOLDER", anchor="w", font=("Segoe UI", 11),
                     text_color=theme["text_secondary"]).pack(fill="x")
        folder_row = ctk.CTkFrame(out, fg_color="transparent")
        folder_row.pack(fill="x", pady=(4, 12))
        self.folder_entry = ctk.CTkEntry(
            folder_row, height=38, corner_radius=10, border_width=1,
            border_color=theme["entry_border"], fg_color=theme["entry"], text_color=theme["text"],
            placeholder_text_color=theme["text_muted"], placeholder_text="Choose where to save",
            font=("Segoe UI", 13))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        if self.folder:
            self.folder_entry.insert(0, self.folder)
        self.folder_btn = self._button(folder_row, "Browse…", self.choose_folder, width=100)
        self.folder_btn.pack(side="left", padx=(10, 0))

        ctk.CTkLabel(out, text="FORMAT", anchor="w", font=("Segoe UI", 11),
                     text_color=theme["text_secondary"]).pack(fill="x")
        self.format_selector = ModernSegmented(out, values=list(qr_export.FORMATS), height=32,
                                               command=lambda _v: self._update_summary())
        self.format_selector.set("PNG")
        self.format_selector.pack(anchor="w", pady=(4, 12))
        self.style_label = ctk.CTkLabel(out, text="", anchor="w", justify="left", wraplength=820,
                                        font=("Segoe UI", 12), text_color=theme["text_secondary"])
        self.style_label.pack(fill="x")

        # ======================= right: summary and progress =======================
        self.summary = SectionCard(self.right, title="Summary", dot=True)
        self.summary.pack(fill="both", expand=True)
        sbody = self.summary.body
        self.buttons = ctk.CTkFrame(sbody, fg_color="transparent")
        self.buttons.pack(side="bottom", fill="x", pady=(12, 0))
        self.start_btn = self._button(self.buttons, "Create codes", self.start, primary=True)
        self.start_btn.pack(fill="x")
        self.cancel_btn = self._button(self.buttons, "Cancel", self.cancel, danger=True)
        self.open_btn = self._button(self.buttons, "Open folder", self.open_folder)

        self.counts = ctk.CTkLabel(sbody, text="", anchor="w", justify="left", wraplength=300,
                                   font=("Segoe UI Semibold", 15), text_color=theme["text"])
        self.counts.pack(fill="x")
        self.detail = ctk.CTkLabel(sbody, text="", anchor="w", justify="left", wraplength=300,
                                   font=("Segoe UI", 12), text_color=theme["text_secondary"])
        self.detail.pack(fill="x", pady=(4, 0))
        self.progress = ctk.CTkProgressBar(
            sbody, height=10, corner_radius=5, fg_color=theme["scrollbar"],
            progress_color=theme["primary"])
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(16, 6))
        self.status = ctk.CTkLabel(sbody, text="", anchor="w", justify="left", wraplength=300,
                                   font=("Segoe UI", 12), text_color=theme["text_secondary"])
        self.status.pack(fill="x")
        self.problems = ctk.CTkLabel(sbody, text="", anchor="w", justify="left", wraplength=300,
                                     font=("Segoe UI", 12), text_color=theme["danger"])
        self.problems.pack(fill="x", pady=(8, 0))

        self._update_summary()

    # ------------------------------------------------------------------ widgets

    def _button(self, parent, text, command, primary=False, danger=False, width=None):
        theme = ThemeManager.get_theme()
        kwargs = {"width": width} if width else {}
        return ctk.CTkButton(
            parent, text=text, command=command, height=44 if primary else 38, corner_radius=11,
            fg_color=theme["primary"] if primary else theme["segment_bg"],
            hover_color=theme["primary_hover"] if primary else theme["card_hover"],
            text_color=theme["on_primary"] if primary else (theme["danger"] if danger else theme["text"]),
            border_width=0 if primary else 1, border_color=theme["border"],
            text_color_disabled=theme["text_muted"],
            font=("Segoe UI Semibold", 14 if primary else 12), **kwargs)

    # ------------------------------------------------------------------ file

    def choose_csv(self):
        path = filedialog.askopenfilename(
            title="Choose a CSV file", filetypes=[("CSV file", "*.csv"), ("All files", "*.*")])
        if path:
            self.load_csv(path)

    def load_csv(self, path):
        """Read and check a CSV; shows its rows or why it cannot be used."""
        theme = ThemeManager.get_theme()
        self.csv_path = path
        self._table_limit = TABLE_PAGE
        try:
            self.rows = bulk_csv.read_rows(path)
        except bulk_csv.BulkFileError as e:
            self.rows = []
            self.file_label.configure(text=f"{os.path.basename(path)}\n{e}", text_color=theme["danger"])
            self._draw_table()
            self._update_summary()
            return
        bulk_csv.validate_size(self.rows, QRGenerator())
        self.file_label.configure(text=os.path.basename(path), text_color=theme["text"])
        self._draw_table()
        self._update_summary()

    def download_sample(self):
        path = filedialog.asksaveasfilename(
            title="Save the sample CSV", initialfile="mosaiq-bulk-sample.csv",
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(bulk_csv.SAMPLE_CSV)
        except OSError as e:
            messagebox.showerror("Could not save", e.strerror or str(e))
            return
        messagebox.showinfo("Sample saved", "Fill it in, then choose it with Choose CSV.")

    # ------------------------------------------------------------------ table

    def _filter_table(self, value):
        self._errors_only = value == "Errors only"
        self._table_limit = TABLE_PAGE
        self._draw_table()

    def _more_rows(self):
        self._table_limit += TABLE_PAGE
        self._draw_table()

    def _draw_table(self):
        theme = ThemeManager.get_theme()
        for child in self.table.winfo_children():
            child.destroy()
        if not self.rows:
            self.table_bar.pack_forget()
            self.table.pack_forget()
            self.more_btn.pack_forget()
            return
        errors = sum(1 for r in self.rows if not r.ok)
        self.table_bar.pack(fill="x", pady=(14, 8))
        self.table.pack(fill="x")
        shown_rows = [r for r in self.rows if (not r.ok or not self._errors_only)]
        visible = shown_rows[:self._table_limit]
        self.table_info.configure(
            text=f"{len(self.rows)} rows · {errors} with errors" if errors else f"{len(self.rows)} rows · all fine")

        self.table.grid_columnconfigure(3, weight=1)
        for column, (name, width) in enumerate(COLUMNS):
            ctk.CTkLabel(self.table, text=name.upper(), anchor="w", font=("Segoe UI", 10),
                         text_color=theme["text_secondary"], width=width).grid(
                row=0, column=column, sticky="w", padx=(12 if column == 0 else 4, 4), pady=(8, 4))
        for index, row in enumerate(visible, start=1):
            result = row.error or ("OK" + (f"  ·  {row.notes[0]}" if row.notes else ""))
            color = theme["danger"] if row.error else (theme["warning"] if row.notes else theme["success"])
            cells = (str(row.number), row.type, row.stem, " ".join(row.payload.split())[:70] or "—", result)
            for column, text in enumerate(cells):
                label = ctk.CTkLabel(
                    self.table, text=text, anchor="w", justify="left", font=("Segoe UI", 12),
                    text_color=color if column == 4 else theme["text"],
                    width=COLUMNS[column][1], wraplength=230 if column == 4 else 0)
                label.grid(row=index, column=column, sticky="ew" if column == 3 else "w",
                           padx=(12 if column == 0 else 4, 4), pady=2)
        if not visible:
            ctk.CTkLabel(self.table, text="No rows with errors.", font=("Segoe UI", 12),
                         text_color=theme["text_secondary"]).grid(row=1, column=0, columnspan=5, pady=14)
        left = len(shown_rows) - len(visible)
        if left > 0:
            self.more_btn.configure(text=f"Show {min(left, TABLE_PAGE)} more of {left} rows")
            self.more_btn.pack(pady=(10, 0))
        else:
            self.more_btn.pack_forget()

    # ------------------------------------------------------------------ output

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Choose the folder for the QR codes",
                                         initialdir=self.folder or None)
        if folder:
            self.folder_entry.delete(0, "end")
            self.folder_entry.insert(0, folder)
            self._folder_changed()

    def _folder_changed(self):
        self.folder = self.folder_entry.get().strip()
        settings_store.set(FOLDER_KEY, self.folder)
        self._update_summary()

    def _style_and_logo(self):
        if self.style_provider is None:
            from utils.qr_render import QRStyle
            return QRStyle(), None
        return self.style_provider()

    def _update_summary(self):
        theme = ThemeManager.get_theme()
        ok = sum(1 for r in self.rows if r.ok)
        bad = len(self.rows) - ok
        style, logo = self._style_and_logo()
        look = f"{style.module_shape} modules, {style.eye_shape} eyes"
        if style.gradient != "none":
            look += f", {style.gradient} gradient {style.fg} → {style.fg2}"
        else:
            look += f", {style.fg} on {style.bg}"
        self.style_label.configure(
            text=f"Look: {look}{', with your logo' if logo else ''}. It comes from the Generate page; "
                 f"change it there.")
        running = self.job is not None and self.job.running
        if not self.rows:
            self.counts.configure(text="No file loaded")
            self.detail.configure(text="Choose a CSV to see how many codes it makes.")
        else:
            self.counts.configure(text=f"{ok} code{'s' if ok != 1 else ''} to create")
            self.detail.configure(
                text=(f"{bad} row{'s' if bad != 1 else ''} with errors will be skipped. "
                      f"Fix them in the CSV and load it again." if bad else "Every row is fine."),
                text_color=theme["warning"] if bad else theme["text_secondary"])
        can_start = bool(ok) and not running
        self.start_btn.configure(
            state="normal" if can_start else "disabled",
            text=f"Create {ok} {self.format_selector.get()} file{'s' if ok != 1 else ''}" if ok else "Create codes")
        self.choose_btn.configure(state="disabled" if running else "normal")
        self.folder_btn.configure(state="disabled" if running else "normal")
        self.format_selector.configure(state="disabled" if running else "normal")

    # ------------------------------------------------------------------ run

    def start(self):
        folder = self.folder_entry.get().strip()
        if not folder:
            self.folder = ""
            messagebox.showwarning("Choose a folder", "Choose the folder where the QR codes are saved.")
            return
        self.folder = folder
        settings_store.set(FOLDER_KEY, folder)
        style, logo = self._style_and_logo()
        job = bulk_runner.BulkJob(self.rows, folder, style, self.format_selector.get(), logo)
        try:
            job.start()
        except OSError as e:
            messagebox.showerror("Could not use this folder", e.strerror or str(e))
            return
        self.job = job
        self.progress.set(0)
        self.problems.configure(text="")
        self.open_btn.pack_forget()
        self.cancel_btn.configure(state="normal")
        self.cancel_btn.pack(fill="x", pady=(8, 0))
        self.status.configure(text=f"Creating 0 of {job.total}…",
                              text_color=ThemeManager.get_theme()["text_secondary"])
        self._update_summary()
        self._poll_job = self.after(80, self._poll)

    def _poll(self):
        self._poll_job = None
        job = self.job
        if job is None:
            return
        done, total, finished = job.progress()
        if done is not None:
            self.progress.set(done / total if total else 1)
            self.status.configure(text=f"Creating {done} of {total}…")
        if finished:
            self._finished(job)
            return
        self._poll_job = self.after(80, self._poll)

    def cancel(self):
        if self.job is not None and self.job.running:
            self.job.cancel()
            self.cancel_btn.configure(state="disabled")
            self.status.configure(text="Cancelling after the current code…")

    def _finished(self, job):
        theme = ThemeManager.get_theme()
        self.cancel_btn.pack_forget()
        cancelled = job.state == bulk_runner.CANCELLED
        self.progress.set(job.saved / job.total if job.total else 1)
        verb = "Cancelled" if cancelled else "Done"
        self.status.configure(
            text=f"{verb}: {job.saved} of {job.total} codes saved in\n{job.folder}",
            text_color=theme["warning"] if (cancelled or job.failed) else theme["success"])
        if job.failed:
            lines = []
            for row, message in job.failed[:5]:
                lines.append(f"Row {row.number} ({row.stem}): {message}" if row else message)
            more = f"\n… and {len(job.failed) - 5} more" if len(job.failed) > 5 else ""
            self.problems.configure(text="Not saved:\n" + "\n".join(lines) + more)
        if job.saved:
            self.open_btn.pack(fill="x", pady=(8, 0))
        self.job = None
        self._update_summary()

    def open_folder(self):
        folder = self.folder_entry.get().strip()
        if folder and os.path.isdir(folder):
            os.startfile(folder)

    def on_hide(self):
        """Leaving the page never stops a running job; nothing to release."""

    def shutdown(self):
        """The app is closing: stop a running job after its current code."""
        if self.job is not None and self.job.running:
            self.job.cancel()
            self.job.join(5)

    # ------------------------------------------------------------------ theme

    def refresh_theme(self):
        super().refresh_theme()
        theme = ThemeManager.get_theme()
        for card in (self.file_card, self.output_card, self.summary):
            card.refresh_theme()
        self.table.configure(fg_color=theme["segment_bg"], border_color=theme["border"])
        self.table_filter.apply_theme()
        self.format_selector.apply_theme()
        self.folder_entry.configure(fg_color=theme["entry"], border_color=theme["entry_border"],
                                    text_color=theme["text"], placeholder_text_color=theme["text_muted"])
        self.progress.configure(fg_color=theme["scrollbar"], progress_color=theme["primary"])
        for label in (self.file_label, self.table_info, self.style_label, self.status):
            label.configure(text_color=theme["text_secondary"])
        self.counts.configure(text_color=theme["text"])
        self.problems.configure(text_color=theme["danger"])
        for button, primary, danger in ((self.choose_btn, True, False), (self.sample_btn, False, False),
                                        (self.folder_btn, False, False), (self.more_btn, False, False),
                                        (self.start_btn, True, False), (self.cancel_btn, False, True),
                                        (self.open_btn, False, False)):
            button.configure(
                fg_color=theme["primary"] if primary else theme["segment_bg"],
                hover_color=theme["primary_hover"] if primary else theme["card_hover"],
                text_color=theme["on_primary"] if primary else (theme["danger"] if danger else theme["text"]),
                border_color=theme["border"])
        self._draw_table()
        self._update_summary()
