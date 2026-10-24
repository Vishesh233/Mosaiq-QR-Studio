"""Settings persist: the Settings page's Apply writes everything, Cancel and "Don't save" write nothing,
leaving the page or closing the app with changes asks, a failed write is reported, the next launch starts
with the saved theme, and the Apply / Cancel footer is always visible (100 / 125 / 150 % scaling).

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

    import customtkinter as ctk
    from ui.app import QRCodeStudioApp
    from utils import history_store, settings_store
    from utils.theme_manager import ThemeManager

    path = settings_store._settings_path()
    check("test set-up: a throw-away settings folder", APPDATA in path, path)
    check("test set-up: no settings file yet", not os.path.exists(path))

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()
    page = app.settings_page

    def settle(seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def open_page(from_page="generate"):
        getattr(app, f"show_{from_page}_page")()
        app.sidebar.navigate("settings")
        settle()

    def on_disk():
        raw = read_file(path)
        return json.loads(raw) if raw else None

    def shown_theme():
        return app.sidebar._theme_name_label.cget("text")

    def asked():
        return len([c for c in dialogs.calls if c[0] == "save_changes"])

    # ---- the page is part of the window, reached from the sidebar and the header ----
    check("Settings is a page of the main window", page.winfo_toplevel() is root and "settings" in app._pages)
    app.show_generate_page()
    check("the sidebar has a Settings entry at the bottom with the other entries' style",
          "settings" in app.sidebar._nav_buttons
          and app.sidebar._nav_buttons["settings"].winfo_rooty() > app.sidebar._nav_buttons["bulk"].winfo_rooty())
    app.sidebar.navigate("settings")
    settle()
    check("the sidebar entry opens the page", app._current_page == "settings" and page.winfo_ismapped())
    check("... marks it selected like the other pages", app.sidebar.active_tab == "settings"
          and app.sidebar._indicators["settings"].cget("fg_color").upper() == ThemeManager.get_theme()["primary"].upper())
    check("... and sets the header", app.header._title_label.cget("text") == "Settings")
    app.sidebar.navigate("history")
    settle()
    app.header.open_settings()
    settle()
    check("the header's gear opens the page too", app._current_page == "settings")
    page.cancel()
    settle()
    check("Cancel returns to the page Settings was opened from", app._current_page == "history")

    # ---- a fresh install: defaults, nothing on disk ----
    from config import DEFAULT_THEME
    check("default theme at first start", ThemeManager.get_current_theme() == DEFAULT_THEME)

    # ---- Apply: live preview writes nothing; Apply writes everything in one go ----
    open_page("generate")
    check("page opens unchanged", not page.has_changes())
    page.preview_theme("Emerald")
    settle()
    check("live preview shows the theme", shown_theme() == "Emerald" and ThemeManager.get_current_theme() == "Emerald")
    check("live preview writes nothing", not os.path.exists(path))
    check("page knows it has changes", page.has_changes())
    page.splash_var.set(False)
    page.history_var.set(False)
    page.wifi_var.set(True)
    check("still nothing written before Apply", not os.path.exists(path))
    page.apply_button.invoke()
    settle()
    check("Apply goes back to the page the user came from", app._current_page == "generate")
    saved = on_disk() or {}
    check("settings.json holds the theme", saved.get("theme") == "Emerald", str(saved))
    check("... the intro switch", saved.get("splash_enabled") is False, str(saved))
    check("... the history switches", saved.get(history_store.KEY_ENABLED) is False
          and saved.get(history_store.KEY_WIFI_PASSWORDS) is True, str(saved))
    check("no temp file left behind", not os.path.exists(path + ".tmp"))
    check("the app keeps showing the applied theme", shown_theme() == "Emerald")
    check("the page has no changes after Apply", not page.has_changes())

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
            "app.show_settings_page(); root.update()\n"
            "print('LAUNCH', ThemeManager.get_current_theme(), app.sidebar._theme_name_label.cget('text'), "
            "root.cget('fg_color'), ThemeManager.get_theme()['background'], app.settings_page._selected)\n"
            "app.close()\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=90,
                         cwd=os.path.dirname(os.path.abspath(__file__)), env=dict(os.environ))
    line = next((ln for ln in out.stdout.splitlines() if ln.startswith("LAUNCH")), "")
    parts = line.split()
    check("a new process starts with the saved theme", parts[1:3] == ["Emerald", "Emerald"],
          f"{line!r} {out.stderr[-300:]!r}")
    check("... and its window uses that theme's colours",
          len(parts) == 6 and parts[3].upper() == parts[4].upper() == ThemeManager.THEMES["Emerald"]["background"].upper(), line)
    check("... and its Settings page has that theme selected", len(parts) == 6 and parts[5] == "Emerald", line)

    # ---- Cancel: back to the opening state, file untouched ----
    before = read_file(path)
    mtime = os.path.getmtime(path)
    open_page("scan")
    page.preview_theme("Ember")
    page.splash_var.set(True)
    settle()
    check("Cancel test: preview is showing", shown_theme() == "Ember")
    page.cancel_button.invoke()
    settle()
    check("Cancel reverts the theme", ThemeManager.get_current_theme() == "Emerald" and shown_theme() == "Emerald")
    check("Cancel writes nothing", read_file(path) == before and os.path.getmtime(path) == mtime)
    check("Cancel goes back to the page it came from", app._current_page == "scan")
    open_page("scan")
    check("reopening shows what is saved, not the cancelled choices",
          page.splash_var.get() is False and page._selected == "Emerald" and not page.has_changes())
    app.show_generate_page()
    settle()

    # ---- leaving the page without changes: no question ----
    dialogs.clear()
    open_page("generate")
    app.sidebar.navigate("scan")
    settle()
    check("leaving Settings without changes goes straight on", app._current_page == "scan" and asked() == 0)
    # a change that is changed back is no change
    open_page("generate")
    page.preview_theme("Ember")
    page.preview_theme("Emerald")
    check("changing back leaves no changes", not page.has_changes())
    app.sidebar.navigate("history")
    settle()
    check("... and leaving asks nothing", app._current_page == "history" and asked() == 0)
    check("leaving without changes writes nothing", read_file(path) == before)

    # ---- leaving with changes: ask; Cancel stays, Don't save reverts, Save writes ----
    dialogs.clear()
    open_page("generate")
    page.preview_theme("Ember")
    settle()
    dialogs.answers["save_changes"] = "cancel"
    app.sidebar.navigate("scan")
    settle()
    check("leaving with changes asks 'Save changes?'", asked() == 1)
    check("[Cancel] stays on Settings with the preview", app._current_page == "settings" and shown_theme() == "Ember")
    check("... the sidebar still marks Settings", app.sidebar.active_tab == "settings")
    check("... and writes nothing", read_file(path) == before)
    dialogs.answers["save_changes"] = "discard"
    app.sidebar.navigate("scan")
    settle()
    check("[Don't save] goes to the page and brings the old theme back", app._current_page == "scan"
          and ThemeManager.get_current_theme() == "Emerald" and shown_theme() == "Emerald")
    check("... and writes nothing", read_file(path) == before and os.path.getmtime(path) == mtime)

    open_page("generate")
    page.preview_theme("Ember")
    page.splash_var.set(True)
    dialogs.answers["save_changes"] = "save"
    app.sidebar.navigate("bulk")
    settle()
    saved = on_disk() or {}
    check("[Save] writes the theme and the switches and goes on", app._current_page == "bulk"
          and saved.get("theme") == "Ember" and saved.get("splash_enabled") is True, str(saved))
    check("... the app shows it", shown_theme() == "Ember")
    dialogs.answers.pop("save_changes")

    # ---- closing the app with changes asks too ----
    before = read_file(path)
    open_page("generate")
    page.preview_theme("Graphite")
    dialogs.clear()
    dialogs.answers["save_changes"] = "cancel"
    app.close()
    settle(0.2)
    check("closing with changes asks", asked() == 1)
    check("[Cancel] keeps the app open", root.winfo_exists() and app._current_page == "settings")
    dialogs.answers.pop("save_changes")
    page.discard()
    settle()
    page.cancel()
    settle()

    # ---- the real "Save changes?" window (the other checks use a stand-in) ----
    box_seen = []

    def press(label):
        box = [w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel)][-1]
        buttons = []
        stack = list(box.winfo_children())
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if isinstance(widget, ctk.CTkButton):
                buttons.append(widget)
        box_seen.append(sorted(b.cget("text") for b in buttons))
        next(b for b in buttons if b.cget("text") == label).invoke()

    for label, expected in (("Save", "save"), ("Don't save", "discard"), ("Cancel", "cancel")):
        root.after(500, lambda label=label: press(label))
        root.after(8000, lambda: [w.destroy() for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel)])  # failsafe
        check(f"the real window answers {expected} for [{label}]",
              _test_dialogs.real_ask_save_changes(root) == expected)
    check("the real window offers Save, Don't save and Cancel", box_seen[0] == ["Cancel", "Don't save", "Save"], str(box_seen))
    def escape():
        box = [w for w in root.winfo_children() if isinstance(w, ctk.CTkToplevel)][-1]
        box.focus_force()                  # key events go to the window that has the focus
        box.update()
        box.event_generate("<Escape>")
        root.after(1500, lambda: box.winfo_exists() and box.destroy())     # never hang the test if the key is lost

    root.after(500, escape)
    check("Escape in the real window means Cancel", _test_dialogs.real_ask_save_changes(root) == "cancel")

    # ---- a failed write is shown, nothing is half-written, the choices stay ----
    before = read_file(path)
    real_replace = os.replace
    open_page("generate")
    page.preview_theme("Graphite")
    settle()

    def broken_replace(src, dst, *a, **k):
        raise PermissionError(13, "Access is denied")

    os.replace = broken_replace
    try:
        result = page.apply()
    finally:
        os.replace = real_replace
    errors = [c for c in dialogs.calls if c[0] == "showerror" and "save settings" in (c[1] or "").lower()]
    check("a failed write is reported to the user", result is False and len(errors) == 1
          and "Access is denied" in (errors[0][2] or ""), str(errors))
    dialogs.expect(*errors)
    check("the old file is untouched (atomic write)", read_file(path) == before)
    check("no temp file left after the failure", not os.path.exists(path + ".tmp"))
    check("the page stays open with its changes", app._current_page == "settings" and page.has_changes())
    check("memory matches the disk after the failure", settings_store.get("theme") == "Ember")
    page.apply_button.invoke()
    settle()
    check("Apply works once the problem is gone", (on_disk() or {}).get("theme") == "Graphite"
          and app._current_page == "generate")

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

    # ---- the footer: Apply and Cancel are always visible, at 100 / 125 / 150 % ----
    from utils import window_guard
    labels = sorted(b.cget("text") for b in page.footer.winfo_children())
    check("footer has Cancel and Apply", labels == ["Apply", "Cancel"], str(labels))
    theme = ThemeManager.get_theme()
    check("Apply is the accent button", page.apply_button.cget("fg_color").upper() == theme["primary"].upper())
    for scaling in (1.0, 1.25, 1.5):
        ctk.set_widget_scaling(scaling)
        ctk.set_window_scaling(scaling)
        for width, height in ((1280, 820), (1080, 680)):         # the start size and the smallest size
            root.geometry(f"{width}x{height}+-30000+-30000")
            open_page("generate")
            settle(0.4)
            for scroll in (0.0, 1.0):                             # the page scrolled to the top and to the end
                page.body._parent_canvas.yview_moveto(scroll)
                settle(0.15)
                bottom = root.winfo_rooty() + root.winfo_height()
                check(f"footer buttons visible at {int(scaling * 100)} %, {width}x{height}, scrolled to {scroll}",
                      page.footer.winfo_ismapped() and all(
                          b.winfo_ismapped() and b.winfo_rooty() >= root.winfo_rooty()
                          and b.winfo_rooty() + b.winfo_height() <= bottom for b in page.footer.winfo_children()),
                      f"bottom {bottom}, footer {page.footer.winfo_rooty() + page.footer.winfo_height()}")
            check(f"the body scrolls above the footer at {int(scaling * 100)} %, {width}x{height}",
                  page.body.winfo_rooty() + page.body.winfo_height() <= page.footer.winfo_rooty() + 2)
            page.cancel()
            settle(0.2)
    ctk.set_widget_scaling(1.0)
    ctk.set_window_scaling(1.0)

    # ---- the dialog-placement helper still used by the "Save changes?" prompt ----
    area = (0, 0, 1920, 1160)
    for parent in ((0, 0, 1920, 1160), (-9, -9, 1929, 1149), (300, 200, 1500, 900), (1500, 800, 3000, 1500)):
        for size in ((950, 1085), (950, 700), (1200, 400)):
            at = window_guard.centred_over(parent, [area], size)
            if at is None:
                continue
            check(f"window {size} for parent {parent} sits inside the work area",
                  at[0] >= area[0] and at[1] >= area[1] and at[0] + size[0] <= area[2] and at[1] + size[1] <= area[3], str(at))
    check("a parent on no monitor gives no position (the system decides)",
          window_guard.centred_over((-30000, -30000, -28700, -29200), [area], (950, 1085)) is None)
    check("a window is centred over a parent that has room",
          window_guard.centred_over((200, 100, 1000, 700), [area], (400, 300)) == (400, 250))
    check("with two monitors the window stays on the parent's monitor",
          window_guard.centred_over((-1900, 150, -100, 1100), [(0, 0, 1920, 1160), (-1920, 113, 0, 1193)], (950, 1000))[0] < 0)

    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("SETTINGS_PERSIST_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("SETTINGS_PERSIST_OK: Settings page: Apply writes all settings atomically, Cancel / Don't save write nothing, "
          "leaving or closing with changes asks, failed writes are reported, the next launch uses the saved theme, "
          "footer always visible at 100 / 125 / 150 %")
