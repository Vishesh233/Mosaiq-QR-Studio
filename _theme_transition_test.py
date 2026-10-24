"""The liquid blob theme transition (utils/theme_transition.py).

Covers the maths (mask at T=0 and T=1, growth that never shrinks, the order of the three patches,
droplets, the edge glow outside the union only), the snapshot (own window only), the behaviour on
screen (it runs for live changes and reverts, skips on click / key / resize, a new change finishes
the old animation first, off switch, Windows animations off, snapshot failure, not at start-up),
the sizes at different scalings, and a frame-time benchmark.

Run:  .venv\\Scripts\\python.exe _theme_transition_test.py
"""
import math
import os
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
os.environ["APPDATA"] = tempfile.mkdtemp()
LOG_DIR = tempfile.mkdtemp()
os.environ["QRSTUDIO_LOG_DIR"] = LOG_DIR

problems = []
bench = {}


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def test_maths():
    from utils import theme_transition as tt

    size = (640, 400)
    w, h = size
    cfg = tt.CONFIG
    check("duration constant is 3.0 s", tt.DURATION_SEC == 3.0)
    check("config holds the locked numbers", cfg["patches"] == 3 and cfg["wobble"] == 1.2
          and cfg["inkDroplets"] is True and cfg["edgeGlow"] is True)

    m0 = tt.render_mask(size, 0.0)
    check("T=0: nothing is covered", m0.getextrema() == (0, 0), str(m0.getextrema()))
    m1 = tt.render_mask(size, 1.0)
    check("T=1: everything is covered", m1.getextrema() == (255, 255), str(m1.getextrema()))
    check("mask is drawn at half resolution", m0.size == (320, 200), str(m0.size))
    check("just before the end almost everything is covered",
          tt.covered_fraction(tt.render_mask(size, 0.985)) > 0.995)

    # coverage never goes down as T grows
    steps = 150
    areas = [tt.covered_fraction(tt.render_mask(size, i / steps)) for i in range(steps + 1)]
    worst = min(b - a for a, b in zip(areas, areas[1:]))
    check("covered area never shrinks as T grows", worst >= -0.0015, f"worst step {worst:.5f}")
    check("coverage starts at 0 and ends at 1", areas[0] == 0 and areas[-1] == 1.0)
    check("coverage really grows", areas[steps // 2] > 0.2 and areas[steps // 4] > 0.02, str(areas[::30]))

    # the order of the patches: top-left, middle, bottom-right
    def covered(T, fx, fy):
        mask = tt.render_mask(size, T)
        return mask.getpixel((int(fx * (mask.width - 1)), int(fy * (mask.height - 1)))) == 255

    check("T=0.2: top-left is covered", covered(0.2, 0.04, 0.06))
    check("T=0.2: the middle is not yet", not covered(0.2, 0.52, 0.50))
    check("T=0.2: bottom-right is not", not covered(0.2, 0.97, 0.96))
    check("T=0.45: the middle is covered", covered(0.45, 0.52, 0.50))
    check("T=0.45: bottom-right is still not", not covered(0.45, 0.98, 0.97))
    check("T=0.8: bottom-right is covered", covered(0.8, 0.98, 0.97))
    check("patch k starts at k * 0.225",
          tt.patch_progress(0.225, 1) == 0 and tt.patch_progress(0.45, 2) == 0
          and tt.patch_progress(0.226, 1) > 0 and abs(tt.patch_progress(1.0, 2) - 1.0) < 1e-9)
    diag = math.hypot(*size)
    check("radius follows 1-(1-p)^2", abs(tt.patch_radius(0.55 / 2 + 0.0, 0, diag)
          - cfg["rmax"][0] * diag * (1 - (1 - 0.5) ** 2)) < 1e-6)

    # the blob outline
    check("no wobble gives a circle", all(abs(tt.blob_factor(a / 10, 1.9, 0.7, 0.0) - 1) < 1e-12 for a in range(63)))
    factors = [tt.blob_factor(a / 20, 3.3, 1.1, 1.2) for a in range(126)]
    check("the wobble stays within the formula's bounds", 0.72 <= min(factors) and max(factors) <= 1.28,
          f"{min(factors):.3f}..{max(factors):.3f}")
    outline = tt.blob_outline((100, 100), 50, 0.0, 0.0, 1.2, cfg["points"])
    check("outline has 96 points", len(outline) == 96)

    # ink droplets
    centre = tt.patch_centre(0, w, h, 1.0)
    drops_mid = tt.droplets(0, 0.275, centre, diag, 0.8, 1.2)
    check("nine droplets per patch", len(drops_mid) == 9, str(len(drops_mid)))
    def total_size(T):
        return sum(r for _x, _y, r in tt.droplets(0, T, centre, diag, 0.8, 1.2))
    check("droplet size follows sin(pi p)", total_size(0.275) > total_size(0.04) and total_size(0.275) > total_size(0.5),
          f"{total_size(0.04):.1f} {total_size(0.275):.1f} {total_size(0.5):.1f}")
    check("no droplets before the patch starts or after it finishes", not tt.droplets(0, 0.0, centre, diag, 0, 1.2)
          and not tt.droplets(0, 0.56, centre, diag, 1.6, 1.2))
    outside = sum(1 for x, y, r in drops_mid
                  if math.hypot(x - centre[0], y - centre[1]) > tt.patch_radius(0.275, 0, diag) * 0.7)
    check("droplets sit at the blob's edge or ahead of it", outside == 9, f"{outside} of 9")
    no_drops = dict(cfg, inkDroplets=False)
    a = tt.render_mask(size, 0.3, cfg)
    b = tt.render_mask(size, 0.3, no_drops)
    from PIL import ImageChops
    check("droplets change the mask, and can be switched off", ImageChops.difference(a, b).getbbox() is not None)

    # edge glow: only outside the union, strongest in the middle, none at the ends
    for T in (0.0, 1.0):
        check(f"no glow at T={T}", tt.edge_glow_alpha(tt.render_mask(size, T), T) is None)
    check("glow strength is sin(pi T)", abs(tt.glow_strength(0.5) - 1) < 1e-12 and tt.glow_strength(0) == 0
          and abs(tt.glow_strength(1)) < 1e-9)
    mask = tt.render_mask(size, 0.5)
    alpha = tt.edge_glow_alpha(mask, 0.5)
    import numpy as np
    inside = np.asarray(mask) == 255
    inside_max = int(np.asarray(alpha)[inside].max()) if inside.any() else 0
    check("no glow inside the union (overlap lines never show)", inside_max == 0, f"max {inside_max}")
    check("glow is visible just outside the union", alpha.getextrema()[1] > 100, str(alpha.getextrema()))
    weaker = tt.edge_glow_alpha(tt.render_mask(size, 0.5), 0.5).getextrema()[1]
    ends = tt.edge_glow_alpha(tt.render_mask(size, 0.08), 0.08)
    check("glow is weaker near the start than in the middle", ends is not None and ends.getextrema()[1] < weaker)
    off = dict(cfg, edgeGlow=False)
    check("glow can be switched off", tt.edge_glow_alpha(mask, 0.5, off) is None)

    # frames
    from PIL import Image
    old = Image.new("RGB", size, (200, 0, 0))
    new = Image.new("RGB", size, (0, 0, 200))
    renderer = tt.FrameRenderer(old, new, "#00FF00")
    check("frame at T=0 is the old picture and at T=1 the new", renderer.render(0.0) is old and renderer.render(1.0) is new)
    frame = renderer.render(0.5)
    check("a frame has the window's size", frame.size == size)
    pixels = np.asarray(frame).astype(int)
    reds = int(((pixels[..., 0] > 150) & (pixels[..., 2] < 60)).sum())
    blues = int(((pixels[..., 2] > 150) & (pixels[..., 0] < 60)).sum())
    check("a middle frame shows both pictures", reds > 1000 and blues > 1000, f"{reds} {blues}")
    check("a lower quality frame has the same size", renderer.render(0.5, quality=0.5).size == size)

    source = open(tt.__file__, encoding="utf-8").read()
    check("snapshots use PrintWindow only (no screen grab)", "PrintWindow" in source and "ImageGrab" not in source
          and "BitBlt" not in source and "GetDC(None)" not in source and "GetDesktopWindow" not in source)

    # timings of the maths
    for quality in (1.0, 0.5):
        big = (1600, 1000)
        r = tt.FrameRenderer(Image.new("RGB", big, "red"), Image.new("RGB", big, "blue"), "#00FF00")
        r.render(0.5, quality)
        started = time.perf_counter()
        for i in range(30):
            r.render(0.05 + i * 0.03, quality)
        bench[f"compose {big[0]}x{big[1]} q={quality}"] = (time.perf_counter() - started) / 30 * 1000


def test_on_screen():
    import customtkinter as ctk

    import _test_dialogs
    _test_dialogs.install()
    os.environ.pop("QRSTUDIO_NO_THEME_ANIMATION", None)      # this test is about the animation

    from ui.app import QRCodeStudioApp
    from ui.dialogs.settings_dialog import SettingsDialog
    from utils import settings_store, theme_transition as tt
    from utils.theme_manager import ThemeManager

    app = QRCodeStudioApp()
    root = app.root
    # On screen (but without a taskbar button): Tk paints a window that is outside every monitor
    # only partly, so a snapshot of one is blank and the animation would rightly skip itself.
    root.geometry("1280x800+20+20")
    root.update()
    manager = app.theme_transition

    def settle(seconds=0.2):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.005)

    def overlays():
        return [w for w in root.winfo_children() if isinstance(w, __import__("tkinter").Canvas)]

    settle(0.5)
    check("start-up does not animate", not manager.running and manager.last_run is None and not overlays())
    tt.system_animations_enabled = lambda: True          # deterministic: "Animation effects" on
    check("animation is enabled by default", tt.enabled() is True)

    # --- a live change runs; the new theme is already applied underneath ---
    started = manager.run(lambda: (ThemeManager.set_theme("Emerald", persist=False), app.refresh_theme()))
    check("a theme change starts an animation", started is True and manager.running)
    check("the final theme is applied at once", ThemeManager.get_current_theme() == "Emerald"
          and app.sidebar._theme_name_label.cget("text") == "Emerald")
    box = overlays()
    check("one overlay covers the window", len(box) == 1)
    root.update_idletasks()
    snap = manager._overlays[0]
    check("overlay, snapshot and window client area have the same size",
          snap.size == (root.winfo_width(), root.winfo_height()) == (box[0].winfo_width(), box[0].winfo_height()),
          f"{snap.size} {(root.winfo_width(), root.winfo_height())} {(box[0].winfo_width(), box[0].winfo_height())}")
    import numpy as np
    for name, picture in (("before", snap.renderer.old), ("after", snap.renderer.new)):
        pixels = np.asarray(picture)
        check(f"the {name} snapshot shows the real window (not blank)", (pixels.min(axis=2) > 245).mean() < 0.2
              and pixels.std() > 10, f"white share {(pixels.min(axis=2) > 245).mean():.2f}")
    settle(0.35)
    check("frames are being shown and the window keeps answering", manager._frames >= 3, f"{manager._frames} frames")

    # --- a click skips to the end ---
    box[0].event_generate("<Button-1>", x=10, y=10)
    settle(0.05)
    check("a click ends the animation at once", not manager.running and not overlays())
    check("... and the final theme stays", ThemeManager.get_current_theme() == "Emerald")

    # --- a key press skips too ---
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    settle(0.1)
    check("second animation is running", manager.running)
    root.event_generate("<Key>", keysym="a")
    settle(0.05)
    check("a key press ends the animation", not manager.running and not overlays())

    # --- resizing the window ends it ---
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settle(0.1)
    root.geometry("1200x760+20+20")
    settle(0.3)
    check("resizing the window ends the animation", not manager.running and not overlays())
    root.geometry("1280x800+20+20")
    settle(0.3)

    # --- a new change while one runs: the old one finishes, the new one starts, no crash ---
    manager.run(lambda: (ThemeManager.set_theme("Ultraviolet", persist=False), app.refresh_theme()))
    settle(0.15)
    runs_before = manager.runs
    manager.run(lambda: (ThemeManager.set_theme("Aqua Mint", persist=False), app.refresh_theme()))
    check("a change during an animation starts a new one", manager.running and manager.runs == runs_before + 1)
    check("only one overlay exists", len(overlays()) == 1)
    check("the final theme is the last one chosen", ThemeManager.get_current_theme() == "Aqua Mint"
          and app.sidebar._theme_name_label.cget("text") == "Aqua Mint")
    manager.finish()
    check("finish() removes the overlay", not manager.running and not overlays())

    # --- it ends by itself, with timing facts ---
    manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()), duration=1.2)
    end = time.time() + 5
    while manager.running and time.time() < end:
        root.update()
        time.sleep(0.004)
    check("the animation ends by itself", not manager.running and not overlays())
    stats = manager.last_run or {}
    check("it made a fair number of frames", stats.get("frames", 0) >= 12, str(stats))
    bench["on screen, 1280x800 window"] = stats.get("avg_ms", 0)
    bench["on screen frames (1.2 s run)"] = stats.get("frames", 0)
    bench["on screen max frame ms"] = stats.get("max_ms", 0)
    bench["on screen final quality"] = stats.get("quality", 1)

    # --- a window outside every monitor cannot be snapshotted: skipped with a warning, theme still applies ---
    root.geometry("1280x800+-30000+-30000")
    settle(0.4)
    away = manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    check("an off-screen window is not animated (and not snapshotted blank)", away is False and not overlays()
          and ThemeManager.get_current_theme() == "Ember" and "outside every monitor" in log)
    root.geometry("1280x800+20+20")
    settle(0.5)

    # --- switches that turn it off ---
    runs = manager.runs
    settings_store.set(tt.SETTING_KEY, False)
    check("the Settings switch turns it off", tt.enabled() is False)
    check("off: no animation, theme applied", manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False),
          app.refresh_theme())) is False and not overlays() and manager.runs == runs
          and ThemeManager.get_current_theme() == "Ember")
    settings_store.set(tt.SETTING_KEY, True)
    tt.system_animations_enabled = lambda: False
    check("Windows animations off: no animation", manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False),
          app.refresh_theme())) is False and not overlays() and ThemeManager.get_current_theme() == "Midnight")
    tt.system_animations_enabled = lambda: True
    os.environ["QRSTUDIO_NO_THEME_ANIMATION"] = "1"
    check("the environment switch turns it off", tt.enabled() is False)
    del os.environ["QRSTUDIO_NO_THEME_ANIMATION"]

    # --- a snapshot that fails: theme still applies, warning in the log ---
    real_capture = tt.capture_client

    def failing(window):
        raise tt.SnapshotError("test failure")

    tt.capture_client = failing
    try:
        ok = manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    finally:
        tt.capture_client = real_capture
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    check("failed snapshot: no animation but the theme changes", ok is False and not overlays()
          and ThemeManager.get_current_theme() == "Graphite")
    check("... and a warning is logged", "Theme transition skipped" in log and "test failure" in log, log[-300:])

    # --- the Settings dialog: previews and reverts animate, the switch decides, the dialog changes at once ---
    ThemeManager.set_theme("Midnight", persist=False)
    app.refresh_theme()
    settle(0.3)
    dlg = SettingsDialog(app.header)
    settle(0.4)
    runs = manager.runs
    dlg.preview_theme("Emerald")
    check("a live preview animates", manager.runs == runs + 1 and manager.running)
    check("the main window is covered by the effect; the dialog changes at once, on top of it",
          len(manager._overlays) == 1 and manager._overlays[0].window is root, str([o.window for o in manager._overlays]))
    check("the dialog is already in the new theme",
          dlg.container.cget("fg_color").upper() == ThemeManager.THEMES["Emerald"]["background"].upper())
    for overlay in manager._overlays:
        window = overlay.window
        check(f"overlay matches its window ({window.winfo_class()})",
              overlay.size == (window.winfo_width(), window.winfo_height()))
    settle(0.2)
    runs = manager.runs
    dlg.cancel()
    settle(0.1)
    check("Cancel reverts the theme with an animation", manager.runs == runs + 1 and manager.running
          and ThemeManager.get_current_theme() == "Midnight")
    manager.finish()

    dlg = SettingsDialog(app.header)
    settle(0.4)
    dlg.animate_var.set(False)
    runs = manager.runs
    dlg.preview_theme("Ember")
    check("the dialog's switch turns the animation off before Apply", manager.runs == runs and not manager.running
          and ThemeManager.get_current_theme() == "Ember")
    dlg.animate_var.set(True)
    dlg.cancel()
    manager.finish()
    check("closing the dialog clears the override", tt.ENABLED_OVERRIDE is None)

    dlg = SettingsDialog(app.header)
    settle(0.4)
    check("the switch shows the saved value (on)", dlg.animate_var.get() is True)
    check("opening unchanged is no change", not dlg.has_changes())
    dlg.animate_var.set(False)
    check("changing the switch counts as a change", dlg.has_changes())
    check("Apply saves it", dlg.apply() is True and settings_store.get(tt.SETTING_KEY) is False)
    settings_store.set(tt.SETTING_KEY, True)
    manager.finish()

    # --- sizes at different scalings (the snapshot is in physical pixels; the overlay must match) ---
    for factor in (0.8, 1.0, 1.2):
        ctk.set_widget_scaling(factor)
        settle(0.6)
        manager.run(lambda: (ThemeManager.set_theme("Ultraviolet" if ThemeManager.get_current_theme() != "Ultraviolet"
                                                    else "Midnight", persist=False), app.refresh_theme()))
        shown = manager._overlays[0] if manager.running else None
        check(f"widget scaling {factor}: animation runs", shown is not None)
        if shown is not None:
            canvas = shown.canvas
            check(f"widget scaling {factor}: overlay == snapshot == window ({shown.size})",
                  shown.size == (root.winfo_width(), root.winfo_height()) == (canvas.winfo_width(), canvas.winfo_height()),
                  f"{shown.size} {(root.winfo_width(), root.winfo_height())} {(canvas.winfo_width(), canvas.winfo_height())}")
            settle(0.25)
        manager.finish()
    ctk.set_widget_scaling(1.0)
    settle(0.5)

    app.close()


def main():
    test_maths()
    test_on_screen()
    print("BENCHMARK (ms per frame):")
    for key, value in bench.items():
        print(f"  {key}: {value:.1f}" if isinstance(value, float) else f"  {key}: {value}")


if __name__ == "__main__":
    main()
    if problems:
        print("THEME_TRANSITION_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("THEME_TRANSITION_OK: mask maths, patch order, droplets, edge glow outside the union, snapshot, skip on click / key / "
          "resize, restart, off switches, dialog, scalings, benchmark")
