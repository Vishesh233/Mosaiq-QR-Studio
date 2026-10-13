# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for Mosaiq QR Studio (Windows, one-folder build).
#
#   python -m PyInstaller --noconfirm --clean QRCodeStudio.spec
#
# Produces: dist\MosaiqQRStudio\MosaiqQRStudio.exe  (+ all DLLs/data next to it)
#
# Notes:
#   * GUI app -> console = False (no black console window).
#   * One-folder (COLLECT) build is used on purpose: it is the most reliable and
#     fastest-to-start option for OpenCV + NumPy + Tkinter apps, and it avoids
#     per-launch temp extraction / antivirus false positives that one-file builds
#     of OpenCV tend to trigger.
#   * 'pyzbar' is excluded because the app never imports it (the scanner uses
#     cv2.QRCodeDetector). Excluding it means no external libzbar DLL is needed.

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# ---- Splash intro: ui/splash.py reads these two files at runtime from
#      <bundle>/reference/. The .html / .mp4 in reference/ are dev-only. ----
datas += [
    (os.path.join(SPECPATH, "reference", "qr_matrix.json"), "reference"),
    (os.path.join(SPECPATH, "reference", "Exo2-BlackItalic.ttf"), "reference"),
]

# ---- App icon: exe icon + window title bars (ui/brand_logo.apply_window_icon).
#      Regenerate with ui.brand_logo.save_app_icon(). ----
APP_ICON = os.path.join(SPECPATH, "assets", "app.ico")
datas += [(APP_ICON, "assets")]


def _collect_all(pkg):
    """collect_all is best-effort: skip anything that is not importable."""
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[spec] WARNING: could not collect '{pkg}': {exc}")


# ---- CustomTkinter: ships its own fonts / icons / themes (must be bundled) ----
_collect_all("customtkinter")

# ---- darkdetect: used by CustomTkinter for OS light/dark detection ----
_collect_all("darkdetect")

# ---- OpenCV: pulls cv2 extension + its DLLs + cv2/data ----
_collect_all("cv2")

# ---- NumPy: OpenCV dependency; bundling its DLLs avoids a broken frozen build ----
_collect_all("numpy")

# ---- pywin32 (Windows clipboard: utils/clipboard.py -> import win32clipboard) ----
for _pkg in (
    "win32clipboard",
    "win32api",
    "win32gui",
    "win32con",
    "pywintypes",
    "pywin32_system32",
):
    _collect_all(_pkg)

# ---- qrcode: image backends are chosen via a factory and are NOT auto-detected ----
hiddenimports += collect_submodules("qrcode")
hiddenimports += [
    "qrcode.image.pil",
    "qrcode.image.styledpil",
    "qrcode.image.styles.moduledrawers.pil",
    "qrcode.image.styles.colormasks",
]

# ---- Explicit safety hidden imports ----
hiddenimports += [
    "PIL.Image",
    "win32clipboard",
    "win32api",
    "win32gui",
]

# ---- Size trim: things the app never loads. Checked by running every feature
#      (splash, generate + logo, save, scan, settings, themes) with an import
#      trace; none of these was imported. ----
EXCLUDES = [
    "pyzbar",                       # not used; avoids needing libzbar-64.dll
    "ssl", "_ssl", "_hashlib",      # no network access; drops OpenSSL (~9 MB)
    "PIL._avif",                    # AVIF codec (~7.5 MB); pickers offer PNG/JPG/WEBP/BMP
    "numpy.f2py", "numpy.testing", "numpy.typing",
    "pythoncom", "win32com",        # no COM; the clipboard needs win32clipboard only
]
hiddenimports = [h for h in hiddenimports
                 if ".tests" not in h and not h.startswith(tuple(EXCLUDES))]


def _keep(entry):
    """Drop files only needed to build or type-check, and the video plugin."""
    dest = entry[0].replace("\\", "/").lower()
    if "opencv_videoio_ffmpeg" in dest:      # FFmpeg video I/O (~29 MB): stills only
        return False
    if dest.rsplit("/", 1)[-1].startswith("pythoncom"):   # COM runtime DLL, unused
        return False
    if dest.startswith("numpy/") and (
            "/tests/" in dest
            or dest.startswith(("numpy/f2py/", "numpy/typing/", "numpy/testing/"))):
        return False
    return not dest.endswith((".pyi", ".pxd", ".h", ".c", ".lib", ".a"))


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
a.datas = [e for e in a.datas if _keep(e)]
a.binaries = [e for e in a.binaries if _keep(e)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MosaiqQRStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX can corrupt OpenCV/NumPy DLLs -> keep disabled
    console=False,      # GUI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MosaiqQRStudio",
)
