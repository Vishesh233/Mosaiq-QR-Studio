"""App-window screenshots of the Settings dialog (footer visible) and the Generate page (bright
status dot with its glow) in two themes. Only the app's own windows are captured (PrintWindow),
never the screen; a throw-away APPDATA is used.

Run:  .venv\\Scripts\\python.exe _settings_dot_shots.py <output folder> [theme theme ...]
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"

THEMES = ("Aqua Mint", "Emerald")


def _one(theme, outdir):
    import win32gui

    from _window_capture import capture_window
    from ui.app import QRCodeStudioApp
    from ui.dialogs.settings_dialog import SettingsDialog

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1440x900+40+20")
    root.update()
    root.deiconify()
    hwnd = win32gui.GetParent(root.winfo_id())

    def settle(seconds):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.02)

    settle(1.0)
    gp = app.generate_page
    gp.content_card.set_type("UPI Payment")
    gp.content_card.forms["UPI Payment"].fill({"upi_id": "sample@examplebank", "payee": "Mosaiq Cafe",
                                               "amount": "249.00", "note": "Order #1024"})
    gp.generate_qr()
    settle(2.0)                                   # fade finished, test scan done
    capture_window(hwnd).save(os.path.join(outdir, f"{theme}-generate-bright-dot.png"))

    dlg = SettingsDialog(app.header)
    dlg.geometry("+120+40")
    settle(1.2)
    capture_window(win32gui.GetAncestor(dlg.winfo_id(), 2)).save(
        os.path.join(outdir, f"{theme}-settings-footer.png"))
    dlg.cancel()
    app.close()


def main():
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        _one(sys.argv[2], sys.argv[3])
        return
    outdir = os.path.abspath(sys.argv[1])
    os.makedirs(outdir, exist_ok=True)
    for theme in (sys.argv[2:] or THEMES):
        with tempfile.TemporaryDirectory() as appdata:
            folder = os.path.join(appdata, "QR Code Studio")
            os.makedirs(folder)
            with open(os.path.join(folder, "settings.json"), "w", encoding="utf-8") as fh:
                json.dump({"theme": theme, "splash_enabled": False}, fh)
            env = dict(os.environ, APPDATA=appdata)
            subprocess.run([sys.executable, os.path.abspath(__file__), "--one", theme, outdir],
                           env=env, check=True, timeout=180)
        print("shot", theme)


if __name__ == "__main__":
    main()
