"""Webcam scanning tests.

Part 1 drives CameraScanner with fake cameras (frames, failures, black frames).
Part 2 drives the real Scan page with a fake camera: view, result, release on
Stop / tab switch / window close, and that the UI keeps ticking while it streams.
Part 3 tries the REAL camera on this PC (frames or a clean error; either passes).

Run:  .venv\\Scripts\\python.exe _camera_test.py
Exit code 0 = every check passed. A live QR in front of a real webcam is NOT
covered here (manual check).
"""
import os
import sys
import threading
import time

os.environ["QRSTUDIO_NO_SPLASH"] = "1"

import cv2
import numpy as np

import _test_samples as samples
from utils.camera_scanner import CameraError, CameraScanner, CvFrameSource
from utils.qr_generator import QRGenerator

problems = []
checks = [0]


def check(name, ok, detail=""):
    checks[0] += 1
    if not ok:
        problems.append(f"{name} {detail}".strip())


def qr_frame(text, size=(640, 480)):
    """A BGR camera-like frame: grey background with a QR code in the middle."""
    qr = np.asarray(QRGenerator().generate(text).convert("RGB").resize((300, 300)))
    frame = np.full((size[1], size[0], 3), 90, np.uint8)
    y, x = (size[1] - 300) // 2, (size[0] - 300) // 2
    frame[y:y + 300, x:x + 300] = qr[:, :, ::-1]
    return frame


def blank_frame(size=(640, 480)):
    return np.full((size[1], size[0], 3), 90, np.uint8)


class FakeSource:
    """Plays a list of frames (None = failed read), then repeats the last one."""

    def __init__(self, frames, delay=0.01):
        self.frames = list(frames)
        self.delay = delay
        self.index = 0
        self.released = False
        self.release_thread = None

    def read(self):
        time.sleep(self.delay)
        frame = self.frames[min(self.index, len(self.frames) - 1)]
        self.index += 1
        return (frame is not None, frame)

    def release(self):
        self.released = True
        self.release_thread = threading.current_thread().name


def collect(scanner, timeout=6.0, until=("stopped",)):
    """Poll like the UI does; return all events seen."""
    seen = []
    end = time.time() + timeout
    while time.time() < end:
        _, events = scanner.poll()
        seen += events
        if any(kind in until for kind, _ in seen):
            return seen
        time.sleep(0.01)
    return seen


def kinds(events):
    return [k for k, _ in events]


# ======================================================================


def test_scanner():
    text = "https://example.com/camera"

    # --- finds a QR after some empty frames, stops itself, releases ---
    source = FakeSource([blank_frame()] * 8 + [qr_frame(text)])
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start()
    events = collect(scanner)
    check("found: event order", kinds(events) == ["running", "found", "stopped"], str(kinds(events)))
    check("found: text", ("found", text) in events)
    check("found: camera released", source.released)
    check("found: released on the worker thread", source.release_thread == "camera-scanner",
          str(source.release_thread))
    check("found: thread finished", not scanner.active)

    # --- the hard case from real use: a phone in dark mode (light-on-dark, dotted
    #     modules, logo, blur) seen by the camera; only one recipe runs per frame ---
    upi = "upi://pay?pa=someone@okhdfcbank&pn=Some%20Shop&mc=0000&mode=02&purpose=00"
    for inverted, style, sigma in ((True, "dots", 1.2), (True, "square", 1.2), (True, "dots", 1.8), (False, "dots", 1.2)):
        qr = samples.render_qr(upi, inverted=inverted, style=style, logo=True)
        frames = [blank_frame((1280, 720))] * 3 + [samples.camera_frame(qr, seed=i, sigma=sigma) for i in range(6)]
        source = FakeSource(frames, delay=0.033)            # a 30 fps camera
        scanner = CameraScanner(source_factory=lambda: source)
        started = time.time()
        scanner.start()
        events = collect(scanner, timeout=10)
        took = time.time() - started
        tag = f"{'light-on-dark' if inverted else 'dark-on-light'} {style} blur {sigma}"
        check(f"hard camera[{tag}]: found", ("found", upi) in events, str(kinds(events)))
        check(f"hard camera[{tag}]: released", source.released)
        print(f"[camera] {tag}: found after {took:.2f} s ({source.index} frames read)")

    # --- the preview keeps its frame rate while decoding fails on every attempt ---
    qr = samples.render_qr(upi, inverted=True, style="dots", logo=True)
    hopeless = samples.camera_frame(qr, seed=1, sigma=4.5)      # too blurry to ever decode
    source = FakeSource([hopeless], delay=0.02)
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start()
    shown = 0
    end = time.time() + 3.0
    while time.time() < end:
        frame, _ = scanner.poll()
        shown += frame is not None
        time.sleep(0.01)
    scanner.stop()
    print(f"[camera] preview while decoding never succeeds: {shown / 3.0:.0f} fps polled")
    check("preview stays smooth while the decoder works (>= 15 fps)", shown / 3.0 >= 15, f"{shown / 3.0:.1f} fps")
    check("preview+decoder threads released", source.released and not scanner.active)

    # --- Stop while streaming: released, idempotent ---
    source = FakeSource([blank_frame()])
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start()
    time.sleep(0.3)
    frame, _ = scanner.poll()
    check("stop: preview frames arrive", frame is not None and frame.ndim == 3 and frame.shape[2] == 3)
    check("stop: preview is RGB-sized to 640 max", frame is not None and frame.shape[1] <= 640)
    scanner.stop()
    check("stop: released", source.released)
    check("stop: thread finished", not scanner.active)
    scanner.stop()                              # second stop must be harmless
    check("stop: idempotent", True)

    # --- camera cannot be opened ---
    def cannot_open():
        raise CameraError("Could not open a camera. test")

    scanner = CameraScanner(source_factory=cannot_open)
    scanner.start()
    events = collect(scanner)
    check("no camera: error then stopped", kinds(events) == ["error", "stopped"], str(kinds(events)))
    check("no camera: message", events and "Could not open a camera" in events[0][1])

    # --- camera stops delivering frames ---
    source = FakeSource([blank_frame()] * 5 + [None], delay=0.001)
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start()
    events = collect(scanner)
    check("read failures: error reported", "error" in kinds(events), str(kinds(events)))
    check("read failures: released", source.released)
    check("read failures: message mentions settings",
          any("Privacy" in v for k, v in events if k == "error"))

    # --- only black frames (blocked / covered camera) ---
    source = FakeSource([np.zeros((480, 640, 3), np.uint8)], delay=0.001)
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start()
    events = collect(scanner)
    check("black frames: error reported", any(k == "error" and "black" in v for k, v in events), str(events))
    check("black frames: released", source.released)

    # --- unexpected exception in decoding: reported, still released ---
    def broken_decode(frame, **kwargs):
        raise RuntimeError("decoder exploded")

    source = FakeSource([blank_frame()])
    scanner = CameraScanner(source_factory=lambda: source, decode=broken_decode)
    scanner.start()
    events = collect(scanner)
    check("decoder crash: error reported", any(k == "error" and "decoder exploded" in v for k, v in events))
    check("decoder crash: released", source.released)

    # --- stop requested while the camera is still opening ---
    opened = threading.Event()
    holder = {}

    def slow_open():
        time.sleep(0.5)
        holder["source"] = FakeSource([blank_frame()])
        opened.set()
        return holder["source"]

    scanner = CameraScanner(source_factory=slow_open)
    scanner.start()
    scanner.stop()
    check("stop during open: source released after open completes",
          opened.wait(2) and holder["source"].released)

    # --- restart after stop ---
    source = FakeSource([qr_frame("again")])
    scanner = CameraScanner(source_factory=lambda: source)
    scanner.start(); scanner.stop()
    source2 = FakeSource([qr_frame("again")])
    scanner.source_factory = lambda: source2
    scanner.start()
    events = collect(scanner)
    check("restart: finds QR", ("found", "again") in events)

    # --- real open() with indices that do not exist ---
    try:
        CvFrameSource.open(indices=(97, 98))
    except CameraError as e:
        check("open(): missing camera gives a clear message", "Could not open a camera" in str(e))
    else:
        check("open(): missing camera raises CameraError", False)


# ======================================================================


def test_ui():
    from ui.app import QRCodeStudioApp

    app = QRCodeStudioApp()
    root = app.root
    sp = app.scan_page
    uc = sp.upload_card
    rc = sp.result_card

    def pump(seconds):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
            time.sleep(0.01)

    def wait_until(cond, timeout=6.0):
        end = time.time() + timeout
        while time.time() < end:
            root.update()
            if cond():
                return True
            time.sleep(0.01)
        return False

    app.show_scan_page()
    root.update()

    # --- 1. camera finds a QR: view shown, result in the SAME panel, camera released ---
    text = "WIFI:T:WPA;S:CamNet;P:camera-pass-1;;"
    source = FakeSource([blank_frame()] * 15 + [qr_frame(text)])
    sp.camera_factory = lambda: source
    sp.start_camera()
    pump(0.1)
    check("ui: camera view visible", uc.camera_visible and uc.camera_frame.winfo_manager() == "pack")
    check("ui: upload area hidden", uc.upload_frame.winfo_manager() == "")
    check("ui: result found", wait_until(lambda: rc.result == text), repr(rc.result))
    check("ui: result shown like an image scan (WiFi kind)",
          "WiFi: CamNet" in rc.result_label.cget("text") and rc.action == ("Copy password", "camera-pass-1"))
    check("ui: camera released after found", source.released)
    check("ui: back to image area", not uc.camera_visible and uc.upload_frame.winfo_manager() == "pack")
    check("ui: capture preview kept", uc.has_content and uc.title_label.cget("text") == "Camera capture")
    check("ui: no camera object left", sp.camera is None)

    # --- 2. UI keeps responding while frames stream (no freeze) ---
    rc.clear()
    source = FakeSource([blank_frame()], delay=0.02)
    sp.camera_factory = lambda: source
    sp.start_camera()
    gaps = []
    last = [time.perf_counter()]

    def ticker():
        now = time.perf_counter()
        gaps.append(now - last[0])
        last[0] = now
        if not done[0]:
            root.after(20, ticker)

    done = [False]
    root.after(20, ticker)
    frames_before = None
    pump(2.5)
    check("ui: preview image updates", uc.camera_image is not None)
    hint = uc.camera_status.cget("text")
    check("ui: camera hint shown", "Tip: hold the QR steady, 15–25 cm from the camera." in hint, repr(hint))
    frames_before = source.index
    done[0] = True
    pump(0.1)
    steady = sorted(gaps[len(gaps) // 5:])        # skip the first fifth (warm-up)
    worst = steady[-1] if steady else 9.9
    p95 = steady[int(len(steady) * 0.95)] if steady else 9.9
    # A real freeze (camera work on the UI thread) shows as MANY long gaps, so p95
    # must stay small; the worst gap only has to rule out a multi-second stall (a
    # single desktop hiccup from other processes can reach a few hundred ms).
    check("ui: no freeze while streaming (p95 tick gap < 100 ms, worst < 600 ms)",
          p95 < 0.1 and worst < 0.6, f"p95 {p95 * 1000:.0f} ms, worst {worst * 1000:.0f} ms")
    print(f"[camera] streaming: {frames_before} frames in 2.6 s, worst UI tick gap {worst * 1000:.0f} ms, "
          f"mean {sum(gaps[2:]) / max(1, len(gaps[2:])) * 1000:.0f} ms (target 20)")

    # --- 3. Stop button ---
    uc.camera_stop_button.invoke()
    root.update()
    check("ui: Stop releases the camera", source.released)
    check("ui: Stop returns to the image area", not uc.camera_visible)
    check("ui: poll cancelled", sp._camera_poll_id is None and sp.camera is None)

    # --- 4. switching tab releases the camera ---
    source = FakeSource([blank_frame()])
    sp.camera_factory = lambda: source
    sp.start_camera()
    pump(0.3)
    check("ui: camera running before tab switch", sp.camera is not None and sp.camera.active)
    app.show_generate_page()
    root.update()
    check("ui: tab switch releases the camera", source.released and sp.camera is None)
    app.show_scan_page()
    root.update()
    check("ui: scan tab shows the image area again", not uc.camera_visible)

    # --- 5. closing the app releases the camera ---
    source = FakeSource([blank_frame()])
    sp.camera_factory = lambda: source
    sp.start_camera()
    pump(0.3)
    app.root.protocol("WM_DELETE_WINDOW")    # handler is registered
    check("ui: close handler registered", bool(app.root.protocol("WM_DELETE_WINDOW")))
    closed = {}
    original_destroy = root.destroy
    root.destroy = lambda: closed.setdefault("destroyed", True)
    try:
        app.close()
    finally:
        root.destroy = original_destroy
    check("ui: app close releases the camera", source.released and closed.get("destroyed"))

    # --- 6. other scan sources stop the camera ---
    source = FakeSource([blank_frame()])
    sp.camera_factory = lambda: source
    sp.start_camera()
    pump(0.2)
    sp.paste_from_clipboard()           # clipboard may or may not hold an image
    check("ui: Paste stops the camera", source.released and sp.camera is None)

    # --- 7. camera cannot open: clear message, buttons, no crash ---
    def cannot_open():
        raise CameraError("Could not open a camera. test help text")

    sp.camera_factory = cannot_open
    sp.start_camera()
    check("ui: error shown", wait_until(lambda: "Could not open a camera" in uc.camera_status.cget("text")),
          uc.camera_status.cget("text"))
    check("ui: settings button offered", uc.camera_settings_button.winfo_manager() == "pack")
    check("ui: panel says camera unusable", rc.status_chip.cget("text") == "Nothing decoded")
    opened = []
    original_startfile = os.startfile
    os.startfile = lambda target: opened.append(target)
    try:
        uc.camera_settings_button.invoke()
    finally:
        os.startfile = original_startfile
    check("ui: settings button opens the camera privacy page", opened == ["ms-settings:privacy-webcam"], str(opened))
    uc.camera_stop_button.invoke()
    root.update()
    check("ui: error view closes", not uc.camera_visible and sp.camera is None)

    # --- 8. start twice is a no-op; start again after stop works ---
    source = FakeSource([blank_frame()])
    sp.camera_factory = lambda: source
    sp.start_camera()
    first = sp.camera
    sp.start_camera()
    check("ui: second start ignored", sp.camera is first)
    sp.stop_camera()
    source2 = FakeSource([qr_frame("second run")])
    sp.camera_factory = lambda: source2
    sp.start_camera()
    check("ui: restart works", wait_until(lambda: rc.result == "second run"), repr(rc.result))

    # --- 9. the REAL camera on this PC ---
    sp.camera_factory = CvFrameSource.open
    rc.clear()
    sp.start_camera()
    outcome = {}

    def real_settled():
        if sp.camera is None:
            outcome["state"] = "closed"
            return True
        if uc.camera_image is not None:
            outcome["state"] = "streaming"
            return True
        if uc.camera_settings_button.winfo_manager() == "pack":
            outcome["state"] = "error"
            return True
        return False

    wait_until(real_settled, timeout=15.0)
    state = outcome.get("state", "timeout")
    print(f"[camera] real camera: {state}"
          + (f" - {uc.camera_status.cget('text')}" if state == "error" else ""))
    check("real camera: either streams or shows a clear error", state in ("streaming", "error"), state)
    sp.stop_camera()
    root.update()
    check("real camera: released after stop", sp.camera is None and not uc.camera_visible)
    time.sleep(0.5)
    live = [t for t in threading.enumerate() if t.name == "camera-scanner"]
    check("no camera thread left running", not live, str(live))

    root.destroy()


def main():
    try:
        test_scanner()
    except Exception as e:
        import traceback
        traceback.print_exc()
        problems.append(f"test_scanner raised {type(e).__name__}: {e}")
    try:
        test_ui()
    except Exception as e:
        import traceback
        traceback.print_exc()
        problems.append(f"test_ui raised {type(e).__name__}: {e}")

    if problems:
        print("CAMERA_FAIL")
        for p in problems:
            print(" - " + p)
        sys.exit(1)

    print(f"CAMERA_OK: {checks[0]} checks")


if __name__ == "__main__":
    main()
