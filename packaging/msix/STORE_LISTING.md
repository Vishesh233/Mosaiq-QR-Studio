# Microsoft Store listing: Mosaiq QR Studio

Text and settings to paste into Partner Center. The package is
`dist\MosaiqQRStudio-2.1.0.0-x64.msix`, built by `build_msix.ps1`. Upload it as is;
the Store signs it.

## Properties

- **Category:** Utilities & tools (Productivity also fits)
- **Privacy policy URL:** https://github.com/Vishesh233/Mosaiq-QR-Studio/blob/main/PRIVACY.md
- **Website:** https://github.com/Vishesh233/Mosaiq-QR-Studio
- **Support contact:** https://github.com/Vishesh233/Mosaiq-QR-Studio/issues
- **System requirements:** Windows 10 version 1809 or later, 64-bit (x64)
- **Product declarations:** no in-app purchases, no ads, no account, no network access.
  The package declares the **webcam** capability (Scan tab > Use Camera); the listing will
  show "Use your camera". Camera images stay in memory and are never saved or sent.

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

## Capability: webcam

> The Scan tab has a "Use Camera" button that looks for a QR code through the webcam. The
> camera is opened only while that view is showing and is released when a code is found, on
> Stop, when the user leaves the tab and when the app closes. Frames are processed in memory
> and never saved or sent anywhere. The privacy policy (linked above) describes this.

## Notes for certification

> Desktop app, no sign-in. On launch an intro animation plays for about 9 seconds, then the
> main window opens maximized. Generate tab: pick a type (URL / Text, UPI Payment, WiFi,
> Contact, Email or SMS), fill in the small form, click "Generate QR", then "Save As".
> Scan tab: click "Browse Image" and pick the saved PNG (or drag the file onto the Scan
> page, or press Paste after copying an image); the decoded result appears on the right.
> "Use Camera" needs a webcam: it shows a live preview and reads a QR code held in front of
> it; without a camera it shows a clear message instead. "Screen Region" hides the window
> briefly and lets you drag a box around a QR code on screen. The gear icon (top right)
> opens Settings, where the theme can be changed and the intro turned off.

## Store listing (English, United States)

### Product name

Mosaiq QR Studio

### Short description

Make QR codes for links, UPI, WiFi, contacts and more, with your colours and logo, and scan
them with your webcam, image files, the clipboard or your screen. Works offline.

### Description

Mosaiq QR Studio is a fast, good-looking QR code maker and scanner for Windows.

Create a QR code from a link or text, or use a ready-made form for a UPI payment, a WiFi
network, a contact card, an email or an SMS. Pick its colours, place your logo in the middle
and save it as a PNG, or copy it straight to the clipboard. Codes use high error correction,
so they still scan with a logo on top.

Scan a QR code however it reaches you: point your webcam at it, open or drag in an image file
(PNG, JPG, WEBP or BMP), paste a screenshot from the clipboard, or drag a box around it
anywhere on your screen. Mosaiq recognises what it reads and shows it clearly, such as
"WiFi: MyNetwork" or the payee and amount of a UPI code. Links open in your browser with one
click and anything decoded can be copied. Scanning a payment, WiFi or contact code never
starts a payment or changes your settings.

Make it yours with eight themes, including AMOLED black and the light Daylight theme, and a
cinematic intro you can switch off at any time.

Everything runs on your PC: no account, no ads, no tracking and no internet connection
needed.

### Product features (one per field, each under 200 characters)

- Generate QR codes for links, text, UPI payments, WiFi, contacts, email and SMS
- Custom QR and background colours
- Add your logo to the centre of the code
- High error correction, so codes still scan with a logo
- Save as PNG or copy to the clipboard
- Scan with your webcam, from image files, the clipboard or a region of your screen
- Drag and drop an image onto the Scan page
- Scanned UPI, WiFi, contact, email and SMS codes shown in a readable form, with copy buttons
- Open scanned links in one click and copy any decoded text
- Eight themes with live preview, including AMOLED and a light theme
- Cinematic intro animation that can be turned off
- Works offline, with no account, ads or tracking

### What's new in this version

Scan with your webcam, paste an image from the clipboard, select a region of your screen or
drag an image onto the window. New QR types with their own forms: UPI payment, WiFi, contact,
email and SMS, and scanned codes of these types are shown in a readable form. Reads
light-on-dark (dark mode) and dotted QR codes, blurred webcam pictures and tightly cropped
images, and shows clear messages when an image cannot be read. Scanned links now have
"Open link" and "Copy link" buttons.

### Search terms (7)

QR code · QR generator · QR scanner · QR code maker · WiFi QR · UPI QR · QR code reader

### Copyright and trademark info

© 2026 Vishesh Khanna

### Screenshots (desktop, 1920 × 1140 PNG)

| File | Caption |
|---|---|
| `assets/images/generate.png` | Design a QR code with your colours, a logo and a live preview |
| `assets/images/scan.png` | Scan a QR code from an image, the clipboard, your screen or your webcam |
| `assets/images/theme_settings.png` | Eight themes with live preview |
| `assets/images/light_mode.png` | Light mode with the Daylight theme |
| `assets/thumbnail/qr-studio-splash-1920x1080.png` | The intro animation (can be turned off) |

The package already contains the app's logos (rendered by `make_assets.py`), so the
optional Store logo uploads can be skipped.
