"""History page and everything around it: saving from Generate and Scan, Open / Re-generate /
Copy / Delete, the Settings switches and Clear history, filters, paging and layout.

Run:  .venv\\Scripts\\python.exe _history_ui_test.py
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
PASSWORD = "hunter2-pass"


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def main():
    from tkinter import messagebox

    from config import WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
    from ui.app import QRCodeStudioApp
    from ui.dialogs.settings_dialog import SettingsDialog
    from utils import history_store as h, qr_payloads
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()
    gp, sp, hp = app.generate_page, app.scan_page, app.history_page

    def settle(seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    shown = []
    messagebox.showinfo = lambda *a, **k: shown.append(("info", a))
    messagebox.showwarning = lambda *a, **k: shown.append(("warning", a))
    messagebox.showerror = lambda *a, **k: shown.append(("error", a))
    answers = {"yes": True}
    messagebox.askyesno = lambda *a, **k: answers["yes"]

    # ---- navigation and the empty page ----
    check("History is in the sidebar", "history" in app.sidebar._nav_buttons)
    app.sidebar._nav_buttons["history"].invoke()
    settle()
    check("the sidebar opens the History page", app._current_page == "history" and hp.winfo_manager())
    check("title and subtitle", app.header._title_label.cget("text") == "History")
    check("empty page says so", "No history yet" in hp.empty_label.cget("text"), hp.empty_label.cget("text"))
    check("buttons disabled with nothing selected",
          all(str(b.cget("state")) == "disabled" for b in (hp.open_btn, hp.copy_btn, hp.regen_btn, hp.delete_btn)))
    app.show_generate_page()

    # ---- Generate saves, once, and not on live redraws ----
    gp.content_card.url_entry.insert(0, "https://example.com/history-a")
    gp.generate_qr()
    settle()
    entries = h.entries()
    check("generate adds one entry", len(entries) == 1 and entries[0]["kind"] == "generated"
          and entries[0]["type"] == "URL / Text" and entries[0]["text"] == "https://example.com/history-a")
    check("form values saved", entries[0]["fields"] == {"url": "https://example.com/history-a"})
    check("preview saved", h.thumbnail_path(entries[0]) is not None)
    gp.generate_qr()
    check("same code again is not a new entry", h.count() == 1)
    gp.design_card.style.module_tiles.tiles["dots"].invoke()
    settle(0.6)
    check("a live style redraw does not add an entry", h.count() == 1)
    gp.generate_qr()
    check("a different look is a new entry", h.count() == 2)
    check("the style is saved", QRStyle.from_dict(h.entries()[0]["style"]).module_shape == "dots")

    # ---- WiFi: password and picture are not kept ----
    gp.clear_form()
    gp.content_card.set_type("WiFi")
    wifi = gp.content_card.forms["WiFi"]
    wifi.ssid.set("Guest Net")
    wifi.password.set(PASSWORD)
    gp.generate_qr()
    settle()
    top = h.entries()[0]
    check("wifi entry saved without password", top["type"] == "WiFi" and top.get("redacted")
          and PASSWORD not in top["text"] and "password" not in top["fields"], str(top))
    check("wifi entry has no picture", h.thumbnail_path(top) is None)
    hp.refresh()
    settle()
    boxes = {(row.picture.winfo_width(), row.picture.winfo_height()) for row in hp._rows.values()}
    check("a row without a picture has the same picture box as the others", len(boxes) == 1, str(boxes))
    sizes = {tuple(row._thumb._size) for row in hp._rows.values()}
    check("... and the same image size", len(sizes) == 1, str(sizes))
    wifi_row = next(r for r in hp._rows.values() if r.entry["type"] == "WiFi")
    check("the WiFi row is among them", wifi_row is not None)
    for path in h.stored_files():
        if path.endswith(".json"):
            check("password not in history.json", PASSWORD not in open(path, encoding="utf-8").read())

    # ---- Scan saves the text only ----
    app.show_scan_page()
    qr_path = os.path.join(tempfile.mkdtemp(), "scan.png")
    upi = qr_payloads.build_upi("shop@okaxis", "Corner Shop", "99.50", "Order")
    QRGenerator().generate(upi).save(qr_path)
    before = h.count()
    sp.on_image_selected(qr_path)
    settle()
    scanned = h.entries()[0]
    check("scanning adds an entry", h.count() == before + 1 and scanned["kind"] == "scanned")
    check("scanned type recognised", scanned["type"] == "UPI Payment", scanned["type"])
    check("scanned text kept", scanned["text"] == upi)
    check("scan preview is a drawing of the text", decode(h.thumbnail_path(scanned)) == upi)
    sp.on_image_selected(qr_path)
    check("scanning the same code twice in a row is one entry", h.count() == before + 1)
    wifi_text = qr_payloads.build_wifi("Scan Net", PASSWORD, "WPA")
    wifi_path = os.path.join(tempfile.mkdtemp(), "wifi.png")
    QRGenerator().generate(wifi_text).save(wifi_path)
    sp.on_image_selected(wifi_path)
    wifi_scanned = h.entries()[0]
    check("scanned wifi: no password, no picture", PASSWORD not in wifi_scanned["text"]
          and h.thumbnail_path(wifi_scanned) is None and wifi_scanned.get("redacted"))
    sp.result_card.clear()
    sp.upload_card.clear()
    sp.scan_image(QRGenerator().generate("https://example.com/pasted"))
    check("scan_image (clipboard / screen) also saves", h.entries()[0]["text"] == "https://example.com/pasted")
    check("nothing found saves nothing", True)
    count = h.count()
    from PIL import Image
    sp.scan_image(Image.new("RGB", (200, 200), "white"))
    check("an image without a code saves nothing", h.count() == count)

    # ---- the page lists them ----
    app.show_history_page()
    settle()
    total = h.count()
    check("every entry is listed", len(hp._rows) == total, f"{len(hp._rows)} rows for {total}")
    check("count shown", f"{total} codes" in hp.count_label.cget("text"), hp.count_label.cget("text"))
    hp.filter.set("Scanned")
    hp._filter_changed("Scanned")
    check("scanned filter", all(r.entry["kind"] == "scanned" for r in hp._rows.values()) and len(hp._rows) == 3)
    hp.filter.set("Generated")
    hp._filter_changed("Generated")
    check("generated filter", all(r.entry["kind"] == "generated" for r in hp._rows.values()) and len(hp._rows) == 3)
    hp.filter.set("All")
    hp._filter_changed("All")

    # ---- details, Copy ----
    generated_ids = [e["id"] for e in h.entries() if e["kind"] == "generated"]
    hp.select(generated_ids[-1])                    # the oldest generated entry (plain, square)
    settle()
    check("details show the entry", "history-a" in hp.detail_title.cget("text"))
    check("buttons enabled", all(str(b.cget("state")) == "normal" for b in (hp.open_btn, hp.copy_btn, hp.regen_btn, hp.delete_btn)))
    check("preview drawn for a normal entry", hp._detail_image is not None)
    hp._copy()
    check("Copy puts the text on the clipboard", root.clipboard_get() == "https://example.com/history-a")
    wifi_entry = next(e for e in h.entries() if e["type"] == "WiFi" and e["kind"] == "generated")
    hp.select(wifi_entry["id"])
    settle()
    check("no preview for a redacted WiFi code", hp._detail_image is None and "No picture" in hp.preview.cget("text"))
    check("note about the missing password", "password was not saved" in hp.detail_note.cget("text"))

    # ---- Open / Re-generate ----
    ids_before = [e["id"] for e in h.entries()]
    dotted = next(e for e in h.entries() if e["kind"] == "generated" and e["style"]["module_shape"] == "dots")
    hp.select(dotted["id"])
    hp._open()
    settle()
    check("Open goes to Generate", app._current_page == "generate")
    check("Open fills the form", gp.content_card.url_entry.get() == "https://example.com/history-a")
    check("Open restores the style", gp.design_card.get_style().module_shape == "dots")
    check("Open draws the code", gp.generated_image is not None and gp.generated_data == dotted["text"])
    check("Open adds no entry", [e["id"] for e in h.entries()] == ids_before)

    app.show_history_page()
    plain = next(e for e in h.entries() if e["kind"] == "generated" and e["style"]["module_shape"] == "square"
                 and e["type"] == "URL / Text")
    hp.select(plain["id"])
    hp._regenerate()
    settle()
    check("Re-generate adds an entry on top", h.count() == len(ids_before) + 1
          and h.entries()[0]["text"] == plain["text"])
    check("Re-generate shows the square style", gp.design_card.get_style().module_shape == "square")

    app.show_history_page()
    scanned_url = next(e for e in h.entries() if e["kind"] == "scanned" and e["text"] == upi)
    hp.select(scanned_url["id"])
    hp._open()
    settle()
    check("Open on a scanned code goes to Scan", app._current_page == "scan")
    check("... and shows its result", sp.result_card.result == upi and "Corner Shop" in sp.result_card.shown_text())
    app.show_history_page()
    hp.select(scanned_url["id"])
    count = h.count()
    hp._regenerate()
    settle()
    check("Re-generate from a scan opens Generate with the text", app._current_page == "generate"
          and gp.content_card.active_type == "URL / Text" and gp.content_card.url_entry.get() == upi)
    check("... draws it and saves a generated entry", h.entries()[0]["kind"] == "generated"
          and h.entries()[0]["text"] == upi and h.count() == count + 1)

    app.show_history_page()
    del shown[:]
    hp.select(wifi_entry["id"])
    hp._open()
    settle()
    check("Open on a WiFi entry without password asks for it", any("password" in a[1].lower() for k, a in shown), repr(shown))
    check("... form is filled but nothing is drawn", gp.content_card.active_type == "WiFi"
          and gp.content_card.forms["WiFi"].ssid.get() == "Guest Net"
          and gp.content_card.forms["WiFi"].password.get() == "" and gp.generated_image is None)

    # ---- Delete ----
    app.show_history_page()
    victim = h.entries()[-1]
    thumb = h.thumbnail_path(victim)
    hp.select(victim["id"])
    count = h.count()
    hp._delete()
    check("Delete removes the entry", h.count() == count - 1 and h.get(victim["id"]) is None)
    check("... and its picture", thumb is None or not os.path.exists(thumb))
    check("... and clears the selection", hp.selected_entry() is None
          and str(hp.delete_btn.cget("state")) == "disabled")

    # ---- Settings: switches and Clear history ----
    dlg = SettingsDialog(app.header)
    settle()
    check("settings show the history switches", dlg.history_var.get() is True and dlg.wifi_var.get() is False)
    check("saved count shown", f"{h.count()} saved" in dlg.history_count.cget("text"), dlg.history_count.cget("text"))
    dlg.history_var.set(False)
    dlg.apply()
    settle()
    check("Apply switches history off", h.enabled() is False)
    count = h.count()
    gp.clear_form()
    gp.content_card.url_entry.insert(0, "https://example.com/not-saved")
    gp.generate_qr()
    check("nothing saved while history is off", h.count() == count)
    sp.scan_image(QRGenerator().generate("https://example.com/not-saved-scan"))
    check("scans are not saved either", h.count() == count)
    app.show_history_page()
    settle()
    check("the page tells it is off", "switched off" in hp.notice.cget("text"))
    check("old entries are still listed", len(hp._rows) > 0)

    dlg = SettingsDialog(app.header)
    settle()
    dlg.history_var.set(True)
    dlg.wifi_var.set(True)
    dlg.apply()
    settle()
    check("Apply switches history and WiFi passwords on", h.enabled() and h.save_wifi_passwords())
    gp.clear_form()
    gp.content_card.set_type("WiFi")
    wifi = gp.content_card.forms["WiFi"]
    wifi.ssid.set("Kept Net")
    wifi.password.set(PASSWORD)
    gp.generate_qr()
    kept = h.entries()[0]
    check("with the switch on the WiFi password is saved", PASSWORD in kept["text"] and h.thumbnail_path(kept))
    dlg = SettingsDialog(app.header)
    dlg.wifi_var.set(False)
    dlg.cancel()
    settle()
    check("Cancel changes nothing", h.save_wifi_passwords() is True)

    dlg = SettingsDialog(app.header)
    settle()
    answers["yes"] = False
    count = h.count()
    dlg._clear_history()
    check("declining Clear history keeps everything", h.count() == count)
    answers["yes"] = True
    dlg._clear_history()
    settle()
    check("Clear history empties the list", h.count() == 0 and h.entries() == [])
    check("... and every picture, the folder included", h.stored_files() == [], str(h.stored_files()))
    check("... and the page", len(hp._rows) == 0 and "No history yet" in hp.empty_label.cget("text"))
    check("the dialog shows it", "No saved codes" in dlg.history_count.cget("text")
          and str(dlg.clear_button.cget("state")) == "disabled")
    dlg.cancel()
    h.set_save_wifi_passwords(False)

    # ---- paging ----
    for index in range(95):
        h.add_scanned(f"https://example.com/p/{index}", "URL / Text")
    hp.refresh()
    settle()
    check("first page of 40 rows", len(hp._rows) == 40, str(len(hp._rows)))
    check("'Show more' offered", bool(hp.more_button.winfo_manager()), hp.more_button.cget("text"))
    hp._show_more()
    check("next page adds 40", len(hp._rows) == 80)
    hp._show_more()
    check("everything shown at last", len(hp._rows) == 95 and not hp.more_button.winfo_manager())

    # ---- a damaged file never breaks the page ----
    with open(h._list_path(), "w", encoding="utf-8") as fh:
        fh.write("{{{ damaged")
    hp.refresh()
    check("damaged history file: page shows empty", len(hp._rows) == 0)
    check("damaged file set aside", os.path.exists(h._list_path() + ".damaged"))
    h.clear()

    # ---- layout at the smallest window ----
    h.add_scanned("https://example.com/layout", "URL / Text", QRGenerator().generate("https://example.com/layout"))
    hp.refresh()
    hp.select(h.entries()[0]["id"])
    for width, height in ((WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT), (1280, 820)):
        root.geometry(f"{width}x{height}+-30000+-30000")
        settle()
        bottom = root.winfo_rooty() + root.winfo_height()
        for button in (hp.open_btn, hp.copy_btn, hp.regen_btn, hp.delete_btn):
            check(f"{button.cget('text')} visible at {width}x{height}",
                  button.winfo_ismapped() and button.winfo_rooty() + button.winfo_height() <= bottom)
        check(f"title and cards share an edge at {width}x{height}",
              abs(app.header._title_label.winfo_rootx() - hp.left.winfo_rootx()) <= 3,
              f"{app.header._title_label.winfo_rootx()} vs {hp.left.winfo_rootx()}")

    app.close()


def decode(path):
    from PIL import Image
    from utils.qr_scanner import QRScanner
    image = Image.open(path).convert("RGB")
    image = image.resize((image.width * 4, image.height * 4), Image.Resampling.LANCZOS)
    return QRScanner.decode_image(image, thorough=True)


if __name__ == "__main__":
    main()
    if problems:
        print("HISTORY_UI_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("HISTORY_UI_OK: save from Generate and Scan, page, Open / Re-generate / Copy / Delete, Settings, paging")
