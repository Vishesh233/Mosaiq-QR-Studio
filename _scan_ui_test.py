"""Scan page layout and behaviour of the redesigned widgets.

Covers: source tiles are wired to their actions, the drop zone opens the file dialog and
turns solid once an image is shown, the camera tile shows the active source, the result
card keeps its buttons visible at the smallest window for every kind of result (including
a very long text), secrets are masked until clicked, and an empty / error state is soft.

Run:  .venv\\Scripts\\python.exe _scan_ui_test.py
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


def main():
    from tkinter import filedialog

    from config import WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
    from ui.app import QRCodeStudioApp
    from utils import qr_payloads
    from utils.qr_generator import QRGenerator

    appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = appdata

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()

    def settle():
        for _ in range(4):
            root.update()

    app.show_scan_page()
    sp = app.scan_page
    uc, rc = sp.upload_card, sp.result_card
    settle()

    # ---- the right column is not inside the scrolling area ----
    check("result card is outside the scrolling column",
          not str(rc).startswith(str(sp.left)))

    # ---- source tiles run the right action ----
    calls = []
    sp.paste_from_clipboard = lambda: calls.append("paste")
    sp.scan_screen_region = lambda: calls.append("region")
    sp.start_camera = lambda: calls.append("camera")
    # (the page wired the real methods at start-up; re-wire the tiles to the stand-ins)
    uc.paste_button.configure(command=sp.paste_from_clipboard)
    uc.region_button.configure(command=sp.scan_screen_region)
    uc.camera_button.configure(command=sp.start_camera)
    for tile in (uc.paste_button, uc.region_button, uc.camera_button):
        tile.invoke()
    check("tiles call paste / region / camera", calls == ["paste", "region", "camera"], repr(calls))

    # ---- drop zone click opens the dialog and loads the picked file ----
    path = os.path.join(appdata, "sample.png")
    QRGenerator().generate("https://example.com/scan-ui").save(path)
    original = filedialog.askopenfilename
    asked = []
    filedialog.askopenfilename = lambda **kw: (asked.append(kw), path)[1]
    try:
        uc.upload_frame.canvas.event_generate("<Button-1>", x=20, y=20)
        settle()
    finally:
        filedialog.askopenfilename = original
    check("clicking the drop zone opens the file dialog", len(asked) == 1, repr(asked))
    check("picked image is scanned", rc.result == "https://example.com/scan-ui", repr(rc.result))
    check("zone shows the file name", uc.title_label.cget("text") == "sample.png",
          uc.title_label.cget("text"))
    check("zone is solid with an image", uc.upload_frame._solid is True)
    zone = uc.upload_frame
    inner = zone.inner
    check("picture, name and button stay inside the zone's outline (do not cover it)",
          inner.winfo_rooty() > zone.winfo_rooty() + 3
          and inner.winfo_rooty() + inner.winfo_height() < zone.winfo_rooty() + zone.winfo_height() - 3,
          f"content {inner.winfo_rooty()}..{inner.winfo_rooty() + inner.winfo_height()}, "
          f"zone {zone.winfo_rooty()}..{zone.winfo_rooty() + zone.winfo_height()}")
    uc.clear()
    rc.clear()
    check("zone is dashed again after Clear", uc.upload_frame._solid is False)

    # ---- camera tile marks the active source ----
    uc.show_camera_view("Starting...")
    settle()
    check("camera tile selected while the camera view is open",
          uc.camera_button._selected and not uc.image_button._selected)
    uc.hide_camera_view()
    settle()
    check("image tile selected again", uc.image_button._selected and not uc.camera_button._selected)

    # ---- the first scan after a cold start can take seconds (OpenCV loads): "Reading" is on screen first ----
    from utils.qr_scanner import QRScanner
    seen = {}
    real_decode = QRScanner.decode_image

    def spying_decode(image):
        seen["chip"], seen["label"] = rc.status_chip.cget("text"), rc.result_label.cget("text")
        return real_decode(image)

    QRScanner.decode_image = staticmethod(spying_decode)
    try:
        sp.scan_image(QRGenerator().generate("https://example.com/reading"))
    finally:
        QRScanner.decode_image = staticmethod(real_decode)
    check("'Reading the code…' is shown while the picture is decoded",
          seen.get("chip") == "Reading" and "Reading" in (seen.get("label") or ""), str(seen))
    check("... and the result replaces it", rc.result == "https://example.com/reading"
          and rc.status_chip.cget("text") != "Reading", rc.status_chip.cget("text"))

    # ---- empty and error states ----
    rc.clear()
    check("empty state text", "Nothing yet" in rc.result_label.cget("text"),
          rc.result_label.cget("text"))
    check("empty: copy disabled", str(rc.copy_btn.cget("state")) == "disabled")
    rc.set_message("No QR code found in this image.")
    check("error state keeps the reason", "No QR code found" in rc.result_label.cget("text"))
    check("error chip", rc.status_chip.cget("text") == "Nothing decoded")
    check("error border is the danger colour",
          rc.result_box.cget("border_color").upper() ==
          __import__("utils.theme_manager", fromlist=["ThemeManager"]).ThemeManager
          .get_theme()["danger"].upper())

    # ---- a "Copied" flash must not put an old label back on a newer result ----
    import time as _time
    rc.set_result(qr_payloads.build_upi("shop@okaxis", "Corner Shop", "10", ""))
    settle()
    rc._press(0)                                   # copies and flashes "Copied" for 1.2 s
    check("button flashes Copied", "Copied" in rc.copy_btn.cget("text"), rc.copy_btn.cget("text"))
    rc.set_result("+919876543210")                 # another result arrives within the flash
    wanted = rc.copy_btn.cget("text")
    end = _time.time() + 1.6
    while _time.time() < end:
        root.update()
        _time.sleep(0.02)
    check("the new result keeps its own button label", rc.copy_btn.cget("text") == wanted
          and "UPI" not in rc.copy_btn.cget("text"), f"{wanted!r} -> {rc.copy_btn.cget('text')!r}")
    rc.clear()

    # ---- secrets are masked until clicked ----
    secret = "hunter2-pass"
    rc.set_result(qr_payloads.build_wifi("Guest Net", secret, "WPA"))
    settle()
    check("title shows the network", "Guest Net" in rc.result_label.cget("text"))
    check("password hidden in the fields", secret not in rc.shown_text(), rc.shown_text())
    check("password row exists", any(lbl.cget("text") == "Password" for lbl, _ in rc.field_rows))
    value = next(v for lbl, v in rc.field_rows if lbl.cget("text") == "Password")
    value._label.event_generate("<Button-1>", x=2, y=2)
    settle()
    check("click reveals the password", value.cget("text") == secret, value.cget("text"))
    value._label.event_generate("<Button-1>", x=2, y=2)
    settle()
    check("click hides it again", secret not in value.cget("text"))
    check("primary button copies the password",
          "Copy password" in rc.copy_btn.cget("text"), rc.copy_btn.cget("text"))

    # ---- every kind of result keeps its buttons visible at the smallest window ----
    long_text = "word " * 400
    samples = {
        "empty": None,
        "long text": long_text.strip(),
        "long url": "https://example.com/" + "a" * 300,
        "upi": qr_payloads.build_upi("shop@okaxis", "Corner Shop", "99.50", "Order #7"),
        "contact": qr_payloads.build_vcard("Asha Verma", "+91 98765 43210", "asha@example.com", "Mosaiq"),
        "email": qr_payloads.build_email("hi@example.com", "Hello", "Body text " * 30),
        "sms": qr_payloads.build_sms("+919876543210", "On my way " * 20),
        "wifi": qr_payloads.build_wifi("MyNetwork", "secret-pass1", "WPA"),
    }
    for width, height in ((WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT), (1280, 820), (1920, 1080)):
        root.geometry(f"{width}x{height}+-30000+-30000")
        for name, text in samples.items():
            if text is None:
                rc.clear()
            else:
                rc.set_result(text)
            settle()
            window_bottom = root.winfo_rooty() + root.winfo_height()
            card_bottom = rc.winfo_rooty() + rc.winfo_height()
            for button in (rc.copy_btn, rc.action_btn):
                if button.winfo_manager():
                    bottom = button.winfo_rooty() + button.winfo_height()
                    check(f"{name} @{width}x{height}: {button.cget('text')!r} inside card and window",
                          button.winfo_ismapped() and bottom <= card_bottom and bottom <= window_bottom,
                          f"bottom {bottom}, card {card_bottom}, window {window_bottom}")
            check(f"{name} @{width}x{height}: content does not cover the buttons",
                  rc.scroll._parent_frame.winfo_rooty() + rc.scroll._parent_frame.winfo_height() <= rc.buttons.winfo_rooty() + 1)
            # the long text wraps inside the card instead of running off its edge
            label = rc.result_label
            check(f"{name} @{width}x{height}: text stays inside the card",
                  label.winfo_rootx() + label.winfo_width() <= rc.winfo_rootx() + rc.winfo_width() + 1)

    # ---- upload card and result card sit on the page's grid: same top ----
    check("both cards start at the same height",
          abs(uc.winfo_rooty() - rc.winfo_rooty()) <= 2, f"{uc.winfo_rooty()} vs {rc.winfo_rooty()}")

    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("SCAN_UI_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("SCAN_UI_OK: tiles, drop zone, camera tile, states, masked secrets, buttons visible at all sizes")
