"""What a fresh install starts with: no settings file at all.

The intro animation is ON by default, history is on with WiFi passwords off, and the theme is
the default one. Uses a throw-away APPDATA, so the real user's settings are never read or changed.

Run:  .venv\\Scripts\\python.exe _defaults_test.py
"""
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["APPDATA"] = tempfile.mkdtemp()          # a fresh install: no settings.json
os.environ.pop("QRSTUDIO_NO_SPLASH", None)          # the runner sets it for the other tests

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def main():
    from utils import history_store, settings_store

    settings_path = settings_store._settings_path()
    check("test set-up: no settings file", not os.path.exists(settings_path), settings_path)
    check("test set-up: not the real settings folder", os.environ["APPDATA"] in settings_path, settings_path)

    from ui.splash import splash_disabled
    check("the environment does not switch the intro off", not splash_disabled())
    check("intro animation setting defaults to ON", settings_store.get("splash_enabled", True) is True)

    import _test_dialogs
    _test_dialogs.install()
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()
    app.show_settings_page()
    root.update()
    dialog = app.settings_page
    check("Settings shows the intro animation switch ON", dialog.splash_var.get() is True)
    check("history is on", dialog.history_var.get() is True)
    check("WiFi passwords in history are off", dialog.wifi_var.get() is False)
    dialog.cancel()
    check("opening and cancelling Settings does not create a settings file with the intro off",
          settings_store.get("splash_enabled", True) is True)

    # The decision App.run() makes, for this fresh profile and no environment override:
    use_splash = bool(settings_store.get("splash_enabled", True)) and not splash_disabled()
    check("a fresh install plays the intro", use_splash)
    check("history store defaults", history_store.enabled() and not history_store.save_wifi_passwords())
    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("DEFAULTS_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("DEFAULTS_OK: fresh install has the intro animation ON, history on, WiFi passwords off")
