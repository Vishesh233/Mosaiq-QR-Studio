"""Headless UI smoke test for QR Code Studio v2.

Builds the real application widget tree (no interactive display needed),
switches pages, exercises the generate workflow, and verifies core state.
Run:  .venv\\Scripts\\python.exe _smoke_test.py
Exit code 0 = UI constructed and core flows ran without exceptions.
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")


def _run():
    # Import AFTER cwd is the repo root so package imports resolve.
    from ui.app import QRCodeStudioApp

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    # Parked far off-screen instead of withdrawn: a withdrawn window reports every widget
    # as unmapped, and this test checks which widgets are really shown.
    root.geometry("1280x820+-30000+-30000")
    root.update()

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

    # --- Sidebar: every nav button opens its page and shows as active ---
    sb = app.sidebar
    for key, page in (("scan", app.scan_page), ("generate", app.generate_page)):
        sb._nav_buttons[key].invoke()
        root.update_idletasks()
        if sb.active_tab != key or not page.winfo_ismapped():
            problems.append(f"sidebar item {key!r} did not open its page / become active")
    if set(sb._nav_buttons) != set(sb._nav_icons) or not sb._nav_buttons:
        problems.append("sidebar nav items and icons disagree")

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
    messagebox.showwarning = lambda title, msg, *a, **k: shown.append(msg)
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

    # --- Scan result card: readable smart results, button sets, safe actions, no clipping ---
    import webbrowser
    app.show_scan_page()
    root.update_idletasks()
    rc = app.scan_page.result_card
    opened = []
    original_open = webbrowser.open
    webbrowser.open = lambda url, *a, **k: opened.append(url)

    def buttons():
        """(primary text, secondary text or None) as shown."""
        second = rc.action_btn.cget("text") if rc.action_btn.winfo_ismapped() else None
        return rc.copy_btn.cget("text"), second

    def card_fits(label):
        root.update_idletasks()
        root.update()
        card_bottom = rc.winfo_rooty() + rc.winfo_height()
        for button in (rc.copy_btn, rc.action_btn):
            if button.winfo_ismapped() and button.winfo_rooty() + button.winfo_height() > card_bottom:
                problems.append(f"{label}: a button is cut off")
        # The buttons are pinned under the scrolling content: it must never cover them.
        visible = rc.scroll._parent_frame      # (rc.scroll itself is the full-length inner frame)
        scroll_bottom = visible.winfo_rooty() + visible.winfo_height()
        if scroll_bottom > rc.buttons.winfo_rooty():
            problems.append(f"{label}: result content overlaps the buttons")

    def expect(label, text, primary, secondary, *, opens=None, primary_copies=None, secondary_copies=None):
        rc.set_result(text)
        card_fits(label)
        got = buttons()
        if primary not in got[0] or (secondary is None) != (got[1] is None) \
                or (secondary is not None and secondary not in got[1]):
            problems.append(f"{label}: buttons are {got!r}, expected {primary!r} / {secondary!r}")
            return
        if got[1] is not None and got[0] == got[1]:
            problems.append(f"{label}: both buttons say the same thing: {got!r}")
        # Press them and look at what really happens.
        del opened[:]
        rc.clipboard_clear()
        rc.copy_btn.invoke()
        root.update_idletasks()
        clip = None
        try:
            clip = rc.clipboard_get()
        except Exception:
            clip = None                      # nothing was copied
        if primary_copies is None and clip not in (None, ""):
            problems.append(f"{label}: primary should not copy but clipboard has {clip!r}")
        if primary_copies is not None and clip != primary_copies:
            problems.append(f"{label}: primary copied {clip!r}, expected {primary_copies!r}")
        if (opens is None) != (not opened) or (opens is not None and opened != [opens]):
            problems.append(f"{label}: browser opened {opened!r}, expected {opens!r}")
        if secondary is not None:
            del opened[:]
            rc.clipboard_clear()
            rc.action_btn.invoke()
            root.update_idletasks()
            try:
                clip = rc.clipboard_get()
            except Exception:
                clip = None
            if clip != secondary_copies:
                problems.append(f"{label}: secondary copied {clip!r}, expected {secondary_copies!r}")
            if opened:
                problems.append(f"{label}: copy button opened a browser: {opened!r}")
            if primary_copies is not None and primary_copies == secondary_copies:
                problems.append(f"{label}: both buttons copy the same value")

    try:
        upi = qr_payloads.build_upi("shop@okaxis", "Corner Shop", "99.50", "Order")
        expect("UPI", upi, "Copy UPI ID", "Copy raw text", primary_copies="shop@okaxis", secondary_copies=upi)
        label = rc.shown_text()
        if "Corner Shop" not in label or "shop@okaxis" not in label or "INR 99.50" not in label:
            problems.append(f"UPI result not readable: {label!r}")
        rc.result_label.event_generate("<Button-1>")
        root.update_idletasks()
        if opened:
            problems.append(f"UPI result tried to open something when clicked: {opened!r}")

        wifi = qr_payloads.build_wifi("MyNetwork", "secret-pass1", "WPA")
        expect("WiFi", wifi, "Copy password", "Copy raw text", primary_copies="secret-pass1", secondary_copies=wifi)
        if "WiFi: MyNetwork" not in rc.result_label.cget("text"):
            problems.append("WiFi result not shown as 'WiFi: MyNetwork'")
        openwifi = qr_payloads.build_wifi("CafeFree", "", "None")
        expect("WiFi open network", openwifi, "Copy raw text", None, primary_copies=openwifi)

        card = qr_payloads.build_vcard("Asha Verma", "+91 98765 43210", "asha@example.com", "Mosaiq")
        expect("Contact", card, "Copy phone", "Copy raw text", primary_copies="+919876543210", secondary_copies=card)
        nophone = qr_payloads.build_vcard("Asha Verma", "", "asha@example.com", "")
        expect("Contact without phone", nophone, "Copy raw text", None, primary_copies=nophone)

        mail = qr_payloads.build_email("hi@example.com", "Hello", "Body text")
        expect("Email", mail, "Copy address", "Copy raw text", primary_copies="hi@example.com", secondary_copies=mail)
        sms = qr_payloads.build_sms("+919876543210", "On my way")
        expect("SMS", sms, "Copy number", "Copy raw text", primary_copies="+919876543210", secondary_copies=sms)

        url = "https://example.com/a?b=c"
        expect("URL", url, "Open link", "Copy link", opens=url, secondary_copies=url)
        expect("www link", "www.example.com", "Open link", "Copy link",
               opens="https://www.example.com", secondary_copies="www.example.com")
        expect("Plain text", "hello world", "Copy Result", None, primary_copies="hello world")
        long_text = "word " * 120
        expect("Very long text", long_text.strip(), "Copy Result", None, primary_copies=long_text.strip())

        rc.set_message("No QR code found")
        card_fits("error state")
        if str(rc.copy_btn.cget("state")) != "disabled" or rc.action_btn.winfo_ismapped():
            problems.append("error state should disable the copy button and hide the second one")
        rc.set_result("")
        card_fits("empty state")
        if rc.result != "" or rc.copy_btn.cget("text").strip().split("  ")[-1] != "Copy Result":
            problems.append("empty result did not clear to the disabled generic button")
    finally:
        webbrowser.open = original_open
    app.show_generate_page()
    root.update_idletasks()

    # --- Clipboard scan: real Windows clipboard, every case ---
    import subprocess
    import win32clipboard
    from utils.clipboard import ClipboardManager

    def open_clipboard():
        # Windows clipboard history (a service, svchost) can hold the clipboard for several seconds.
        try:
            ClipboardManager._open(attempts=600, pause=0.05)      # up to 30 s
        except Exception:
            import ctypes
            import win32gui
            import win32process
            holder = ctypes.windll.user32.GetOpenClipboardWindow()
            who = ""
            if holder:
                who = (f"pid {win32process.GetWindowThreadProcessId(holder)[1]}, class "
                       f"{win32gui.GetClassName(holder)!r}, title {win32gui.GetWindowText(holder)!r}")
            print(f"[smoke] clipboard stayed locked for 30 s; open by: {who or chr(110)+chr(111)+chr(98)+chr(111)+chr(100)+chr(121)}; this test is pid {os.getpid()}")
            raise

    def wait_for_clipboard():
        """The copy buttons tested above change the clipboard many times in a second; a
        clipboard manager running on the PC can hold it for a while afterwards."""
        open_clipboard()
        win32clipboard.CloseClipboard()

    def set_clipboard_text(text):
        open_clipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def empty_clipboard():
        open_clipboard()
        try:
            win32clipboard.EmptyClipboard()
        finally:
            win32clipboard.CloseClipboard()

    app.show_scan_page()
    root.update_idletasks()
    sp = app.scan_page
    rc = sp.result_card
    wifi_text = qr_payloads.build_wifi("PasteNet", "paste-pass-1", "WPA")
    wait_for_clipboard()
    ClipboardManager.copy_image(QRGenerator().generate(wifi_text))
    sp.paste_from_clipboard()
    if rc.result != wifi_text or not sp.upload_card.has_content:
        problems.append("clipboard image was not scanned into the result panel")

    # The Ctrl+V binding is registered on the window; its handler is called directly
    # because a synthetic key event needs real keyboard focus, which a hidden test
    # window does not have.
    bound = str(root.tk.call("bind", str(root)))      # Tk spells it <Control-Key-v>
    if "<Control-Key-v>" not in bound and "<Control-v>" not in bound:
        problems.append("Ctrl+V is not bound on the main window")
    rc.clear()
    wait_for_clipboard()
    ClipboardManager.copy_image(QRGenerator().generate("https://example.com/ctrl-v"))
    sp._on_ctrl_v()
    root.update()
    if rc.result != "https://example.com/ctrl-v":
        problems.append(
            "Ctrl+V on the scan page did not paste the clipboard image "
            f"(panel says {rc.result_label.cget('text')!r})"
        )

    app.show_generate_page()
    root.update_idletasks()
    rc.clear()
    sp._on_ctrl_v()          # same handler, Scan page hidden: must do nothing
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

    # --- Release metadata: version, manifest capability, sidebar label agree ---
    import json
    import xml.etree.ElementTree as ET
    import config
    ident = json.load(open(os.path.join("packaging", "msix", "identity.json"), encoding="utf-8"))
    if ident["Version"] != "2.2.0.0" or config.APP_VERSION != "v2.2":
        problems.append(f"version mismatch: identity {ident['Version']} / config {config.APP_VERSION}")
    manifest_text = open(os.path.join("packaging", "msix", "AppxManifest.xml.in"), encoding="utf-8").read()
    for key in ("IdentityName", "Publisher", "PublisherDisplayName", "DisplayName", "Version"):
        manifest_text = manifest_text.replace("@@" + key + "@@", ident[key])
    manifest = ET.fromstring(manifest_text)
    ns = {"m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    caps = {c.get("Name") for c in manifest.findall("m:Capabilities/m:DeviceCapability", ns)}
    if caps != {"webcam"}:
        problems.append(f"manifest DeviceCapability should be exactly webcam, got {caps}")
    if manifest.find("m:Identity", ns).get("Version") != "2.2.0.0":
        problems.append("manifest identity version is not 2.2.0.0")

    # --- the Settings page opens and closes cleanly ---
    app.show_settings_page()
    root.update_idletasks()
    app.settings_page.cancel()
    root.update_idletasks()

    # --- Settings APPLY actually re-themes the app shell (regression guard) ---
    from utils.theme_manager import ThemeManager
    original_theme = ThemeManager.get_current_theme()
    other = next(t for t in ThemeManager.get_theme_names() if t != original_theme)
    ThemeManager.set_theme(original_theme)
    app.refresh_theme()
    root.update_idletasks()
    bg_before = app.root.cget("fg_color")

    app.show_settings_page()
    app.settings_page.preview_theme(other)      # live preview re-themes the app
    app.settings_page.apply_and_close()         # saves the choice + goes back
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


def main():
    """Run the checks without leaving the tester's saved settings changed."""
    from utils import settings_store

    path = settings_store._settings_path()
    try:
        with open(path, "rb") as fh:
            saved = fh.read()
    except OSError:
        saved = None

    try:
        _run()
    finally:
        if saved is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            with open(path, "wb") as fh:
                fh.write(saved)


if __name__ == "__main__":
    main()
