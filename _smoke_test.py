"""Headless UI smoke test for QR Code Studio v2.

Builds the real application widget tree (no interactive display needed),
switches pages, exercises the generate workflow, and verifies core state.
Run:  .venv\\Scripts\\python.exe _smoke_test.py
Exit code 0 = UI constructed and core flows ran without exceptions.
"""
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")


def main():
    # Import AFTER cwd is the repo root so package imports resolve.
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    root = app.root
    root.withdraw()
    root.update_idletasks()

    problems = []

    # --- Navigation: both destinations must open without error ---
    app.show_scan_page()
    root.update_idletasks()
    if not app.scan_page.winfo_ismapped():
        problems.append("scan_page not mapped after show_scan_page()")

    app.show_generate_page()
    root.update_idletasks()
    if not app.generate_page.winfo_ismapped():
        problems.append("generate_page not mapped after show_generate_page()")

    # --- Generate workflow: real QRGenerator path ---
    gp = app.generate_page
    gp.content_card.url_entry.delete(0, "end")
    gp.content_card.url_entry.insert(0, "https://example.com/smoke")
    gp.generate_qr()
    root.update_idletasks()

    if gp.generated_image is None:
        problems.append("generate_qr() did not produce an image")
    if str(gp.action_buttons.copy_btn.cget("state")) != "normal":
        problems.append("copy button not enabled after generate")

    # --- Scan workflow: decode the just-generated image via a temp file ---
    import tempfile
    from utils.qr_scanner import QRScanner

    tmp = os.path.join(tempfile.gettempdir(), "_smoke_qr.png")
    gp.generated_image.save(tmp)
    decoded = QRScanner.decode(tmp)
    if decoded != "https://example.com/smoke":
        problems.append(f"roundtrip decode mismatch: {decoded!r}")
    os.remove(tmp)

    # --- Settings dialog opens and closes cleanly ---
    from ui.dialogs.settings_dialog import SettingsDialog
    dlg = SettingsDialog(app.header)
    root.update_idletasks()
    dlg.destroy()
    root.update_idletasks()

    # --- Settings APPLY actually re-themes the app shell (regression guard) ---
    from utils.theme_manager import ThemeManager
    original_theme = ThemeManager.get_current_theme()
    other = next(t for t in ThemeManager.get_theme_names() if t != original_theme)
    ThemeManager.set_theme(original_theme)
    app.refresh_theme()
    root.update_idletasks()
    bg_before = app.root.cget("fg_color")

    dlg2 = SettingsDialog(app.header)
    dlg2.preview_theme(other)        # live preview re-themes the app
    dlg2.apply()                     # saves the choice + closes the dialog
    root.update_idletasks()
    bg_after = app.root.cget("fg_color")
    if bg_before == bg_after:
        problems.append(
            f"Settings Apply did not change app background ({other})"
        )
    # restore
    ThemeManager.set_theme(original_theme)
    app.refresh_theme()
    root.update_idletasks()

    # --- Theme switching: apply every theme and refresh the whole shell ---
    try:
        for name in ThemeManager.get_theme_names():
            ThemeManager.set_theme(name)
            app.refresh_theme()          # must not raise on any theme
            root.update_idletasks()
    finally:
        ThemeManager.set_theme(original_theme)
        app.refresh_theme()
        root.update_idletasks()

    root.destroy()

    if problems:
        print("SMOKE_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)

    print("SMOKE_OK: nav, generate, decode-roundtrip, settings dialog all ran")


if __name__ == "__main__":
    main()
