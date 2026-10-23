# Microsoft Store listing: Mosaiq QR Studio

Text and settings to paste into Partner Center. The package is
`dist\MosaiqQRStudio-2.2.0.0-x64.msix`, built by `build_msix.ps1`. Upload it as is;
the Store signs it.

## Properties

- **Category:** Utilities & tools (Productivity also fits)
- **Privacy policy URL:** https://github.com/Vishesh233/Mosaiq-QR-Studio/blob/main/PRIVACY.md
- **Website:** https://github.com/Vishesh233/Mosaiq-QR-Studio
- **Support contact:** https://github.com/Vishesh233/Mosaiq-QR-Studio/issues
- **System requirements:** Windows 10 version 1809 or later, 64-bit (x64)
- **Product declarations:** no in-app purchases, no ads, no account, no network access. History is kept
  on the PC only (see the privacy policy).
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
> main window opens maximized. Generate: pick a type (URL / Text, UPI Payment, WiFi, Contact,
> Email or SMS), fill in the small form, click "Generate QR", then choose PNG, SVG or PDF under
> the preview and click Save (the file name is asked in the Save dialog). Scan QR: click
> "Browse Image" and pick the saved PNG (or drag the file onto the page, or press Paste after
> copying an image); the decoded result appears on the right. "Use Camera" needs a webcam: it
> shows a live preview and reads a QR code held in front of it; without a camera it shows a
> clear message instead. "Screen Region" hides the window briefly and lets you drag a box
> around a QR code on screen. History lists the codes generated and scanned on this PC (kept
> locally; Settings has switches to turn it off, to save WiFi passwords, which is off by
> default, and to clear it). Bulk Create loads a CSV file (a sample can be downloaded in the
> app) and writes the codes to a folder. Settings is at the bottom of the sidebar; there the
> theme can be changed and the intro turned off. On Windows N editions without the Media
> Feature Pack, Generate and the rest of the app work and the Scan tab explains that the Media
> Feature Pack is needed.

## Store listing (English, United States)

### Product name

Mosaiq QR Studio

### Short description

Make styled QR codes for links, UPI, WiFi, contacts and more (dots, gradients, your logo), export
PNG, SVG or PDF, create hundreds from a CSV, and scan with your webcam, files, clipboard or
screen. Works offline.

### Description

Mosaiq QR Studio is a fast, good-looking QR code maker and scanner for Windows.

Create a QR code from a link or text, or use a ready-made form for a UPI payment, a WiFi
network, a contact card, an email or an SMS. Make it yours: pick one of eight colour presets or
your own colours, round or dotted modules, round eyes, a linear or radial gradient, and put
your logo in the middle. A test scan under the preview reads the code back and tells you
whether it scans. Save it as PNG, SVG or PDF, or copy it straight to the clipboard.

Need many codes? Bulk Create turns a CSV file into a folder of QR codes, up to 1000 at a time,
with progress and a Cancel button; rows with mistakes are listed and skipped.

History keeps the codes you generated and scanned on your PC, so you can open, copy or
re-generate them later. It can be switched off and cleared at any time, and WiFi passwords
are not saved unless you turn that on.

Scan a QR code however it reaches you: point your webcam at it, open or drag in an image file
(PNG, JPG, WEBP or BMP), paste a screenshot from the clipboard, or drag a box around it
anywhere on your screen. Mosaiq recognises what it reads and shows it clearly, such as
"WiFi: MyNetwork" or the payee and amount of a UPI code. Links open in your browser with one
click and anything decoded can be copied. Scanning a payment, WiFi or contact code never
starts a payment or changes your settings.

Eight themes, including AMOLED black and the light Daylight theme, and a cinematic intro you
can switch off at any time.

Everything runs on your PC: no account, no ads, no tracking and no internet connection
needed.

### Product features (one per field, each under 200 characters)

- Generate QR codes for links, text, UPI payments, WiFi, contacts, email and SMS
- Colour presets, an in-app colour picker and contrast advice that never blocks you
- Round or dotted modules, round eyes, linear or radial gradients
- Your logo in the centre, with a size limit that keeps the code scannable
- Test scan under the preview: "Scans correctly" or "May not scan"
- Save as PNG, SVG or PDF, or copy to the clipboard
- Bulk Create: up to 1000 codes from a CSV file, with progress and Cancel
- History of generated and scanned codes, local only, easy to switch off or clear
- WiFi passwords are not kept in history unless you choose to
- Scan with your webcam, image files, the clipboard or a region of your screen
- Eight themes with live preview, including AMOLED and a light theme
- Works offline, with no account, ads or tracking

### What's new in this version

A redesigned, calmer layout: numbered Content and Design steps, a live preview that stays in view
and a clearer Scan page. Style your codes with colour presets, a built-in colour picker, round
or dotted modules, round eyes, gradients and a logo size slider, and let the test scan check
that the result still reads. Save as PNG, SVG or PDF; the file name is now asked in the Save
dialog. New History page for generated and scanned codes (local only, can be switched off and
cleared; WiFi passwords are not saved by default) and a new Bulk Create page for making up to
1000 codes from a CSV file. The window now always opens on screen. Also in this release:
webcam, clipboard, screen-region and drag-and-drop scanning, UPI, WiFi, contact, email and SMS
forms, and better reading of dark-mode, dotted and blurred codes.

### Search terms (7)

QR code · QR generator · QR scanner · QR code maker · bulk QR code · QR code SVG · WiFi QR

### Copyright and trademark info

© 2026 Vishesh Khanna

### Screenshots (desktop, 1920 x 1140 PNG, up to 7; sample data only)

| File | Caption |
|---|---|
| `assets/images/generate.png` | Make a code from a link, UPI, WiFi, contact, email or SMS, with a live preview that stays in view |
| `assets/images/style.png` | Colour presets, dots, gradients and your logo, with a test scan that checks the result |
| `assets/images/scan.png` | Scan a QR code from an image, the clipboard, your screen or your webcam |
| `assets/images/history.png` | History of generated and scanned codes, kept only on your PC |
| `assets/images/bulk.png` | Bulk Create: turn a CSV file into up to 1000 QR codes |
| `assets/images/theme_settings.png` | Eight themes with live preview, plus history and privacy switches |
| `assets/images/light_mode.png` | The light Daylight theme |

The package already contains the app's logos (rendered by `make_assets.py`), so the
optional Store logo uploads can be skipped.
