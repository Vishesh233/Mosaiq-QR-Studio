"""Generate page layout and Save dialog behaviour.

Covers: shared left edge (title, subtitle, cards), sticky preview column (buttons stay
visible while the left column scrolls, also at the smallest window), default file names
per type, and the Save dialog on cancel / odd names / unwritable paths (no crash).

Run:  .venv\\Scripts\\python.exe _generate_ui_test.py
"""
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def test_filenames():
    from utils import filenames as fn

    check("default names", [fn.default_stem(t) for t in
          ("URL / Text", "UPI Payment", "WiFi", "Contact", "Email", "SMS")] ==
          ["url_qr", "upi_qr", "wifi_qr", "contact_qr", "email_qr", "sms_qr"])
    check("unknown type falls back", fn.default_stem("???") == "qr_code")
    for raw, expected in (
        ("", "qr_code"), (None, "qr_code"), ("   ", "qr_code"), ("...", "qr_code"),
        ("con", "qr_code"), ("NUL.txt", "qr_code"), ("COM3", "qr_code"), ("lpt1", "qr_code"),
        ("a/b\\c:d*e?f\"g<h>i|j", "a_b_c_d_e_f_g_h_i_j"),
        ("name. ", "name"), ("my qr", "my qr"), ("ड्रॉप क्यूआर", "ड्रॉप क्यूआर"),
    ):
        got = fn.safe_stem(raw)
        check(f"safe_stem({raw!r})", got == expected, f"-> {got!r}, expected {expected!r}")
    check("long names are cut", len(fn.safe_stem("x" * 500)) <= fn.MAX_STEM)
    check("with_extension adds", fn.with_extension("C:/a/b", ".png") == "C:/a/b.png")
    check("with_extension keeps", fn.with_extension("C:/a/b.PNG", ".png") == "C:/a/b.PNG")
    check("with_extension other ext", fn.with_extension("C:/a/b.jpg", ".png") == "C:/a/b.jpg.png")


def test_ui():
    from tkinter import filedialog, messagebox

    from ui.app import QRCodeStudioApp
    from config import WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH

    appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = appdata

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")   # off-screen, but mapped (withdrawn = unmapped)
    root.update()
    gp = app.generate_page

    def settle():
        for _ in range(4):
            root.update()

    settle()

    # ---- alignment: header title/subtitle and the first card share one left edge ----
    title_x = app.header._title_label.winfo_rootx()
    sub_x = app.header._subtitle_label.winfo_rootx()
    card_x = gp.content_card.winfo_rootx()
    check("title and subtitle share an edge", abs(title_x - sub_x) <= 3, f"{title_x} vs {sub_x}")
    check("title and cards share an edge", abs(title_x - card_x) <= 3, f"{title_x} vs {card_x}")
    app.show_scan_page()
    settle()
    scan_card_x = app.scan_page.upload_card.winfo_rootx()
    check("scan page cards on the same edge", abs(title_x - scan_card_x) <= 3,
          f"{title_x} vs {scan_card_x}")
    app.show_generate_page()
    settle()

    # ---- the right column is not inside the scrolling area ----
    check("preview is outside the scrolling column",
          not str(gp.preview_card).startswith(str(gp.left)))

    # ---- buttons visible at the minimum window size, before and after generating ----
    for stage in ("empty", "generated"):
        if stage == "generated":
            gp.content_card.url_entry.insert(0, "https://example.com/layout")
            gp.generate_qr()
        for width, height in ((WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT), (1280, 820)):
            root.geometry(f"{width}x{height}+-30000+-30000")
            settle()
            window_bottom = root.winfo_rooty() + root.winfo_height()
            for name in ("generate_btn", "save_btn", "copy_btn", "clear_btn"):
                button = getattr(gp.action_buttons, name)
                bottom = button.winfo_rooty() + button.winfo_height()
                check(f"{name} visible ({stage}, {width}x{height})",
                      button.winfo_ismapped() and bottom <= window_bottom,
                      f"bottom {bottom} > window {window_bottom}")
            qr_box = gp.preview_card.preview_box
            check(f"QR box not squashed ({stage}, {width}x{height})",
                  qr_box.winfo_height() >= 150, f"{qr_box.winfo_height()} px")

    # ---- scrolling the left column does not move the buttons ----
    root.geometry("1280x820+-30000+-30000")
    settle()
    before = gp.action_buttons.generate_btn.winfo_rooty()
    gp.left._parent_canvas.yview_moveto(1.0)
    settle()
    check("buttons stay put while the left column scrolls",
          gp.action_buttons.generate_btn.winfo_rooty() == before)

    # ---- Save dialog ----
    original = (filedialog.asksaveasfilename, messagebox.showinfo, messagebox.showerror,
                messagebox.showwarning)
    shown = []
    messagebox.showinfo = lambda *a, **k: shown.append(("info", a))
    messagebox.showerror = lambda *a, **k: shown.append(("error", a))
    messagebox.showwarning = lambda *a, **k: shown.append(("warning", a))
    asked = {}
    answer = {"value": ""}

    def fake_dialog(**kwargs):
        asked.update(kwargs)
        return answer["value"]

    filedialog.asksaveasfilename = fake_dialog
    try:
        gp.generate_qr()
        # default name follows the type
        for type_name, stem in (("URL / Text", "url_qr"), ("UPI Payment", "upi_qr"),
                                ("WiFi", "wifi_qr"), ("Contact", "contact_qr"),
                                ("Email", "email_qr"), ("SMS", "sms_qr")):
            gp.content_card.set_type(type_name)
            answer["value"] = ""
            gp.save_qr()
            check(f"default name for {type_name}", asked.get("initialfile") == f"{stem}.png",
                  repr(asked.get("initialfile")))
        check("dialog offers PNG", asked.get("defaultextension") == ".png")

        # cancelled dialog: nothing saved, no message, no crash
        del shown[:]
        answer["value"] = ""
        gp.save_qr()
        check("cancel shows no message", shown == [], repr(shown))

        # a name without extension gets .png
        target = os.path.join(appdata, "no_extension")
        answer["value"] = target
        gp.save_qr()
        check("extension added", os.path.exists(target + ".png"), repr(os.listdir(appdata)))
        check("saved file is a PNG", open(target + ".png", "rb").read(8) == b"\x89PNG\r\n\x1a\n")
        check("success message shown", any(kind == "info" for kind, _ in shown), repr(shown))

        # unwritable / invalid paths: an error message, no crash, app still usable
        for bad in (os.path.join(appdata, "missing_folder", "x.png"),
                    os.path.join(appdata, "a<b>c.png"), "Z:\\no\\such\\drive\\x.png"):
            del shown[:]
            answer["value"] = bad
            try:
                gp.save_qr()
                check(f"bad path {bad!r} reported", any(kind == "error" for kind, _ in shown),
                      repr(shown))
            except Exception as e:
                check(f"bad path {bad!r} did not raise", False, repr(e))

        # nothing generated yet: warning, no dialog
        gp.clear_form()
        asked.clear()
        del shown[:]
        gp.save_qr()
        check("save with nothing generated warns", shown and shown[0][0] == "warning", repr(shown))
        check("... and opens no dialog", not asked)
    finally:
        (filedialog.asksaveasfilename, messagebox.showinfo, messagebox.showerror,
         messagebox.showwarning) = original

    app.close()


def main():
    test_filenames()
    test_ui()
    if problems:
        print("GENERATE_UI_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("GENERATE_UI_OK: edges, sticky preview, min-size fit, filenames, Save dialog")


if __name__ == "__main__":
    main()
