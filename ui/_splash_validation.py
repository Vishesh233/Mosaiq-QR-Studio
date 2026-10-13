"""Validation harness for the cinematic splash (dev-only, headless).

Implements section 7 of the reference spec (reference/qr-splash-reference.html):

1. Renders t = 0, 1.6, 2.4, 3.3, 4.1, 5.3, 6.2, 7.2, 8.5 s at 1280x800 with
   ``render_frame`` into ui/_splash_frames/ and builds a 3x3 contact sheet.
   Every frame is checked to stay in [0, 1] before it is quantised.
2. Numeric checks: one module per dark cell of reference/qr_matrix.json; all
   formed (e = 1) by t = 2.8 s; none broken at t = 4.4 s; no particle left at
   t >= 8.5 s (the last ends by 8440 ms); alpha_title at 0 / 2.6 / 7.6 / 8.8 s;
   the mulberry32 self-test; the section 2 layout numbers at 1280x800.
3. Frame time of ``render_frame_into`` over the one-shot timeline. The
   on-screen blit (PhotoImage paste + canvas redraw) adds ~8 ms on top.

Run:  .venv\\Scripts\\python.exe ui\\_splash_validation.py
Exits non-zero when a check fails.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

import ui.splash as sp  # noqa: E402

KEYFRAMES_S = (0.0, 1.6, 2.4, 3.3, 4.1, 5.3, 6.2, 7.2, 8.5)

# Section 2 of the spec: numbers measured from the reference at 1280x800.
LAYOUT_TOLERANCE_PX = 0.6


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_splash_frames")
    os.makedirs(out_dir, exist_ok=True)
    failures = []

    def check(ok, label):
        print("  [%s] %s" % ("ok" if ok else "FAIL", label))
        if not ok:
            failures.append(label)

    # --- 1) keyframes + 3x3 contact sheet ---------------------------------
    sp.render_frame._verify = True
    tw, th = sp.SPLASH_W // 3, sp.SPLASH_H // 3
    sheet = Image.new("RGB", (tw * 3, th * 3))
    draw = ImageDraw.Draw(sheet)
    for i, t_s in enumerate(KEYFRAMES_S):
        t = int(round(t_s * 1000))
        img = Image.fromarray(sp.render_frame(t, t))
        img.save(os.path.join(out_dir, "frame_%05d.png" % t))
        x, y = (i % 3) * tw, (i // 3) * th
        sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y))
        draw.text((x + 8, y + 6), "%d   t = %.1f s" % (i + 1, t_s), fill=(215, 244, 247))
    sp.render_frame._verify = False
    sheet_path = os.path.join(out_dir, "contact_sheet.png")
    sheet.save(sheet_path)
    print("keyframes and contact sheet ->", sheet_path)

    # --- 2) numeric checks --------------------------------------------------
    print("numeric checks")
    sc = sp._scene()
    with open(sp._QR_JSON, encoding="utf-8") as fh:
        dark = sum(row.count("1") for row in json.load(fh)["rows"])
    check(sc.n_modules == dark, "%d dark modules, as in qr_matrix.json (got %d)" % (dark, sc.n_modules))
    formed = float(np.max(sc.m_asm + sp.ASM_DUR))
    check(formed <= 2800.0, "every module fully formed by t = 2.8 s (last at %.0f ms)" % formed)
    broken = float(np.min(sc.m_brk))
    check(broken > 4400.0, "no module broken at t = 4.4 s (first at %.0f ms)" % broken)
    last = float(np.max(sc.p_brk + sc.p_dly + sc.p_life))
    check(last <= 8440.0, "last particle ends by 8440 ms (at %.0f ms)" % last)
    for t, want in ((0, 1.0), (2600, 0.3), (7600, 0.3), (8800, 1.0)):
        got = sp.title_alpha(t)
        check(abs(got - want) < 1e-9, "alpha_title(%d ms) = %g" % (t, got))

    r7, r3 = sp.mulberry32(7), sp.mulberry32(3)
    got7 = ["%.10f" % r7() for _ in range(5)]
    got3 = ["%.10f" % r3() for _ in range(3)]
    check(got7 == ["0.0117047532", "0.0619582576", "0.9769076328",
                   "0.6990287057", "0.5214452685"], "mulberry32(7) self-test")
    check(got3 == ["0.7202267838", "0.0386621605", "0.4561921926"],
          "mulberry32(3) self-test")

    title_x = sc.W / 2.0 - sc._title_width / 2.0
    ver_x = sc.W / 2.0 - sc._v2_width / 2.0
    pad = 0.12 * sc.titleFS
    for label, got, want in (
            ("QR slot x", sc.qr_x, 504.0),
            ("QR slot y", sc.qr_y, 153.0),
            ("QR side", sc.S, 272.0),
            ("title line box top", sc.title_box_top, 449.0),
            ("title line box bottom", sc.title_box_top + sc.title_box_h, 512.0),
            ("title baseline", sc.title_base, 504.0),
            ("V2 line box top", sc.ver_box_top, 514.0),
            ("V2 line box bottom", sc.ver_box_top + sc.ver_box_h, 647.0),
            ("V2 baseline", sc.ver_base, 636.0),
            ("V2 text x", ver_x, 552.1),
            ("V2 text width", sc._v2_width, 175.7)):
        check(abs(got - want) <= LAYOUT_TOLERANCE_PX,
              "%s %.1f (reference %.1f)" % (label, got, want))
    # The reference measured the title x / width for "QR CODE STUDIO"; the
    # rebranded title is checked for centring and for fitting in the frame.
    check(abs(title_x + sc._title_width / 2.0 - sc.W / 2.0) <= LAYOUT_TOLERANCE_PX,
          "title centred (x %.1f, width %.1f)" % (title_x, sc._title_width))
    check(title_x - pad >= 0 and title_x + sc._title_width + pad <= sc.W,
          "title gradient box inside the frame (%.1f .. %.1f)" % (title_x - pad, title_x + sc._title_width + pad))

    # --- 3) frame time ------------------------------------------------------
    print("frame time: render_frame_into over the one-shot timeline, 60 fps sampling")
    out = np.empty((sc.ph, sc.pw, 3), np.float32)
    u8 = np.empty((sc.ph, sc.pw, 3), np.uint8)
    sp.render_frame_into(sc, out, u8, 0.0, 0.0)          # warm-up
    times = []
    for ts in np.arange(0.0, sp.FI1 + 1.0, 1000.0 / 60.0):
        a = time.perf_counter()
        sp.render_frame_into(sc, out, u8, ts, ts)
        times.append((time.perf_counter() - a) * 1000.0)
    times = np.array(times)
    p95 = float(np.percentile(times, 95))
    print("  average %.1f ms, p95 %.1f ms, worst %.1f ms over %d frames" % (
        times.mean(), p95, times.max(), times.size))
    check(p95 < 1000.0 / 30.0, "95% of frames render in under 33.3 ms (30 fps)")

    print("FAILED: %d check(s)" % len(failures) if failures else "all checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
