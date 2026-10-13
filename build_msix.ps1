<#
    Mosaiq QR Studio - Microsoft Store package (MSIX).

    Usage (from the repository root, after .\build.ps1 produced dist\MosaiqQRStudio):
        .\build_msix.ps1          # Store package; packaging\msix\identity.json must be filled in
        .\build_msix.ps1 -Test    # dummy identity, only to check that packing works

    Output:
        dist\MosaiqQRStudio-<version>-x64.msix   (upload in Partner Center; the Store signs it)

    makeappx.exe / makepri.exe come from the Microsoft.Windows.SDK.BuildTools
    NuGet package, downloaded once into .tools\ (no Windows SDK install needed).
#>
param([switch]$Test)

$ErrorActionPreference = "Stop"

$root   = $PSScriptRoot
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$appDir = Join-Path $root "dist\MosaiqQRStudio"
$here   = Join-Path $root "packaging\msix"

if (-not (Test-Path -LiteralPath (Join-Path $appDir "MosaiqQRStudio.exe"))) {
    throw "dist\MosaiqQRStudio\MosaiqQRStudio.exe not found - run .\build.ps1 first."
}

# ---- Identity (Partner Center > Product management > Product identity) ----
$id = Get-Content -LiteralPath (Join-Path $here "identity.json") -Raw | ConvertFrom-Json
if ($Test) {
    $id.IdentityName = "MosaiqQRStudio.LocalTest"
    $id.Publisher = "CN=MosaiqQRStudioLocalTest"
    $id.PublisherDisplayName = "Local test"
    $id.DisplayName = "Mosaiq QR Studio (test)"
} elseif (($id.PSObject.Properties.Value -join " ") -match "TODO") {
    throw "Fill in packaging\msix\identity.json from Partner Center first (or use -Test)."
}

# ---- Tools: makeappx / makepri from the SDK BuildTools NuGet package ----
$tools = Join-Path $root ".tools\sdk-buildtools"
function Find-Tool($name) {
    Get-ChildItem -LiteralPath $tools -Recurse -Filter $name -ErrorAction SilentlyContinue |
        Where-Object { $_.DirectoryName -match '\\x64$' } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not (Find-Tool "makeappx.exe")) {
    Write-Host "==> Downloading Microsoft.Windows.SDK.BuildTools (one time)..."
    New-Item -ItemType Directory -Force -Path $tools | Out-Null
    $pkg = Join-Path $tools "buildtools.zip"
    Invoke-WebRequest -UseBasicParsing -OutFile $pkg `
        -Uri "https://www.nuget.org/api/v2/package/Microsoft.Windows.SDK.BuildTools"
    Expand-Archive -LiteralPath $pkg -DestinationPath $tools -Force
    Remove-Item -LiteralPath $pkg
}
$makeappx = Find-Tool "makeappx.exe"
$makepri  = Find-Tool "makepri.exe"
if (-not $makeappx -or -not $makepri) { throw "makeappx.exe / makepri.exe not found under $tools" }

# ---- Layout: the PyInstaller app + Assets + AppxManifest.xml + resources.pri ----
$work   = Join-Path $root "dist\msix"
$layout = Join-Path $work "layout"
Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $layout | Out-Null
Write-Host "==> Copying the app into the package layout..."
Copy-Item -Path (Join-Path $appDir "*") -Destination $layout -Recurse

Write-Host "==> Rendering logo assets..."
& $venvPy (Join-Path $here "make_assets.py") (Join-Path $layout "Assets")
if ($LASTEXITCODE -ne 0) { throw "make_assets.py failed" }

$manifest = Get-Content -LiteralPath (Join-Path $here "AppxManifest.xml.in") -Raw
foreach ($key in "IdentityName", "Publisher", "PublisherDisplayName", "DisplayName", "Version") {
    $value = [System.Security.SecurityElement]::Escape([string]$id.$key)
    $manifest = $manifest.Replace("@@$key@@", $value)
}
[System.IO.File]::WriteAllText((Join-Path $layout "AppxManifest.xml"), $manifest,
    (New-Object System.Text.UTF8Encoding $false))

# resources.pri lets Windows pick the scale-/targetsize- image variants.
# Index only Assets + the manifest, not the ~2000 files of the app itself.
Write-Host "==> Generating resources.pri..."
$priRoot = Join-Path $work "pri"
New-Item -ItemType Directory -Force -Path $priRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $layout "Assets") -Destination $priRoot -Recurse
Copy-Item -LiteralPath (Join-Path $layout "AppxManifest.xml") -Destination $priRoot
$priConfig = Join-Path $work "priconfig.xml"
& $makepri createconfig /cf $priConfig /dq en-US /pv 10.0.0 /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makepri createconfig failed" }
& $makepri new /pr $priRoot /cf $priConfig /mn (Join-Path $priRoot "AppxManifest.xml") `
    /of (Join-Path $layout "resources.pri") /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makepri new failed" }

# ---- Pack ----
$suffix = if ($Test) { "-test" } else { "" }
$out = Join-Path $root ("dist\MosaiqQRStudio-{0}-x64{1}.msix" -f $id.Version, $suffix)
Write-Host "==> Packing $out ..."
& $makeappx pack /d $layout /p $out /o | Out-Null
if ($LASTEXITCODE -ne 0) { throw "makeappx pack failed (rerun without '| Out-Null' to see why)" }

Write-Host ""
Write-Host "==> MSIX OK: $out" -ForegroundColor Green
if ($Test) {
    Write-Host "    Test identity - for checking the build only, not for upload."
} else {
    Write-Host "    Upload it in Partner Center (Packages). The Store signs it; do not sign it yourself."
}
