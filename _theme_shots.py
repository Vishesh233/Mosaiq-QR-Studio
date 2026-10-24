"""App-window screenshots of every theme (Generate, Scan, History, Bulk Create, Settings, colour picker).

Only the app's own window is captured (PrintWindow, see _window_capture.py), never the
screen. Each theme runs in its own process with a throw-away APPDATA, so the saved
settings of the real user are never read or changed.

Run:  .venv\\Scripts\\python.exe _theme_shots.py <output folder>
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"

SAMPLE_URL = "https://example.com/mosaiq"


def _one(theme, outdir):
    import win32gui

    from _window_capture import capture_window
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1440x900+40+20")
    root.update()
    root.deiconify()
    root.update()
    hwnd = win32gui.GetParent(root.winfo_id())

    def shot(name):
        for _ in range(8):
            root.update()
        capture_window(hwnd).save(os.path.join(outdir, f"{theme}-{name}.png"))

    gp = app.generate_page
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, SAMPLE_URL)
    gp.generate_qr()
    end = time.time() + 2.0                     # let the test scan finish: the badge is part of the picture
    while time.time() < end:
        root.update()
        time.sleep(0.02)
    shot("generate")

    app.show_scan_page()
    shot("scan")

    # History and Bulk Create with sample data only (throw-away APPDATA).
    from utils import bulk_csv, history_store
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle

    gen = QRGenerator()
    for text, kind in (("https://example.com/menu", "URL / Text"),
                       ("upi://pay?pa=sample@examplebank&pn=Mosaiq%20Cafe&am=249.00", "UPI Payment"),
                       ("mailto:hello@example.com", "Email")):
        history_store.add_scanned(text, kind, gen.generate(text))
    look = QRStyle(module_shape="rounded", eye_shape="rounded", gradient="linear",
                   fg="#0E7490", fg2="#1E3A8A")
    history_store.add_generated("URL / Text", "https://example.com/launch",
                                {"url": "https://example.com/launch"}, look, None,
                                gen.generate("https://example.com/launch", style=look))
    history_store.add_generated("WiFi", "WIFI:T:WPA;S:Mosaiq Guest;P:sample-pass-123;;",
                                {"ssid": "Mosaiq Guest", "password": "sample-pass-123"}, QRStyle())
    app.show_history_page()
    app.history_page.select(history_store.entries()[1]["id"])
    shot("history")

    sample = os.path.join(tempfile.mkdtemp(), "mosaiq-bulk-sample.csv")
    with open(sample, "w", encoding="utf-8", newline="") as fh:
        fh.write(bulk_csv.SAMPLE_CSV)
    app.show_bulk_page()
    app.bulk_page.load_csv(sample)
    # the folder box shows the real default (Documents\QR codes), as a user sees it
    app.bulk_page._update_summary()
    shot("bulk")
    app.show_generate_page()

    # The Settings page (part of the main window, so still window-only).
    app.show_settings_page()
    end = time.time() + 1.0
    while time.time() < end:
        root.update()
        time.sleep(0.02)
    shot("settings")
    app.settings_page.cancel()

    # Colour picker, with a few recent colours so that row is visible.
    from ui.dialogs.color_picker import ColorPickerDialog
    from utils import colors

    for color in ("#7C2D12", "#0E7490", "#1E3A8A", "#15803D"):
        colors.remember(color)
    picker = ColorPickerDialog(app.header, "#0E7490", "QR colour")
    picker.geometry("+120+60")
    end = time.time() + 1.0
    while time.time() < end:
        root.update()
        time.sleep(0.02)
    capture_window(win32gui.GetAncestor(picker.winfo_id(), 2)).save(
        os.path.join(outdir, f"{theme}-picker.png"))
    picker.cancel()
    app.close()


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        _one(sys.argv[2], sys.argv[3])
        return

    outdir = os.path.abspath(sys.argv[1])
    os.makedirs(outdir, exist_ok=True)
    from utils.theme_manager import ThemeManager

    for theme in ThemeManager.get_theme_names():
        with tempfile.TemporaryDirectory() as appdata:
            folder = os.path.join(appdata, "QR Code Studio")
            os.makedirs(folder)
            with open(os.path.join(folder, "settings.json"), "w", encoding="utf-8") as fh:
                json.dump({"theme": theme, "splash_enabled": False}, fh)
            env = dict(os.environ, APPDATA=appdata)
            subprocess.run([sys.executable, os.path.abspath(__file__), "--one", theme, outdir],
                           env=env, check=True, timeout=120)
        print("shot", theme)


if __name__ == "__main__":
    main()
