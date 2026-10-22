"""Test scan: read a freshly generated QR back with the app's own decoder.

It runs on a worker thread so the window never waits for it, and it never blocks anything:
the result only decides which badge is shown next to the preview. The plain (first) decoding
recipe is used on purpose: it does not try the tricks the Scan page uses for difficult
pictures (inverting, sharpening, enlarging), so a code that only decodes with those tricks is
reported as "may not scan", as many phone scanners would also struggle with it.
"""
import queue
import threading

from utils.app_log import get_logger
from utils.qr_scanner import QRScanner
from utils.scan_errors import ScannerUnavailable

OK = "ok"                      # decoded to exactly the text that was encoded
FAIL = "fail"                  # not decoded, or decoded to something else
UNAVAILABLE = "unavailable"    # OpenCV cannot load on this PC (Windows N without the Media Pack)
ERROR = "error"                # the check itself crashed (written to the error log)


def check_image(image, expected):
    """Outcome (OK / FAIL / UNAVAILABLE / ERROR) of scanning ``image`` for ``expected``."""
    try:
        text = QRScanner.decode_image(image.convert("RGB"), thorough=False)
    except ScannerUnavailable:
        return UNAVAILABLE
    except Exception:
        get_logger().error("Test scan crashed", exc_info=True)
        return ERROR
    return OK if text == expected else FAIL


class BackgroundCheck:
    """Runs check_image on a worker thread; only the newest request's result is ever reported."""

    def __init__(self):
        self._results = queue.Queue()
        self._token = 0
        self._lock = threading.Lock()

    def start(self, image, expected):
        with self._lock:
            self._token += 1
            token = self._token
        threading.Thread(target=self._run, args=(token, image.copy(), expected),
                         daemon=True, name="test-scan").start()
        return token

    def cancel(self):
        """Forget any request still running."""
        with self._lock:
            self._token += 1

    def _run(self, token, image, expected):
        self._results.put((token, check_image(image, expected)))

    def poll(self):
        """The outcome of the newest request if it has finished, else None."""
        latest = None
        while True:
            try:
                token, outcome = self._results.get_nowait()
            except queue.Empty:
                return latest
            with self._lock:
                current = self._token
            if token == current:
                latest = outcome
