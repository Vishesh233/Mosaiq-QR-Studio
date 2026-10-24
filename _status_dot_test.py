"""The status dot in front of the card titles (Live Preview, Result, Summary, Details).

Dim while the card is empty; bright with a glow ring once it holds a result; back to dim on
Clear, on invalid input and when the result is gone. The change fades in (about 180 ms) without
slowing the window, and the dot follows every theme.

Run:  .venv\\Scripts\\python.exe _status_dot_test.py
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


def main():
    import _test_dialogs
    dialogs = _test_dialogs.install()

    from ui.app import QRCodeStudioApp
    from ui.widgets import StatusDot
    from utils import bulk_csv, colors, history_store
    from utils.qr_generator import QRGenerator
    from utils.theme_manager import ThemeManager

    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x820+-30000+-30000")
    root.update()

    def settle(seconds=0.4):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def shown(dot):
        """(dot colour, ring colour or None) as drawn right now (read from the canvas)."""
        fills = [dot.itemcget(item, "fill") for item in dot.find_all()]
        return (fills[-1].upper(), fills[0].upper() if len(fills) > 1 else None)

    def state(name, dot, want):
        settle(0.35)
        end = time.time() + 3                    # a busy page (Bulk redraws its table) may delay the fade
        while dot._job is not None and time.time() < end:
            settle(0.05)
        theme = ThemeManager.get_theme()
        dim, bright = theme["text_muted"].upper(), theme["success"].upper()
        core, ring = shown(dot)
        if want:
            check(f"{name}: bright after the fade", dot.active and core == bright, f"{core} vs {bright}")
            check(f"{name}: glow ring shown", ring is not None and ring != core, str(ring))
        else:
            check(f"{name}: dim", not dot.active and core == dim, f"{core} vs {dim}")
            check(f"{name}: no glow ring", ring is None, str(ring))

    # ---- the dots exist on the four cards ----
    gp, sp, hp, bp = app.generate_page, app.scan_page, app.history_page, app.bulk_page
    dots = {"Generate": gp.preview_card.status_dot, "Scan": sp.result_card.status_dot,
            "History": hp.details.status_dot, "Bulk": bp.summary.status_dot}
    for name, dot in dots.items():
        check(f"{name}: has a StatusDot", isinstance(dot, StatusDot))

    # ---- Generate: dim -> QR -> bright -> invalid -> dim -> QR -> Clear -> dim ----
    app.show_generate_page()
    state("Generate at start", dots["Generate"], False)
    gp.content_card.url_entry.insert(0, "https://example.com/dot")
    gp.generate_qr()
    state("Generate with a QR", dots["Generate"], True)
    gp.content_card.url_entry.delete(0, "end")
    gp.generate_qr()
    warnings = [c for c in dialogs.calls if c[0] == "showwarning"]
    check("Generate: invalid input warned", bool(warnings))
    dialogs.expect(*warnings)
    state("Generate after invalid input", dots["Generate"], False)
    gp.content_card.url_entry.insert(0, "https://example.com/dot2")
    gp.generate_qr()
    state("Generate with a QR again", dots["Generate"], True)
    gp.clear_form()
    state("Generate after Clear", dots["Generate"], False)

    # ---- Scan: dim -> result -> bright -> nothing decoded -> dim -> result -> Clear -> dim ----
    app.show_scan_page()
    rc = sp.result_card
    state("Scan at start", dots["Scan"], False)
    rc.set_result("https://example.com/scanned")
    state("Scan with a result", dots["Scan"], True)
    rc.set_message("No QR code found in this image.")
    state("Scan with an error message", dots["Scan"], False)
    rc.set_result("hello text")
    state("Scan with a result again", dots["Scan"], True)
    rc.clear()
    state("Scan after Clear", dots["Scan"], False)

    # ---- Bulk: dim -> CSV loaded -> bright -> unusable file -> dim ----
    app.show_bulk_page()

    def write(text):
        path = os.path.join(tempfile.mkdtemp(), "rows.csv")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    state("Bulk at start", dots["Bulk"], False)
    bp.load_csv(write(bulk_csv.SAMPLE_CSV))
    state("Bulk with a CSV", dots["Bulk"], True)
    bp.load_csv(write(""))
    state("Bulk with an empty file", dots["Bulk"], False)
    bp.load_csv(write("type,content\nfax,hello\n"))
    state("Bulk with only bad rows", dots["Bulk"], False)
    bp.load_csv(write("content\nhttps://example.com/a\n"))
    state("Bulk with a CSV again", dots["Bulk"], True)

    # ---- History: dim -> item selected -> bright -> deleted -> dim ----
    gen = QRGenerator()
    history_store.add_scanned("https://example.com/h", "URL / Text", gen.generate("https://example.com/h"))
    app.show_history_page()
    state("History with nothing selected", dots["History"], False)
    hp.select(history_store.entries()[0]["id"])
    state("History with an item selected", dots["History"], True)
    hp._delete()
    state("History after Delete", dots["History"], False)

    # ---- the fade: in between for a moment, done in well under half a second ----
    app.show_scan_page()
    settle(0.3)                                  # the page must be on screen for a fade to be seen
    dot = dots["Scan"]
    rc.set_result("fade check")
    settle(0.02)
    check("fade: the dot is part-way right after the change", 0 < dot._level < 1, f"level {dot._level}")
    settle(0.4)
    check("fade: finished within 0.4 s", dot._level == 1.0, f"level {dot._level}")
    rc.clear()
    settle(0.4)

    # ---- cheap: many changes cost next to nothing ----
    started = time.time()
    for index in range(300):
        dot.set_active(index % 2 == 0)
        root.update_idletasks()
    check("300 state changes take well under a second", time.time() - started < 1.0, f"{time.time() - started:.2f}s")
    dot.set_active(False)
    settle(0.3)

    # ---- the sidebar's theme dot: accent colour with a glow; a theme change blends and pulses ----
    sidebar_dot = app.sidebar._theme_dot
    settle(0.5)
    ThemeManager.set_theme("Aqua Mint", persist=False)
    app.refresh_theme()
    settle(0.5)
    fills = [sidebar_dot.itemcget(i, "fill").upper() for i in sidebar_dot.find_all()]
    check("sidebar dot: accent colour with a glow ring", fills[-1] == ThemeManager.get_theme()["primary"].upper()
          and len(fills) == 2 and fills[0] != fills[-1], str(fills))
    ThemeManager.set_theme("Ember", persist=False)
    app.refresh_theme()
    settle(0.07)
    check("sidebar dot: animating right after a theme change", 0 < sidebar_dot._t < 1, f"t={sidebar_dot._t}")
    mid = [sidebar_dot.itemcget(i, "fill").upper() for i in sidebar_dot.find_all()]
    check("sidebar dot: mid-animation shows an extra spreading ring", len(mid) == 3, str(mid))
    settle(0.6)
    check("sidebar dot: finished on the new accent colour",
          sidebar_dot.itemcget(sidebar_dot.find_all()[-1], "fill").upper() == ThemeManager.get_theme()["primary"].upper()
          and sidebar_dot._t == 1.0)
    check("theme name shows the new theme in its normal colour",
          app.sidebar._theme_name_label.cget("text") == "Ember"
          and app.sidebar._theme_name_label.cget("text_color").upper() == ThemeManager.get_theme()["text_secondary"].upper())
    ThemeManager.set_theme("Aqua Mint", persist=False)
    app.refresh_theme()
    settle(0.6)

    # ---- every theme: dim is visible, bright is clearly different, both follow a theme change ----
    for name in ThemeManager.get_theme_names():
        ThemeManager.set_theme(name, persist=False)
        app.refresh_theme()
        settle(0.1)
        theme = ThemeManager.get_theme()
        for page, d in dots.items():
            d.set_active(False)
        settle(0.3)
        for page, d in dots.items():
            core, ring = shown(d)
            check(f"{name}/{page}: dim colour is the theme's muted colour", core == theme["text_muted"].upper(), core)
            check(f"{name}/{page}: surface behind the dot is the card colour",
                  d.cget("bg").upper() == theme["card"].upper(), d.cget("bg"))
        d = dots["Scan"]
        d.set_active(True)
        settle(0.3)
        core, ring = shown(d)
        check(f"{name}: bright colour is the theme's success colour", core == theme["success"].upper(), core)
        check(f"{name}: ring is between card and bright", ring is not None
              and ring not in (theme["card"].upper(), core), str(ring))
        d.set_active(False)
        settle(0.3)

    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("STATUS_DOT_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("STATUS_DOT_OK: dim -> result -> bright -> clear -> dim on Generate, Scan, Bulk and History; fade; every theme")
