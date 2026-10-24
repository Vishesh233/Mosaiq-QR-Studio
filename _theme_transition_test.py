"""The liquid blob theme transition (utils/theme_transition.py).

Covers the maths (mask at T=0 and T=1, growth that never shrinks, the order of the three patches,
droplets, the edge glow outside the union only), the snapshot (own window only), the behaviour on
screen (it runs for live changes and reverts, on the Settings page too, skips on click / key / move /
resize / minimize / focus loss, a new change finishes the old animation first, changes never overlap,
off switches, snapshot failure, not at start-up), the reason of every start and skip in mosaiq.log,
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
    check("duration constant is 2.0 s", tt.DURATION_SEC == 2.0)
    check("config holds the locked numbers", cfg["patches"] == 3 and cfg["wobble"] == 1.2
          and cfg["inkDroplets"] is True and cfg["edgeGlow"] is True)

    m0 = tt.render_mask(size, 0.0)
    check("T=0: nothing is covered", m0.getextrema() == (0, 0), str(m0.getextrema()))
    m1 = tt.render_mask(size, 1.0)
    check("T=1: everything is covered", m1.getextrema() == (255, 255), str(m1.getextrema()))
    check("mask is drawn at half resolution", m0.size == (320, 200), str(m0.size))
    check("the ink covers the whole window well before the end (as in the reference)",
          tt.covered_fraction(tt.render_mask(size, 0.9)) == 1.0)
    check("blob end sizes follow the reference (520 / 470 / 1000 px of an 840 x 520 canvas)",
          all(abs(cfg["rmax"][i] * tt.REFERENCE_DIAGONAL - v) < 1e-6 for i, v in enumerate((520, 470, 1000))))

    # coverage never goes down as T grows
    steps = 150
    areas = [tt.covered_fraction(tt.render_mask(size, i / steps)) for i in range(steps + 1)]
    worst = min(b - a for a, b in zip(areas, areas[1:]))
    check("covered area never shrinks as T grows", worst >= -1e-9, f"worst step {worst:.6f}")
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

    # ink droplets (as in the reference page)
    centre = tt.patch_centre(0, w, h, 1.0)
    p_mid = 0.5
    T_mid = p_mid * cfg["span"]                              # patch 0 is at progress 0.5 here
    drops_mid = tt.droplets(0, T_mid, centre, diag)
    check("nine droplets per patch", len(drops_mid) == 9, str(len(drops_mid)))

    def total_size(T):
        return sum(r for _x, _y, r in tt.droplets(0, T, centre, diag))

    low_T, high_T = cfg["span"] * 0.12, cfg["span"] * 0.88
    check("droplet size follows sin(pi p)", total_size(T_mid) > total_size(low_T) > 0 and total_size(T_mid) > total_size(high_T) > 0,
          f"{total_size(low_T):.1f} {total_size(T_mid):.1f} {total_size(high_T):.1f}")
    check("no droplets before progress 0.08 or after 0.92 (nor before the patch starts)",
          not tt.droplets(0, 0.0, centre, diag) and not tt.droplets(0, cfg["span"] * 0.05, centre, diag)
          and not tt.droplets(0, cfg["span"] * 0.95, centre, diag) and tt.droplets(0, cfg["span"] * 0.1, centre, diag))
    base = tt.patch_radius(T_mid, 0, diag)
    lags = sorted(math.hypot(x - centre[0], y - centre[1]) / base for x, y, r in drops_mid)
    check("droplets ride at 1.06 to 1.22 times the unwobbled radius", abs(lags[0] - 1.06) < 1e-6 and lags[-1] <= 1.06 + 9 / 55 + 1e-6
          and all(1.06 - 1e-6 <= v <= 1.23 for v in lags), f"{lags[0]:.3f}..{lags[-1]:.3f}")
    unit = diag / tt.REFERENCE_DIAGONAL
    check("droplet radii are 4 to 12 px of the reference canvas, scaled",
          all(4 * unit * 0.99 * math.sin(math.pi * p_mid) <= r <= 12 * unit * 1.01 for _x, _y, r in drops_mid))
    no_drops = dict(cfg, inkDroplets=False)
    a = tt.render_mask(size, 0.3, cfg)
    b = tt.render_mask(size, 0.3, no_drops)
    from PIL import ImageChops
    check("droplets change the mask, and can be switched off", ImageChops.difference(a, b).getbbox() is not None)

    # edge glow: only outside the union, strongest in the middle, none at the ends
    for T in (0.0, 1.0):
        check(f"no glow at T={T}", tt.edge_glow_alpha(size, T) is None)
    check("glow strength is sin(pi T)", abs(tt.glow_strength(0.5) - 1) < 1e-12 and tt.glow_strength(0) == 0
          and abs(tt.glow_strength(1)) < 1e-9)
    import numpy as np
    T_glow = 0.3
    shapes = tt.build_shapes(size, T_glow)
    mask = tt.render_mask(size, T_glow, scale=cfg["glowScale"], shapes=shapes)
    alpha = tt.edge_glow_alpha(size, T_glow, shapes=shapes)
    check("glow and mask are drawn at the same size", alpha.size == mask.size, f"{alpha.size} {mask.size}")
    inside = np.asarray(mask) == 255
    inside_max = int(np.asarray(alpha)[inside].max()) if inside.any() else 0
    check("no glow inside the union (overlap lines never show)", inside_max == 0, f"max {inside_max}")
    check("glow is visible just outside the union", alpha.getextrema()[1] > 100, str(alpha.getextrema()))
    outside_values = np.asarray(alpha)[~inside]
    check("the thin line is stronger than the soft glow (55 % vs 18 %)",
          outside_values.max() > 0.5 * 255 * tt.glow_strength(T_glow) and (outside_values > 0).mean() > 0, str(outside_values.max()))
    near_start = tt.edge_glow_alpha(size, 0.05)
    check("glow is weaker near the start than at T=0.3", near_start is None or near_start.getextrema()[1] < alpha.getextrema()[1])
    off = dict(cfg, edgeGlow=False)
    check("glow can be switched off", tt.edge_glow_alpha(size, 0.3, off) is None)

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


def shown_theme_is(app, name):
    from utils.theme_manager import ThemeManager
    return (ThemeManager.get_current_theme() == name and app.sidebar._theme_name_label.cget("text") == name
            and app.root.cget("fg_color").upper() == ThemeManager.THEMES[name]["background"].upper())


def stray_colours(app, name):
    """CustomTkinter widgets under the window that hold a colour which is not a token of theme ``name``."""
    import _theme_contrast_test as contrast
    found = []
    contrast.audit_tree(app.root, name, "leak", found)
    return found


def test_on_screen():
    import customtkinter as ctk

    import _test_dialogs
    _test_dialogs.install()
    os.environ.pop("QRSTUDIO_NO_THEME_ANIMATION", None)      # this test is about the animation

    from ui.app import QRCodeStudioApp
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

    import tkinter

    def overlays():
        """The overlay windows (plain Toplevels: a Settings dialog is a CTkToplevel)."""
        return [w for w in root.winfo_children() if type(w) is tkinter.Toplevel]

    settle(0.5)
    check("start-up does not animate", not manager.running and manager.last_run is None and not overlays())
    tt.system_animations_enabled = lambda: True          # deterministic: "Animation effects" on
    check("animation is enabled by default", tt.enabled() is True)

    # --- a live change runs; the new theme is already applied underneath ---
    seen = {}

    def own_pixels(window, points):
        """Pixels of a window's own surface (PrintWindow of that window: nothing else on the screen).
        A window that was shown a moment ago may still answer blank: ask again for up to a second."""
        for _attempt in range(20):
            try:
                image = real_capture_client(window)
                break
            except tt.SnapshotError:
                time.sleep(0.05)
                window.update_idletasks()
        else:
            image = real_capture_client(window)
        return [image.getpixel(pt) for pt in points]

    taken = []
    real_capture_client = tt.capture_client

    def recording_capture(window):
        image = real_capture_client(window)
        taken.append(image)
        return image

    tt.capture_client = recording_capture
    points = [(40, 40), (400, 300), (900, 500), (1200, 700), (150, 400)]

    def change_emerald():
        shown = overlays()
        seen.update(count=len(shown), visible=bool(shown) and all(o.winfo_viewable() for o in shown), running=manager.running)
        if shown:
            seen["painted"] = own_pixels(shown[0], points) == [taken[0].getpixel(pt) for pt in points]
        ThemeManager.set_theme("Emerald", persist=False)
        app.refresh_theme()

    started = manager.run(change_emerald)
    tt.capture_client = real_capture_client
    check("the old picture is already on screen when the change is applied (the window does not look frozen)",
          seen.get("count") == 1 and seen.get("visible") is True and seen.get("running") is True, str(seen))
    check("... and it is really painted there (the overlay's own pixels are the old picture)",
          seen.get("painted") is True, str(seen))
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
    check("the overlay sits exactly over the client area",
          (box[0].winfo_rootx(), box[0].winfo_rooty()) == (root.winfo_rootx(), root.winfo_rooty()),
          f"{(box[0].winfo_rootx(), box[0].winfo_rooty())} vs {(root.winfo_rootx(), root.winfo_rooty())}")
    difference = np.abs(np.asarray(snap.renderer.old).astype(int) - np.asarray(snap.renderer.new).astype(int)).mean()
    check("the 'after' snapshot is the new theme, not the overlay (they differ)", difference > 3, f"{difference:.1f}")
    settle(0.35)
    check("frames are being shown and the window keeps answering", manager._frames >= 3, f"{manager._frames} frames")

    # --- a click skips to the end ---
    box[0].event_generate("<Button-1>", x=10, y=10)       # a click on the overlay
    settle(0.05)
    check("a click ends the animation at once", not manager.running and not overlays())
    check("... and the final theme stays", ThemeManager.get_current_theme() == "Emerald")

    # --- a click anywhere else in the app (the window itself, a dialog) skips as well ---
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    check("a click right at the start does not end it (the starting click is still being delivered)",
          manager.running)
    settle(0.3)
    check("click and key handlers are attached shortly after the start", len(manager._overlays[0].bindings) >= 3,
          str(len(manager._overlays[0].bindings)))
    root.event_generate("<ButtonPress-1>", x=40, y=40)
    settle(0.05)
    check("a click on the app window ends the animation", not manager.running and not overlays())

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

    # --- the overlay is a tool window: no taskbar button, not in Alt+Tab, never takes the focus ---
    import ctypes
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = ctypes.c_long
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    settle(0.2)
    handle = manager._overlays[0].top.winfo_id()
    ex = user32.GetWindowLongW(ctypes.c_void_p(handle), -20) & 0xFFFFFFFF
    check("overlay is a tool window", ex & tt.WS_EX_TOOLWINDOW, hex(ex))
    check("... that is not an app window (no taskbar button)", not ex & tt.WS_EX_APPWINDOW, hex(ex))
    check("... and never takes the focus", ex & tt.WS_EX_NOACTIVATE, hex(ex))

    def alt_tab_windows():
        """Visible top-level windows without an owner that are not tool windows: what Alt+Tab lists."""
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def collect(h, _):
            style = user32.GetWindowLongW(ctypes.c_void_p(h), -20) & 0xFFFFFFFF
            if user32.IsWindowVisible(ctypes.c_void_p(h)) and not user32.GetWindow(ctypes.c_void_p(h), 4)                     and not style & tt.WS_EX_TOOLWINDOW:
                found.append(h)
            return True

        user32.EnumWindows(collect, 0)
        return found

    check("Alt+Tab does not list the overlay", handle not in alt_tab_windows())
    manager.finish()

    # --- minimizing the window ends it ---
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settle(0.2)
    root.iconify()
    settle(0.3)
    check("minimizing the window ends the animation and removes the overlay", not manager.running and not overlays())
    root.deiconify()
    settle(0.5)
    check("... and the window comes back normally", root.state() in ("normal", "zoomed"))

    # --- losing the focus: only when the user really went to another program, and never in the first 300 ms ---
    real_focus = root.focus_displayof
    real_other = tt.another_program_has_focus

    def focus_out():
        root.event_generate("<FocusOut>")

    manager.run(lambda: (ThemeManager.set_theme("Ultraviolet", persist=False), app.refresh_theme()))
    settle(0.12)                                              # the skip handlers are attached by now
    root.focus_displayof = lambda: None
    tt.another_program_has_focus = lambda: True               # the user really is in another program ...
    focus_out()
    settle(0.12)                                              # ... but this is within the first 300 ms
    check("a focus change in the first 300 ms is ignored", manager.running)
    settle(0.3)
    focus_out()                                               # later: the same event ends it
    settle(0.3)
    check("focus really going to another program ends the animation", not manager.running and not overlays())

    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settle(0.5)
    root.focus_displayof = lambda: root                       # focus stays in the application
    tt.another_program_has_focus = lambda: True
    focus_out()
    settle(0.3)
    check("focus moving inside the application does not end the animation", manager.running)
    root.focus_displayof = lambda: None                       # no focus widget, but no other program in front either
    tt.another_program_has_focus = lambda: False
    focus_out()
    settle(0.3)
    check("a moment without focus (windows being activated) does not end it", manager.running)
    root.focus_displayof = real_focus
    tt.another_program_has_focus = real_other
    manager.finish()
    check("the foreground check works on this PC", tt.another_program_has_focus() in (True, False))

    # --- a worker that hangs never keeps the overlay (or the window) waiting ---
    real_render = tt.FrameRenderer.render

    def stuck(self, T, quality=1.0, phase=None):
        time.sleep(4)
        return real_render(self, T, quality, phase)

    tt.FrameRenderer.render = stuck
    try:
        manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()), duration=0.8)
        begun = time.time()
        while manager.running and time.time() - begun < 5:
            root.update()
            time.sleep(0.005)
        took = time.time() - begun
    finally:
        tt.FrameRenderer.render = real_render
    check("a hung worker: the overlay is gone on time (duration 0.8 s)", not manager.running and not overlays() and took < 1.4,
          f"{took:.1f} s")
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()), duration=3.0)
    settle(0.2)
    begun = time.time()
    manager.finish()
    check("finish() returns at once (it does not wait for workers)", time.time() - begun < 0.3, f"{time.time() - begun:.2f} s")

    # --- the safety timer ends it even when the frame loop itself has stopped ---
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()), duration=0.5)
    manager._tick = lambda: None                              # the loop dies
    settle(0.9)
    check("with the frame loop dead the overlay is still up before the safety limit", manager.running)
    settle(1.0)
    del manager._tick
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    check("the safety timer removes the overlay at duration + 1 s", not manager.running and not overlays()
          and tt.SAFETY_EXTRA_SEC == 1.0 and "was ended" in log)

    # --- moving the window ends it too (the overlay would no longer cover it) ---
    manager.run(lambda: (ThemeManager.set_theme("Ultraviolet", persist=False), app.refresh_theme()))
    settle(0.1)
    root.geometry("1280x800+60+50")
    settle(0.3)
    check("moving the window ends the animation", not manager.running and not overlays())
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
    check("... and a warning is logged", "not started (snapshot-failed" in log and "test failure" in log, log[-300:])

    # --- the Settings page: a click on a theme card animates the WHOLE window (the page included) ---
    ThemeManager.set_theme("Midnight", persist=False)
    app.refresh_theme()
    settle(0.3)
    app.sidebar.navigate("settings")
    settle(0.5)
    page = app.settings_page
    check("Settings is a page of the window, so no second window can hide the effect",
          page.winfo_toplevel() is root and app._current_page == "settings")
    runs = manager.runs
    taken.clear()
    tt.capture_client = recording_capture
    tile = page._tiles["Emerald"]
    tile._canvas.event_generate("<Button-1>", x=6, y=6)       # a real click on the theme card
    settle(0.05)
    tt.capture_client = real_capture_client
    check("a click on a theme card starts the animation", manager.runs == runs + 1 and manager.running)
    check("... on the main window, which holds the Settings page", len(manager._overlays) == 1
          and manager._overlays[0].window is root)
    check("... and the new theme is already applied underneath", ThemeManager.get_current_theme() == "Emerald"
          and page._selected == "Emerald")
    overlay = manager._overlays[0]
    check("overlay, snapshots and window have the same size", overlay.size == (root.winfo_width(), root.winfo_height())
          and all(img.size == overlay.size for img in taken), f"{overlay.size} {[i.size for i in taken]}")
    import numpy as np
    before_img, after_img = np.asarray(taken[0]).astype(int), np.asarray(taken[-1]).astype(int)
    check("the 'before' picture shows the Settings page in the old theme (Midnight background)",
          (np.abs(before_img - np.array([int(ThemeManager.THEMES['Midnight']['background'][i:i + 2], 16)
                                         for i in (1, 3, 5)])).sum(axis=2) < 6).mean() > 0.15)
    def share(image, theme, token, region=slice(None)):
        colour = np.array([int(ThemeManager.THEMES[theme][token][i:i + 2], 16) for i in (1, 3, 5)])
        return (np.abs(image[:, region] - colour).sum(axis=2) < 3).mean()

    sidebar_px = slice(0, int(overlay.size[0] * 0.15))
    check("the 'after' picture is the Settings page in the new theme (Emerald background, sidebar with no Midnight left)",
          share(after_img, "Emerald", "background") > 0.15 and share(after_img, "Midnight", "navbar", sidebar_px) == 0
          and share(after_img, "Emerald", "navbar", sidebar_px) > 0.5,
          f"{share(after_img, 'Emerald', 'background'):.2f} {share(after_img, 'Midnight', 'navbar', sidebar_px):.3f}")
    pts = [(x, y) for x in range(120, overlay.size[0] - 60, 260) for y in range(160, overlay.size[1] - 160, 190)]
    frame_a = own_pixels(overlay.top, pts)
    settle(0.4)
    frame_b = own_pixels(overlay.top, pts) if manager.running else frame_a
    check("frames change while it runs (the overlay's pixels differ from one moment to the next)",
          frame_a != frame_b, f"{len(pts)} points")
    end = time.time() + 4
    while manager.running and time.time() < end:
        settle(0.05)
    check("it ends in the new theme", not manager.running and not overlays() and shown_theme_is(app, "Emerald"))

    # Cancel brings the old theme back with the animation, and the page switch is part of it
    runs = manager.runs
    page.cancel_button.invoke()
    settle(0.1)
    check("Cancel reverts the theme with an animation", manager.runs == runs + 1 and manager.running
          and ThemeManager.get_current_theme() == "Midnight")
    check("... and the page it returns to is already showing under the effect", app._current_page == "generate")
    manager.finish()

    # leaving with changes and answering "Don't save": the old theme comes back with the animation too
    import _test_dialogs as dialogs
    app.sidebar.navigate("settings")
    settle(0.3)
    page.preview_theme("Ember")
    manager.finish()
    dialogs.answers["save_changes"] = "discard"
    runs = manager.runs
    app.sidebar.navigate("scan")
    settle(0.1)
    check("[Don't save] brings the old theme back with the animation", manager.runs == runs + 1 and manager.running
          and ThemeManager.get_current_theme() == "Midnight" and app._current_page == "scan")
    dialogs.answers.pop("save_changes")
    manager.finish()

    # the "Save changes?" window opens on screen, over the app
    from utils import window_guard
    page.preview_theme("Graphite")
    manager.finish()
    seen_box = {}

    def look_at_box():
        box = [w for w in root.winfo_children() if type(w).__name__ == "CTkToplevel"][-1]
        seen_box["rect"] = (box.winfo_rootx(), box.winfo_rooty(), box.winfo_rootx() + box.winfo_width(),
                            box.winfo_rooty() + box.winfo_height())
        box.event_generate("<Escape>")

    root.after(600, look_at_box)
    dialogs.real_ask_save_changes(root)
    areas = window_guard.work_areas()
    rect = seen_box.get("rect")
    centre = ((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2) if rect else (0, 0)
    area = next((a for a in areas if a[0] <= centre[0] < a[2] and a[1] <= centre[1] < a[3]), None)
    check("the 'Save changes?' window is fully on screen", area is not None and rect[0] >= area[0] and rect[1] >= area[1]
          and rect[2] <= area[2] and rect[3] <= area[3], f"{rect} in {area}")
    check("... and over the app window", rect is not None and root.winfo_rootx() <= centre[0] <= root.winfo_rootx() + root.winfo_width()
          and root.winfo_rooty() <= centre[1] <= root.winfo_rooty() + root.winfo_height(), str(rect))
    page.discard()
    manager.finish()

    # the switch decides at once, before it is applied
    app.sidebar.navigate("settings")
    settle(0.3)
    page.animate_var.set(False)
    runs = manager.runs
    page.preview_theme("Ember")
    check("the page's switch turns the animation off before Apply", manager.runs == runs and not manager.running
          and ThemeManager.get_current_theme() == "Ember")
    page.animate_var.set(True)
    page.cancel()
    manager.finish()
    check("leaving the page clears the override", tt.ENABLED_OVERRIDE is None)
    app.sidebar.navigate("settings")
    settle(0.3)
    check("the switch shows the saved value (on)", page.animate_var.get() is True)
    check("opening unchanged is no change", not page.has_changes())
    page.animate_var.set(False)
    check("changing the switch counts as a change", page.has_changes())
    check("Apply saves it", page.apply() is True and settings_store.get(tt.SETTING_KEY) is False)
    settings_store.set(tt.SETTING_KEY, True)
    page.cancel()
    settle(0.3)
    manager.finish()

    # --- changes never overlap: one that arrives while another is being set up waits and runs next ---
    ThemeManager.set_theme("Midnight", persist=False)
    app.refresh_theme()
    settle(0.3)
    orig_init = tt._Overlay.__init__
    state = {"n": 0}

    def nested_init(self, *a, **k):
        orig_init(self, *a, **k)
        if state["n"] == 0:                                   # a second request arrives right here
            state["n"] = 1
            state["nested_result"] = app.change_theme("Ember")

    tt._Overlay.__init__ = nested_init
    try:
        manager.run(lambda: (ThemeManager.set_theme("Emerald", persist=False), app.refresh_theme()))
    finally:
        tt._Overlay.__init__ = orig_init
    settle(0.2)
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    check("the request that arrived during set-up waits and then runs; the latest wins",
          ThemeManager.get_current_theme() == "Ember" and manager.running and len(manager._overlays) == 1
          and "it runs next" in log, f"{ThemeManager.get_current_theme()} running={manager.running}")
    manager.finish()
    check("no overlay is left without a renderer (the old 'NoneType' failure)", "NoneType" not in log, log[-400:])
    check("the window shows one theme only", shown_theme_is(app, "Ember") and not stray_colours(app, "Ember"),
          str(stray_colours(app, "Ember")[:3]))
    # the same when the second request comes from inside the refresh itself
    fired = {"n": 0}
    orig_refresh = app.sidebar.refresh_theme

    def refresh_then_ask():
        orig_refresh()
        if fired["n"] == 0:
            fired["n"] = 1
            app.change_theme("Daylight")

    app.sidebar.refresh_theme = refresh_then_ask
    try:
        manager.run(lambda: (ThemeManager.set_theme("Aqua Mint", persist=False), app.refresh_theme()))
        settle(0.3)
    finally:
        app.sidebar.refresh_theme = orig_refresh
    manager.finish()
    check("a change asked for from inside a refresh ends with the latest theme, complete",
          ThemeManager.get_current_theme() == "Daylight" and shown_theme_is(app, "Daylight")
          and not stray_colours(app, "Daylight"), str(stray_colours(app, "Daylight")[:3]))

    # --- the log says what happened to every change ---
    log_before = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()), duration=0.6)
    end = time.time() + 3
    while manager.running and time.time() < end:
        settle(0.05)
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settle(0.3)
    root.event_generate("<ButtonPress-1>", x=40, y=40)
    settle(0.1)
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    settle(0.3)
    root.event_generate("<Key>", keysym="a")
    settle(0.1)
    manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()))
    settle(0.3)
    root.geometry("1200x760+20+20")
    settle(0.3)
    root.geometry("1280x800+20+20")
    settle(0.3)
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    settle(0.3)
    root.geometry("1280x800+60+50")
    settle(0.3)
    root.geometry("1280x800+20+20")
    settle(0.3)
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settle(0.3)
    root.iconify()
    settle(0.3)
    root.deiconify()
    settle(0.5)
    manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()))
    settle(0.2)
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    settle(0.2)
    manager.finish("test")
    settings_store.set(tt.SETTING_KEY, False)
    manager.run(lambda: (ThemeManager.set_theme("Graphite", persist=False), app.refresh_theme()))
    settings_store.set(tt.SETTING_KEY, True)
    tt.system_animations_enabled = lambda: False
    manager.run(lambda: (ThemeManager.set_theme("Midnight", persist=False), app.refresh_theme()))
    tt.system_animations_enabled = lambda: True
    os.environ["QRSTUDIO_NO_THEME_ANIMATION"] = "1"
    manager.run(lambda: (ThemeManager.set_theme("Ember", persist=False), app.refresh_theme()))
    del os.environ["QRSTUDIO_NO_THEME_ANIMATION"]
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()[len(log_before):]
    for expected in ("Theme transition started", "Theme transition finished", "skipped (click)", "skipped (key)",
                     "skipped (resized)", "skipped (moved)", "skipped (minimized)", "skipped (new-change)",
                     "not started (setting-off)", "not started (windows-animations-off)",
                     "not started (disabled-by-environment)"):
        check(f"the log records '{expected}'", expected in log, log[-600:])
    check("every start is followed by a finish or a skip",
          log.count("Theme transition started") == log.count("Theme transition finished") + log.count("skipped ("),
          f"{log.count('Theme transition started')} started, {log.count('Theme transition finished')} finished, "
          f"{log.count('skipped (')} skipped")

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
          "move / resize / minimize / focus, changes never overlap, log reasons, off switches, Settings page, scalings, benchmark")
