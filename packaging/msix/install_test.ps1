<#
    Mosaiq QR Studio - MSIX install test and Windows App Certification Kit (WACK) run.

    RUN FROM AN ADMINISTRATOR POWERSHELL (WACK and trusting a test certificate both need it):
        cd "D:\Codes\qr code\QR-Code-Studio-v2"
        .\packaging\msix\install_test.ps1

    What it does, in order. The real .msix in dist\ is never touched or signed.
      1. Stops if a Mosaiq package is already installed (it would be replaced: you decide first).
      2. Makes a throw-away self-signed certificate that matches the package publisher and
         signs a COPY of the .msix with it (in a temp folder).
      3. Trusts the certificate (LocalMachine\TrustedPeople) and runs WACK on the copy.
      4. Installs the copy, checks Get-AppxPackage, launches the app from its Start entry and
         drives it: generate a QR code, scan it back (_installed_app_test.py; hands off mouse
         and keyboard for about a minute).
      5. Uninstalls the package, removes the certificate from every store and deletes the copy.
    Results go to dist\install-test-report.txt (and WACK's own XML next to it).
    Use -SkipWack to leave out WACK, -SkipApp to leave out the window test.
#>
param([switch]$SkipWack, [switch]$SkipApp)

$ErrorActionPreference = "Stop"
$root   = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$id     = Get-Content -LiteralPath (Join-Path $PSScriptRoot "identity.json") -Raw | ConvertFrom-Json
$msix   = Join-Path $root ("dist\MosaiqQRStudio-{0}-x64.msix" -f $id.Version)
$report = Join-Path $root "dist\install-test-report.txt"
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
$sign   = (Get-ChildItem -LiteralPath (Join-Path $root ".tools\sdk-buildtools") -Recurse -Filter signtool.exe |
           Where-Object { $_.DirectoryName -match '\\x64$' } | Select-Object -First 1).FullName
$appcert = "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe"
$lines = New-Object System.Collections.Generic.List[string]
function Say($text) { Write-Host $text; $script:lines.Add($text) }

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an Administrator PowerShell."
}
if (-not (Test-Path -LiteralPath $msix)) { throw "$msix not found - run .\build.ps1 and .\build_msix.ps1 first." }

$existing = Get-AppxPackage -AllUsers ($id.IdentityName)
if ($existing) {
    throw ("A package named {0} is already installed ({1}). Remove it yourself first, or decide that it " +
           "may be replaced; this script will not do it.") -f $id.IdentityName, ($existing.PackageFullName -join ", ")
}

$work = Join-Path ([IO.Path]::GetTempPath()) ("mosaiq-install-test-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Force -Path $work | Out-Null
$thumb = $null
$installed = $false
$ok = $true
Say ("Mosaiq install test, {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"))
Say ("Package: {0}  ({1:N0} bytes)" -f $msix, (Get-Item -LiteralPath $msix).Length)

try {
    # ---- 2. test-signed copy ----
    $cert = New-SelfSignedCertificate -Type Custom -Subject $id.Publisher -KeyUsage DigitalSignature `
        -FriendlyName "Mosaiq TEST cert (temporary, removed by install_test.ps1)" `
        -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddDays(2) `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    $thumb = $cert.Thumbprint
    $pfx = Join-Path $work "test.pfx"
    $cer = Join-Path $work "test.cer"
    $password = ConvertTo-SecureString -String "mosaiq-test" -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $password | Out-Null
    Export-Certificate -Cert $cert -FilePath $cer | Out-Null
    $copy = Join-Path $work "MosaiqQRStudio-TESTSIGNED.msix"
    Copy-Item -LiteralPath $msix -Destination $copy
    & $sign sign /fd SHA256 /f $pfx /p mosaiq-test $copy | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
    Say "Test-signed copy made in $work (the real package is unchanged)."

    # ---- 3. trust + WACK ----
    Import-Certificate -FilePath $cer -CertStoreLocation "Cert:\LocalMachine\TrustedPeople" | Out-Null
    if (-not $SkipWack) {
        if (-not (Test-Path -LiteralPath $appcert)) { throw "appcert.exe not found: $appcert" }
        $wackXml = Join-Path $root "dist\wack-report.xml"
        Remove-Item -LiteralPath $wackXml -ErrorAction SilentlyContinue
        Say "Running WACK (a few minutes; it opens and closes the app by itself)..."
        & $appcert reset | Out-Null
        & $appcert test -appxpackagepath $copy -reportoutputpath $wackXml | Out-Null
        if (Test-Path -LiteralPath $wackXml) {
            [xml]$xml = Get-Content -LiteralPath $wackXml
            $overall = $xml.DocumentElement.GetAttribute("OVERALL_RESULT")
            Say ("WACK overall result: {0}" -f $overall)
            # Optional tests are advice (the Python/Tcl/OpenCV runtime DLLs always trip "Blocked executables").
            $failed = @($xml.SelectNodes("//TEST[RESULT='FAIL']"))
            foreach ($t in $failed) {
                $optional = $t.GetAttribute("OPTIONAL") -eq "TRUE"
                Say ("  {0}: {1}" -f $(if ($optional) { "advice (optional test failed)" } else { "FAIL" }), $t.GetAttribute("NAME"))
                if (-not $optional) { $ok = $false }
            }
            if ($overall -ne "PASS") { $ok = $false }
            Say "WACK report: $wackXml"
        } else {
            Say "WACK produced no report."
            $ok = $false
        }
    }

    # ---- 4. install, launch, drive ----
    Add-AppxPackage -Path $copy
    $installed = $true
    $pkg = Get-AppxPackage ($id.IdentityName)
    Say ("Installed: {0}  version {1}" -f $pkg.PackageFullName, $pkg.Version)
    if ($pkg.Version -ne $id.Version) { Say "  version differs from identity.json"; $ok = $false }
    $aumid = "shell:AppsFolder\{0}!MosaiqQRStudio" -f $pkg.PackageFamilyName
    if (-not $SkipApp) {
        Say "Driving the installed app (hands off mouse and keyboard)..."
        Push-Location $root
        try {
            $env:PYTHONUTF8 = "1"
            $ErrorActionPreference = "Continue"      # Python's stderr (a traceback) must reach the report
            $out = & $venvPy (Join-Path $root "_installed_app_test.py") $aumid 2>&1 | ForEach-Object { "$_" } | Out-String
        } finally { $ErrorActionPreference = "Stop"; Pop-Location }
        Say $out.Trim()
        if ($out -notmatch "INSTALLED_APP_OK") { $ok = $false }
    }
}
catch {
    Say ("ERROR: {0}" -f $_.Exception.Message)
    $ok = $false
}
finally {
    # ---- 5. clean up, whatever happened ----
    # Only the installed test package's own process is stopped, never another copy of the app.
    $pkgNow = Get-AppxPackage ($id.IdentityName)
    if ($pkgNow) {
        Get-Process -Name MosaiqQRStudio -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -and $_.Path.StartsWith($pkgNow.InstallLocation, [StringComparison]::OrdinalIgnoreCase) } |
            Stop-Process -Force
    }
    if ($installed) {
        Get-AppxPackage ($id.IdentityName) | Remove-AppxPackage
    }
    $left = Get-AppxPackage ($id.IdentityName)
    Say ("After uninstall, Mosaiq packages still installed: {0}" -f @($left).Count)
    if ($thumb) {
        foreach ($store in "Cert:\CurrentUser\My", "Cert:\LocalMachine\TrustedPeople", "Cert:\CurrentUser\TrustedPeople") {
            Get-ChildItem $store -ErrorAction SilentlyContinue | Where-Object { $_.Thumbprint -eq $thumb } | Remove-Item -Force
        }
        $leftCerts = @(Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\TrustedPeople, Cert:\CurrentUser\TrustedPeople |
                       Where-Object { $_.Thumbprint -eq $thumb })
        Say ("Test certificate copies left in any store: {0}" -f $leftCerts.Count)
    }
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
    Say ("Temp folder removed: {0}" -f (-not (Test-Path -LiteralPath $work)))
    Say ("RESULT: {0}" -f $(if ($ok) { "PASS" } else { "FAIL" }))
    Set-Content -LiteralPath $report -Value $lines -Encoding UTF8
    Write-Host "Report: $report"
}
