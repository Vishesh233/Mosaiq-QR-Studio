"""Colour presets and the contrast advice.

Run:  .venv\\Scripts\\python.exe _design_features_test.py
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
os.environ["APPDATA"] = tempfile.mkdtemp()

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def test_contrast_rules():
    from utils import qr_checks
    from utils.qr_render import QRStyle

    def verdict(**kw):
        return qr_checks.check_style(QRStyle(**kw))

    good = verdict(fg="#000000", bg="#FFFFFF")
    check("black on white is good", good.level == "good" and good.text == qr_checks.GOOD_TEXT)
    check("brand blue on white is good", verdict(fg="#0E7490", bg="#FFFFFF").level == "good")

    for label, kw in (
        ("yellow on white", dict(fg="#FFEB3B", bg="#FFFFFF")),
        ("light grey on white", dict(fg="#BBBBBB", bg="#FFFFFF")),
        ("dark on dark", dict(fg="#222222", bg="#111111")),
        ("same colour", dict(fg="#336699", bg="#336699")),
        ("one gradient end near the background",
         dict(fg="#000000", fg2="#F4F4F4", bg="#FFFFFF", gradient="linear")),
        ("gradient middle crossing the background",
         dict(fg="#000000", fg2="#000000", bg="#FFFFFF", gradient="linear")),   # sanity: this one is fine
    ):
        v = verdict(**kw)
        if label == "gradient middle crossing the background":
            check(label + " (control, identical stops = solid)", v.level == "good")
            continue
        check(f"{label} warns", v.level == "warn" and v.text == qr_checks.LOW_CONTRAST_TEXT,
              f"{v.level}: {v.text}")
    check("exact wording", qr_checks.LOW_CONTRAST_TEXT == "These colours may not scan. Try more contrast.")

    # a gradient ending near the background warns even though the first colour is fine
    v = verdict(fg="#000000", fg2="#EEEEEE", bg="#FFFFFF", gradient="radial")
    check("radial gradient with a pale end warns", v.level == "warn")
    # the same colours without the gradient are fine (the second colour is not used)
    v = verdict(fg="#000000", fg2="#EEEEEE", bg="#FFFFFF", gradient="none")
    check("second colour ignored without a gradient", v.level == "good")

    inv = verdict(fg="#FFFFFF", bg="#000000")
    check("light on dark gets its own advice", inv.level == "warn" and inv.text == qr_checks.INVERTED_TEXT,
          f"{inv.level}: {inv.text}")
    check("threshold boundary", verdict(fg="#767676", bg="#FFFFFF").level == "good"      # 4.5:1
          and verdict(fg="#CCCCCC", bg="#FFFFFF").level == "warn")                       # 1.6:1


def test_presets():
    from utils import qr_checks, qr_presets
    from utils import qr_payloads as p
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle
    from utils.qr_scanner import QRScanner

    names = [preset.name for preset in qr_presets.PRESETS]
    check("6 to 8 presets", 6 <= len(names) <= 8, str(names))
    check("the named ones exist", all(n in names for n in
          ("Classic", "Midnight", "Ocean", "Sunset", "Mint", "Mono")), str(names))
    check("names are unique", len(set(names)) == len(names))
    check("Classic is the default look", qr_presets.get("Classic").style == QRStyle())

    generator = QRGenerator()
    samples = ("https://example.com/preset", p.build_upi("shop@okaxis", "Shop", "10", "x"),
               p.build_wifi("Net", "pw123456", "WPA"))
    for preset in qr_presets.PRESETS:
        verdict = qr_checks.check_style(preset.style)
        check(f"{preset.name}: good contrast", verdict.level == "good",
              f"{verdict.text} ({verdict.worst_ratio:.1f}:1)")
        check(f"{preset.name}: recognised as itself", qr_presets.matching(preset.style) == preset.name)
        for text in samples:
            image = generator.generate(text, style=preset.style).convert("RGB")
            check(f"{preset.name}: scans ({text[:12]})",
                  QRScanner.decode_image(image, thorough=False) == text)
    check("a changed colour matches no preset",
          qr_presets.matching(qr_presets.get("Ocean").style.with_(fg="#123456")) is None)
    check("logo size does not affect matching",
          qr_presets.matching(qr_presets.get("Ocean").style.with_(logo_scale=0.1)) == "Ocean")


def test_background_check():
    from PIL import Image
    from utils import self_check
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle

    generator = QRGenerator()
    good = generator.generate("https://example.com/check")
    blank = Image.new("RGB", (300, 300), "white")
    check("good code passes", self_check.check_image(good, "https://example.com/check") == self_check.OK)
    check("wrong text fails", self_check.check_image(good, "something else") == self_check.FAIL)
    check("blank image fails", self_check.check_image(blank, "x") == self_check.FAIL)
    pale = generator.generate("https://example.com/check", style=QRStyle(fg="#F8F8F8"))
    check("near-white on white fails", self_check.check_image(pale, "https://example.com/check")
          == self_check.FAIL)

    # only the newest request is reported
    runner = self_check.BackgroundCheck()
    runner.start(blank, "x")
    runner.start(good, "https://example.com/check")
    outcome = None
    end = time.time() + 15
    while outcome is None and time.time() < end:
        outcome = runner.poll()
        time.sleep(0.02)
    check("newest request wins", outcome == self_check.OK, repr(outcome))
    time.sleep(0.5)
    check("stale results are dropped", runner.poll() is None)
    runner.start(good, "https://example.com/check")
    runner.cancel()
    time.sleep(1.5)
    check("cancelled request reports nothing", runner.poll() is None)

    # OpenCV missing / crashing: reported, never raised
    original = self_check.QRScanner.decode_image
    from utils.scan_errors import ScannerUnavailable

    def unavailable(*a, **k):
        raise ScannerUnavailable("no cv2")

    def crash(*a, **k):
        raise RuntimeError("boom")

    try:
        self_check.QRScanner.decode_image = staticmethod(unavailable)
        check("unavailable reported", self_check.check_image(good, "x") == self_check.UNAVAILABLE)
        self_check.QRScanner.decode_image = staticmethod(crash)
        check("crash reported, not raised", self_check.check_image(good, "x") == self_check.ERROR)
        from utils import app_log
        for handler in app_log.get_logger().handlers:
            handler.flush()
        log = open(app_log.log_path(), encoding="utf-8").read()
        check("crash written to the error log", "Test scan crashed" in log and "boom" in log)
    finally:
        self_check.QRScanner.decode_image = original


def test_ui():
    from ui.app import QRCodeStudioApp
    from utils import qr_checks, qr_presets
    from utils.theme_manager import ThemeManager

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()
    gp = app.generate_page
    card = gp.design_card

    def wait_redraw():
        end = time.time() + 0.5
        while time.time() < end:
            root.update()
            time.sleep(0.02)

    theme = ThemeManager.get_theme()
    check("hint starts with good contrast", qr_checks.GOOD_TEXT in card.hint.cget("text"))
    check("Classic highlighted at start", card.colours.preset_row._selected == "Classic")

    gp.content_card.url_entry.insert(0, "https://example.com/presets")
    gp.generate_qr()
    redraws = []
    original = gp.preview_card.set_image
    gp.preview_card.set_image = lambda *a, **k: (redraws.append(1), original(*a, **k))[1]

    # a preset sets every field and redraws the preview exactly once
    tile = card.colours.preset_row._frames["Ocean"]._canvas
    tile.event_generate("<ButtonPress-1>", x=3, y=3, when="now")
    root.update()
    if card.colours.preset_row._selected != "Ocean":   # a fresh window can swallow the first click
        tile.event_generate("<ButtonPress-1>", x=3, y=3, when="now")
    wait_redraw()
    ocean = qr_presets.get("Ocean").style
    style = card.get_style()
    check("preset sets colours", (style.fg, style.bg) == (ocean.fg, ocean.bg), f"{style.fg} {style.bg}")
    check("preset sets shapes and gradient",
          (style.module_shape, style.eye_shape, style.gradient, style.fg2) ==
          (ocean.module_shape, ocean.eye_shape, ocean.gradient, ocean.fg2))
    check("the swatches show the preset colours", card.colours.qr_hex.cget("text") == ocean.fg)
    check("the Style tab shows the preset", card.style.module_shape == "rounded"
          and card.style.gradient == "linear")
    check("preset highlighted", card.colours.preset_row._selected == "Ocean")
    check("preview redrawn once", len(redraws) == 1, f"{len(redraws)} redraws")

    # preset keeps the logo
    card.logo.logo_path = None
    card.apply_preset("Mono")
    wait_redraw()
    check("another preset replaces the look", card.get_style().fg == qr_presets.get("Mono").style.fg)

    # editing a colour afterwards leaves no preset highlighted
    card.colours.set_colors(qr="#123456")
    wait_redraw()
    check("no preset highlighted after a manual change", card.colours.preset_row._selected is None)

    # low contrast: the warning shows, Generate still works
    card.colours.set_colors(qr="#FFEB3B", bg="#FFFFFF")
    card.style.set_style(gradient="none")
    wait_redraw()
    check("warning shown for low contrast",
          qr_checks.LOW_CONTRAST_TEXT in card.hint.cget("text"), card.hint.cget("text"))
    check("warning uses the warning colour", card.hint.cget("text_color") == ThemeManager.get_theme()["warning"])
    gp.generated_image = None
    gp.generated_data = None
    gp.generate_qr()
    check("low contrast does not block Generate", gp.generated_image is not None)
    check("... and the buttons are enabled", str(gp.action_buttons.save_btn.cget("state")) == "normal")

    # a gradient end near the background warns
    card.colours.set_colors(qr="#000000", bg="#FFFFFF")
    card.style.set_style(gradient="linear", gradient_end="#F8F8F8")
    check("pale gradient end warns", qr_checks.LOW_CONTRAST_TEXT in card.hint.cget("text"))
    card.style.set_style(gradient_end="#1E3A8A")
    check("dark gradient end clears the warning", qr_checks.GOOD_TEXT in card.hint.cget("text"))

    # light on dark
    card.style.set_style(gradient="none")
    card.colours.set_colors(qr="#FFFFFF", bg="#000000")
    check("light on dark advice", qr_checks.INVERTED_TEXT in card.hint.cget("text"))

    # ---- test-scan badge ----
    def badge():
        return gp.preview_card.badge.cget("text")

    def wait_badge(seconds=15):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            if not badge().startswith("Checking"):
                return badge()
            time.sleep(0.02)
        return badge()

    gp.clear_form()
    check("no badge before a QR exists", not gp.preview_card.badge.winfo_manager())
    gp.content_card.url_entry.insert(0, "https://example.com/badge")
    gp.generate_qr()
    check("badge says it is checking", badge().startswith("Checking"), badge())
    text = wait_badge()
    check("good code: scans correctly", "Scans correctly" in text and "URL / text" in text, text)
    check("good badge is green", gp.preview_card.badge.cget("text_color") ==
          ThemeManager.get_theme()["success"])
    card.colours.set_colors(qr="#F8F8F8", bg="#FFFFFF")          # live redraw -> new test scan
    time.sleep(0.2)
    text = wait_badge()
    check("pale code: may not scan", "May not scan" in text, text)
    check("warning badge is amber", gp.preview_card.badge.cget("text_color") ==
          ThemeManager.get_theme()["warning"])
    check("Generate and Save still allowed with the warning",
          str(gp.action_buttons.save_btn.cget("state")) == "normal")
    card.colours.set_colors(qr="#000000")
    time.sleep(0.2)
    check("fixed colours: scans correctly again", "Scans correctly" in wait_badge())
    gp.content_card.set_type("UPI Payment")
    form = gp.content_card.forms["UPI Payment"]
    for fld, val in ((form.upi_id, "shop@okaxis"), (form.payee, "Corner Shop")):
        fld.widget.insert(0, val)
    gp.generate_qr()
    check("badge names the type", "UPI payment" in wait_badge(), badge())

    # the window keeps answering while the test scan runs on its thread
    big = "https://example.com/" + "long/" * 120
    gp.content_card.set_type("URL / Text")
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, big)
    gp.generate_qr()
    worst, last = 0.0, time.time()
    end = time.time() + 6
    while time.time() < end and badge().startswith("Checking"):
        root.update()
        now = time.time()
        worst, last = max(worst, now - last), now
        time.sleep(0.005)
    check("UI not frozen by the test scan", worst < 0.35, f"worst gap {worst:.2f}s")

    gp.clear_form()
    check("Clear removes the badge", not gp.preview_card.badge.winfo_manager())
    gp.content_card.clear()

    # ---- logo size slider ----
    import tempfile as _tmp
    from PIL import Image
    logo_file = os.path.join(_tmp.mkdtemp(), "logo.png")
    Image.new("RGBA", (120, 120), (200, 30, 60, 255)).save(logo_file)
    logo = card.logo
    check("slider disabled without a logo", str(logo.size_slider.cget("state")) == "disabled")
    gp.content_card.set_type("URL / Text")
    gp.content_card.url_entry.insert(0, "a")                        # a version 1 code: smallest limit
    card.show_tab("Logo")
    root.update()
    check("limit follows the typed content (small code)",
          "Safe up to 18%" in logo.limit_label.cget("text"), logo.limit_label.cget("text"))
    logo.set_logo(logo_file)
    root.update()
    check("slider enabled with a logo", str(logo.size_slider.cget("state")) == "normal")
    check("default size inside the limit", logo.get_logo_scale() <= 0.18 + 1e-9, str(logo.get_logo_scale()))
    logo._slid(100)                                                  # far beyond the track
    check("size cannot pass the limit", logo.get_logo_scale() <= 0.18 + 1e-9, str(logo.get_logo_scale()))
    check("label shows the size", f"{int(round(logo.get_logo_scale() * 100))}%" in logo.size_label.cget("text"))
    gp.generate_qr()
    check("small code with logo scans", "Scans correctly" in wait_badge(), badge())
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, "https://example.com/a/much/longer/address/for/a/bigger/code/" * 2)
    logo.refresh_limit()
    check("limit grows with a bigger code", "Safe up to 30%" in logo.limit_label.cget("text"),
          logo.limit_label.cget("text"))
    logo._slid(30)
    check("larger size allowed on a bigger code", abs(logo.get_logo_scale() - 0.30) < 1e-9)
    gp.generate_qr()
    check("bigger code with the largest logo scans", "Scans correctly" in wait_badge(), badge())
    drawn = gp.generated_image
    # content shrinks to a tiny code: the size snaps down instead of exceeding the limit
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, "a")
    gp.generate_qr()
    check("size snaps to the new limit", logo.get_logo_scale() <= 0.18 + 1e-9
          and "Safe up to 18%" in logo.limit_label.cget("text"))
    check("the slider moved with it", abs(logo.size_slider.get() - logo.get_logo_scale() * 100) < 0.6)
    check("tiny code with logo still scans", "Scans correctly" in wait_badge(), badge())
    logo.reset_logo()
    check("removing the logo disables the slider", str(logo.size_slider.cget("state")) == "disabled")
    gp.clear_form()
    gp.content_card.clear()
    gp.content_card.url_entry.insert(0, "https://example.com/layout")

    # Clear resets look and hint
    gp.clear_form()
    check("Clear restores Classic and good contrast",
          card.colours.preset_row._selected == "Classic" and qr_checks.GOOD_TEXT in card.hint.cget("text"))

    # theme switch keeps the hint readable
    for name in ThemeManager.get_theme_names():
        ThemeManager.set_theme(name, persist=False)
        app.refresh_theme()
        check(f"{name}: hint colour is a token",
              card.hint.cget("text_color").upper() in (ThemeManager.get_theme()["success"].upper(),
                                                      ThemeManager.get_theme()["warning"].upper()))
    app.close()


def main():
    test_contrast_rules()
    test_presets()
    test_background_check()
    test_ui()
    if problems:
        print("DESIGN_FEATURES_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("DESIGN_FEATURES_OK: contrast rules, presets, test-scan badge (background thread), logo size limits, warning never blocks")


if __name__ == "__main__":
    main()
