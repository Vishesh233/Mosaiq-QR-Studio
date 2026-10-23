"""Theme consistency test.

1. Token contrast: every theme's text / accent colours are readable (WCAG ratios) on the
   surfaces they are drawn on.
2. Token hygiene: every theme defines the same keys, and no colour value repeats inside
   a theme (ThemeManager.retheme_tree maps a colour back to its token by value).
3. Widget audit: every colour on every real widget (all pages, the settings dialog, the
   colour picker when present) is one of the active theme's tokens, "transparent", or
   marked as user data - nothing falls back to CustomTkinter's default blue/grey.
4. Live switching: moving from every theme to every other one leaves no stray colours.

Run:  .venv\\Scripts\\python.exe _theme_contrast_test.py
Exit code 0 = all checks passed. Use  --report  to print the contrast matrix.
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ["QRSTUDIO_NO_SPLASH"] = "1"

COLOR_OPTIONS = (
    "fg_color", "bg_color", "border_color", "text_color", "hover_color",
    "button_color", "button_hover_color", "dropdown_fg_color",
    "dropdown_hover_color", "dropdown_text_color", "placeholder_text_color",
    "progress_color", "scrollbar_button_color", "scrollbar_button_hover_color",
    "text_color_disabled", "selected_color", "selected_hover_color",
    "unselected_color", "unselected_hover_color", "checkmark_color",
)
TK_COLOR_OPTIONS = ("bg", "background", "fg", "foreground", "highlightbackground",
                    "selectbackground", "insertbackground")

# (foreground token, background tokens, minimum ratio, what it is)
CONTRAST_RULES = [
    ("text", ("background", "navbar", "card", "panel", "panel_alt", "card_hover", "entry"), 7.0, "body text"),
    ("text_secondary", ("background", "navbar", "card", "panel", "panel_alt", "card_hover", "entry"), 4.5, "secondary text"),
    ("text_muted", ("card", "entry", "panel"), 3.0, "placeholder / hint text"),
    ("on_primary", ("primary", "primary_hover"), 4.5, "text on primary buttons"),
    ("primary", ("background", "card", "navbar", "panel"), 3.0, "primary as icon / accent"),
    ("accent", ("background", "card", "navbar"), 3.0, "accent as icon"),
    ("danger", ("card", "panel"), 4.5, "danger text"),
    ("success", ("card", "panel"), 4.5, "success text"),
    ("warning", ("card", "panel"), 4.5, "warning text"),
    ("text", ("segment_bg", "segment_hover"), 4.5, "text on segmented buttons"),
    ("entry_border", ("entry", "card"), 1.5, "input border visible against its surface"),
]


def _lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def check_tokens(problems, report=False):
    from utils.theme_manager import ThemeManager

    themes = ThemeManager.THEMES
    names = list(themes)
    keys = set(themes[names[0]])
    for name in names:
        t = themes[name]
        if set(t) != keys:
            problems.append(f"{name}: token keys differ: {sorted(set(t) ^ keys)}")
        seen = {}
        for key, value in t.items():
            if key in ThemeManager.META_KEYS:
                continue
            if value.upper() in seen:
                problems.append(f"{name}: {key} and {seen[value.upper()]} share {value}")
            seen[value.upper()] = key
        for fg, backgrounds, minimum, what in CONTRAST_RULES:
            for bg in backgrounds:
                if fg not in t or bg not in t:
                    continue
                r = ratio(t[fg], t[bg])
                if report:
                    print(f"{name:12s} {fg:15s} on {bg:14s} {r:5.2f}  (need {minimum})")
                if r < minimum:
                    problems.append(f"{name}: {what}: {fg} {t[fg]} on {bg} {t[bg]} = {r:.2f} < {minimum}")


def _resolve(value, mode):
    if isinstance(value, (tuple, list)):
        return value[1 if mode == "Dark" else 0]
    return value


def audit_tree(root, theme_name, label, problems, limit=40):
    """Every colour on every widget under root must be a token of ``theme_name``."""
    import customtkinter as ctk
    from utils.theme_manager import ThemeManager

    theme = ThemeManager.THEMES[theme_name]
    allowed = {v.upper() for k, v in theme.items() if k not in ThemeManager.META_KEYS}
    allowed |= {"TRANSPARENT"}
    mode = theme["mode"]
    found = []
    stack = [root]
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
        if getattr(widget, "_theme_skip", False):
            stack = [w for w in stack if not str(w).startswith(str(widget) + ".")]
            continue
        is_ctk = isinstance(widget, ctk.windows.widgets.core_widget_classes.CTkBaseClass)
        if not is_ctk:
            continue   # CustomTkinter's drawing surfaces / inner tk widgets follow their owner
        for opt in COLOR_OPTIONS:
            try:
                value = widget.cget(opt)
            except Exception:
                continue
            if opt == "border_color" and isinstance(widget, ctk.CTkSegmentedButton):
                continue   # not an option of the segmented frame; its segments are audited
            # Options that are not drawn right now are not a visible inconsistency.
            if opt == "border_color" and is_ctk:
                try:
                    if not widget.cget("border_width"):
                        continue
                except Exception:
                    pass
            if opt == "text_color_disabled":
                try:
                    if widget.cget("state") != "disabled":
                        continue
                except Exception:
                    continue
            value = _resolve(value, mode)
            if not isinstance(value, str) or not value:
                continue
            if value.startswith("#") and value.upper() in allowed:
                continue
            if value.upper() in allowed:
                continue
            found.append((f"{type(widget).__name__} {opt}={value}", str(widget)))
    kinds = {}
    for kind, path in found:
        kinds.setdefault(kind, []).append(path)
    for kind in sorted(kinds)[:limit]:
        problems.append(f"{theme_name} {label}: stray colour: {kind} x{len(kinds[kind])} e.g. {kinds[kind][:3]}")


def check_widgets(problems):
    import json
    import tempfile

    # Throw-away settings so the real user's saved theme is never touched.
    appdata = tempfile.mkdtemp()
    os.environ["APPDATA"] = appdata
    os.makedirs(os.path.join(appdata, "QR Code Studio"))
    with open(os.path.join(appdata, "QR Code Studio", "settings.json"), "w", encoding="utf-8") as fh:
        json.dump({"theme": "Midnight", "splash_enabled": False}, fh)

    from ui.app import QRCodeStudioApp
    from ui.dialogs.color_picker import ColorPickerDialog
    from ui.dialogs.settings_dialog import SettingsDialog
    from utils.theme_manager import ThemeManager

    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    # Parked off-screen (not withdrawn): dialogs of a withdrawn window never become visible.
    root.geometry("1280x820+-30000+-30000")
    root.update()
    names = ThemeManager.get_theme_names()

    def pages():
        yield "generate", app.show_generate_page
        yield "scan", app.show_scan_page
        for key in ("history", "bulk"):
            fn = getattr(app, f"show_{key}_page", None)
            if fn:
                yield key, fn

    def audit_all(theme_name, how):
        for label, show in pages():
            show()
            root.update_idletasks()
            # Audit the whole window: sidebar, header and every page (hidden pages too).
            audit_tree(root, theme_name, f"{how}/{label}", problems)
        app.show_generate_page()

    # 1. every theme as it would look after a fresh start is covered by the live path
    #    from Midnight; 2. every ordered pair of themes
    for first in names:
        ThemeManager.set_theme(first, persist=False)
        app.refresh_theme()
        audit_all(first, "switch")
        for second in names:
            if second == first:
                continue
            ThemeManager.set_theme(second, persist=False)
            app.refresh_theme()
            audit_all(second, f"from {first}")
            ThemeManager.set_theme(first, persist=False)
            app.refresh_theme()

    # Settings dialog (it holds theme tiles that deliberately show other themes' colours).
    for name in names:
        ThemeManager.set_theme(name, persist=False)
        app.refresh_theme()
        dlg = SettingsDialog(app.header)
        root.update_idletasks()
        audit_tree(dlg, name, "settings", problems)
        dlg.destroy()
        root.update_idletasks()
        picker = ColorPickerDialog(app.header, "#0E7490", "audit")
        root.update_idletasks()
        audit_tree(picker, name, "colour picker", problems)
        picker.destroy()
        root.update_idletasks()

    app.close()


def main():
    problems = []
    check_tokens(problems, report="--report" in sys.argv)
    if "--tokens-only" not in sys.argv:
        check_widgets(problems)
    if problems:
        print(f"THEME_FAIL: {len(problems)} problem(s)")
        for p in problems[:200]:
            print(" -", p)
        sys.exit(1)
    print("THEME_OK: token contrast, token hygiene, widget audit, live switching")


if __name__ == "__main__":
    main()
