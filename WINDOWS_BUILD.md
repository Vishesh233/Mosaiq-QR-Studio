# Windows Build & Release — QR Code Studio v2

This project is a **Python CustomTkinter desktop application** (not a web app).
It is packaged for Windows with **PyInstaller** into a standalone `.exe`.

No application source files were changed. Three new files were added for packaging:

| File | Purpose |
|------|---------|
| `QRCodeStudio.spec` | PyInstaller build definition (hidden imports, data, DLLs). |
| `build.ps1` | One-command build script (installs PyInstaller, cleans, builds). |
| `WINDOWS_BUILD.md` | This document (build / test / release steps). |

---

## 1. What the app actually needs at runtime (verified)

Entry point: `main.py` → `ui/app.py` (`customtkinter.CTk` window, `root.mainloop()`).

Imported at runtime:

- `customtkinter` — GUI (ships its own `assets/` with fonts, icons, themes → **must be bundled**)
- `PIL` (Pillow) — image generation / previews
- `cv2` (OpenCV) — QR **scanning** via `cv2.QRCodeDetector()`
- `numpy` — OpenCV dependency
- `qrcode` — QR generation (image backend chosen via factory → **hidden imports required**)
- `win32clipboard` (pywin32) — copy QR to Windows clipboard
- `darkdetect` — used by CustomTkinter
- `colorama`, `packaging` — transitive deps

### Important: QR scanning does NOT need ZBar / libzbar

`utils/qr_scanner.py` uses **`cv2.QRCodeDetector()`** (OpenCV's built-in decoder).
`pyzbar` is listed in `requirements.txt` but is **never imported anywhere** in the code,
and the scanner was verified to work without it. The spec therefore **excludes `pyzbar`**,
so **no external ZBar DLL (`libzbar-64.dll`) is required** for the packaged app.
(If you ever add a `pyzbar`-based scanner, you must then bundle `libzbar-64.dll` — see §6.)

### Important: only two repo data files are needed at runtime

The splash intro (`ui/splash.py`) reads `reference/qr_matrix.json` and
`reference/Exo2-BlackItalic.ttf`; the spec bundles both under `reference/`.
The rest of `reference/` (the `.html` spec and `.mp4`) is dev-only and is not shipped.

The `assets/` folder only holds README screenshots, logo PNGs and thumbnails. The brand
logo is rendered in code (`ui/brand_logo.py`), so nothing from `assets/` is loaded by the app.
**CustomTkinter's own bundled assets** must also ship (handled by `collect_all("customtkinter")`).

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
dist\QRCodeStudio\QRCodeStudio.exe    <-- the app
dist\QRCodeStudio\_internal\...       <-- required DLLs and data (do NOT delete)
```

This is a **one-folder** build. Distribute the whole `dist\QRCodeStudio\` folder
(or zip it). The `.exe` must stay next to its `_internal\` folder.

---

## 4. Test the executable locally (do this before releasing)

```powershell
cd "d:\Codes\qr code\QR-Code-Studio-v2"
.\dist\QRCodeStudio\QRCodeStudio.exe
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
   Compress-Archive -Path "dist\QRCodeStudio" -DestinationPath "dist\QRCodeStudio-$ver-win64.zip" -Force
   ```

3. Go to the repo → **Releases** → **Draft a new release**.
4. Create a tag (e.g. `v2.0`), title, and release notes.
5. **Attach** `dist\QRCodeStudio-v2.0-win64.zip` (drag & drop) and **Publish**.

CLI alternative (GitHub CLI):

```powershell
gh release create v2.0 "dist\QRCodeStudio-v2.0-win64.zip" --title "QR Code Studio v2.0" --notes "Windows build."
```

---

## 6. Notes, caveats, and recommendations

- **Executables are never committed/uploaded automatically.** Build locally, test, then attach to a Release.
- **One-file vs one-folder:** the spec produces a one-folder build (more reliable for OpenCV).
  A one-file `.exe` can be produced by merging `COLLECT` into `EXE` (drop `COLLECT`, add `a.binaries`/`a.zipfiles`/`a.datas`
  to `EXE`) but expect slower startup and more antivirus false positives — test thoroughly if you switch.
- **Antivirus / SmartScreen:** unsigned PyInstaller exes are often flagged. Users may need to click
  "More info → Run anyway". Signing the exe requires a code-signing certificate (not included).
- **`__pycache__/*.pyc` files are currently tracked in git.** Consider removing them from tracking and
  adding a `.gitignore` (e.g. `__pycache__/`, `*.pyc`, `.venv/`, `build/`, `dist/`). This does not affect the build.
- **If you later use `pyzbar`:** bundle `libzbar-64.dll` from the `pyzbar` wheel via
  `collect_all("pyzbar")` (or ship `libzbar-64.dll` next to the exe) and remove `pyzbar` from `excludes`.
- **Optional exe icon:** add `assets/app.ico` and uncomment `icon="assets/app.ico"` in the spec.
