# Builds service/core_service.py into a standalone exe with PyInstaller and
# copies the onedir output into ui-app/src-tauri/binaries/ under Tauri's
# required sidecar naming convention (<name>-<target-triple>.exe), with the
# accompanying _internal/ dependency folder alongside it (see
# tauri.conf.json's bundle.resources, which ships that folder next to the
# sidecar so its __file__-relative DLL lookups keep working).

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$DistPath = Join-Path $RepoRoot "dist"
$BuildPath = Join-Path $RepoRoot "build"
$SpecFile = Join-Path $RepoRoot "service\pyinstaller\core_service.spec"
$BinariesDir = Join-Path $ScriptDir "..\src-tauri\binaries"

# Pre-clean the previous output ourselves, with retries: PyInstaller's own
# cleanup can hit a transient PermissionError on freshly-written DLLs
# (observed here, most likely Windows Defender's real-time scan briefly
# holding a handle open right after they're extracted).
$OldOutput = Join-Path $DistPath "core_service"
if (Test-Path $OldOutput) {
    $attempt = 0
    while ($true) {
        try {
            Remove-Item $OldOutput -Recurse -Force -ErrorAction Stop
            break
        } catch {
            $attempt++
            if ($attempt -ge 5) { throw }
            Write-Host "Cleanup locked (attempt $attempt/5), retrying in 2s..."
            Start-Sleep -Seconds 2
        }
    }
}

Write-Host "Building core_service.exe with PyInstaller..."
python -m PyInstaller $SpecFile --distpath $DistPath --workpath $BuildPath --noconfirm
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed (exit $LASTEXITCODE)"
}

$Target = ((rustc -vV | Select-String "^host:").ToString() -split "\s+")[1]
Write-Host "Target triple: $Target"

if (Test-Path $BinariesDir) {
    $attempt = 0
    while ($true) {
        try {
            Remove-Item $BinariesDir -Recurse -Force -ErrorAction Stop
            break
        } catch {
            $attempt++
            if ($attempt -ge 5) { throw }
            Write-Host "Cleanup locked (attempt $attempt/5), retrying in 2s..."
            Start-Sleep -Seconds 2
        }
    }
}
New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null

$SourceDir = Join-Path $DistPath "core_service"
Copy-Item -Path (Join-Path $SourceDir "*") -Destination $BinariesDir -Recurse -Force

$SourceExe = Join-Path $BinariesDir "core_service.exe"
$DestExe = Join-Path $BinariesDir "core_service-$Target.exe"
Move-Item -Path $SourceExe -Destination $DestExe -Force

Write-Host "Sidecar ready: $DestExe"
Write-Host "Dependencies:  $(Join-Path $BinariesDir '_internal')"
