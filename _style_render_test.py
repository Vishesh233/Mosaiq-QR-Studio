"""QR style engine: module / eye shapes, gradients, colours and logo.

Every style must produce a code that the app's own scanner reads back, the plain style must be
pixel-identical to what the old renderer produced, and every module must sit where the QR
matrix says it should (checked by sampling the picture).

Run:  .venv\\Scripts\\python.exe _style_render_test.py
"""
import itertools
import os
import sys
import tempfile

os.environ.setdefault("PYTHONUTF8", "1")

problems = []


def check(label, ok, detail=""):
    if not ok:
        problems.append(f"{label} {detail}".strip())


def payloads_under_test():
    from utils import qr_payloads as p
    return {
        "url": "https://example.com/style-check?x=1&y=two",
        "text": "hello world",
        "upi": p.build_upi("shop@okaxis", "Corner Shop", "99.50", "Order 7"),
        "wifi": p.build_wifi("MyNetwork", "secret-pass1", "WPA"),
        "contact": p.build_vcard("Asha Verma", "+91 98765 43210", "asha@example.com", "Mosaiq"),
        "email": p.build_email("hi@example.com", "Hello", "Body text"),
        "sms": p.build_sms("+919876543210", "On my way"),
    }


def test_every_style_scans():
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle, MODULE_SHAPES, EYE_SHAPES, GRADIENTS
    from utils.qr_scanner import QRScanner

    generator = QRGenerator()
    for kind, text in payloads_under_test().items():
        for module, eye, gradient in itertools.product(MODULE_SHAPES, EYE_SHAPES, GRADIENTS):
            style = QRStyle(module_shape=module, eye_shape=eye, gradient=gradient,
                            fg="#0E7490", fg2="#1E3A8A", bg="#FFFFFF")
            image = generator.generate(text, style=style).convert("RGB")
            plain = QRScanner.decode_image(image, thorough=False)
            check(f"{kind} {module}/{eye}/{gradient}: plain scan", plain == text, repr(plain))


def test_plain_style_matches_the_old_renderer():
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    from PIL import ImageChops
    from utils.qr_generator import QRGenerator

    for text in ("https://example.com/a", "WIFI:T:WPA;S:Net;P:pw;;", "x" * 300):
        qr = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_H, box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        old = qr.make_image(fill_color="#102030", back_color="#F0E0D0").convert("RGB")
        new = QRGenerator().generate(text, "#102030", "#F0E0D0").convert("RGB")
        check(f"same size ({len(text)} chars)", old.size == new.size, f"{old.size} vs {new.size}")
        if old.size == new.size:
            diff = ImageChops.difference(old, new).getbbox()
            check(f"identical pixels ({len(text)} chars)", diff is None, f"differs inside {diff}")


def test_modules_sit_where_the_matrix_says():
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle, MODULE_SHAPES, EYE_SHAPES, finder_origins
    from utils import colors

    generator = QRGenerator()
    text = "https://example.com/grid-check?abc=123"
    matrix, version = generator.matrix(text)
    size = len(matrix)
    origins = finder_origins(size, generator.border)

    def in_eye(x, y):
        return any(ox <= x + generator.border < ox + 7 and oy <= y + generator.border < oy + 7
                   for ox, oy in origins)

    for module, eye in itertools.product(MODULE_SHAPES, EYE_SHAPES):
        style = QRStyle(module_shape=module, eye_shape=eye, fg="#000000", bg="#FFFFFF")
        image = generator.generate(text, style=style).convert("L")
        wrong = 0
        for y in range(size):
            for x in range(size):
                if in_eye(x, y):
                    continue
                cx = (x + generator.border) * generator.box_size + generator.box_size // 2
                cy = (y + generator.border) * generator.box_size + generator.box_size // 2
                is_dark = image.getpixel((cx, cy)) < 128
                if is_dark != bool(matrix[y][x]):
                    wrong += 1
        check(f"{module}/{eye}: module centres match the matrix", wrong == 0, f"{wrong} wrong")
        # finder patterns: ring dark, gap light, centre dark
        for ox, oy in origins:
            def at(mx, my):
                return image.getpixel((int((ox + mx) * generator.box_size),
                                       int((oy + my) * generator.box_size))) < 128
            check(f"{module}/{eye}: eye ring dark / gap light / centre dark",
                  at(3.5, 0.5) and not at(3.5, 1.5) and at(3.5, 3.5))
        # quiet zone stays empty
        check(f"{module}/{eye}: quiet zone empty",
              image.getpixel((3, 3)) > 200 and image.getpixel((image.width - 4, image.height // 2)) > 200)


def test_colours_and_gradients():
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle
    from utils import colors

    generator = QRGenerator()
    text = "https://example.com/colour-check"
    matrix, _ = generator.matrix(text)
    size = len(matrix)
    box, border = generator.box_size, generator.border

    def module_colour(image, x, y):
        return image.getpixel(((x + border) * box + box // 2, (y + border) * box + box // 2))[:3]

    def near(a, b, tolerance=14):
        return all(abs(p - q) <= tolerance for p, q in zip(a, b))

    # solid colours
    image = generator.generate(text, style=QRStyle(fg="#AA2244", bg="#EEFF00")).convert("RGB")
    check("solid: dark module has the QR colour", near(module_colour(image, 0, 0), (0xAA, 0x22, 0x44), 2))
    check("solid: background colour", near(image.getpixel((2, 2)), (0xEE, 0xFF, 0x00), 2))

    # linear: top-left is fg, bottom-right is fg2; radial: centre fg, corner fg2
    dark = [(x, y) for y in range(size) for x in range(size) if matrix[y][x]]
    first = min(dark, key=lambda p: p[0] + p[1])
    last = max(dark, key=lambda p: p[0] + p[1])
    linear = generator.generate(text, style=QRStyle(fg="#FF0000", fg2="#0000FF", gradient="linear")).convert("RGB")
    check("linear: starts with the first colour", module_colour(linear, *first)[0] > 200 and module_colour(linear, *first)[2] < 60,
          str(module_colour(linear, *first)))
    check("linear: ends with the second colour", module_colour(linear, *last)[2] > 200 and module_colour(linear, *last)[0] < 60,
          str(module_colour(linear, *last)))
    radial = generator.generate(text, style=QRStyle(fg="#FF0000", fg2="#0000FF", gradient="radial")).convert("RGB")
    centre = min(dark, key=lambda p: (p[0] - size / 2) ** 2 + (p[1] - size / 2) ** 2)
    corner = max(dark, key=lambda p: min(p[0], size - p[0]) * 0 + (p[0] - size / 2) ** 2 + (p[1] - size / 2) ** 2)
    check("radial: centre is the first colour", module_colour(radial, *centre)[0] > 200,
          str(module_colour(radial, *centre)))
    check("radial: edge leans to the second colour", module_colour(radial, *corner)[2] > module_colour(radial, *corner)[0],
          str(module_colour(radial, *corner)))

    # gradient with identical colours is just a solid fill
    flat = generator.generate(text, style=QRStyle(fg="#336699", fg2="#336699", gradient="linear")).convert("RGB")
    check("identical gradient colours = solid", near(module_colour(flat, *first), module_colour(flat, *last), 1))

    # every dark pixel of a gradient is a blend of the two colours (no stray hues)
    check("gradient pixels stay between the two colours",
          all(min(0xFF, 0) <= module_colour(linear, x, y)[1] <= 3 for x, y in dark[:200]))


def test_logo():
    from PIL import Image, ImageDraw
    from utils.qr_generator import QRGenerator
    from utils.qr_render import QRStyle, MAX_LOGO_SCALE
    from utils.qr_scanner import QRScanner

    tmp = tempfile.mkdtemp()
    logo_path = os.path.join(tmp, "logo.png")
    logo = Image.new("RGBA", (200, 120), (0, 0, 0, 0))               # transparent corners
    ImageDraw.Draw(logo).ellipse((20, 0, 180, 120), fill=(220, 30, 60, 255))
    logo.save(logo_path)

    generator = QRGenerator()
    text = "https://example.com/logo-check"
    plain = generator.generate(text)
    for scale in (0.10, 0.20, 0.25):
        style = QRStyle(logo_scale=scale, fg="#0E7490")
        image = generator.generate(text, style=style, logo_path=logo_path).convert("RGB")
        centre = image.getpixel((image.width // 2, image.height // 2))
        check(f"logo {scale}: logo visible in the middle", centre[0] > 180 and centre[1] < 90, str(centre))
        check(f"logo {scale}: still scans", QRScanner.decode_image(image, thorough=False) == text)
        check(f"logo {scale}: size unchanged", image.size == plain.size)

    # a transparent logo corner shows the clear patch (background), not the QR modules
    style = QRStyle(logo_scale=0.25, bg="#FFFFFF")
    image = generator.generate(text, style=style, logo_path=logo_path).convert("RGB")
    code = (image.width - 8 * generator.box_size)
    side = int(round(code * 0.25))
    left = 4 * generator.box_size + (code - side) // 2
    corner = image.getpixel((left + 2, left + 2))
    check("logo patch is clear background", corner == (255, 255, 255), str(corner))

    check("logo size is capped", QRStyle(logo_scale=5).logo_scale == MAX_LOGO_SCALE)
    check("logo size has a floor", QRStyle(logo_scale=-1).logo_scale >= 0.05)
    check("junk logo size falls back", QRStyle(logo_scale="big").logo_scale == 0.2)

    # a missing / broken logo file raises instead of silently dropping the logo
    for bad in (os.path.join(tmp, "missing.png"), None):
        if bad is None:
            continue
        try:
            generator.generate(text, logo_path=bad)
            check("missing logo file reported", False)
        except (OSError, ValueError):
            pass
    broken = os.path.join(tmp, "broken.png")
    with open(broken, "wb") as fh:
        fh.write(b"not an image")
    try:
        generator.generate(text, logo_path=broken)
        check("broken logo file reported", False)
    except (OSError, ValueError):
        pass


def test_style_data():
    from utils.qr_render import QRStyle

    style = QRStyle(module_shape="dots", eye_shape="rounded", fg="#112233", bg="#FFEEDD",
                    gradient="radial", fg2="#445566", logo_scale=0.22)
    check("to_dict / from_dict round trip", QRStyle.from_dict(style.to_dict()) == style)
    for junk in (None, 5, "x", [], {"module_shape": "triangle", "fg": "red", "gradient": 3,
                                    "unknown": 1, "logo_scale": None}):
        loaded = QRStyle.from_dict(junk)
        check(f"from_dict({junk!r}) gives a usable style",
              loaded.module_shape == "square" and loaded.fg == "#000000" and loaded.gradient == "none")
    check("colours are normalised", QRStyle(fg="#abc", bg="fff").fg == "#AABBCC"
          and QRStyle(fg="#abc", bg="fff").bg == "#FFFFFF")
    check("bad colour falls back", QRStyle(fg="nonsense").fg == "#000000")
    check("styles are hashable and comparable", QRStyle() == QRStyle() and len({QRStyle(), QRStyle()}) == 1)


def test_sizes_and_errors():
    from utils.qr_generator import QRGenerator
    from utils.qr_scanner import QRScanner

    generator = QRGenerator()
    for text in ("a", "x" * 120, "y" * 700):
        matrix, version = generator.matrix(text)
        image = generator.generate(text)
        check(f"size follows the version ({len(text)} chars, v{version})",
              image.size == ((len(matrix) + 8) * 10,) * 2)
        check(f"big/small codes scan ({len(text)} chars)",
              QRScanner.decode_image(image.convert("RGB")) == text)
    for bad in ("", "   ", None):
        try:
            generator.generate(bad)
            check(f"empty data {bad!r} rejected", False)
        except ValueError:
            pass
    try:
        generator.generate("z" * 5000)
        check("too much data rejected", False)
    except ValueError as e:
        check("too much data message", "too much data" in str(e), str(e))


def main():
    test_style_data()
    test_plain_style_matches_the_old_renderer()
    test_modules_sit_where_the_matrix_says()
    test_colours_and_gradients()
    test_logo()
    test_sizes_and_errors()
    test_every_style_scans()
    if problems:
        print("STYLE_RENDER_FAIL")
        for p in problems[:60]:
            print(" -", p)
        sys.exit(1)
    print("STYLE_RENDER_OK: all styles scan, plain style identical to before, modules on the matrix, gradients, logo")


if __name__ == "__main__":
    main()
