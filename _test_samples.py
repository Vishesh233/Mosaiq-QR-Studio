"""Hard QR samples shared by the tests: light-on-dark, dotted modules, a logo in the
middle, and a "camera looking at a phone" frame (perspective, blur, noise).

Not part of the app.
"""
import cv2
import numpy as np
import qrcode
from PIL import Image, ImageDraw
from qrcode.constants import ERROR_CORRECT_H


def render_qr(text, inverted=False, style="square", logo=True, px=14,
              shrink=0.88, border=2):
    """A QR code drawn module by module.

    inverted  white modules on a black background (phone dark mode)
    style     "square" or "dots" (data modules are round, finder patterns stay solid)
    logo      a round logo cut out of the middle (error correction H allows it)
    """
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, border=border)
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)

    fg, bg = ((255, 255, 255), (0, 0, 0)) if inverted else ((0, 0, 0), (255, 255, 255))
    image = Image.new("RGB", (n * px, n * px), bg)
    draw = ImageDraw.Draw(image)

    def in_finder(r, c):
        return ((r < border + 7 and c < border + 7)
                or (r < border + 7 and c >= n - border - 7)
                or (r >= n - border - 7 and c < border + 7))

    inset = (1 - shrink) * px / 2
    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x, y = c * px, r * px
            if style == "square" or in_finder(r, c):
                draw.rectangle((x, y, x + px - 1, y + px - 1), fill=fg)
            else:
                draw.ellipse((x + inset, y + inset, x + px - 1 - inset, y + px - 1 - inset), fill=fg)

    if logo:
        radius = int(n * px * 0.12)
        centre = n * px // 2
        draw.ellipse((centre - radius, centre - radius, centre + radius, centre + radius), fill=bg)
        draw.ellipse((centre - radius + 5, centre - radius + 5,
                      centre + radius - 5, centre + radius - 5), fill=(66, 133, 244))

    return image


def camera_frame(qr_image, seed=0, size=(1280, 720), qr_px=240, sigma=1.2,
                 noise=6, tilt=6, dark_phone=True):
    """A BGR frame like a webcam looking at a phone showing `qr_image`."""
    rng = np.random.default_rng(seed)
    frame = np.full((size[1], size[0], 3), 70, np.uint8)
    cx, cy = size[0] // 2, size[1] // 2
    w, h = int(qr_px * 1.7), int(qr_px * 2.4)
    screen = (8, 8, 8) if dark_phone else (240, 240, 240)
    cv2.rectangle(frame, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), (30, 30, 30), -1)
    cv2.rectangle(frame, (cx - w // 2 + 8, cy - h // 2 + 8),
                  (cx + w // 2 - 8, cy + h // 2 - 8), screen, -1)

    qr = np.asarray(qr_image.convert("RGB").resize((qr_px, qr_px), Image.LANCZOS))[:, :, ::-1]
    x0, y0 = cx - qr_px // 2, cy - qr_px // 2
    frame[y0:y0 + qr_px, x0:x0 + qr_px] = qr

    corners = np.float32([[0, 0], [size[0], 0], [size[0], size[1]], [0, size[1]]])
    jitter = np.float32([[rng.uniform(-tilt, tilt) * 4, rng.uniform(-tilt, tilt) * 4] for _ in range(4)])
    matrix = cv2.getPerspectiveTransform(corners, corners + jitter)
    frame = cv2.warpPerspective(frame, matrix, size, borderValue=(70, 70, 70))
    frame = cv2.GaussianBlur(frame, (0, 0), sigma)
    noisy = frame.astype(np.float32) + rng.normal(0, noise, frame.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)
