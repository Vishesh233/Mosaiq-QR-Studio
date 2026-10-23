<#
    Mosaiq QR Studio - Windows build script (PyInstaller, one-folder).

    Usage (from the repository root, with the .venv present):
        .\build.ps1

    Output:
        dist\MosaiqQRStudio\MosaiqQRStudio.exe   (run this; keep the folder intact)
#>
$ErrorActionPreference = "Stop"

$root    = $PSScriptRoot
$venvPy  = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPy)) {
    throw "Virtualenv Python not found at: $venvPy`nCreate it first (see WINDOWS_BUILD.md)."
}

Write-Host "==> Python: $(& $venvPy --version 2>&1)"

Write-Host "==> Installing / upgrading PyInstaller..."
& $venvPy -m pip install --upgrade pyinstaller

Write-Host "==> Cleaning previous build artifacts..."
Remove-Item -LiteralPath (Join-Path $root "build") -Recurse -Force -ErrorAction SilentlyContinue
# Only the app folder and the MSIX work folder are rebuilt. Older packages and dist\old are kept.
Remove-Item -LiteralPath (Join-Path $root "dist\MosaiqQRStudio") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $root "dist\msix") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "==> Building with PyInstaller (QRCodeStudio.spec)..."
Push-Location $root
try {
    & $venvPy -m PyInstaller --noconfirm --clean --log-level WARN "QRCodeStudio.spec"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
}
finally {
    Pop-Location
}

$exe = Join-Path $root "dist\MosaiqQRStudio\MosaiqQRStudio.exe"
if (Test-Path -LiteralPath $exe) {
    Write-Host ""
    Write-Host "==> BUILD OK" -ForegroundColor Green
    Write-Host "    Executable: $exe"
    Write-Host "    Test it:    & '$exe'"
} else {
    Write-Host ""
    Write-Host "==> BUILD FAILED: executable was not produced." -ForegroundColor Red
    exit 1
}
