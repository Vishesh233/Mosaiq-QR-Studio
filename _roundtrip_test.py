"""Round-trip tests: build payload -> generate QR image -> scan -> parse.

Run:  .venv\\Scripts\\python.exe _roundtrip_test.py
Exit code 0 = every check passed.
"""
import os
import sys
import tempfile

import time

import cv2
import numpy as np
from PIL import Image, ImageDraw

import _test_samples as samples
from utils import qr_payloads as P
from utils.qr_generator import QRGenerator
from utils.qr_scanner import QRScanner, ScanError

failures = []
checks = 0


def check(name, condition, detail=""):
    global checks
    checks += 1
    if not condition:
        failures.append(f"{name} {detail}".strip())


def expect_error(name, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except ValueError:
        check(name, True)
    else:
        check(name, False, "(no ValueError raised)")


GEN = QRGenerator()


def roundtrip(payload):
    """Payload text -> QR image -> decoded text."""
    return QRScanner.decode_image(GEN.generate(payload))


def fields_of(parsed):
    return dict(parsed.fields)


def test_upi():
    text = P.build_upi("rahul.k-1@okhdfcbank", "Rahul Kumar", "125.50",
                       "Rent & dues #5 ₹ 100%")
    check("upi: starts", text.startswith("upi://pay?pa=rahul.k-1%40okhdfcbank"))
    check("upi: space is %20", "+" not in text and "Rahul%20Kumar" in text)
    check("upi: INR", "&cu=INR" in text)
    got = roundtrip(text)
    check("upi: scan equals build", got == text, repr(got))
    parsed = P.parse(got)
    f = fields_of(parsed)
    check("upi: kind", parsed.kind == "upi")
    check("upi: payee", f.get("Payee") == "Rahul Kumar")
    check("upi: id", f.get("UPI ID") == "rahul.k-1@okhdfcbank")
    check("upi: amount", f.get("Amount") == "INR 125.50")
    check("upi: note", f.get("Note") == "Rent & dues #5 ₹ 100%", repr(f))
    check("upi: copy action", parsed.action == ("Copy UPI ID", "rahul.k-1@okhdfcbank"))

    minimal = P.build_upi("a.b@upi", "Shop")
    check("upi: optional fields omitted", "am=" not in minimal and "tn=" not in minimal)
    check("upi: minimal roundtrip", P.parse(roundtrip(minimal)).kind == "upi")

    expect_error("upi: empty id", P.build_upi, "", "X")
    expect_error("upi: bad id (no @)", P.build_upi, "rahul", "X")
    expect_error("upi: bad id (spaces)", P.build_upi, "ra hul@upi", "X")
    expect_error("upi: no name", P.build_upi, "a@upi", "  ")
    for bad in ("0", "-5", "abc", "1.234", "1e5", "10,5"):
        expect_error(f"upi: amount {bad!r}", P.build_upi, "a@upi", "X", bad)


def test_wifi():
    ssid = 'My;Net:work,"v1"\\x'
    password = 'p;a:s,s"w\\ord1'
    text = P.build_wifi(ssid, password, "WPA", True)
    check("wifi: header", text.startswith("WIFI:T:WPA;S:"))
    check("wifi: ends with ;;", text.endswith(";;"))
    check("wifi: hidden flag", "H:true;" in text)
    got = roundtrip(text)
    check("wifi: scan equals build", got == text, repr(got))
    parsed = P.parse(got)
    f = fields_of(parsed)
    check("wifi: kind", parsed.kind == "wifi")
    check("wifi: title", parsed.title == f"WiFi: {ssid}", parsed.title)
    check("wifi: ssid", f.get("Network") == ssid, repr(f))
    check("wifi: password", f.get("Password") == password, repr(f))
    check("wifi: security", f.get("Security") == "WPA")
    check("wifi: hidden", f.get("Hidden") == "Yes")
    check("wifi: copy action", parsed.action == ("Copy password", password))

    open_net = P.build_wifi("CafeFree", "ignored", "None")
    check("wifi: open network text", open_net == "WIFI:T:nopass;S:CafeFree;;", open_net)
    op = P.parse(roundtrip(open_net))
    check("wifi: open parsed", fields_of(op).get("Security") == "None" and op.action is None)

    wep = P.parse(roundtrip(P.build_wifi("Old", "12345", "WEP")))
    check("wifi: wep", fields_of(wep).get("Security") == "WEP")

    # Another app's field order, hidden=false
    other = P.parse("WIFI:S:Home;P:secret99;T:WPA2;H:false;;")
    check("wifi: foreign order", fields_of(other).get("Network") == "Home"
          and "Hidden" not in fields_of(other))

    expect_error("wifi: empty ssid", P.build_wifi, "", "12345678", "WPA")
    expect_error("wifi: long ssid", P.build_wifi, "x" * 33, "12345678", "WPA")
    expect_error("wifi: wpa no password", P.build_wifi, "N", "", "WPA")
    expect_error("wifi: short wpa password", P.build_wifi, "N", "short", "WPA")
    expect_error("wifi: unknown security", P.build_wifi, "N", "12345678", "WPA9")


def test_contact():
    name = "विशेष खन्ना"
    text = P.build_vcard(name, "+91 98765-43210", "v@example.com", "Mosaiq, Inc; R&D")
    check("vcard: version 3.0", "VERSION:3.0" in text)
    check("vcard: CRLF", "\r\n" in text)
    got = roundtrip(text)
    check("vcard: scan equals build", got == text, repr(got))
    parsed = P.parse(got)
    f = fields_of(parsed)
    check("vcard: kind", parsed.kind == "contact")
    check("vcard: name", f.get("Name") == name, repr(f))
    check("vcard: phone", f.get("Phone") == "+919876543210", repr(f))
    check("vcard: email", f.get("Email") == "v@example.com")
    check("vcard: org", f.get("Organisation") == "Mosaiq, Inc; R&D", repr(f))
    check("vcard: title", parsed.title == f"Contact: {name}")

    single = P.parse(roundtrip(P.build_vcard("Madonna")))
    check("vcard: single name", fields_of(single) == {"Name": "Madonna"})

    foreign = P.parse("BEGIN:VCARD\nVERSION:2.1\nN:Doe;Jane;;;\nTEL;CELL:12345\nEND:VCARD")
    check("vcard: foreign 2.1 (N only)", fields_of(foreign).get("Name") == "Jane Doe"
          and fields_of(foreign).get("Phone") == "12345", repr(foreign.fields))

    expect_error("vcard: no name", P.build_vcard, "")
    expect_error("vcard: bad email", P.build_vcard, "A B", "", "nope")
    expect_error("vcard: bad phone", P.build_vcard, "A B", "12ab")


def test_email():
    text = P.build_email("to@example.com", "Hello & welcome = 100%", "Line1\nLine2 + more")
    got = roundtrip(text)
    check("email: scan equals build", got == text, repr(got))
    parsed = P.parse(got)
    f = fields_of(parsed)
    check("email: kind", parsed.kind == "email")
    check("email: to", f.get("To") == "to@example.com")
    check("email: subject", f.get("Subject") == "Hello & welcome = 100%", repr(f))
    check("email: body", f.get("Message") == "Line1\nLine2 + more", repr(f))

    bare = P.parse(roundtrip(P.build_email("a@b.co")))
    check("email: bare", bare.kind == "email" and fields_of(bare) == {"To": "a@b.co"})

    expect_error("email: empty", P.build_email, "")
    expect_error("email: invalid", P.build_email, "not-an-email")


def test_sms():
    text = P.build_sms("+91 98765 43210", "Hi there\nsecond: line")
    check("sms: SMSTO", text.startswith("SMSTO:+919876543210:"))
    got = roundtrip(text)
    check("sms: scan equals build", got == text, repr(got))
    f = fields_of(P.parse(got))
    check("sms: number", f.get("To") == "+919876543210")
    check("sms: message", f.get("Message") == "Hi there\nsecond: line", repr(f))

    alt = P.parse("sms:12345?body=Hello%20you")
    check("sms: foreign sms: form", fields_of(alt) == {"To": "12345", "Message": "Hello you"})

    expect_error("sms: empty number", P.build_sms, "")
    expect_error("sms: bad number", P.build_sms, "abc")


def test_plain():
    url = P.parse(roundtrip("https://example.com/a?b=c&d=e"))
    check("plain: url", url.kind == "url")
    check("plain: www link", P.parse("www.example.com").kind == "url")
    txt = P.parse(roundtrip("just some text"))
    check("plain: text", txt.kind == "text" and txt.raw == "just some text")
    broken = P.parse("WIFI:garbage")
    check("plain: malformed wifi falls back to text", broken.kind == "text")
    broken = P.parse("upi://pay?pn=NoVpa")
    check("plain: upi without pa falls back", broken.kind == "text")


def test_scanner():
    tmp = tempfile.mkdtemp()
    image = GEN.generate("https://example.com/unicode-path")

    path = os.path.join(tmp, "क्यूआर कोड ✓.png")
    image.save(path)
    check("scanner: unicode path", QRScanner.decode(path) == "https://example.com/unicode-path")

    blank = os.path.join(tmp, "blank.png")
    Image.new("RGB", (300, 300), "white").save(blank)
    check("scanner: no QR -> None", QRScanner.decode(blank) is None)

    junk = os.path.join(tmp, "junk.png")
    with open(junk, "wb") as fh:
        fh.write(b"this is not an image")
    for name, target in (("corrupt file", junk),
                         ("missing file", os.path.join(tmp, "nope.png")),
                         ("empty file", os.path.join(tmp, "empty.png"))):
        if name == "empty file":
            open(target, "wb").close()
        try:
            QRScanner.decode(target)
        except ScanError as e:
            check(f"scanner: {name} -> ScanError", bool(str(e)))
        else:
            check(f"scanner: {name} -> ScanError", False, "(returned instead of raising)")

    small = image.resize((120, 120), Image.NEAREST)
    check("scanner: small image", QRScanner.decode_image(small) == "https://example.com/unicode-path")

    # No quiet zone (cropped tight, as screenshots often are)
    w, h = image.size
    b = 4 * 10
    cropped = image.crop((b, b, w - b, h - b))
    check("scanner: no quiet zone", QRScanner.decode_image(cropped) == "https://example.com/unicode-path")

    rgba = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rgba.alpha_composite(image.convert("RGBA"))
    check("scanner: RGBA image", QRScanner.decode_image(rgba) == "https://example.com/unicode-path")

    check("scanner: rotated 90", QRScanner.decode_image(image.rotate(90)) == "https://example.com/unicode-path")


def test_overflow():
    try:
        GEN.generate("x" * 5000)
    except ValueError as e:
        check("generator: overflow message", "too much data" in str(e).lower(), str(e))
    else:
        check("generator: overflow raises ValueError", False)

    big = P.build_vcard("A B", "123456", "a@b.co", "Org " * 20)
    check("generator: normal vCard fits", roundtrip(big) == big)


def test_hard_images():
    """Light-on-dark, logo in the middle, dotted modules, blur, camera-like frames."""
    # A Google Pay style UPI link (extra mc / mode / purpose parameters).
    gpay = "upi://pay?pa=someone@okhdfcbank&pn=Some%20Shop&mc=0000&mode=02&purpose=00"
    for text, label in ((gpay, "gpay-style"), (P.build_upi("a.b@okaxis", "Cafe", "99.50", "Lunch"), "app-built")):
        parsed = P.parse(text)
        check(f"hard[{label}]: parses as UPI", parsed.kind == "upi", parsed.kind)

        # Generated by this app with white-on-black colours and a logo, then scanned back.
        tmp = tempfile.mkdtemp()
        logo = os.path.join(tmp, "logo.png")
        mark = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(mark).ellipse((0, 0, 199, 199), fill=(66, 133, 244, 255))
        mark.save(logo)
        for colours in (("#FFFFFF", "#000000"), ("#000000", "#FFFFFF"), ("#FFD60A", "#101820")):
            image = QRGenerator().generate(text, qr_color=colours[0], bg_color=colours[1], logo_path=logo)
            check(f"hard[{label}]: generator round-trip {colours}",
                  QRScanner.decode_image(image) == text)

        for inverted in (False, True):
            for style in ("square", "dots"):
                tag = f"{label} {'light-on-dark' if inverted else 'dark-on-light'} {style}+logo"
                qr = samples.render_qr(text, inverted=inverted, style=style, logo=True)
                check(f"hard[{tag}]: clean image", QRScanner.decode_image(qr) == text)

                # Webcam looking at a phone: tilt, blur, noise.
                for sigma in (0.6, 1.2, 1.8):
                    ok = sum(
                        QRScanner.decode_image(samples.camera_frame(qr, seed=i, sigma=sigma)) == text
                        for i in range(5)
                    )
                    # Sharp and moderately blurred must always work; at 1.8 (very soft) allow one miss.
                    need = 5 if sigma <= 1.2 else 4
                    check(f"hard[{tag}]: camera frame, blur {sigma} (still, all recipes)", ok >= need, f"{ok}/5")

                # What the live camera does: ONE recipe per frame, cycling. The
                # whole cycle must find it, and no single attempt may find a wrong text.
                frame = samples.camera_frame(qr, seed=11, sigma=1.2)
                found = [QRScanner.decode_image(frame, variant=i) for i in range(12)]
                check(f"hard[{tag}]: camera cycle finds it", text in found, str(found[:6]))
                check(f"hard[{tag}]: camera attempts never return wrong text",
                      all(f in (None, text) for f in found), str(found))

    # No QR: nothing may be "found" (no false positives from the extra recipes).
    rng = np.random.default_rng(5)
    for i in range(10):
        noise = rng.integers(0, 255, (480, 640), dtype=np.uint8)
        check(f"hard: random noise {i} has no QR", QRScanner.decode_image(noise) is None)
    check("hard: blank white", QRScanner.decode_image(np.full((480, 640), 255, np.uint8)) is None)
    check("hard: blank black", QRScanner.decode_image(np.zeros((480, 640), np.uint8)) is None)

    # How long does a "nothing here" scan take on big images? (stills run on the UI thread)
    for size in ((1280, 720), (1920, 1080), (3840, 2160)):
        blank = np.full((size[1], size[0]), 128, np.uint8)
        started = time.perf_counter()
        QRScanner.decode_image(blank)
        took = time.perf_counter() - started
        print(f"[roundtrip] no-QR scan of {size[0]}x{size[1]}: {took:.2f} s")
        check(f"hard: no-QR scan of {size[0]}x{size[1]} stays under 5 s", took < 5.0, f"{took:.1f}s")


def main():
    for test in (test_upi, test_wifi, test_contact, test_email, test_sms,
                 test_plain, test_scanner, test_overflow, test_hard_images):
        try:
            test()
        except Exception as e:  # report which group blew up, then keep going
            failures.append(f"{test.__name__} raised {type(e).__name__}: {e}")

    if failures:
        print("ROUNDTRIP_FAIL")
        for line in failures:
            print(" - " + line)
        sys.exit(1)

    print(f"ROUNDTRIP_OK: {checks} checks")


if __name__ == "__main__":
    main()
