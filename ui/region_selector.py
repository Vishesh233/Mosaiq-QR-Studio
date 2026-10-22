"""Full-desktop overlay to drag a rectangle over a frozen screenshot."""

import tkinter as tk

from PIL import ImageTk

from utils.screen_capture import region_to_crop


class RegionSelector:
    """Shows `screenshot` across the whole desktop and lets the user drag a box.

    on_done(image, message) is called exactly once:
        image   - the selected part of the screenshot, or None
        message - why there is no image ("" when the user simply cancelled)
    The crop is taken from the frozen screenshot, not from the live screen, so
    nothing that changes after the overlay opens can end up in it.
    """

    HINT = "Drag around the QR code     Esc to cancel"

    def __init__(self, master, screenshot, origin, on_done, accent="#7C6CFF"):

        self.screenshot = screenshot
        self.on_done = on_done
        self.finished = False
        self.start = None

        width, height = screenshot.size
        left, top = origin

        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        # "+-1920" (not "-1920"): a bare minus would mean "from the right edge".
        self.window.geometry(f"{width}x{height}+{left}+{top}")

        self.canvas = tk.Canvas(
            self.window,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            cursor="crosshair",
            bg="black"
        )
        self.canvas.pack(fill="both", expand=True)
        self.window.update()

        # Windows may make the overlay a different size than the screenshot
        # (display scaling); draw at the size it got and map back on release.
        self.shown_size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        shown = screenshot
        if self.shown_size != screenshot.size:
            shown = screenshot.resize(self.shown_size)

        self.photo = ImageTk.PhotoImage(shown)
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        sw, sh = self.shown_size
        self.shades = [
            self.canvas.create_rectangle(
                0, 0, sw, sh, fill="black", stipple="gray50", outline=""
            )
            for _ in range(4)
        ]
        self._shade(None)

        self.box = self.canvas.create_rectangle(
            0, 0, 0, 0, outline=accent, width=2, state="hidden"
        )

        hint_x = sw // 2
        hint_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="black", outline="")
        hint = self.canvas.create_text(
            hint_x, 36, text=self.HINT, fill="white", font=("Segoe UI", 14)
        )
        x0, y0, x1, y1 = self.canvas.bbox(hint)
        self.canvas.coords(hint_bg, x0 - 16, y0 - 8, x1 + 16, y1 + 8)

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<ButtonPress-3>", lambda e: self._finish(None, ""))
        self.window.bind("<Escape>", lambda e: self._finish(None, ""))

        self.window.focus_force()
        self.canvas.focus_set()

    # ==================================================

    def _shade(self, rect):
        """Dim everything except `rect` (or the whole screen when None)."""
        sw, sh = self.shown_size

        if rect is None:
            areas = [(0, 0, sw, sh), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)]
        else:
            x0, y0, x1, y1 = rect
            areas = [
                (0, 0, sw, y0),
                (0, y1, sw, sh),
                (0, y0, x0, y1),
                (x1, y0, sw, y1),
            ]

        for item, area in zip(self.shades, areas):
            self.canvas.coords(item, *area)

    def _press(self, event):
        self.start = (event.x, event.y)
        self.canvas.itemconfigure(self.box, state="normal")
        self._drag(event)

    def _drag(self, event):
        if self.start is None:
            return
        x0, y0 = self.start
        rect = (min(x0, event.x), min(y0, event.y),
                max(x0, event.x), max(y0, event.y))
        self.canvas.coords(self.box, *rect)
        self._shade(rect)

    def _release(self, event):
        if self.start is None:
            return

        crop = region_to_crop(
            (*self.start, event.x, event.y),
            self.shown_size,
            self.screenshot.size
        )

        if crop is None:
            self._finish(None, "That selection was too small. Try again and drag around the whole QR code.")
        else:
            self._finish(self.screenshot.crop(crop), "")

    def _finish(self, image, message):
        if self.finished:
            return
        self.finished = True
        self.window.destroy()
        self.on_done(image, message)
