"""Screen-region scan test: drives the real overlay on the real screen.

Needs a visible desktop (it grabs the screen, so keep other always-on-top
windows away from the top-left corner while it runs, about 10 seconds).
Run:  .venv\\Scripts\\python.exe _region_test.py
Exit code 0 = every check passed.

What this proves: capture -> overlay -> drag -> crop -> decode -> result panel
at THIS machine's display scaling, and that the main window comes back
(still maximized) afterwards. Other scalings are covered only by the pure
mapping checks (region_to_crop); real 125%/150% needs a manual run.
"""
import ctypes
import os
import sys
import time
import tkinter as tk

os.environ["QRSTUDIO_NO_SPLASH"] = "1"

from PIL import ImageTk

from ui.app import QRCodeStudioApp
from utils import qr_payloads
from utils.qr_generator import QRGenerator
from utils.screen_capture import region_to_crop

problems = []
checks = [0]


def check(name, ok, detail=""):
    checks[0] += 1
    if not ok:
        problems.append(f"{name} {detail}".strip())


def test_mapping():
    # Same size: identity.
    check("map: identity", region_to_crop((10, 20, 110, 220), (1000, 800), (1000, 800)) == (10, 20, 110, 220))
    # Any corner order.
    check("map: reversed corners", region_to_crop((110, 220, 10, 20), (1000, 800), (1000, 800)) == (10, 20, 110, 220))
    # Overlay smaller than the screenshot, as under 125%, 150%, 200% scaling.
    for scale in (1.25, 1.5, 1.75, 2.0):
        shot = (3000, 1800)
        shown = (round(shot[0] / scale), round(shot[1] / scale))
        box = region_to_crop((100, 50, 300, 250), shown, shot)
        want = (round(100 * scale), round(50 * scale), round(300 * scale), round(250 * scale))
        ok = box is not None and all(abs(a - b) <= 2 for a, b in zip(box, want))
        check(f"map: scale {scale}", ok, f"got {box} want {want}")
    # Clamped to the screenshot, and tiny selections rejected.
    check("map: clamp", region_to_crop((-50, -50, 5000, 5000), (1000, 800), (1000, 800)) == (0, 0, 1000, 800))
    check("map: too small", region_to_crop((10, 10, 14, 300), (1000, 800), (1000, 800)) is None)


def main():
    test_mapping()

    app = QRCodeStudioApp()
    root = app.root
    state = {"done": False}

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.02)

    def wait_until(cond, timeout=8.0):
        end = time.time() + timeout
        while time.time() < end:
            root.update()
            if cond():
                return True
            time.sleep(0.02)
        return False

    def make_target(text):
        """A topmost window showing a QR code, returned with its screen rectangle."""
        image = QRGenerator().generate(text).convert("RGB")
        target = tk.Toplevel(root)
        target.overrideredirect(True)
        target.attributes("-topmost", True)
        target.geometry(f"{image.width}x{image.height}+120+120")
        photo = ImageTk.PhotoImage(image)
        label = tk.Label(target, image=photo, bd=0)
        label.image = photo
        label.pack()
        target.update()
        pump(0.5)
        return target, (label.winfo_rootx(), label.winfo_rooty(),
                        image.width, image.height)

    def drag(selector, rect):
        """Mouse press/move/release on the overlay; rect is in screen pixels."""
        left, top = selector_origin[0], selector_origin[1]
        shot_w = selector.screenshot.size[0]
        k = selector.shown_size[0] / shot_w     # overlay pixels per screen pixel
        x0, y0, x1, y1 = rect
        c = selector.canvas
        px = lambda v, o: int(round((v - o) * k))
        c.event_generate("<ButtonPress-1>", x=px(x0, left), y=px(y0, top))
        c.event_generate("<B1-Motion>", x=px((x0 + x1) // 2, left), y=px((y0 + y1) // 2, top), state=0x100)
        c.event_generate("<B1-Motion>", x=px(x1, left), y=px(y1, top), state=0x100)
        c.event_generate("<ButtonRelease-1>", x=px(x1, left), y=px(y1, top))

    def driver():
        global selector_origin
        try:
            sp = app.scan_page
            app.show_scan_page()
            pump(0.3)
            check("window starts maximized", root.state() == "zoomed", root.state())

            dpi = ctypes.windll.user32.GetDpiForSystem()
            print(f"[region] system DPI {dpi} = {dpi / 96 * 100:.0f}% scaling; "
                  f"Tk scaling {root.tk.call('tk', 'scaling'):.3f}")

            from utils.screen_capture import virtual_screen_origin
            selector_origin = virtual_screen_origin()

            # ---- 1. drag around a QR code ----
            text = qr_payloads.build_wifi("RegionNet", "region-pass-1", "WPA")
            target, (tx, ty, tw, th) = make_target(text)
            sp.scan_screen_region()
            check("app hidden while selecting", root.state() == "withdrawn", root.state())
            got = wait_until(lambda: hasattr(sp.region_selector, "canvas"))
            check("overlay opened", got)
            if got:
                sel = sp.region_selector
                sw, sh = sel.screenshot.size
                check("overlay covers the screenshot",
                      sel.shown_size == sel.screenshot.size,
                      f"overlay {sel.shown_size} vs screenshot {sel.screenshot.size}")
                drag(sel, (tx - 12, ty - 12, tx + tw + 12, ty + th + 12))
                check("overlay closed after drag", wait_until(lambda: sp.region_selector is None))
                pump(0.3)
                check("window restored maximized", root.state() == "zoomed", root.state())
                check("region decoded into result panel", sp.result_card.result == text,
                      repr(sp.result_card.result))
                check("preview shows the selection", sp.upload_card.has_content)
                check("title says Screen region",
                      sp.upload_card.title_label.cget("text") == "Screen region")
            target.destroy()
            sp.result_card.clear()

            # ---- 2. partial drag (only part of the QR): must not decode garbage ----
            target, (tx, ty, tw, th) = make_target("https://example.com/partial")
            sp.scan_screen_region()
            if wait_until(lambda: hasattr(sp.region_selector, "canvas")):
                drag(sp.region_selector, (tx, ty, tx + tw // 3, ty + th // 3))
                wait_until(lambda: sp.region_selector is None)
                pump(0.3)
                check("partial region is not a false result", sp.result_card.result == "",
                      repr(sp.result_card.result))
                check("partial region shows a message",
                      sp.result_card.status_chip.cget("text") == "Nothing decoded")
            else:
                check("overlay opened (partial)", False)
            target.destroy()
            sp.result_card.clear()

            # ---- 3. Esc cancels, nothing is shown, window returns ----
            sp.scan_screen_region()
            if wait_until(lambda: hasattr(sp.region_selector, "canvas")):
                sp.region_selector.window.event_generate("<Escape>")
                wait_until(lambda: sp.region_selector is None)
                pump(0.3)
                check("Esc: window restored", root.state() == "zoomed", root.state())
                check("Esc: no result and no error", sp.result_card.result == ""
                      and sp.result_card.status_chip.cget("text") == "Waiting",
                      sp.result_card.status_chip.cget("text"))
            else:
                check("overlay opened (Esc)", False)

            # ---- 4. a click without dragging is an accidental click ----
            sp.scan_screen_region()
            if wait_until(lambda: hasattr(sp.region_selector, "canvas")):
                drag(sp.region_selector, (300, 300, 303, 303))
                wait_until(lambda: sp.region_selector is None)
                pump(0.3)
                check("tiny selection: message shown",
                      "too small" in sp.result_card.result_label.cget("text"))
                check("tiny selection: window restored", root.state() == "zoomed", root.state())
            else:
                check("overlay opened (tiny)", False)

            # ---- 5. a second request while one is open is ignored ----
            sp.scan_screen_region()
            sp.scan_screen_region()
            if wait_until(lambda: hasattr(sp.region_selector, "canvas")):
                sp.region_selector.window.event_generate("<Escape>")
                wait_until(lambda: sp.region_selector is None)
            check("double click: window restored", wait_until(lambda: root.state() == "zoomed"), root.state())
        except Exception as e:                  # report, don't hang the mainloop
            import traceback
            traceback.print_exc()
            problems.append(f"driver raised {type(e).__name__}: {e}")
        finally:
            state["done"] = True
            root.destroy()

    root.after(1500, driver)
    app.run()

    if not state["done"]:
        problems.append("driver never ran")

    if problems:
        print("REGION_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)

    print(f"REGION_OK: {checks[0]} checks")


if __name__ == "__main__":
    main()
