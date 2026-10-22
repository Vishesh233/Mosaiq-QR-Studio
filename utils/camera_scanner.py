"""Live QR scanning from a webcam.

The camera is opened, read, decoded and released on ONE worker thread; the UI
thread only calls start()/stop()/poll(), so the interface never waits on the
camera. Tk widgets are never touched from the worker.
"""

import queue
import threading
import time
import traceback

import cv2
import numpy as np

from utils.qr_scanner import QRScanner

CAMERA_HELP = (
    "Check that a camera is connected, that no other app is using it, and "
    "that desktop apps are allowed to use it (Windows Settings > Privacy & "
    "security > Camera)."
)

# Preview frames are shrunk on the worker so the UI thread has little to do.
PREVIEW_MAX_WIDTH = 640


class CameraError(Exception):
    """The camera could not be opened or stopped delivering images."""


class CvFrameSource:
    """A real camera through OpenCV."""

    FAILED_READS_BEFORE_ERROR = 30
    FIRST_FRAME_ATTEMPTS = 60

    def __init__(self, capture):
        self.capture = capture

    @classmethod
    def open(cls, indices=(0, 1, 2)):
        """Open the first camera that delivers a frame; raise CameraError if none does."""

        for index in indices:
            # DirectShow opens quickly; Media Foundation is the fallback.
            for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
                capture = cv2.VideoCapture(index, backend)

                if not capture.isOpened():
                    capture.release()
                    continue

                capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

                for _ in range(cls.FIRST_FRAME_ATTEMPTS):
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        return cls(capture)
                    time.sleep(0.02)

                capture.release()

        raise CameraError("Could not open a camera. " + CAMERA_HELP)

    def read(self):
        return self.capture.read()

    def release(self):
        self.capture.release()


class CameraScanner:
    """Runs a camera on a worker thread until a QR code is decoded.

    poll() (UI thread) returns (latest preview frame or None, [events]); each
    event is a (kind, value) tuple:
        ("running", None)   first frame arrived
        ("found", text)     QR decoded; the camera stops itself
        ("error", message)  could not open / stopped delivering frames
        ("stopped", None)   always the last event; the camera is released
    """

    DECODE_EVERY = 3                 # frames; decoding every frame is wasteful
    BLACK_FRAMES_BEFORE_ERROR = 45   # ~1.5 s of pure black (blocked or covered)

    def __init__(self, source_factory=CvFrameSource.open,
                 decode=QRScanner.decode_image):
        self.source_factory = source_factory
        self.decode = decode
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.latest = None
        self.lock = threading.Lock()

    # ==================================================

    @property
    def active(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):

        if self.active:
            return

        self.stop_event.clear()
        self.latest = None
        self.events = queue.Queue()
        self.thread = threading.Thread(
            target=self._run, name="camera-scanner", daemon=True
        )
        self.thread.start()

    def stop(self, timeout=3.0):
        """Ask the worker to stop and wait briefly for the camera to be released."""

        self.stop_event.set()

        if self.thread is not None:
            self.thread.join(timeout)

    def poll(self):

        with self.lock:
            frame, self.latest = self.latest, None

        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return frame, events

    # ==================================================

    def _run(self):

        source = None

        try:
            source = self.source_factory()

            if self.stop_event.is_set():
                return

            self.events.put(("running", None))
            self._stream(source)

        except CameraError as e:
            self.events.put(("error", str(e)))

        except Exception as e:
            # Unexpected: show it to the user and leave the traceback in the log.
            traceback.print_exc()
            self.events.put(("error", f"The camera stopped unexpectedly: {e}"))

        finally:
            if source is not None:
                try:
                    source.release()
                except Exception:
                    traceback.print_exc()
            self.events.put(("stopped", None))

    def _stream(self, source):

        frames = 0
        failed_reads = 0
        black_frames = 0

        while not self.stop_event.is_set():

            ok, frame = source.read()

            if not ok or frame is None:
                failed_reads += 1
                if failed_reads >= CvFrameSource.FAILED_READS_BEFORE_ERROR:
                    raise CameraError(
                        "The camera stopped sending images. " + CAMERA_HELP
                    )
                time.sleep(0.03)
                continue

            failed_reads = 0
            frames += 1

            if int(frame.max()) < 2:
                black_frames += 1
                if black_frames >= self.BLACK_FRAMES_BEFORE_ERROR:
                    raise CameraError(
                        "The camera only shows black. The lens may be "
                        "covered, or access is blocked. " + CAMERA_HELP
                    )
            else:
                black_frames = 0

            self._publish_preview(frame)

            if frames % self.DECODE_EVERY == 0:
                text = self.decode(frame, thorough=False)
                if text:
                    self.events.put(("found", text))
                    return

    def _publish_preview(self, frame):

        height, width = frame.shape[:2]

        if width > PREVIEW_MAX_WIDTH:
            scale = PREVIEW_MAX_WIDTH / width
            frame = cv2.resize(
                frame, (PREVIEW_MAX_WIDTH, int(height * scale)),
                interpolation=cv2.INTER_AREA
            )

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        with self.lock:
            self.latest = np.ascontiguousarray(rgb)
