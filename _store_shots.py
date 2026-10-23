"""Store screenshots (1920 x 1140, app window only, sample data only).

Only the app's own windows are captured (PrintWindow, see _window_capture.py), never the
screen. Each picture runs in its own process with a throw-away APPDATA, so the real user's
settings and history are never read or changed.

Run:  .venv\\Scripts\\python.exe _store_shots.py <output folder>
Writes generate.png, style.png, scan.png, history.png, bulk.png, theme_settings.png and
light_mode.png.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"

WIDTH, HEIGHT = 1920, 1140
SHOTS = {
    "generate": "Aqua Mint", "style": "Aqua Mint", "scan": "Aqua Mint", "history": "Aqua Mint",
    "bulk": "Aqua Mint", "theme_settings": "Aqua Mint", "light_mode": "Daylight",
}


def _settle(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def _fill_upi(gp):
    gp.content_card.set_type("UPI Payment")
    form = gp.content_card.forms["UPI Payment"]
    form.fill({"upi_id": "sample@examplebank", "payee": "Mosaiq Cafe",
               "amount": "249.00", "note": "Order #1024"})


def _one(name, outdir):
    import win32gui

    from _window_capture import capture_window
    from ui.app import QRCodeStudioApp
    from utils import bulk_csv, history_store, qr_payloads
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1440x900+0+0")
    root.update()
    root.deiconify()
    root.update()
    hwnd = win32gui.GetParent(root.winfo_id())
    left, top, _r, _b = win32gui.GetWindowRect(hwnd)
    win32gui.MoveWindow(hwnd, left, top, WIDTH, HEIGHT, True)    # exact outer size in pixels
    _settle(root, 0.6)

    gp, sp = app.generate_page, app.scan_page
    gen = QRGenerator()
    look = QRStyle(module_shape="dots", eye_shape="rounded", gradient="linear",
                   fg="#0E7490", fg2="#1E3A8A")

    def save(image=None):
        _settle(root, 0.5)
        (image or capture_window(hwnd)).save(os.path.join(outdir, f"{name}.png"))

    def design_and_generate(tab):
        _fill_upi(gp)
        gp.design_card.apply_preset("Ocean")
        gp.design_card.style.set_style(module_shape="dots", eye_shape="rounded")
        gp.design_card.show_tab(tab)
        gp.generate_qr()
        _settle(root, 2.0)                       # the test scan badge is part of the picture

    def sample_history():
        for text, kind in (("https://example.com/menu", "URL / Text"),
                           (qr_payloads.build_upi("sample@examplebank", "Mosaiq Cafe", "249.00", "Order 1024"),
                            "UPI Payment"),
                           ("mailto:hello@example.com", "Email")):
            history_store.add_scanned(text, kind, gen.generate(text))
        history_store.add_generated("URL / Text", "https://example.com/launch",
                                    {"url": "https://example.com/launch"}, look, None,
                                    gen.generate("https://example.com/launch", style=look))
        history_store.add_generated("WiFi", "WIFI:T:WPA;S:Mosaiq Guest;P:sample-pass-123;;",
                                    {"ssid": "Mosaiq Guest", "password": "sample-pass-123"}, QRStyle())
        history_store.add_generated("UPI Payment",
                                    qr_payloads.build_upi("sample@examplebank", "Mosaiq Cafe", "249.00", "Order 1024"),
                                    {"upi_id": "sample@examplebank", "payee": "Mosaiq Cafe"}, look, None,
                                    gen.generate(qr_payloads.build_upi("sample@examplebank", "Mosaiq Cafe",
                                                                       "249.00", "Order 1024"), style=look))

    def scan_sample(text):
        path = os.path.join(tempfile.mkdtemp(), "qr.png")
        gen.generate(text).save(path)
        app.show_scan_page()
        sp.upload_card.load_path(path)
        _settle(root, 1.0)

    if name == "generate":
        design_and_generate("Colours")
        save()
    elif name == "style":
        design_and_generate("Style")
        save()
    elif name == "scan":
        scan_sample(qr_payloads.build_wifi("Mosaiq Guest", "sample-pass-123", "WPA"))
        save()
    elif name == "light_mode":
        scan_sample(qr_payloads.build_upi("sample@examplebank", "Mosaiq Cafe", "249.00", "Order 1024"))
        save()
    elif name == "history":
        sample_history()
        app.show_history_page()
        app.history_page.select(history_store.entries()[0]["id"])
        save()
    elif name == "bulk":
        sample = os.path.join(tempfile.mkdtemp(), "mosaiq-bulk-sample.csv")
        with open(sample, "w", encoding="utf-8", newline="") as fh:
            fh.write(bulk_csv.SAMPLE_CSV)
        gp.design_card.apply_preset("Ocean")
        app.show_bulk_page()
        app.bulk_page.load_csv(sample)
        app.bulk_page.folder_entry.insert(0, r"C:\Users\you\Documents\QR codes")
        app.bulk_page._update_summary()
        save()
    elif name == "theme_settings":
        from PIL import Image, ImageEnhance

        from ui.dialogs.settings_dialog import SettingsDialog
        design_and_generate("Colours")
        backdrop = ImageEnhance.Brightness(capture_window(hwnd)).enhance(0.45)
        dlg = SettingsDialog(app.header)
        dlg.geometry("+300+40")
        _settle(root, 1.2)
        dialog = capture_window(win32gui.GetAncestor(dlg.winfo_id(), 2))
        canvas = backdrop.copy()
        canvas.paste(dialog, ((WIDTH - dialog.width) // 2, max(0, (HEIGHT - dialog.height) // 2)))
        save(canvas)
        dlg.destroy()
    app.close()


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        _one(sys.argv[2], sys.argv[3])
        return

    outdir = os.path.abspath(sys.argv[1])
    os.makedirs(outdir, exist_ok=True)
    for name, theme in SHOTS.items():
        with tempfile.TemporaryDirectory() as appdata:
            folder = os.path.join(appdata, "QR Code Studio")
            os.makedirs(folder)
            with open(os.path.join(folder, "settings.json"), "w", encoding="utf-8") as fh:
                json.dump({"theme": theme, "splash_enabled": False}, fh)
            env = dict(os.environ, APPDATA=appdata)
            subprocess.run([sys.executable, os.path.abspath(__file__), "--one", name, outdir],
                           env=env, check=True, timeout=180)
        print("shot", name)


if __name__ == "__main__":
    main()
