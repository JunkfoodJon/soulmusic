# ─────────────────────────────────────────────────────────────────────────────
#  build_installer.ps1  —  Full SoulMusic release build
#
#  Steps
#    1. Verify tool prerequisites (Python, PyInstaller, Inno Setup)
#    2. Clean previous build artefacts
#    3. Run PyInstaller  →  dist\SoulMusic\
#    4. Run Inno Setup Compiler  →  installer\SoulMusic-Setup-*.exe
#
#  Run from the repository root:
#    powershell -ExecutionPolicy Bypass -File build_installer.ps1
# ─────────────────────────────────────────────────────────────────────────────

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$AppName    = 'SoulMusic'
$SpecFile   = 'SoulMusic.spec'
$IssFile    = 'SoulMusic.iss'
$DistDir    = Join-Path $ScriptDir 'dist'
$BuildDir   = Join-Path $ScriptDir 'build'
$OutDir     = Join-Path $ScriptDir 'installer'

# ── Colour helpers ────────────────────────────────────────────────────────────
function Write-Step  { param([string]$msg) Write-Host "`n[$AppName] $msg" -ForegroundColor Cyan }
function Write-OK    { param([string]$msg) Write-Host "  [OK]  $msg" -ForegroundColor Green }
function Write-Fail  { param([string]$msg) Write-Host "  [ERR] $msg" -ForegroundColor Red; exit 1 }
function Write-Info  { param([string]$msg) Write-Host "  [..]  $msg" -ForegroundColor DarkGray }

# ── Step 1: Prerequisites ─────────────────────────────────────────────────────
Write-Step 'Checking prerequisites'

# Python
try   { $pyVer = (python --version 2>&1).ToString(); Write-OK "Python: $pyVer" }
catch { Write-Fail 'Python not found. Install Python 3.10+ and add it to PATH.' }

# PyInstaller
try   { $piVer = (pyinstaller --version 2>&1).ToString().Trim(); Write-OK "PyInstaller: $piVer" }
catch { Write-Fail 'PyInstaller not found. Run: pip install pyinstaller' }

# Inno Setup Compiler — check common install paths
$IssccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 5\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 5\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
)
$Iscc = $null
foreach ($path in $IssccCandidates) {
    if (Test-Path $path) { $Iscc = $path; break }
}
if ($null -eq $Iscc) {
    Write-Fail (@"
Inno Setup Compiler (ISCC.exe) not found.
Download and install Inno Setup 6 from:
  https://jrsoftware.org/isdl.php

After installation, re-run this script.
"@)
}
Write-OK "Inno Setup: $Iscc"

# ── Step 2: Clean ─────────────────────────────────────────────────────────────
Write-Step 'Cleaning previous artefacts'

foreach ($dir in @($DistDir, $BuildDir, $OutDir)) {
    if (Test-Path $dir) {
        Remove-Item -Recurse -Force $dir
        Write-Info "Removed: $dir"
    }
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
Write-OK 'Clean done'

# ── Step 3: PyInstaller ───────────────────────────────────────────────────────
Write-Step 'Running PyInstaller'
Write-Info "Spec: $SpecFile"

& pyinstaller $SpecFile --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'PyInstaller failed (exit code $LASTEXITCODE). See output above.'
}

$ExePath = Join-Path $DistDir "$AppName\$AppName.exe"
if (-not (Test-Path $ExePath)) {
    Write-Fail "Expected EXE not found at: $ExePath"
}
Write-OK "Built: $ExePath"

# ── Step 4: Inno Setup ────────────────────────────────────────────────────────
Write-Step 'Running Inno Setup Compiler'
Write-Info "Script: $IssFile"

& $Iscc $IssFile
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'Inno Setup compilation failed (exit code $LASTEXITCODE). See output above.'
}

$Installers = @(Get-ChildItem -Path $OutDir -Filter '*.exe')
if ($Installers.Count -eq 0) {
    Write-Fail "No installer found in $OutDir after Inno Setup run."
}
foreach ($ins in $Installers) {
    $mb = [math]::Round($ins.Length / 1MB, 1)
    Write-OK "Installer: $($ins.FullName)  ($mb MB)"
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Step 'Build complete'
Write-Host ''
Write-Host "  Distribute:  $OutDir\SoulMusic-Setup-*.exe" -ForegroundColor White
Write-Host ''
