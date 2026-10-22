# Windows Build & Release — Mosaiq QR Studio

This project is a **Python CustomTkinter desktop application** (not a web app).
It is packaged for Windows with **PyInstaller** into a standalone `.exe`.

Packaging files:

| File | Purpose |
|------|---------|
| `QRCodeStudio.spec` | PyInstaller build definition (hidden imports, data, DLLs, size trim). |
| `build.ps1` | One-command build script (installs PyInstaller, cleans, builds). |
| `build_msix.ps1` | Microsoft Store package (MSIX) from the PyInstaller build (§7). |
| `packaging/msix/` | MSIX manifest template, Store identity, logo renderer, Store listing text. |
| `WINDOWS_BUILD.md` | This document (build / test / release steps). |

---

## 1. What the app actually needs at runtime (verified)

Entry point: `main.py` → `ui/app.py` (`customtkinter.CTk` window, `root.mainloop()`).

Imported at runtime:

- `customtkinter` — GUI (ships its own `assets/` with fonts, icons, themes → **must be bundled**)
- `PIL` (Pillow) — image generation / previews
- `cv2` (OpenCV) — QR **scanning** via `cv2.QRCodeDetector()`, and the webcam (`cv2.VideoCapture`, DirectShow / Media Foundation built into `cv2`)
- `numpy` — OpenCV dependency
- `qrcode` — QR generation (image backend chosen via factory → **hidden imports required**)
- `win32clipboard` (pywin32) — copy QR to Windows clipboard
- `tkinterdnd2` — optional drag and drop of image files onto the Scan page (PyInstaller's stock hook bundles only the win-x64 tkdnd library, about 0.3 MB; if it fails to load, the app runs without drop support)
- `darkdetect` — used by CustomTkinter
- `colorama`, `packaging` — transitive deps

### Important: QR scanning does NOT need ZBar / libzbar

`utils/qr_scanner.py` uses **`cv2.QRCodeDetector()`** (OpenCV's built-in decoder).
`pyzbar` is listed in `requirements.txt` but is **never imported anywhere** in the code,
and the scanner was verified to work without it. The spec therefore **excludes `pyzbar`**,
so **no external ZBar DLL (`libzbar-64.dll`) is required** for the packaged app.
(If you ever add a `pyzbar`-based scanner, you must then bundle `libzbar-64.dll` — see §6.)

### Important: three repo data files are needed at runtime

The splash intro (`ui/splash.py`) reads `reference/qr_matrix.json` and
`reference/Exo2-BlackItalic.ttf`; the window icon is `assets/app.ico`. The spec bundles all
three. `reference/qr-splash-reference.html` (the intro's design spec) is dev-only.

The rest of `assets/` (screenshots, thumbnails) is for the README and the Store listing.
**CustomTkinter's own bundled assets** must also ship (handled by `collect_all("customtkinter")`).

### Size trim

The spec leaves out what the app never loads (checked by running every feature with an
import trace): OpenCV's FFmpeg video plugin, OpenSSL (`ssl` / `_hashlib`), Pillow's AVIF
codec, NumPy's tests / f2py / typing / testing, `.pyi` stubs, C headers and `pythoncom`.
That takes the build from about 204 MB to 146 MB and the MSIX from 84 MB to 60 MB.
Most of what is left is `cv2.pyd` (82 MB), which holds all of OpenCV in one file. If a new
feature needs one of these (for example video or HTTPS), remove it from `EXCLUDES` / `_keep`.

---

## 2. Prerequisites (already present in this repo)

- Windows 10/11 (64-bit)
- A virtualenv at `.venv\` (exists) with the app's dependencies installed
- Internet access on first build (to install PyInstaller)

Verify the environment:

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\.venv\Scripts\Activate.ps1
python --version          # 3.13.x
python -m pip list
```

---

## 3. Build the executable

### Option A — one command (recommended)

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\build.ps1
```

### Option B — manual

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\.venv\Scripts\python.exe -m pip install --upgrade pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean QRCodeStudio.spec
```

### Result

```
dist\MosaiqQRStudio\MosaiqQRStudio.exe    <-- the app
dist\MosaiqQRStudio\_internal\...       <-- required DLLs and data (do NOT delete)
```

This is a **one-folder** build. Distribute the whole `dist\MosaiqQRStudio\` folder
(or zip it). The `.exe` must stay next to its `_internal\` folder.

---

## 4. Test the executable locally (do this before releasing)

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\dist\MosaiqQRStudio\MosaiqQRStudio.exe
```

Manual test checklist:

- [ ] App window opens with **no console window** and no startup error dialog.
- [ ] **Generate:** enter a URL/text → click Generate → QR preview appears.
- [ ] **Save:** Save → choose a location → PNG file is written and opens.
- [ ] **Copy:** Copy → "Copied" message; paste into Paint to confirm image clipboard.
- [ ] **Logo:** pick a small PNG logo → it is embedded in the QR.
- [ ] **Scan:** switch to Scan → upload a QR image (e.g. a PNG you just saved) →
      decoded URL/text is shown.
- [ ] **Scan link:** clicking a decoded `http(s)` URL opens the browser.
- [ ] **Smart types:** generate a UPI, WiFi, Contact, Email and SMS code; scan each back and
      check it reads "UPI payment: …", "WiFi: …" and so on. Scanning UPI must not open any app.
- [ ] **Camera:** Scan → Use Camera → hold a QR code up; the result appears and the camera
      light goes off. Also check Stop, switching to Generate, and closing the app with the
      camera running (the light must go off each time).
- [ ] **Drag and drop:** drag a PNG from File Explorer onto the Scan page.
- [ ] **Paste:** copy a QR with Snipping Tool (Win + Shift + S) → Scan → Paste (or Ctrl+V).
- [ ] **Screen Region:** Scan → Screen Region → drag around a QR code on screen; try at
      100%, 125% and 150% display scaling (Settings → System → Display).
- [ ] **Intro:** the full-screen splash plays, then the maximized main window appears.
- [ ] **Themes:** Settings ⚙ → pick a theme from the gallery (Midnight … Daylight) → Apply.

A quick headless sanity check of the generate→scan→clipboard logic (no GUI) also exists:

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\.venv\Scripts\python.exe _func_test.py
```

> Do not publish until every box above passes on a real Windows desktop.

---

## 5. Publish via GitHub Releases

1. Build and test locally (§3–§4).
2. Zip the folder (PowerShell):

   ```powershell
   cd "d:\Codes\qr code\QR-Code-Studio-v2"
   $ver = "v2.0"   # match config.py APP_VERSION if you prefer
   Compress-Archive -Path "dist\MosaiqQRStudio" -DestinationPath "dist\MosaiqQRStudio-$ver-win64.zip" -Force
   ```

3. Go to the repo → **Releases** → **Draft a new release**.
4. Create a tag (e.g. `v2.0`), title, and release notes.
5. **Attach** `dist\MosaiqQRStudio-v2.0-win64.zip` (drag & drop) and **Publish**.

CLI alternative (GitHub CLI):

```powershell
gh release create v2.0 "dist\MosaiqQRStudio-v2.0-win64.zip" --title "Mosaiq QR Studio v2.0" --notes "Windows build."
```

---

## 6. Notes, caveats, and recommendations

- **Executables are never committed/uploaded automatically.** Build locally, test, then attach to a Release.
- **One-file vs one-folder:** the spec produces a one-folder build (more reliable for OpenCV).
  A one-file `.exe` can be produced by merging `COLLECT` into `EXE` (drop `COLLECT`, add `a.binaries`/`a.zipfiles`/`a.datas`
  to `EXE`) but expect slower startup and more antivirus false positives — test thoroughly if you switch.
- **Antivirus / SmartScreen:** unsigned PyInstaller exes are often flagged. Users may need to click
  "More info → Run anyway". On PCs with **Smart App Control** on, an unsigned exe is blocked outright
  (no "Run anyway"), including on the build machine itself. Signing the exe requires a code-signing
  certificate (not included); the Microsoft Store route (§7) avoids this.
- **If you later use `pyzbar`:** bundle `libzbar-64.dll` from the `pyzbar` wheel via
  `collect_all("pyzbar")` (or ship `libzbar-64.dll` next to the exe) and remove `pyzbar` from `excludes`.
- **App icon:** `assets/app.ico` (exe + window title bars) is generated from the brand logo by
  `ui.brand_logo.save_app_icon()`.

---

## 7. Microsoft Store (MSIX)

The Store signs MSIX packages itself, so Store installs show no SmartScreen or
Smart App Control warnings.

1. In Partner Center, reserve the app name, then copy these from **Product management →
   Product identity** into `packaging\msix\identity.json`: `Package/Identity/Name`,
   `Package/Identity/Publisher` and `Package/Properties/PublisherDisplayName`. Put the
   reserved name in `DisplayName`.
2. Build:

   ```powershell
   .\build.ps1          # PyInstaller app in dist\MosaiqQRStudio
   .\build_msix.ps1     # -> dist\MosaiqQRStudio-<version>-x64.msix
   ```

   `.\build_msix.ps1 -Test` packs with a dummy identity, only to check the build.
   `makeappx` / `makepri` are downloaded once into `.tools\` (no Windows SDK needed).
   Logo assets are rendered from `ui/brand_logo.py` by `packaging\msix\make_assets.py`.
3. Upload the `.msix` under **Packages** in the submission. Do not sign it; the Store does.
   `runFullTrust` asks for a one-line justification (it is a desktop app). The manifest
   also declares the `webcam` capability (live scanning); see `packaging\msix\STORE_LISTING.md`.
4. Raise `Version` in `identity.json` for every new upload (the last part stays `0`).

Test the Store-signed build through a private audience before making the listing public.
