"""Bulk Create: write many QR codes to a folder on a worker thread (no UI).

    job = BulkJob(rows, folder, style, "PNG", logo_path)
    job.start()
    ...                      # poll job.progress() from the UI thread
    job.cancel()             # takes effect before the next code

Existing files are never overwritten: a clash gets " (2)", " (3)" ... appended.
"""
import os
import queue
import threading

from utils import qr_export
from utils.app_log import get_logger
from utils.qr_generator import QRGenerator

DONE, CANCELLED = "done", "cancelled"


class BulkJob:

    def __init__(self, rows, folder, style, fmt="PNG", logo_path=None):
        self.rows = [r for r in rows if r.ok]
        self.folder = folder
        self.style = style
        self.fmt = fmt.upper()
        self.logo_path = logo_path
        self.total = len(self.rows)
        self.saved = 0
        self.failed = []                 # [(row, message)]
        self.files = []                  # paths written
        self.state = None                # None while running, then DONE or CANCELLED
        self._cancel = threading.Event()
        self._events = queue.Queue()
        self._thread = None

    # ---- control ----
    def start(self):
        if self._thread is not None:
            raise RuntimeError("This job was already started.")
        os.makedirs(self.folder, exist_ok=True)
        self._thread = threading.Thread(target=self._run, daemon=True, name="bulk-create")
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    # ---- worker ----
    def _free_path(self, stem):
        extension = qr_export.EXTENSIONS[self.fmt]
        path = os.path.join(self.folder, stem + extension)
        counter = 2
        while os.path.exists(path):
            path = os.path.join(self.folder, f"{stem} ({counter}){extension}")
            counter += 1
        return path

    def _run(self):
        generator = QRGenerator()
        try:
            for index, row in enumerate(self.rows, start=1):
                if self._cancel.is_set():
                    self.state = CANCELLED
                    break
                try:
                    path = self._free_path(row.stem)
                    qr_export.export(path, self.fmt, generator, row.payload, self.style, self.logo_path)
                    self.saved += 1
                    self.files.append(path)
                except (OSError, ValueError) as e:
                    message = (e.strerror or str(e)) if isinstance(e, OSError) else str(e)
                    self.failed.append((row, message))
                self._events.put(("progress", index, self.total))
            else:
                self.state = DONE
        except Exception:
            # Anything unexpected must not leave the window waiting forever.
            get_logger().error("Bulk Create stopped unexpectedly", exc_info=True)
            self.failed.append((None, "Bulk Create stopped unexpectedly. Details are in mosaiq.log."))
            self.state = DONE
        finally:
            self._events.put(("finished", self.saved, self.total))

    # ---- for the UI thread ----
    def progress(self):
        """(done, total, finished) after reading everything the worker reported so far."""
        done, finished = None, False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                done = event[1]
            else:
                finished = True
        return done, self.total, finished
