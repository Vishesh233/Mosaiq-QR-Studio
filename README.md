# Mosaiq QR Studio

![Mosaiq QR Studio](assets/thumbnail/qr-studio-splash-1920x1080.png)

A Windows desktop app for making and scanning QR codes, with a cinematic intro and eight themes.
Formerly *QR Code Studio v2*. Coming to the Microsoft Store.

## Features

### Generate
- QR codes from any URL or text
- Custom QR and background colours
- Your logo in the centre (high error correction, so the code still scans)
- Live preview, then save as a 1200 × 1200 PNG or copy it to the clipboard

### Scan
- Decode a QR code from an image (PNG, JPG, JPEG, WEBP, BMP)
- Links are detected and open in your browser with one click
- Copy the decoded text

### Look and feel
- Full-screen animated intro in three palettes: Aqua Mint, Ultraviolet, Ember (can be turned off in Settings)
- Eight themes with live preview: Midnight, Graphite, AMOLED, Aqua Mint, Ultraviolet, Ember, Emerald and the light Daylight
- Remembers your theme and intro preference
- Works fully offline; nothing is collected or sent ([privacy policy](PRIVACY.md))

## Screenshots

| Generate | Scan |
|---|---|
| ![Generate a QR code](assets/images/generate.png) | ![Scan a QR code](assets/images/scan.png) |
| **Themes** | **Light mode** |
| ![Theme gallery](assets/images/theme_settings.png) | ![Daylight theme](assets/images/light_mode.png) |

## Run from source

Windows 10/11 and Python 3.13:

```powershell
git clone https://github.com/Vishesh233/QR-Code-Studio-v2.git
cd QR-Code-Studio-v2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

To skip the intro, run `main.py --no-splash` or set `QRSTUDIO_NO_SPLASH=1`.

## Build

| Output | Command |
|---|---|
| Windows app (PyInstaller, one folder) | `.\build.ps1` → `dist\MosaiqQRStudio\MosaiqQRStudio.exe` |
| Microsoft Store package (MSIX) | `.\build_msix.ps1` → `dist\MosaiqQRStudio-<version>-x64.msix` |

Details, test checklist and release steps are in [WINDOWS_BUILD.md](WINDOWS_BUILD.md).

## Tech stack

Python · CustomTkinter · Pillow · NumPy (intro renderer) · OpenCV (`cv2.QRCodeDetector`) · qrcode · pywin32 (clipboard) · PyInstaller · MSIX

## Project structure

```
QR-Code-Studio-v2/
├── main.py, config.py
├── ui/                  # app shell, pages, components, settings dialog
│   ├── splash.py        # animated intro (NumPy renderer)
│   └── brand_logo.py    # logo and app icon, drawn in code
├── utils/               # QR generator, scanner, clipboard, themes, settings
├── reference/           # intro data: QR matrix and wordmark font
├── assets/              # app icon, screenshots, thumbnails
├── packaging/msix/      # Store manifest, identity, logo assets, listing text
├── QRCodeStudio.spec    # PyInstaller build
├── build.ps1, build_msix.ps1
└── requirements.txt
```

## Roadmap

- Webcam scanning
- History of generated and scanned codes
- Batch generation

## Author

**Vishesh Khanna**

- GitHub: https://github.com/Vishesh233
- LinkedIn: https://linkedin.com/in/vishesh-khanna-210361252
