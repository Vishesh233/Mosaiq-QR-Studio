"""Bulk Create page: loading a CSV, row-wise errors in the table, the 1000-row limit message,
running with progress and Cancel while the window keeps answering, formats, failures.

Run:  .venv\\Scripts\\python.exe _bulk_ui_test.py
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["APPDATA"] = tempfile.mkdtemp()

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def write(text, name="rows.csv"):
    path = os.path.join(tempfile.mkdtemp(), name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def main():
    from tkinter import filedialog, messagebox

    from config import WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
    from ui.app import QRCodeStudioApp
    from utils import bulk_csv, bulk_runner, qr_export, settings_store
    from utils.qr_scanner import QRScanner

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()

    def settle(seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    shown = []
    messagebox.showinfo = lambda *a, **k: shown.append(("info", a))
    messagebox.showwarning = lambda *a, **k: shown.append(("warning", a))
    messagebox.showerror = lambda *a, **k: shown.append(("error", a))

    check("Bulk Create is in the sidebar", "bulk" in app.sidebar._nav_buttons)
    app.sidebar._nav_buttons["bulk"].invoke()
    settle()
    bp = app.bulk_page
    check("the sidebar opens the page", app._current_page == "bulk" and bp.winfo_manager())
    check("title", app.header._title_label.cget("text") == "Bulk Create")
    check("start disabled before a file", str(bp.start_btn.cget("state")) == "disabled")
    from utils.paths import documents_folder
    wanted = os.path.join(documents_folder(), "QR codes")
    check("the folder starts as the user's own Documents\\QR codes", bp.folder_entry.get() == wanted,
          f"{bp.folder_entry.get()!r} vs {wanted!r}")
    check("... without saving it as a choice", settings_store.get("bulk_folder") is None)
    check("no made-up user name in the default", "\\you\\" not in bp.folder_entry.get().lower())
    check("progress bar is empty before a run", bp.progress.get() == 0
          and bp.progress.cget("progress_color") == bp.progress.cget("fg_color"),
          f"{bp.progress.get()} {bp.progress.cget('progress_color')} {bp.progress.cget('fg_color')}")
    check("table hidden before a file", not bp.table.winfo_manager())

    # ---- sample CSV download ----
    target = os.path.join(tempfile.mkdtemp(), "sample.csv")
    filedialog.asksaveasfilename = lambda **kw: target
    bp.download_sample()
    check("sample CSV written", open(target, encoding="utf-8").read() == bulk_csv.SAMPLE_CSV)
    check("sample download confirms", any(k == "info" for k, _ in shown))
    del shown[:]
    filedialog.asksaveasfilename = lambda **kw: ""
    bp.download_sample()
    check("cancelled download writes and says nothing", not shown)
    root.update()

    # ---- load the sample ----
    bp.load_csv(target)
    settle()
    check("sample loaded: seven rows (six types and plain text)", len(bp.rows) == 7 and all(r.ok for r in bp.rows))
    check("table shown", bool(bp.table.winfo_manager()))
    check("table lists the rows", len([w for w in bp.table.winfo_children()
                                         if w.cget("text") == "OK"]) == 7)
    check("count shown", "7 codes to create" in bp.counts.cget("text"), bp.counts.cget("text"))
    check("file name shown", bp.file_label.cget("text") == "sample.csv")
    check("start still needs a folder, but is enabled", str(bp.start_btn.cget("state")) == "normal"
          and "7 PNG files" in bp.start_btn.cget("text"), bp.start_btn.cget("text"))

    # ---- long content: ellipsis, and no text runs into the next column, at every window size ----
    long_url = "https://example.com/" + "very-long-path/" * 12
    bp.load_csv(write("type,content,filename\nurl," + long_url + ",longone\nurl,https://short.example,short\n"))
    settle()

    def table_cells():
        grid = {}
        for widget in bp.table.winfo_children():
            info = widget.grid_info()
            grid[(int(info["row"]), int(info["column"]))] = widget
        headers = {w.cget("text"): c for (r, c), w in grid.items() if r == 0}
        return grid, headers

    for width, height, columns in ((1280, 820, ["#", "FILE NAME", "CONTENT", "RESULT"]),
                                   (WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, ["#", "FILE NAME", "RESULT"]),
                                   (1920, 1080, ["#", "TYPE", "FILE NAME", "CONTENT", "RESULT"])):
        root.geometry(f"{width}x{height}+-30000+-30000")
        settle(0.8)
        grid, headers = table_cells()
        label = f"at {width}x{height}"
        check(f"columns {label}", sorted(headers, key=headers.get) == columns, str(sorted(headers, key=headers.get)))
        for row in (0, 1, 2):
            cells = [grid[(row, c)] for c in range(len(columns))]
            check(f"every cell is shown, row {row} {label}", all(w.winfo_ismapped() for w in cells),
                  str([w.cget("text") for w in cells if not w.winfo_ismapped()]))
            for left, right in zip(cells, cells[1:]):
                check(f"cells do not overlap ('{left.cget('text')[:12]}' / '{right.cget('text')[:12]}') {label}",
                      left.winfo_rootx() + left.winfo_width() <= right.winfo_rootx(),
                      f"{left.winfo_rootx() + left.winfo_width()} vs {right.winfo_rootx()}")
            for cell in cells:                       # the text itself fits its cell (is not clipped)
                import tkinter.font as tkfont
                family, points = cell.cget("font")[:2]
                font = tkfont.Font(root=root, family=family, size=-round(abs(points) * 96 / 72))
                need = font.measure(cell.cget("text")) * cell._get_widget_scaling()
                check(f"text fits its cell: '{cell.cget('text')[:20]}' {label}",
                      need <= cell.winfo_width() + 2 or cell.cget("wraplength"), f"{need:.0f} > {cell.winfo_width()}")
        if "CONTENT" in headers:
            content = grid[(1, headers["CONTENT"])].cget("text")
            check(f"long content is cut with an ellipsis {label}", content.endswith("…") and len(content) < len(long_url),
                  content)
            check(f"short content is whole {label}", grid[(2, headers["CONTENT"])].cget("text") == "https://short.example")
            result = grid[(1, headers["RESULT"])]
            text_cell = grid[(1, headers["CONTENT"])]
            gap = result.winfo_rootx() - (text_cell.winfo_rootx() + text_cell.winfo_width())
            check(f"gap between Content and Result {label}", gap >= 16, f"{gap} px")
    root.geometry("1280x820+-30000+-30000")
    settle(0.6)

    # ---- a file with errors ----
    bad = write("type,content,filename,upi_id,amount\n"
                "url,https://ok.example,fine,,\n"
                "fax,hello,badtype,,\n"
                "url,,empty,,\n"
                "upi,,badupi,notanupiid,abc\n"
                "url,https://ok2.example,fine2,,\n")
    bp.load_csv(bad)
    settle()
    check("errors counted", "3 with errors" in bp.table_info.cget("text"), bp.table_info.cget("text"))
    check("only valid rows will be created", "2 codes to create" in bp.counts.cget("text"))
    check("the warning says what happens", "3 rows with errors will be skipped" in bp.detail.cget("text"),
          bp.detail.cget("text"))
    texts = [w.cget("text") for w in bp.table.winfo_children()]
    check("each error is shown on its row", any("Unknown type 'fax'" in t for t in texts)
          and any("Nothing to encode" in t for t in texts), str([t for t in texts if len(t) > 20]))
    bp.table_filter.set("Errors only")
    bp._filter_table("Errors only")
    settle()
    texts = [w.cget("text") for w in bp.table.winfo_children()]
    check("Errors only hides the good rows", "fine" not in texts and "fine2" not in texts and "badtype" in texts)
    bp.table_filter.set("All rows")
    bp._filter_table("All rows")

    # ---- unusable files ----
    many = write("content\n" + "\n".join(f"https://example.com/{i}" for i in range(1001)) + "\n", "many.csv")
    bp.load_csv(many)
    settle()
    check("1001 rows: clear message", "1000" in bp.file_label.cget("text"), bp.file_label.cget("text"))
    check("1001 rows: nothing loaded, nothing to start", bp.rows == []
          and str(bp.start_btn.cget("state")) == "disabled" and not bp.table.winfo_manager())
    for label, text, expect in (("empty file", "", "empty"), ("no header", "https://a.example,b\nc,d\n", "header"),
                                ("header only", "type,content\n", "no rows")):
        bp.load_csv(write(text))
        check(f"{label}: message", expect in bp.file_label.cget("text").lower(), bp.file_label.cget("text"))
    bp.load_csv(os.path.join(tempfile.mkdtemp(), "missing.csv"))
    check("missing file: message", "Could not read" in bp.file_label.cget("text"))

    # ---- running: no folder, then a real run ----
    bp.load_csv(write("content,filename\n" + "\n".join(
        f"https://example.com/bulk/{i},item{i}" for i in range(150))))
    settle()
    bp.folder_entry.delete(0, "end")
    del shown[:]
    bp.start()
    check("no folder: asks for one", shown and shown[0][0] == "warning" and bp.job is None, repr(shown))

    out = os.path.join(tempfile.mkdtemp(), "codes")
    filedialog.askdirectory = lambda **kw: out
    bp.choose_folder()
    check("folder chosen and remembered", bp.folder_entry.get() == out and settings_store.get("bulk_folder") == out)

    gp = app.generate_page
    gp.design_card.apply_preset("Ocean")          # the look comes from the Generate page
    check("summary names the look", "gradient" in bp.style_label.cget("text") or True)
    bp._update_summary()
    check("summary names the look", "linear gradient" in bp.style_label.cget("text"), bp.style_label.cget("text"))

    bp.start()
    check("job started", bp.job is not None and bp.job.running)
    check("Cancel appears while running", bool(bp.cancel_btn.winfo_manager()))
    check("Start / Choose disabled while running", str(bp.start_btn.cget("state")) == "disabled"
          and str(bp.choose_btn.cget("state")) == "disabled")
    values, worst, last = [], 0.0, time.time()
    end = time.time() + 120
    while bp.job is not None and time.time() < end:
        root.update()
        now = time.time()
        worst, last = max(worst, now - last), now
        values.append(bp.progress.get())
        time.sleep(0.004)
    # One gap of up to ~0.6 s is tolerated: with two monitors of different scaling CustomTkinter's own
    # DPI check (every 100 ms) can re-scale a parked window once. A frozen window shows gaps of seconds.
    check("window kept answering during the run", worst < 0.8, f"worst gap {worst:.2f}s")
    check("progress only goes forward", all(b >= a - 1e-9 for a, b in zip(values, values[1:])))
    check("progress reached the end", values[-1] > 0.99, str(values[-1]))
    check("final message", "Done: 150 of 150 codes saved" in bp.status.cget("text"), bp.status.cget("text"))
    check("Cancel gone, Open folder offered", not bp.cancel_btn.winfo_manager() and bool(bp.open_btn.winfo_manager()))
    check("Start usable again", str(bp.start_btn.cget("state")) == "normal"
          and str(bp.choose_btn.cget("state")) == "normal")
    files = sorted(os.listdir(out))
    check("150 files in the folder", len(files) == 150, str(len(files)))
    from PIL import Image
    sample = Image.open(os.path.join(out, "item7.png")).convert("RGB")
    import numpy as np
    pixels = np.asarray(sample).reshape(-1, 3).astype(int)
    inked = pixels[pixels.sum(axis=1) < 300]                 # module pixels, not the white margin
    check("the Generate page's look was used (blue-ish gradient, not black)",
          len(inked) > 0 and inked[:, 2].mean() > inked[:, 0].mean() + 40,
          str(inked.mean(axis=0)) if len(inked) else "no dark pixels")
    check("a file scans back", QRScanner.decode_image(sample, thorough=False) == "https://example.com/bulk/7")

    # ---- formats ----
    for fmt, magic in (("SVG", b"<svg"), ("PDF", b"%PDF-")):
        bp.format_selector.set(fmt)
        bp._update_summary()
        check(f"{fmt}: start button names the format", fmt in bp.start_btn.cget("text"), bp.start_btn.cget("text"))
        out2 = os.path.join(tempfile.mkdtemp(), fmt)
        bp.folder_entry.delete(0, "end")
        bp.folder_entry.insert(0, out2)
        bp.load_csv(write("content,filename\nhttps://example.com/a,a\nhttps://example.com/b,b\n"))
        bp.start()
        end = time.time() + 60
        while bp.job is not None and time.time() < end:
            root.update()
            time.sleep(0.01)
        names = sorted(os.listdir(out2))
        check(f"{fmt}: files written", names == ["a" + qr_export.EXTENSIONS[fmt], "b" + qr_export.EXTENSIONS[fmt]], str(names))
        check(f"{fmt}: content looks right", open(os.path.join(out2, names[0]), "rb").read(8).startswith(magic))
    bp.format_selector.set("PNG")

    # ---- Cancel ----
    big = write("content,filename\n" + "\n".join(
        f"https://example.com/long/path/for/a/bigger/code/{'x' * 80}/{i},c{i}" for i in range(600)))
    out3 = os.path.join(tempfile.mkdtemp(), "cancel")
    bp.folder_entry.delete(0, "end")
    bp.folder_entry.insert(0, out3)
    bp.load_csv(big)
    bp.start()
    end = time.time() + 30
    while bp.progress.get() == 0 and time.time() < end:
        root.update()
        time.sleep(0.01)
    bp.cancel()
    check("Cancel acknowledged at once", "Cancelling" in bp.status.cget("text")
          and str(bp.cancel_btn.cget("state")) == "disabled")
    end = time.time() + 60
    while bp.job is not None and time.time() < end:
        root.update()
        time.sleep(0.01)
    saved = len(os.listdir(out3))
    check("cancelled: message", bp.status.cget("text").startswith("Cancelled"), bp.status.cget("text"))
    check("cancelled early with some files kept", 0 < saved < 600, str(saved))
    check("cancelled: reported count matches the folder", f"{saved} of 600" in bp.status.cget("text"),
          f"{saved}: {bp.status.cget('text')}")
    check("cancelled: Start usable again", str(bp.start_btn.cget("state")) == "normal")

    # ---- failures are listed, the rest saved ----
    original = qr_export.export

    def flaky(path, fmt, generator, data, style, logo=None):
        if data.endswith("/3"):
            raise OSError(13, "Access is denied")
        return original(path, fmt, generator, data, style, logo)

    qr_export.export = flaky
    try:
        out4 = os.path.join(tempfile.mkdtemp(), "flaky")
        bp.folder_entry.delete(0, "end")
        bp.folder_entry.insert(0, out4)
        bp.load_csv(write("content,filename\n" + "\n".join(f"https://example.com/f/{i},f{i}" for i in range(8))))
        bp.start()
        end = time.time() + 60
        while bp.job is not None and time.time() < end:
            root.update()
            time.sleep(0.01)
    finally:
        qr_export.export = original
    check("failure listed with row and reason", "f3" in bp.problems.cget("text")
          and "Access is denied" in bp.problems.cget("text"), bp.problems.cget("text"))
    check("the other seven saved", len(os.listdir(out4)) == 7 and "7 of 8" in bp.status.cget("text"))

    # ---- an unusable folder is reported before anything starts ----
    blocker = os.path.join(tempfile.mkdtemp(), "file")
    open(blocker, "w").write("x")
    bp.folder_entry.delete(0, "end")
    bp.folder_entry.insert(0, os.path.join(blocker, "sub"))
    del shown[:]
    bp.start()
    check("unusable folder: error shown, no job", shown and shown[0][0] == "error" and bp.job is None, repr(shown))

    # ---- leaving the page does not stop a run ----
    out5 = os.path.join(tempfile.mkdtemp(), "away")
    bp.folder_entry.delete(0, "end")
    bp.folder_entry.insert(0, out5)
    bp.load_csv(write("content,filename\n" + "\n".join(f"https://example.com/away/{i},a{i}" for i in range(80))))
    bp.start()
    app.show_generate_page()
    app.show_bulk_page()
    end = time.time() + 60
    while bp.job is not None and time.time() < end:
        root.update()
        time.sleep(0.01)
    check("a run continues while another page is open", len(os.listdir(out5)) == 80, str(len(os.listdir(out5))))

    # ---- layout ----
    for width, height in ((WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT), (1280, 820)):
        root.geometry(f"{width}x{height}+-30000+-30000")
        settle()
        bottom = root.winfo_rooty() + root.winfo_height()
        check(f"Start visible at {width}x{height}", bp.start_btn.winfo_ismapped()
              and bp.start_btn.winfo_rooty() + bp.start_btn.winfo_height() <= bottom,
              f"mapped={bp.start_btn.winfo_ismapped()} button bottom="
              f"{bp.start_btn.winfo_rooty() + bp.start_btn.winfo_height()} window bottom={bottom}")
        check(f"title and cards share an edge at {width}x{height}",
              abs(app.header._title_label.winfo_rootx() - bp.left.winfo_rootx()) <= 3)
    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("BULK_UI_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("BULK_UI_OK: CSV table and errors, 1000-row message, progress and Cancel without freezing, formats, failures")
