# Microsoft Store listing: Mosaiq QR Studio

Text and settings to paste into Partner Center. The package is
`dist\MosaiqQRStudio-2.0.1.0-x64.msix`, built by `build_msix.ps1`. Upload it as is;
the Store signs it.

## Properties

- **Category:** Utilities & tools (Productivity also fits)
- **Privacy policy URL:** https://github.com/Vishesh233/QR-Code-Studio-v2/blob/main/PRIVACY.md
- **Website:** https://github.com/Vishesh233/QR-Code-Studio-v2
- **Support contact:** https://github.com/Vishesh233/QR-Code-Studio-v2/issues
- **System requirements:** Windows 10 version 1809 or later, 64-bit (x64)
- **Product declarations:** no in-app purchases, no ads, no account, no network access

## Pricing and availability

- **Price:** Free
- **First submission:** choose a *private audience* containing your own Microsoft account.
  Install the Store-signed build from the Store, test it, then make the listing public.

## Age rating (IARC questionnaire)

The app has no violence, no user-generated content shared with others, no chat or
communication between users, no location sharing, no purchases and no built-in web
browser (scanned links open in the user's own browser). Answer accordingly; expect the
lowest rating (3+ / Everyone).

## Restricted capability: runFullTrust

> Mosaiq QR Studio is a Win32 desktop application (Python and Tkinter, packaged with
> PyInstaller) distributed as MSIX. runFullTrust is required for a packaged desktop app to
> run its own executable. The app uses no other restricted capability and makes no network
> requests.

## Notes for certification

> Desktop app, no sign-in. On launch an intro animation plays for about 9 seconds, then the
> main window opens maximized. Generate tab: type a URL, click "Generate QR", then
> "Save As". Scan tab: click "Browse Image" and pick the saved PNG; the decoded link appears on
> the right. The gear icon (top right) opens Settings, where the theme can be changed and
> the intro turned off.

## Store listing (English, United States)

### Product name

Mosaiq QR Studio

### Short description

Make and scan QR codes on your PC: your colours, your logo in the centre, and a scanner
for QR code image files. Works offline.

### Description

Mosaiq QR Studio is a fast, good-looking QR code maker and scanner for Windows.

Create a QR code from any link or text, pick its colours, place your logo in the middle and
save it as a PNG, or copy it straight to the clipboard. Codes use high error correction,
so they still scan with a logo on top.

Got a QR code in a screenshot or a photo saved on your PC? Open the image file (PNG, JPG,
WEBP or BMP) in the Scan tab and Mosaiq reads it instantly. Links are detected and open in
your browser with one click, and any decoded text can be copied.

Make it yours with eight themes, including AMOLED black and the light Daylight theme, and a
cinematic intro you can switch off at any time.

Everything runs on your PC: no account, no ads, no tracking and no internet connection
needed.

### Product features (one per field, each under 200 characters)

- Generate QR codes from links or text
- Custom QR and background colours
- Add your logo to the centre of the code
- High error correction, so codes still scan with a logo
- Save as PNG or copy to the clipboard
- Scan QR codes from PNG, JPG, WEBP and BMP image files
- Open scanned links in one click and copy any decoded text
- Eight themes with live preview, including AMOLED and a light theme
- Cinematic intro animation that can be turned off
- Works offline, with no account, ads or tracking

### What's new in this version

First Microsoft Store release: an animated intro with three colour palettes, eight themes
with live preview, logos in QR codes, scanning from image files and a refreshed interface.

### Search terms (7)

QR code · QR generator · QR scanner · QR code maker · QR with logo · scan QR image · QR code reader

### Copyright and trademark info

© 2026 Vishesh Khanna

### Screenshots (desktop, 1920 × 1140 PNG)

| File | Caption |
|---|---|
| `assets/images/generate.png` | Design a QR code with your colours, a logo and a live preview |
| `assets/images/scan.png` | Scan a QR code from an image file; links open in one click |
| `assets/images/theme_settings.png` | Eight themes with live preview |
| `assets/images/light_mode.png` | Light mode with the Daylight theme |
| `assets/thumbnail/qr-studio-splash-1920x1080.png` | The intro animation (can be turned off) |

The package already contains the app's logos (rendered by `make_assets.py`), so the
optional Store logo uploads can be skipped.
