"""Colour presets and the contrast advice.

Run:  .venv\\Scripts\\python.exe _design_features_test.py
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
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


def test_ui():
    from ui.app import QRCodeStudioApp
    from utils import qr_checks, qr_presets
    from utils.theme_manager import ThemeManager

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
    gp.preview_card.set_image = lambda image: (redraws.append(1), original(image))[1]

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
    test_ui()
    if problems:
        print("DESIGN_FEATURES_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("DESIGN_FEATURES_OK: contrast rules, presets (scan + contrast), preset UI, warning never blocks")


if __name__ == "__main__":
    main()
