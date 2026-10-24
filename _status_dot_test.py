"""The status dot in front of the card titles (Live Preview, Result, Summary, Details).

Dim while the card is empty (a dull core, a faint halo); bright with a strong soft glow once it
holds a result; back to dim on Clear, on invalid input and when the result is gone. The change fades in
(about 180 ms) without slowing the window, and the dot follows every theme. The dots are lit lamps:
the glow is a smooth falloff with no outline or ring anywhere (checked on the drawn pixels).

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
    from ui.widgets import StatusDot, ThemeDot
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
        """(core colour, glow strength) as drawn right now."""
        colour, _spread, strength, _hot = dot.current_look()
        return colour.upper(), strength

    def state(name, dot, want):
        settle(0.35)
        end = time.time() + 3                    # a busy page (Bulk redraws its table) may delay the fade
        while dot._job is not None and time.time() < end:
            settle(0.05)
        theme = ThemeManager.get_theme()
        dim, bright = theme["text_muted"].upper(), theme["success"].upper()
        core, strength = shown(dot)
        if want:
            check(f"{name}: bright after the fade", dot.active and core == bright, f"{core} vs {bright}")
            check(f"{name}: strong glow", strength >= 0.9, str(strength))
        else:
            check(f"{name}: dim", not dot.active and core == dim, f"{core} vs {dim}")
            check(f"{name}: only a faint halo", strength <= 0.2, str(strength))

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
    look = sidebar_dot.current_look()
    check("sidebar dot: accent colour with a strong glow", look[0].upper() == ThemeManager.get_theme()["primary"].upper()
          and look[2] >= 0.8, str(look))
    ThemeManager.set_theme("Ember", persist=False)
    app.refresh_theme()
    settle(0.07)
    check("sidebar dot: animating right after a theme change", 0 < sidebar_dot._t < 1, f"t={sidebar_dot._t}")
    mid = sidebar_dot.current_look()
    check("sidebar dot: mid-animation the glow swells", mid[1] > ThemeDot.GLOW[0], str(mid))
    settle(0.6)
    check("sidebar dot: finished on the new accent colour",
          sidebar_dot.current_look()[0].upper() == ThemeManager.get_theme()["primary"].upper()
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
        app.ensure_themed()              # pages that were hidden follow when they are shown
        settle(0.1)
        theme = ThemeManager.get_theme()
        for page, d in dots.items():
            d.set_active(False)
        settle(0.3)
        for page, d in dots.items():
            core, _strength = shown(d)
            check(f"{name}/{page}: dim colour is the theme's muted colour", core == theme["text_muted"].upper(), core)
            check(f"{name}/{page}: surface behind the dot is the card colour",
                  d.cget("bg").upper() == theme["card"].upper(), d.cget("bg"))
        d = dots["Scan"]
        d.set_active(True)
        settle(0.3)
        core, strength = shown(d)
        check(f"{name}: bright colour is the theme's success colour", core == theme["success"].upper(), core)
        check(f"{name}: strong glow", strength >= 0.9, str(strength))
        d.set_active(False)
        settle(0.3)

    # ---- the drawn pixels: a lit lamp, no outline, a strong smooth glow, a crisp core ----
    from ui import glow
    for name in ThemeManager.get_theme_names():
        t = ThemeManager.THEMES[name]
        for label, surface, colour, core_r, spread, strength, hot in (
                ("status dot lit", t["card"], t["success"], StatusDot.CORE, StatusDot.GLOW_LIT[0], StatusDot.GLOW_LIT[1],
                 StatusDot.HOT if t["mode"] == "Dark" else 0.0),
                ("status dot idle", t["card"], t["text_muted"], StatusDot.CORE, StatusDot.GLOW_IDLE[0], StatusDot.GLOW_IDLE[1], 0.0),
                ("theme dot", t["navbar"], t["primary"], ThemeDot.CORE, ThemeDot.GLOW[0], ThemeDot.GLOW[1],
                 ThemeDot.HOT if t["mode"] == "Dark" else 0.0)):
            for scale in (1.0, 1.25, 1.5):
                size = StatusDot.SIZE if "status" in label else ThemeDot.SIZE
                side = round(size * scale)
                img = glow.render(side, surface.upper(), colour.upper(), round(core_r * scale, 2),
                                  round(spread * scale, 2), round(strength, 3), round(hot, 3))
                mid = side // 2
                row = [img.getpixel((mid + dx, mid)) for dx in range(0, side // 2)]
                bg = colors.hex_to_rgb(surface)
                dist = [sum((a - b) ** 2 for a, b in zip(px, bg)) ** 0.5 for px in row]
                total = max(dist) or 1
                # no outline or ring: moving away from the middle never gets lighter again, and never jumps
                # (the core edge, a single anti-aliased step, may drop by up to half the range)
                rises = [dist[i + 1] - dist[i] for i in range(len(dist) - 1)]
                check(f"{name}/{label}@{int(scale * 100)}%: no ring (the glow only fades outwards)",
                      max(rises) <= 0.04 * total + 3, f"largest rise {max(rises):.1f} of {total:.0f}")
                edge = int(core_r * scale) + 2
                check(f"{name}/{label}@{int(scale * 100)}%: the glow reaches the edge of the image smoothly",
                      dist[-1] <= 0.02 * total + 2, f"{dist[-1]:.1f} of {total:.0f}")
                if label != "status dot idle":
                    check(f"{name}/{label}@{int(scale * 100)}%: strong glow just outside the core",
                          dist[min(edge, len(dist) - 1)] >= 0.2 * total, f"{dist[min(edge, len(dist) - 1)]:.0f} of {total:.0f}")
                corners = [img.getpixel(pt) for pt in ((0, 0), (side - 1, 0), (0, side - 1), (side - 1, side - 1))]
                check(f"{name}/{label}@{int(scale * 100)}%: nothing at the corners (no square)",
                      all(sum((a - b) ** 2 for a, b in zip(px, bg)) ** 0.5 <= 2 for px in corners), str(corners))

    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print("STATUS_DOT_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("STATUS_DOT_OK: dim -> result -> bright -> clear -> dim on Generate, Scan, Bulk and History; fade; every theme")
