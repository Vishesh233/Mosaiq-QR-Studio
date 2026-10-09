"""Temporary functional test: generate -> scan -> clipboard roundtrip."""

import os

from utils.qr_generator import QRGenerator
from utils.qr_scanner import QRScanner
from utils.clipboard import ClipboardManager

TMP_PNG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_qr.png")


def main():
    print("[fn] Generating QR ...", flush=True)
    gen = QRGenerator()
    img = gen.generate("https://example.com/QR-Code-Studio-v2", qr_color="#3B82F6", bg_color="#FFFFFF")
    gen.save(img, TMP_PNG)
    print(f"[fn] Saved to {TMP_PNG}  size={img.size}  OK", flush=True)

    print("[fn] Scanning QR back ...", flush=True)
    data = QRScanner.decode(TMP_PNG)
    print(f"[fn] Decoded: {data!r}", flush=True)
    assert data == "https://example.com/QR-Code-Studio-v2", "Decode mismatch!"

    print("[fn] Copying to Windows clipboard ...", flush=True)
    ClipboardManager.copy_image(img)
    print("[fn] Clipboard copy OK", flush=True)

    print("[fn] ALL FUNCTIONAL TESTS PASSED", flush=True)
    os.remove(TMP_PNG)
    print(f"[fn] Cleaned up {TMP_PNG}", flush=True)


if __name__ == "__main__":
    main()