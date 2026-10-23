"""PNG / SVG / PDF export.

The SVG is checked as XML and then drawn by a real renderer (headless Microsoft Edge): the
rendering must scan, and must match the PNG of the same code pixel for pixel closely (shapes,
gradient and logo included). The PDF is checked as a file: page size and the embedded picture
(at least 2000 px), which is pulled out of the PDF and scanned.

Run:  .venv\\Scripts\\python.exe _export_test.py
"""
import io
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

os.environ.setdefault("PYTHONUTF8", "1")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

problems = []
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
SVG_NS = "{http://www.w3.org/2000/svg}"


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def make_logo(tmp):
    from PIL import Image, ImageDraw
    path = os.path.join(tmp, "logo.png")
    logo = Image.new("RGBA", (160, 100), (0, 0, 0, 0))
    ImageDraw.Draw(logo).ellipse((20, 0, 140, 100), fill=(220, 30, 60, 255))
    ImageDraw.Draw(logo).rectangle((70, 30, 90, 70), fill=(255, 255, 255, 255))
    logo.save(path)
    return path


def edge_render(svg_path, size, out_png, tmp):
    """The SVG drawn by Edge at ``size`` x ``size`` pixels, as a PIL image (page content only)."""
    from PIL import Image
    html = os.path.join(tmp, "page_" + os.path.basename(svg_path) + ".html")
    uri = "file:///" + svg_path.replace("\\", "/")
    with open(html, "w", encoding="utf-8") as fh:
        fh.write(f'<!doctype html><html><body style="margin:0;background:#fff">'
                 f'<img src="{uri}" width="{size}" height="{size}" style="display:block"></body></html>')
    profile = tempfile.mkdtemp(prefix="edge_profile_")
    subprocess.run(
        [EDGE, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
         "--force-device-scale-factor=1", f"--user-data-dir={profile}",
         f"--window-size={size},{size + 120}", f"--screenshot={out_png}",
         "file:///" + html.replace("\\", "/")],
        check=True, timeout=90, capture_output=True)
    return Image.open(out_png).convert("RGB").crop((0, 0, size, size))


def mean_difference(a, b):
    import numpy as np
    x = np.asarray(a.convert("RGB"), dtype=np.int16)
    y = np.asarray(b.convert("RGB"), dtype=np.int16)
    return float(np.abs(x - y).mean())


def main():
    from PIL import Image
    from utils import qr_export, qr_payloads
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle
    from utils.qr_scanner import QRScanner

    tmp = tempfile.mkdtemp()
    logo_path = make_logo(tmp)
    generator = QRGenerator()
    text = qr_payloads.build_upi("shop@okaxis", "Corner Shop", "249.00", "Order 1024")

    styles = {
        "plain": QRStyle(fg="#102030", bg="#F4EFE6"),
        "rounded + linear": QRStyle(module_shape="rounded", eye_shape="rounded", gradient="linear",
                                    fg="#0E7490", fg2="#1E3A8A"),
        "dots + radial + logo": QRStyle(module_shape="dots", eye_shape="rounded", gradient="radial",
                                        fg="#9D174D", fg2="#1E1B4B", logo_scale=0.22),
        "rounded + logo": QRStyle(module_shape="rounded", fg="#064E3B", logo_scale=0.24),
    }
    with_logo = {"dots + radial + logo", "rounded + logo"}

    if not os.path.exists(EDGE):
        check("Microsoft Edge found (needed to draw the SVG)", False, EDGE)

    for name, style in styles.items():
        logo = logo_path if name in with_logo else None
        base = os.path.join(tmp, name.replace(" ", "_").replace("+", "and"))

        # ---- PNG ----
        png_path = base + ".png"
        qr_export.export(png_path, "PNG", generator, text, style, logo)
        png = Image.open(png_path).convert("RGB")
        direct = generator.generate(text, style=style, logo_path=logo).convert("RGB")
        check(f"{name}: PNG file equals the generated image", mean_difference(png, direct) == 0)

        # ---- SVG as a file ----
        svg_path = base + ".svg"
        qr_export.export(svg_path, "SVG", generator, text, style, logo)
        raw = open(svg_path, encoding="utf-8").read()
        root = ET.fromstring(raw)                                  # well-formed XML
        total = png.width // generator.box_size
        check(f"{name}: svg root and viewBox", root.tag == SVG_NS + "svg"
              and root.get("viewBox") == f"0 0 {total} {total}", str(root.attrib))
        check(f"{name}: svg size", root.get("width") == str(png.width))
        check(f"{name}: text of the QR is not in the SVG", text not in raw and "shop@okaxis" not in raw)
        check(f"{name}: background colour", style.bg in raw)
        gradient_nodes = root.findall(f".//{SVG_NS}linearGradient") + root.findall(f".//{SVG_NS}radialGradient")
        if style.gradient == "none":
            check(f"{name}: no gradient for a solid colour", not gradient_nodes)
            check(f"{name}: solid fill colour", f'fill="{style.fg}"' in raw)
        else:
            wanted = SVG_NS + ("linearGradient" if style.gradient == "linear" else "radialGradient")
            check(f"{name}: one {style.gradient} gradient", len(gradient_nodes) == 1
                  and gradient_nodes[0].tag == wanted)
            stops = [(s.get("offset"), s.get("stop-color")) for s in gradient_nodes[0]]
            check(f"{name}: gradient colours", stops == [("0", style.fg), ("1", style.fg2)], str(stops))
            check(f"{name}: modules use the gradient", 'fill="url(#fill)"' in raw)
        images = root.findall(f".//{SVG_NS}image")
        check(f"{name}: logo embedded iff there is one", len(images) == (1 if logo else 0))
        if logo:
            href = images[0].get("{http://www.w3.org/1999/xlink}href", "")
            check(f"{name}: logo is a PNG data URI", href.startswith("data:image/png;base64,"))
        check(f"{name}: SVG is compact", len(raw) < 400_000, f"{len(raw)} bytes")

        # ---- SVG drawn by a real renderer ----
        if os.path.exists(EDGE):
            drawn = edge_render(svg_path, png.width, base + "_edge.png", tmp)
            difference = mean_difference(drawn, png)
            check(f"{name}: Edge's drawing matches the PNG", difference < 4.0,
                  f"mean difference {difference:.2f}/255")
            check(f"{name}: Edge's drawing scans", QRScanner.decode_image(drawn, thorough=False) == text)

        # ---- PDF ----
        pdf_path = base + ".pdf"
        qr_export.export(pdf_path, "PDF", generator, text, style, logo)
        data = open(pdf_path, "rb").read()
        check(f"{name}: PDF header", data.startswith(b"%PDF-"))
        width = int(re.search(rb"/Width (\d+)", data).group(1))
        height = int(re.search(rb"/Height (\d+)", data).group(1))
        check(f"{name}: PDF picture is at least 2000 px", width >= 2000 and height >= 2000,
              f"{width}x{height}")
        check(f"{name}: PDF picture is square and whole modules", width == height
              and width % total == 0, f"{width}x{height}, {total} modules")
        box = re.search(rb"/MediaBox \[ ?0 0 ([\d.]+) ([\d.]+) ?\]", data)
        pt = float(box.group(1)) if box else 0
        check(f"{name}: PDF page is {width}px at 300 dpi", abs(pt - width / 300 * 72) < 1.5, f"{pt} pt")
        stream = re.search(rb"/DCTDecode.*?stream\r?\n(.*?)\r?\nendstream", data, re.S)
        check(f"{name}: PDF holds a picture stream", stream is not None)
        if stream:
            picture = Image.open(io.BytesIO(stream.group(1))).convert("RGB")
            # (the full recipe: OpenCV's quick pass is unreliable on 2000+ px pictures)
            check(f"{name}: PDF picture decodes and scans",
                  QRScanner.decode_image(picture, thorough=True) == text)

    # ---- sizes: PDF always >= 2000 px, small and huge codes ----
    for sample in ("a", "x" * 100, "y" * 1000):
        check(f"pdf size for {len(sample)} chars", qr_export.pdf_pixels(generator, sample) >= 2000)
        matrix, _ = generator.matrix(sample)
        svg = qr_export.build_svg(matrix, QRStyle(module_shape="rounded", eye_shape="rounded"), 10, 4)
        ET.fromstring(svg)
        check(f"svg for {len(sample)} chars stays small", len(svg) < 3_000_000, f"{len(svg)} bytes")

    # ---- errors ----
    try:
        qr_export.export(os.path.join(tmp, "x.bmp"), "BMP", generator, text, QRStyle())
        check("unknown format rejected", False)
    except ValueError:
        pass
    for fmt in ("PNG", "SVG", "PDF"):
        try:
            qr_export.export(os.path.join(tmp, "no_such_folder", "x"), fmt, generator, text, QRStyle())
            check(f"{fmt}: missing folder reported", False)
        except OSError:
            pass
    try:
        qr_export.export(os.path.join(tmp, "e.svg"), "SVG", generator, "", QRStyle())
        check("empty data rejected", False)
    except ValueError:
        pass
    check("formats and extensions agree", set(qr_export.FORMATS) == set(qr_export.EXTENSIONS)
          == set(qr_export.FILE_TYPES))

    if problems:
        print("EXPORT_FAIL")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("EXPORT_OK: PNG, SVG (XML + drawn by Edge, matches the PNG), PDF (>= 2000 px, scanned)")


if __name__ == "__main__":
    main()
