"""Theme leak audit: after a theme change the window must show ONE theme, whatever happened on the way.

A "leak" is a widget (or painted area) that still holds a colour of an earlier theme. The audit checks both
what every CustomTkinter widget is configured with (all pages, hidden ones too: Generate, Scan, History,
Bulk Create, Settings) and what is really painted (a PrintWindow snapshot of the app window only: no colour of
another theme may cover a noticeable area).

It runs many switch sequences with the animation ON (the animation finishing, skipped by a click / key / move /
resize / minimize, changes asked for in quick succession, a change arriving while another is being set up,
changes made from the Settings page: click, Cancel, "Don't save", Apply) and OFF, and every theme is the target
of several changes. Mixed themes after a change was the "half applied theme" bug.

Run:  .venv\\Scripts\\python.exe _theme_leak_test.py
"""
import ctypes
import os
import random
import sys
import tempfile
import time

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"
os.environ["APPDATA"] = tempfile.mkdtemp()
LOG_DIR = tempfile.mkdtemp()
os.environ["QRSTUDIO_LOG_DIR"] = LOG_DIR
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except (AttributeError, OSError):
    pass

problems = []
sequences_run = []
targets = {}


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def main():
    import numpy as np

    import _test_dialogs
    dialogs = _test_dialogs.install()
    os.environ.pop("QRSTUDIO_NO_THEME_ANIMATION", None)

    import _theme_contrast_test as contrast
    from ui.app import QRCodeStudioApp
    from utils import settings_store, theme_transition as tt
    from utils.theme_manager import ThemeManager

    tt.system_animations_enabled = lambda: True
    app = QRCodeStudioApp()
    root = app.root
    root.geometry("1280x800+20+20")             # on screen: Tk paints (and snapshots show) only windows on a monitor
    root.update()
    manager = app.theme_transition
    page = app.settings_page
    names = ThemeManager.get_theme_names()
    pages = ("generate", "scan", "history", "bulk", "settings")

    def settle(seconds=0.2):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.005)

    def wait_idle(limit=4.0):
        end = time.time() + limit
        while manager.running and time.time() < end:
            root.update()
            time.sleep(0.01)
        settle(0.15)

    def tokens(name):
        return {v.upper() for k, v in ThemeManager.THEMES[name].items() if k not in ThemeManager.META_KEYS}

    def rgb(value):
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def painted_leaks(current, mask_rects=()):
        """Colours of other themes that cover a noticeable area of the window as painted now."""
        image = np.asarray(tt.capture_client(root)).astype(int)
        keep = np.ones(image.shape[:2], dtype=bool)
        for left, top, right, bottom in mask_rects:               # the theme cards show other themes on purpose
            keep[max(0, top):max(0, bottom), max(0, left):max(0, right)] = False
        found = {}
        foreign = set()
        for other in names:
            if other != current:
                foreign |= tokens(other)
        foreign -= tokens(current)
        foreign -= {"#FFFFFF", "#000000"}                          # QR codes, logos, text
        for colour in foreign:
            r, g, b = rgb(colour)
            hit = (image[:, :, 0] == r) & (image[:, :, 1] == g) & (image[:, :, 2] == b) & keep
            if hit.sum() > 150:
                found[colour] = int(hit.sum())
        return found

    def audit(label, painted_pages=pages):
        """One theme everywhere: configured colours of every widget, and the painted pixels of every page."""
        current = ThemeManager.get_current_theme()
        check(f"[{label}] the animation is over", not manager.running)
        check(f"[{label}] the widgets show the active theme (nothing waits to be re-themed)",
              not ThemeManager.needs_retheme())
        check(f"[{label}] sidebar, window and header agree on {current}",
              app.sidebar._theme_name_label.cget("text") == current
              and root.cget("fg_color").upper() == ThemeManager.THEMES[current]["background"].upper()
              and app.header._title_label.cget("text_color") in (ThemeManager.THEMES[current]["text"],
                                                                  ThemeManager.THEMES[current]["text"].lower()))
        app.ensure_themed()                   # what showing each page does: a page hidden during the change follows then
        stray = []
        contrast.audit_tree(root, current, label, stray)
        check(f"[{label}] no widget holds a colour of another theme", not stray, str(stray[:3]))
        start_page = app._current_page
        for key in painted_pages:
            if key == "settings":
                app.show_settings_page()
            else:
                app._switch_page(key)
            settle(0.15)
            mask = []
            if key == "settings":
                mask = [(t.winfo_rootx() - root.winfo_rootx(), t.winfo_rooty() - root.winfo_rooty(),
                         t.winfo_rootx() - root.winfo_rootx() + t.winfo_width(),
                         t.winfo_rooty() - root.winfo_rooty() + t.winfo_height()) for t in page._tiles.values()]
                check(f"[{label}] the Settings page has {current} selected", page._selected == current)
            try:
                leaks = painted_leaks(current, mask)
            except tt.SnapshotError as e:
                leaks = {}
                check(f"[{label}] snapshot of the {key} page", False, str(e))
            check(f"[{label}] nothing of another theme is painted on the {key} page", not leaks, str(leaks))
        if start_page == "settings":
            app.show_settings_page()
        else:
            app._switch_page(start_page)
        settle(0.2)

    def finish_settings():
        """Leave the Settings page without leaving changes behind (Apply writes to the throw-away settings)."""
        if app._current_page == "settings":
            if page.has_changes():
                page.apply_and_close()
            else:
                app.close_settings()
            wait_idle()

    # ---- steps a sequence is made of ----
    def change(name, gap=0.0):
        def step():
            app.change_theme(name)
            settle(gap)
        return step

    def click():
        root.event_generate("<ButtonPress-1>", x=60, y=60)
        settle(0.1)

    def key():
        root.event_generate("<Key>", keysym="a")
        settle(0.1)

    def move():
        root.geometry("1280x800+60+50")
        settle(0.3)
        root.geometry("1280x800+20+20")
        settle(0.3)

    def resize():
        root.geometry("1200x760+20+20")
        settle(0.3)
        root.geometry("1280x800+20+20")
        settle(0.3)

    def minimize():
        root.iconify()
        settle(0.3)
        root.deiconify()
        settle(0.5)

    def wait(seconds):
        return lambda: settle(seconds)

    def nav(key_name):
        return lambda: (app.sidebar.navigate(key_name), settle(0.2))

    def page_click(name):
        def step():
            page._tiles[name]._canvas.event_generate("<Button-1>", x=6, y=6)
            settle(0.1)
        return step

    def nested(first, second):
        """``second`` is asked for while ``first`` is being set up (an event handled in the middle)."""
        def step():
            original = tt._Overlay.__init__
            fired = {"n": 0}

            def init(self, *a, **k):
                original(self, *a, **k)
                if fired["n"] == 0:
                    fired["n"] = 1
                    app.change_theme(second)

            tt._Overlay.__init__ = init
            try:
                app.change_theme(first)
            finally:
                tt._Overlay.__init__ = original
            settle(0.2)
        return step

    def run(label, steps, animate=True):
        painted = pages if animate else ("scan", "settings")      # the widget audit always covers every page
        os.environ.pop("QRSTUDIO_NO_THEME_ANIMATION", None)
        if not animate:
            os.environ["QRSTUDIO_NO_THEME_ANIMATION"] = "1"
        try:
            for step in steps:
                step()
            wait_idle()
            if app._current_page == "settings" and page.has_changes():
                pass                                              # audited as it stands, then settled below
            audit(label, painted)
            finish_settings()
        finally:
            os.environ.pop("QRSTUDIO_NO_THEME_ANIMATION", None)
        sequences_run.append((label, animate))
        targets[ThemeManager.get_current_theme()] = targets.get(ThemeManager.get_current_theme(), 0) + 1

    settle(0.6)
    app.change_theme("Midnight")
    wait_idle()

    # ---- animation ON: how the animation can end, and what can happen on the way ----
    run("on: one change, left to finish", [change("Ember"), wait(2.4)])
    run("on: three quick changes", [change("Emerald", 0.1), change("Aqua Mint", 0.1), change("Ultraviolet", 0.1)])
    run("on: a click skips it", [change("Graphite", 0.35), click])
    run("on: a key skips it", [change("AMOLED", 0.35), key])
    run("on: moving the window skips it", [change("Daylight", 0.35), move])
    run("on: resizing the window skips it", [change("Midnight", 0.35), resize])
    run("on: minimizing skips it", [change("Ember", 0.35), minimize])
    run("on: changes right after each other, one skipped half way",
        [change("Ultraviolet", 0.8), change("Emerald", 0.02), click, change("Daylight", 0.0)])
    run("on: a change arrives while another is being set up", [nested("Aqua Mint", "Ember")])
    run("on: ... and again with different themes", [nested("Graphite", "Midnight")])
    run("on: back and forth", [change("AMOLED", 0.2), change("Daylight", 0.2), change("AMOLED", 0.2), change("Ember", 0.0)])
    # a change while the user is on every other page
    for key_name, theme in (("scan", "Emerald"), ("history", "Ultraviolet"), ("bulk", "Aqua Mint"), ("generate", "Graphite")):
        run(f"on: change on the {key_name} page", [nav(key_name), change(theme, 0.5), nav("scan"), nav(key_name)])

    # ---- animation ON, from the Settings page ----
    run("on/page: a click on a theme card", [nav("settings"), page_click("Emerald"), wait(2.4)])
    run("on/page: two cards in a row", [nav("settings"), page_click("Ember"), wait(0.1), page_click("Ultraviolet")])
    run("on/page: a card, skipped by a click", [nav("settings"), page_click("Daylight"), wait(0.4), click])
    run("on/page: all cards, then Cancel back",
        [nav("settings")] + [page_click(n) for n in ("Graphite", "AMOLED", "Aqua Mint", "Midnight")]
        + [lambda: page.cancel(), wait(2.4)])
    dialogs.answers["save_changes"] = "discard"
    run("on/page: leave with \"Don't save\"", [nav("settings"), page_click("Ember"), wait(0.5), nav("scan"), wait(2.4)])
    dialogs.answers["save_changes"] = "save"
    run("on/page: leave with Save", [nav("settings"), page_click("Emerald"), wait(0.5), nav("history"), wait(0.3)])
    dialogs.answers.pop("save_changes")
    run("on/page: Apply", [nav("settings"), page_click("Ultraviolet"), wait(0.5), lambda: page.apply_and_close(), wait(0.3)])
    check("the applied theme is what is saved", settings_store.get("theme") == "Ultraviolet", str(settings_store.get("theme")))

    # ---- animation OFF: every theme as a target, from several starting points ----
    rng = random.Random(7)
    order = list(names)
    for round_number in range(2):
        rng.shuffle(order)
        for name in order:
            run(f"off: to {name} (round {round_number + 1})", [change(name), nav(rng.choice(pages[:-1]))], animate=False)
    run("off: from the Settings page", [nav("settings"), page_click("Daylight"), page_click("Midnight"), page_click("Ember")],
        animate=False)

    # ---- a second change asked for in the middle of every stage of a refresh (the half-applied-theme bug) ----
    # (owner, method, the page that must be on screen for that stage to run: a change only recolours the page
    # on screen, the others follow when they are shown)
    stages = {
        "the generic pass": (ThemeManager, "retheme_tree", "generate"),
        "the sidebar": (app.sidebar, "refresh_theme", "generate"),
        "the header": (app.header, "refresh_theme", "generate"),
        "the Generate page": (app.generate_page, "refresh_theme", "generate"),
        "its preview card": (app.generate_page.preview_card, "refresh_theme", "generate"),
        "the Scan page": (app.scan_page, "refresh_theme", "scan"),
        "the History page": (app.history_page, "refresh_theme", "history"),
        "the Bulk page": (app.bulk_page, "refresh_theme", "bulk"),
        "the Settings page": (page, "refresh_theme", "settings"),
    }

    def interrupted(stage, when, first, second, ):
        owner, attribute, on_screen = stages[stage]

        def step():
            nav(on_screen)()
            original = getattr(owner, attribute)
            fired = {"n": 0}

            def wrapper(*args, **kwargs):
                if when == "before" and fired["n"] == 0:
                    fired["n"] = 1
                    app.change_theme(second)
                result = original(*args, **kwargs)
                if when == "after" and fired["n"] == 0:
                    fired["n"] = 1
                    app.change_theme(second)
                return result

            setattr(owner, attribute, wrapper)
            try:
                app.change_theme(first)
                settle(0.3)
            finally:
                setattr(owner, attribute, original)
        return step

    for number, stage in enumerate(stages):
        for when in ("before", "after"):
            first, second = names[(number * 2) % len(names)], names[(number * 2 + 3) % len(names)]
            run(f"off: {second} asked for {when} {stage} of the change to {first}",
                [change("Midnight" if first != "Midnight" else "Graphite"), interrupted(stage, when, first, second)],
                animate=False)
            check(f"the later request ({second}) wins when it arrives {when} {stage}",
                  ThemeManager.get_current_theme() == second, ThemeManager.get_current_theme())
    for stage in ("the generic pass", "the Generate page"):
        run(f"on: Daylight asked for during {stage}",
            [change("Midnight"), wait(2.4), interrupted(stage, "before", "Ember", "Daylight")])

    # ---- random sequences, animation on ----
    rng = random.Random(11)
    for number in range(6):
        steps = []
        for _ in range(rng.randint(2, 5)):
            steps.append(change(rng.choice(names), rng.choice([0.0, 0.03, 0.1, 0.3, 0.8, 2.3])))
            if rng.random() < 0.25:
                steps.append(rng.choice([click, key, move]))
            if rng.random() < 0.2:
                steps.append(nav(rng.choice(pages[:-1])))
        run(f"on: random sequence {number + 1}", steps)

    check("at least 8 different sequences with the animation on", sum(1 for _, a in sequences_run if a) >= 8,
          str(len(sequences_run)))
    check("at least 8 sequences with the animation off", sum(1 for _, a in sequences_run if not a) >= 8)
    missing = [n for n in names if targets.get(n, 0) < 2]
    check("every theme was the final theme of at least two sequences", not missing, f"{missing} {targets}")
    log = open(os.path.join(LOG_DIR, "mosaiq.log"), encoding="utf-8", errors="replace").read()
    check("no error was logged while switching", " ERROR " not in log and "Traceback" not in log, log[-600:])
    check("every started transition ended (finished or skipped)",
          log.count("Theme transition started") == log.count("Theme transition finished") + log.count("skipped ("),
          f"{log.count('Theme transition started')} started, {log.count('Theme transition finished')} finished, "
          f"{log.count('skipped (')} skipped")
    app.close()


if __name__ == "__main__":
    main()
    if problems:
        print(f"THEME_LEAK_FAIL: {len(problems)} problem(s)")
        for p in problems[:80]:
            print(" -", p)
        sys.exit(1)
    print(f"THEME_LEAK_OK: {len(sequences_run)} switch sequences ({sum(1 for _, a in sequences_run if a)} animated, "
          f"{sum(1 for _, a in sequences_run if not a)} instant) on all pages incl. Settings, no widget or painted area "
          f"kept a colour of another theme")
