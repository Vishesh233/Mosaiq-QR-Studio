"""The main window must be on a monitor after the app starts, even from a bad position.

Covers: the rectangle maths, a window parked outside every monitor is brought back (centred,
inside the work area), a minimized or hidden window is shown again, a healthy window is left
alone, and the real start-up path (App.run) ends with a visible window when the window was
placed far off-screen first. The window is created, checked and destroyed here; nothing is
left running.

Run:  .venv\\Scripts\\python.exe _window_visible_test.py
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


def test_maths():
    from utils import window_guard as wg

    area = (0, 0, 1920, 1040)
    check("window inside is fine", not wg.needs_recovery((100, 100, 1300, 900), [area]))
    check("maximized (a few px outside) is fine", not wg.needs_recovery((-8, -8, 1928, 1048), [area]))
    check("far off-screen needs recovery", wg.needs_recovery((-30000, -30000, -28700, -29200), [area]))
    check("only a sliver visible needs recovery", wg.needs_recovery((1900, 100, 3200, 900), [area]))
    check("second monitor counts", not wg.needs_recovery((2000, 100, 3200, 900), [area, (1920, 0, 3840, 1040)]))
    check("unplugged monitor needs recovery", wg.needs_recovery((2000, 100, 3200, 900), [area]))
    check("no monitor info leaves the window alone", not wg.needs_recovery((-30000, 0, -29000, 800), []))
    check("a small window fully inside is fine", not wg.needs_recovery((10, 10, 110, 60), [area]))
    w, h, x, y = wg.centred(1280, 820, (0, 0, 1920, 1040))
    check("centred", (w, h, x, y) == (1280, 820, 320, 110), str((w, h, x, y)))
    w, h, x, y = wg.centred(3000, 2000, (100, 50, 1100, 650))
    check("shrunk to the work area", (w, h, x, y) == (1000, 600, 100, 50), str((w, h, x, y)))


def test_real_window():
    from ui.app import QRCodeStudioApp
    from utils import window_guard as wg

    os.environ["APPDATA"] = tempfile.mkdtemp()
    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    areas = wg.work_areas()
    check("monitors found", len(areas) >= 1, str(areas))

    def on_screen():
        root.update()
        return not wg.needs_recovery(wg.window_rect(root), areas)

    root.geometry("1280x820+-30000+-30000")
    root.update()
    check("test set-up: window really is off-screen", not on_screen(), str(wg.window_rect(root)))
    action = app.verify_visible()
    check("off-screen window is recentred", action == "recentred", action)
    check("and is now on a monitor", on_screen(), str(wg.window_rect(root)))
    check("and is maximized like a normal start", root.state() == "zoomed", root.state())

    check("a visible window is left alone", app.verify_visible() == "ok")

    root.iconify()
    root.update()
    check("test set-up: minimized", root.state() == "iconic", root.state())
    action = app.verify_visible()
    check("a minimized window is shown again", action == "shown" and root.state() != "iconic",
          f"{action} {root.state()}")

    root.withdraw()
    root.update()
    action = app.verify_visible()
    check("a hidden window is shown again", action == "shown" and root.state() != "withdrawn",
          f"{action} {root.state()}")
    app.close()


def test_startup_path():
    """App.run() from a window placed far off-screen: after start-up it is on a monitor."""
    from ui.app import QRCodeStudioApp
    from utils import window_guard as wg

    os.environ["APPDATA"] = tempfile.mkdtemp()
    app = QRCodeStudioApp()
    root = app.root
    areas = wg.work_areas()
    result = {}

    # The start-up code withdraws the window, maximizes and shows it; start from a bad spot.
    root.geometry("1280x820+-30000+-30000")

    def probe():
        root.update_idletasks()
        result["state"] = root.state()
        result["rect"] = wg.window_rect(root)
        result["visible"] = bool(root.winfo_viewable())
        root.after(10, app.close)

    root.after(1500, probe)
    app.run(show_splash=False)
    check("start-up ends with a viewable window", result.get("visible"), str(result))
    check("start-up ends on a monitor", result.get("rect") is not None
          and not wg.needs_recovery(result["rect"], areas), str(result))


def worker(name):
    """One window scenario in its own process (two Tk apps in one process leave
    stray after() callbacks that print noise when the first one is destroyed)."""
    {"real": test_real_window, "startup": test_startup_path}[name]()
    for p in problems:
        print("PROBLEM:", p)
    sys.exit(1 if problems else 0)


def main():
    import subprocess

    if len(sys.argv) > 1:
        worker(sys.argv[1])
    test_maths()
    for name in ("real", "startup"):
        done = subprocess.run([sys.executable, os.path.abspath(__file__), name],
                              capture_output=True, text=True, timeout=120)
        found = [ln[len("PROBLEM: "):] for ln in done.stdout.splitlines() if ln.startswith("PROBLEM: ")]
        problems.extend(f"[{name}] {p}" for p in found)
        if done.returncode != 0 and not found:
            problems.append(f"[{name}] crashed (exit {done.returncode}): {done.stderr.strip()[-400:]}")
    if problems:
        print("WINDOW_VISIBLE_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("WINDOW_VISIBLE_OK: rectangle maths, off-screen / minimized / hidden window brought back, start-up from off-screen")


if __name__ == "__main__":
    main()
