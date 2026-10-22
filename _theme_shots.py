"""App-window screenshots of every theme (Generate and Scan pages).

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
    shot("generate")

    app.show_scan_page()
    shot("scan")
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
