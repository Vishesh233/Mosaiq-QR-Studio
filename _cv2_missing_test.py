"""OpenCV is loaded lazily and its failure must not crash the app.

Each scenario runs in a fresh interpreter (so sys.modules is clean):
  lazy       real OpenCV: it is NOT loaded at start-up, nor by Generate, only by the first scan
  dllfail    `import cv2` fails like on a Windows N edition (DLL load failed: mf.dll missing)
  otherfail  `import cv2` fails for another reason
For the two failures: the app starts, Generate works, every scan path (file, drop,
paste/region image, camera) shows the clear message, nothing crashes, and the cause is
written to the error log.

Run:  .venv\\Scripts\\python.exe _cv2_missing_test.py
"""
import importlib.abc
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA_PACK = "Scanning needs the Windows Media Feature Pack. Install it from Settings → Apps → Optional features."


# ======================================================================
# Worker (runs inside the child interpreter)
# ======================================================================

class _FailingCv2(importlib.abc.MetaPathFinder):
    def __init__(self, message):
        self.message = message

    def find_spec(self, name, path, target=None):
        if name == "cv2":
            raise ImportError(self.message)
        return None


def worker(mode, log_dir):
    os.environ["QRSTUDIO_NO_SPLASH"] = "1"
    os.environ["QRSTUDIO_LOG_DIR"] = log_dir
    sys.path.insert(0, HERE)
    problems = []

    def check(name, ok, detail=""):
        if not ok:
            problems.append(f"{name} {detail}".strip())

    if mode == "dllfail":
        sys.meta_path.insert(0, _FailingCv2("DLL load failed while importing cv2: The specified module could not be found."))
    elif mode == "otherfail":
        sys.meta_path.insert(0, _FailingCv2("some other import problem"))

    from PIL import Image
    from utils import qr_payloads
    from utils.qr_generator import QRGenerator

    # A QR image made WITHOUT OpenCV (qrcode + Pillow only).
    tmp = tempfile.mkdtemp()
    text = qr_payloads.build_wifi("NoCv2Net", "no-cv2-pass-1", "WPA")
    path = os.path.join(tmp, "wifi.png")
    QRGenerator().generate(text).save(path)

    from ui.app import QRCodeStudioApp
    import _test_dialogs
    _test_dialogs.install()
    app = QRCodeStudioApp()
    root = app.root
    root.withdraw()
    root.update_idletasks()
    check("app starts", root.winfo_exists() == 1)
    check("cv2 is not loaded at start-up", "cv2" not in sys.modules)

    # --- Neither start-up nor opening the pages needs OpenCV ---
    gp = app.generate_page
    app.show_scan_page()
    root.update_idletasks()
    check("opening the Scan page did not load cv2", "cv2" not in sys.modules)
    app.show_generate_page()
    root.update_idletasks()
    check("opening the Generate page did not load cv2", "cv2" not in sys.modules)

    # --- Generate works without OpenCV; only the background test scan wants it ---
    cc = gp.content_card
    cc.set_type("UPI Payment")
    form = cc.forms["UPI Payment"]
    for field, value in ((form.upi_id, "shop@okaxis"), (form.payee, "Corner Shop")):
        field.widget.delete(0, "end")
        field.widget.insert(0, value)
    gp.generate_qr()
    root.update_idletasks()
    check("Generate works", gp.generated_image is not None)
    check("Generate itself did not wait for cv2 (it loads on the test-scan thread)",
          gp.preview_card.badge.cget("text").startswith("Checking"), gp.preview_card.badge.cget("text"))

    import time
    deadline = time.time() + 20
    while time.time() < deadline and gp.preview_card.badge.cget("text").startswith("Checking"):
        root.update()
        time.sleep(0.02)
    badge = gp.preview_card.badge.cget("text")
    if mode == "lazy":
        check("test scan loaded cv2 and passed", "cv2" in sys.modules and "Scans correctly" in badge, badge)
    else:
        check("badge says the test scan is not available", badge == "Test scan is not available on this PC", badge)
        check("test scan did not load cv2", "cv2" not in sys.modules)
    check("preview and buttons still usable", str(gp.action_buttons.save_btn.cget("state")) == "normal")
    app.show_scan_page()
    root.update_idletasks()

    sp = app.scan_page
    rc = sp.result_card

    if mode == "lazy":
        sp.on_image_selected(path)
        check("scanning works", "cv2" in sys.modules)
        check("first scan decodes", rc.result == text, repr(rc.result))
    else:
        expected = MEDIA_PACK if mode == "dllfail" else None

        def shows_message(label):
            shown = rc.result_label.cget("text")
            ok = (shown == expected) if expected else ("required component failed to load" in shown)
            check(f"{label}: clear message", ok, repr(shown))
            check(f"{label}: nothing decoded, no result", rc.result == "" and rc.status_chip.cget("text") == "Nothing decoded")
            check(f"{label}: copy buttons off", str(rc.copy_btn.cget("state")) == "disabled")

        sp.on_image_selected(path)
        shows_message("file")

        rc.clear()
        sp.scan_dropped_files([path])
        shows_message("drop")

        rc.clear()
        sp.scan_image(Image.open(path))
        shows_message("pasted / region image")

        rc.clear()
        sp.start_camera()
        root.update()
        shows_message("camera")
        check("camera: nothing started", sp.camera is None and not sp.upload_card.camera_visible)

        check("cv2 stays unloaded", "cv2" not in sys.modules)

        # Everything else still works afterwards.
        app.show_generate_page()
        gp.generated_image = None
        gp.generate_qr()
        check("Generate still works after failed scans", gp.generated_image is not None)

        # The cause went to the error log, with a traceback.
        from utils import app_log
        for handler in app_log.get_logger().handlers:
            handler.flush()
        log = open(app_log.log_path(), encoding="utf-8").read()
        check("error log written", "OpenCV could not be loaded" in log, log[:200])
        check("error log has the cause", ("DLL load failed" in log) if mode == "dllfail" else ("some other import problem" in log))
        check("error log has a traceback", "Traceback" in log)
        check("failure is logged once, not on every scan", log.count("OpenCV could not be loaded") == 1, str(log.count("OpenCV could not be loaded")))

    root.destroy()
    if problems:
        print("WORKER_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)
    print("WORKER_OK")


# ======================================================================
# Driver
# ======================================================================

def main():
    failures = []
    for mode in ("lazy", "dllfail", "otherfail"):
        log_dir = tempfile.mkdtemp()
        result = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--worker", mode, log_dir],
            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=HERE,
        )
        tail = [line for line in result.stdout.splitlines() if line.strip()]
        print(f"[{mode}] exit {result.returncode}: {tail[-1] if tail else result.stderr.strip()[-300:]}")
        if result.returncode != 0:
            failures.append(f"{mode}: " + "; ".join(tail[1:] or [result.stderr.strip()[-400:]]))

    if failures:
        print("CV2_MISSING_FAIL")
        for f in failures:
            print(" - " + f)
        sys.exit(1)
    print("CV2_MISSING_OK: 3 scenarios")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        main()
