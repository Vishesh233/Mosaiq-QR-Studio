"""Headless UI smoke test for QR Code Studio v2.

Builds the real application widget tree (no interactive display needed),
switches pages, exercises the generate workflow, and verifies core state.
Run:  .venv\\Scripts\\python.exe _smoke_test.py
Exit code 0 = UI constructed and core flows ran without exceptions.
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")


def main():
    # Import AFTER cwd is the repo root so package imports resolve.
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    root = app.root
    root.withdraw()
    root.update_idletasks()

    problems = []

    # --- Navigation: both destinations must open without error ---
    app.show_scan_page()
    root.update_idletasks()
    if not app.scan_page.winfo_ismapped():
        problems.append("scan_page not mapped after show_scan_page()")

    app.show_generate_page()
    root.update_idletasks()
    if not app.generate_page.winfo_ismapped():
        problems.append("generate_page not mapped after show_generate_page()")

    # --- Generate workflow: real QRGenerator path ---
    gp = app.generate_page
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, "https://example.com/smoke")
    gp.generate_qr()
    root.update_idletasks()

    if gp.generated_image is None:
        problems.append("generate_qr() did not produce an image")
    if str(gp.action_buttons.copy_btn.cget("state")) != "normal":
        problems.append("copy button not enabled after generate")

    # --- Scan workflow: decode the just-generated image via a temp file ---
    import tempfile
    from utils.qr_scanner import QRScanner
    from utils.qr_generator import QRGenerator

    tmp = os.path.join(tempfile.gettempdir(), "_smoke_qr.png")
    gp.generated_image.save(tmp)
    decoded = QRScanner.decode(tmp)
    if decoded != "https://example.com/smoke":
        problems.append(f"roundtrip decode mismatch: {decoded!r}")
    os.remove(tmp)

    # --- Every QR type through the real form widgets: fill, generate, scan, parse ---
    from utils import qr_payloads
    cc = gp.content_card

    def fill(field, value):
        w = field.widget
        if field.multiline:
            w.clear()
            w.insert("1.0", value)
        else:
            w.delete(0, "end")
            w.insert(0, value)

    def type_case(name, setup, kind, expect_title):
        cc.clear()
        cc.set_type(name)
        setup(cc.forms[name])
        gp.generated_image = None
        gp.generate_qr()
        root.update_idletasks()
        if gp.generated_image is None:
            problems.append(f"{name}: generate_qr() produced no image")
            return
        text = QRScanner.decode_image(gp.generated_image)
        parsed = qr_payloads.parse(text or "")
        if parsed.kind != kind or parsed.title != expect_title:
            problems.append(f"{name}: scanned as {parsed.kind!r} {parsed.title!r}")

    def setup_upi(f):
        fill(f.upi_id, "shop@okaxis"); fill(f.payee, "Corner Shop")
        fill(f.amount, "99.50"); fill(f.note, "Order #12")

    def setup_wifi(f):
        fill(f.ssid, "Home;Net"); fill(f.password, "pa:ss;word1")
        f.security.set("WPA"); f.hidden.select()

    def setup_contact(f):
        fill(f.name, "Asha Verma"); fill(f.phone, "+91 98765 43210")
        fill(f.email, "asha@example.com"); fill(f.organisation, "Mosaiq")

    def setup_email(f):
        fill(f.to, "hi@example.com"); fill(f.subject, "Hello"); fill(f.body, "Line 1" + chr(10) + "Line 2")

    def setup_sms(f):
        fill(f.number, "+919876543210"); fill(f.message, "On my way")

    type_case("URL / Text", lambda f: fill(f.entry_field, "https://example.com/t"),
              "url", "URL detected")
    type_case("UPI Payment", setup_upi, "upi", "UPI payment: Corner Shop")
    type_case("WiFi", setup_wifi, "wifi", "WiFi: Home;Net")
    type_case("Contact", setup_contact, "contact", "Contact: Asha Verma")
    type_case("Email", setup_email, "email", "Email: hi@example.com")
    type_case("SMS", setup_sms, "sms", "SMS: +919876543210")

    # Invalid form input must be refused, not produce a QR code.
    from tkinter import messagebox
    shown = []
    original_warning = messagebox.showwarning
    messagebox.showwarning = lambda title, msg: shown.append(msg)
    try:
        cc.clear()
        cc.set_type("UPI Payment")
        fill(cc.forms["UPI Payment"].upi_id, "not-a-vpa")
        fill(cc.forms["UPI Payment"].payee, "X")
        gp.generated_image = None
        gp.generate_qr()
    finally:
        messagebox.showwarning = original_warning
    if gp.generated_image is not None or not shown:
        problems.append("invalid UPI ID was not rejected with a warning")
    cc.clear()

    # --- Scan result card: readable smart results, safe actions, error state ---
    import webbrowser
    app.show_scan_page()
    root.update_idletasks()
    rc = app.scan_page.result_card
    opened = []
    original_open = webbrowser.open
    webbrowser.open = lambda url, *a, **k: opened.append(url)
    try:
        upi = qr_payloads.build_upi("shop@okaxis", "Corner Shop", "99.50", "Order")
        rc.set_result(upi)
        root.update_idletasks()
        label = rc.result_label.cget("text")
        if "Corner Shop" not in label or "shop@okaxis" not in label or "INR 99.50" not in label:
            problems.append(f"UPI result not readable: {label!r}")
        if rc.action != ("Copy UPI ID", "shop@okaxis"):
            problems.append(f"UPI action wrong: {rc.action!r}")
        rc.open_result()
        rc.result_label.event_generate("<Button-1>")
        root.update_idletasks()
        if opened:
            problems.append(f"UPI result tried to open something: {opened!r}")
        rc.on_copy_action()
        if rc.clipboard_get() != "shop@okaxis":
            problems.append("Copy UPI ID did not copy the UPI ID")
        rc.on_copy()
        if rc.clipboard_get() != upi:
            problems.append("Copy Raw Text did not copy the raw payload")

        rc.set_result(qr_payloads.build_wifi("MyNetwork", "secret-pass1", "WPA"))
        if "WiFi: MyNetwork" not in rc.result_label.cget("text") or rc.action != ("Copy password", "secret-pass1"):
            problems.append("WiFi result not shown as expected")

        rc.set_result("www.example.com")
        rc.open_result()
        if opened != ["https://www.example.com"]:
            problems.append(f"www link did not open as https: {opened!r}")

        rc.set_result("hello world")
        if rc.action is not None or rc.tips_frame.winfo_manager() == "":
            problems.append("plain text should have no action and show tips")

        rc.set_message("No QR code found")
        if str(rc.copy_btn.cget("state")) != "disabled" or rc.action is not None:
            problems.append("error state should disable copy buttons")
        rc.set_result("")
        if rc.result != "":
            problems.append("empty result did not clear")
    finally:
        webbrowser.open = original_open
    app.show_generate_page()
    root.update_idletasks()

    # --- Clipboard scan: real Windows clipboard, every case ---
    import subprocess
    import win32clipboard
    from utils.clipboard import ClipboardManager

    def set_clipboard_text(text):
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def empty_clipboard():
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()

    app.show_scan_page()
    root.update_idletasks()
    sp = app.scan_page
    rc = sp.result_card
    wifi_text = qr_payloads.build_wifi("PasteNet", "paste-pass-1", "WPA")
    ClipboardManager.copy_image(QRGenerator().generate(wifi_text))
    sp.paste_from_clipboard()
    if rc.result != wifi_text or not sp.upload_card.has_content:
        problems.append("clipboard image was not scanned into the result panel")

    # Synthetic key events and the shared Windows clipboard depend on what else
    # is running on the desktop, so allow a few attempts before calling it a failure.
    for attempt in range(3):
        rc.clear()
        ClipboardManager.copy_image(QRGenerator().generate("https://example.com/ctrl-v"))
        root.focus_force(); root.update()
        root.event_generate("<Control-v>")
        root.update()
        if rc.result == "https://example.com/ctrl-v":
            break
    else:
        problems.append(
            "Ctrl+V on the scan page did not paste the clipboard image "
            f"(3 attempts; panel says {rc.result_label.cget('text')!r})"
        )

    app.show_generate_page()
    root.update_idletasks()
    rc.clear()
    root.event_generate("<Control-v>")
    root.update()
    if rc.result:
        problems.append("Ctrl+V scanned while the Generate page was showing")
    app.show_scan_page()
    root.update_idletasks()

    empty_clipboard()
    sp.paste_from_clipboard()
    if rc.result or rc.status_chip.cget("text") != "Nothing decoded":
        problems.append("empty clipboard did not show the 'no image' message")
    if "no image" not in rc.result_label.cget("text").lower():
        problems.append(f"empty clipboard message: {rc.result_label.cget('text')!r}")

    set_clipboard_text("just text on the clipboard")
    sp.paste_from_clipboard()
    if rc.result or "no image" not in rc.result_label.cget("text").lower():
        problems.append("text-only clipboard was not rejected clearly")

    blank = os.path.join(tempfile.gettempdir(), "_smoke_blank.png")
    from PIL import Image as _Image
    _Image.new("RGB", (200, 200), "white").save(blank)
    qr_file = os.path.join(tempfile.gettempdir(), "_smoke_clip_file.png")
    QRGenerator().generate("https://example.com/from-file").save(qr_file)
    notimg = os.path.join(tempfile.gettempdir(), "_smoke_notes.txt")
    open(notimg, "w").write("x")
    for path, check_fn, label in (
        (qr_file, lambda: rc.result == "https://example.com/from-file", "copied QR file"),
        (blank, lambda: not rc.result and rc.status_chip.cget("text") == "Nothing decoded", "copied blank image file"),
        (notimg, lambda: not rc.result and "none of them is an image" in rc.result_label.cget("text"), "copied non-image file"),
    ):
        rc.clear()
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Set-Clipboard -Path '" + path + "'"], check=True)
        sp.paste_from_clipboard()
        if not check_fn():
            problems.append(f"{label} on the clipboard handled wrongly: {rc.result_label.cget('text')!r}")
    for f in (blank, qr_file, notimg):
        os.remove(f)
    empty_clipboard()
    rc.clear()
    app.show_generate_page()
    root.update_idletasks()

    # --- Settings dialog opens and closes cleanly ---
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(app.header)
    root.update_idletasks()
    dlg.destroy()
    root.update_idletasks()

    # --- Settings APPLY actually re-themes the app shell (regression guard) ---
    from utils.theme_manager import ThemeManager
    original_theme = ThemeManager.get_current_theme()
    other = next(t for t in ThemeManager.get_theme_names() if t != original_theme)
    ThemeManager.set_theme(original_theme)
    app.refresh_theme()
    root.update_idletasks()
    bg_before = app.root.cget("fg_color")

    dlg2 = SettingsDialog(app.header)
    dlg2.preview_theme(other)        # live preview re-themes the app
    dlg2.apply()                     # saves the choice + closes the dialog
    root.update_idletasks()
    bg_after = app.root.cget("fg_color")
    if bg_before == bg_after:
        problems.append(
            f"Settings Apply did not change app background ({other})"
        )
    # restore
    ThemeManager.set_theme(original_theme)
    app.refresh_theme()
    root.update_idletasks()

    # --- Theme switching: apply every theme and refresh the whole shell ---
    try:
        for name in ThemeManager.get_theme_names():
            ThemeManager.set_theme(name)
            app.refresh_theme()          # must not raise on any theme
            root.update_idletasks()
    finally:
        ThemeManager.set_theme(original_theme)
        app.refresh_theme()
        root.update_idletasks()

    root.destroy()

    if problems:
        print("SMOKE_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)

    print("SMOKE_OK: nav, generate, all 6 QR types, decode-roundtrip, settings dialog all ran")


if __name__ == "__main__":
    main()
