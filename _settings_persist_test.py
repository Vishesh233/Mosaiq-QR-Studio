"""Settings persist: Apply writes everything, Cancel and "Don't save" write nothing, X asks, a failed
write is reported, and the next launch starts with the saved theme.

Run:  .venv\\Scripts\\python.exe _settings_persist_test.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
APPDATA = tempfile.mkdtemp()
os.environ["APPDATA"] = APPDATA
LOG_DIR = tempfile.mkdtemp()
os.environ["QRSTUDIO_LOG_DIR"] = LOG_DIR

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def read_file(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def main():
    import _test_dialogs
    dialogs = _test_dialogs.install()

    from ui.app import QRCodeStudioApp
    from ui.dialogs import settings_dialog
    from ui.dialogs.settings_dialog import SettingsDialog, dialog_size
    from utils import history_store, settings_store
    from utils.theme_manager import ThemeManager

    path = settings_store._settings_path()
    check("test set-up: a throw-away settings folder", APPDATA in path, path)
    check("test set-up: no settings file yet", not os.path.exists(path))

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()

    def settle(seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def open_dialog():
        dlg = SettingsDialog(app.header)
        settle()
        return dlg

    def on_disk():
        raw = read_file(path)
        return json.loads(raw) if raw else None

    def shown_theme():
        return app.sidebar._theme_name_label.cget("text")

    # ---- a fresh install: defaults, nothing on disk ----
    from config import DEFAULT_THEME
    check("default theme at first start", ThemeManager.get_current_theme() == DEFAULT_THEME)

    # ---- Apply: live preview writes nothing; Apply writes everything in one go ----
    dlg = open_dialog()
    check("dialog opens unchanged", not dlg.has_changes())
    dlg.preview_theme("Emerald")
    settle()
    check("live preview shows the theme", shown_theme() == "Emerald" and ThemeManager.get_current_theme() == "Emerald")
    check("live preview writes nothing", not os.path.exists(path))
    check("dialog knows it has changes", dlg.has_changes())
    dlg.splash_var.set(False)
    dlg.history_var.set(False)
    dlg.wifi_var.set(True)
    check("still nothing written before Apply", not os.path.exists(path))
    check("Apply reports success", dlg.apply() is True)
    settle()
    check("dialog is closed after Apply", not dlg.winfo_exists())
    saved = on_disk() or {}
    check("settings.json holds the theme", saved.get("theme") == "Emerald", str(saved))
    check("... the intro switch", saved.get("splash_enabled") is False, str(saved))
    check("... the history switches", saved.get(history_store.KEY_ENABLED) is False
          and saved.get(history_store.KEY_WIFI_PASSWORDS) is True, str(saved))
    check("no temp file left behind", not os.path.exists(path + ".tmp"))
    check("the app keeps showing the applied theme", shown_theme() == "Emerald")

    # ---- the next launch: read the file again ----
    settings_store.reload()
    ThemeManager.load_saved()
    check("reloading the settings gives the saved theme", ThemeManager.get_current_theme() == "Emerald")
    check("reloading gives the intro switch", settings_store.get("splash_enabled", True) is False)
    code = ("import os, sys, time\n"
            "sys.path.insert(0, os.getcwd())\n"
            "from ui.app import QRCodeStudioApp\n"
            "from utils.theme_manager import ThemeManager\n"
            "app = QRCodeStudioApp(); root = app.root\n"
            "root.geometry('1100x700+-30000+-30000'); root.update(); time.sleep(0.3); root.update()\n"
            "print('LAUNCH', ThemeManager.get_current_theme(), app.sidebar._theme_name_label.cget('text'), "
            "root.cget('fg_color'), ThemeManager.get_theme()['background'])\n"
            "app.close()\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90,
                         cwd=os.path.dirname(os.path.abspath(__file__)), env=dict(os.environ))
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith("LAUNCH")), "")
    parts = line.split()
    check("a new process starts with the saved theme", parts[1:3] == ["Emerald", "Emerald"],
          f"{line!r} {out.stderr[-300:]!r}")
    check("... and its window uses that theme's colours",
          len(parts) == 5 and parts[3].upper() == parts[4].upper() == ThemeManager.THEMES["Emerald"]["background"].upper(), line)

    # ---- Cancel: back to the opening state, file untouched ----
    before = read_file(path)
    mtime = os.path.getmtime(path)
    dlg = open_dialog()
    dlg.preview_theme("Ember")
    dlg.splash_var.set(True)
    settle()
    check("Cancel test: preview is showing", shown_theme() == "Ember")
    dlg.cancel()
    settle()
    check("Cancel reverts the theme", ThemeManager.get_current_theme() == "Emerald" and shown_theme() == "Emerald")
    check("Cancel writes nothing", read_file(path) == before and os.path.getmtime(path) == mtime)
    check("Cancel closes the dialog", not dlg.winfo_exists())

    # ---- X: no changes -> closes at once, no question ----
    dialogs.clear()
    dlg = open_dialog()
    dlg.close_requested()
    settle()
    check("X without changes closes at once", not dlg.winfo_exists())
    check("... without asking", not [c for c in dialogs.calls if c[0] == "save_changes"])
    # a change that is changed back is no change
    dlg = open_dialog()
    dlg.preview_theme("Ember")
    dlg.preview_theme("Emerald")
    check("changing back leaves no changes", not dlg.has_changes())
    dlg.close_requested()
    settle()
    check("... and X closes without asking", not dlg.winfo_exists()
          and not [c for c in dialogs.calls if c[0] == "save_changes"])
    check("X without changes writes nothing", read_file(path) == before)

    # ---- X with changes: ask; Cancel stays, Don't save reverts, Save writes ----
    dialogs.clear()
    dlg = open_dialog()
    dlg.preview_theme("Ember")
    settle()
    dialogs.answers["save_changes"] = "cancel"
    dlg.close_requested()
    settle()
    check("X with changes asks 'Save changes?'", len([c for c in dialogs.calls if c[0] == "save_changes"]) == 1)
    check("[Cancel] keeps the dialog open with the preview", dlg.winfo_exists() and shown_theme() == "Ember")
    check("... and writes nothing", read_file(path) == before)
    dialogs.answers["save_changes"] = "discard"
    dlg.close_requested()
    settle()
    check("[Don't save] closes and reverts the theme", not dlg.winfo_exists()
          and ThemeManager.get_current_theme() == "Emerald" and shown_theme() == "Emerald")
    check("... and writes nothing", read_file(path) == before and os.path.getmtime(path) == mtime)

    dlg = open_dialog()
    dlg.preview_theme("Ember")
    dlg.splash_var.set(True)
    dialogs.answers["save_changes"] = "save"
    dlg.close_requested()
    settle()
    saved = on_disk() or {}
    check("[Save] writes the theme and the switches and closes", not dlg.winfo_exists()
          and saved.get("theme") == "Ember" and saved.get("splash_enabled") is True, str(saved))
    check("... the app shows it", shown_theme() == "Ember")
    dialogs.answers.pop("save_changes")

    # ---- a failed write is shown, nothing is half-written, the choices stay ----
    before = read_file(path)
    real_replace = os.replace
    dlg = open_dialog()
    dlg.preview_theme("Graphite")
    settle()

    def broken_replace(src, dst, *a, **k):
        raise PermissionError(13, "Access is denied")

    os.replace = broken_replace
    try:
        result = dlg.apply()
    finally:
        os.replace = real_replace
    errors = [c for c in dialogs.calls if c[0] == "showerror" and "save settings" in (c[1] or "").lower()]
    check("a failed write is reported to the user", result is False and len(errors) == 1
          and "Access is denied" in (errors[0][2] or ""), str(errors))
    dialogs.expect(*errors)
    check("the old file is untouched (atomic write)", read_file(path) == before)
    check("no temp file left after the failure", not os.path.exists(path + ".tmp"))
    check("the dialog stays open", dlg.winfo_exists() and dlg.has_changes())
    check("memory matches the disk after the failure", settings_store.get("theme") == "Ember")
    check("Apply works once the problem is gone", dlg.apply() is True)
    check("... and the file has the theme", (on_disk() or {}).get("theme") == "Graphite")
    settle()

    # ---- settings_store itself ----
    real_replace = os.replace
    os.replace = broken_replace
    try:
        ok = settings_store.set("probe", 1)
        try:
            settings_store.update({"probe": 2})
            raised = False
        except settings_store.SettingsWriteError:
            raised = True
    finally:
        os.replace = real_replace
    log = (read_file(os.path.join(LOG_DIR, "mosaiq.log")) or b"").decode("utf-8", "replace")
    check("set() returns False and logs instead of raising", ok is False and "could not be saved" in log, log[-200:])
    check("update() raises SettingsWriteError", raised)
    check("a failed write leaves no trace in memory", settings_store.get("probe") is None)
    check("a successful set works and returns True", settings_store.set("probe", 3) is True
          and (on_disk() or {}).get("probe") == 3)
    # a damaged file: defaults, and the problem is logged
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    settings_store.reload()
    check("a damaged settings file gives defaults", settings_store.get("theme", "x") == "x")
    log = (read_file(os.path.join(LOG_DIR, "mosaiq.log")) or b"").decode("utf-8", "replace")
    check("... and is logged", "could not be read" in log)
    settings_store.update({"theme": "Graphite"})
    settings_store.reload()
    check("the next write repairs it", (on_disk() or {}).get("theme") == "Graphite")

    # ---- the dialog is put on screen, whatever Windows would have cascaded it to ----
    from ui.dialogs.settings_dialog import dialog_position
    area = (0, 0, 1920, 1160)
    for parent in ((0, 0, 1920, 1160), (-9, -9, 1929, 1149), (300, 200, 1500, 900), (1500, 800, 3000, 1500)):
        for size in ((950, 1085), (950, 700), (1200, 400)):
            at = dialog_position(parent, [area], size)
            if parent[0] >= area[2] or at is None:
                continue
            check(f"dialog {size} for parent {parent} sits inside the work area",
                  at[0] >= area[0] and at[1] >= area[1] and at[0] + size[0] <= area[2] and at[1] + size[1] <= area[3], str(at))
    check("a parent on no monitor gives no position (the system decides)",
          dialog_position((-30000, -30000, -28700, -29200), [area], (950, 1085)) is None)
    check("a dialog is centred over a parent that has room", dialog_position((200, 100, 1000, 700), [area], (400, 300)) == (400, 250))
    check("with two monitors the dialog stays on the parent's monitor",
          dialog_position((-1900, 150, -100, 1100), [(0, 0, 1920, 1160), (-1920, 113, 0, 1193)], (950, 1000))[0] < 0)

    # ---- the footer: Apply and Cancel are always visible ----
    for screen_w, screen_h, scaling in ((1920, 1200, 1.25), (1920, 1080, 1.5), (1366, 768, 1.0),
                                        (1366, 768, 1.25), (1280, 720, 1.5), (3840, 2160, 1.5)):
        w, h = dialog_size(screen_w, screen_h, scaling)
        check(f"dialog fits a {screen_w}x{screen_h} screen at {int(scaling * 100)}%",
              w * scaling <= screen_w and h * scaling <= screen_h - 40, f"{w}x{h} logical")
    dlg = open_dialog()
    for height_px in (1200, 900, 768, 600):
        w, h = dialog_size(1920, height_px, dlg._get_window_scaling())
        dlg.geometry(f"{w}x{h}")
        settle(0.3)
        bottom = dlg.winfo_rooty() + dlg.winfo_height()
        buttons = [b for b in dlg.footer.winfo_children()]
        check(f"footer buttons visible when the dialog is {h} px tall",
              dlg.footer.winfo_ismapped() and all(b.winfo_ismapped() and b.winfo_rooty() + b.winfo_height() <= bottom
                                                  for b in buttons), f"bottom {bottom}")
    labels = sorted(b.cget("text") for b in dlg.footer.winfo_children())
    check("footer has Cancel and Apply", labels == ["Apply", "Cancel"], str(labels))
    theme = ThemeManager.get_theme()
    apply_button = next(b for b in dlg.footer.winfo_children() if b.cget("text") == "Apply")
    check("Apply is the accent button", apply_button.cget("fg_color").upper() == theme["primary"].upper())
    dlg.cancel()
    settle()

    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("SETTINGS_PERSIST_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("SETTINGS_PERSIST_OK: Apply writes all settings atomically, Cancel / Don't save write nothing, X asks, "
          "failed writes are reported, the next launch uses the saved theme, footer always visible")
