# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for QR Code Studio v2 (Windows, one-folder build).
#
#   python -m PyInstaller --noconfirm --clean QRCodeStudio.spec
#
# Produces: dist\QRCodeStudio\QRCodeStudio.exe  (+ all DLLs/data next to it)
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
    "pythoncom",
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

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pyzbar",  # not used by the app; avoids needing libzbar-64.dll
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QRCodeStudio",
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
    # icon="assets/app.ico",  # optional: add a .ico file and uncomment to set the exe icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="QRCodeStudio",
)
