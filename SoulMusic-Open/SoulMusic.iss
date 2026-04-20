; ─────────────────────────────────────────────────────────────────────────────
;  SoulMusic.iss  —  Inno Setup 6 installer script
;
;  Produces:  installer\SoulMusic-Setup-1.0.0.exe
;  Requires:  Inno Setup 6.x  https://jrsoftware.org/isinfo.php
;             PyInstaller dist\SoulMusic\ directory built first
;
;  Usage:
;    1. Run: pyinstaller SoulMusic.spec --noconfirm
;    2. Run: iscc SoulMusic.iss
;       (or open in Inno Setup Compiler IDE and press Compile)
; ─────────────────────────────────────────────────────────────────────────────

#define AppName      "SoulMusic"
#define AppVersion   "1.0.0"
#define AppPublisher "SoulMusic"
#define AppExeName   "SoulMusic.exe"
#define AppDescription "Acoustic MEMS Resonance Platform — Test Control"
#define SourceDir    "dist\SoulMusic"
#define OutputDir    "installer"

[Setup]
; ── Identity ────────────────────────────────────────────────────────────────
AppId={{8F3C2A41-D7B9-4E5F-A6C1-0D2E3F4A5B6C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright © 2026 {#AppPublisher}
AppComments={#AppDescription}

; ── Paths ───────────────────────────────────────────────────────────────────
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=SoulMusic-Setup-{#AppVersion}

; ── Platform ────────────────────────────────────────────────────────────────
; Minimum: Windows 10 1903 (build 18362)
; Supports: Windows 10, Windows 11 (x64)
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
MinVersion=10.0.18362

; ── Appearance ──────────────────────────────────────────────────────────────
; Use a modern wizard style (no old Win95 look)
WizardStyle=modern
WizardSizePercent=110
; Suppress the obsolete "select components" page — single-component install
DisableReadyPage=no
DisableProgramGroupPage=yes

; ── Compression ─────────────────────────────────────────────────────────────
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; ── Privileges ──────────────────────────────────────────────────────────────
; Request elevation so the app installs to Program Files (all users).
; Users without admin rights will be prompted by UAC.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=commandline

; ── Uninstall ───────────────────────────────────────────────────────────────
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
CreateUninstallRegKey=yes

; ── Misc ────────────────────────────────────────────────────────────────────
; icon=assets\icon.ico  ; uncomment when icon.ico is available

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Optional items the user can toggle during install
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; ── Application binaries (PyInstaller onedir output) ──────────────────────
; Recurse the entire dist\SoulMusic\ folder into {app}
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"; Comment: "{#AppDescription}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
; Desktop (optional, controlled by task above)
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
; Offer to launch the app immediately after install
Filename: "{app}\{#AppExeName}"; \
    Description: "Launch {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Nothing extra to run on uninstall

[Registry]
; Register the app for Add/Remove Programs (Inno Setup does this automatically,
; but we also write the install path for other tools to discover)
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version";     ValueData: "{#AppVersion}"

[Code]
// ── Pre-install checks ────────────────────────────────────────────────────

function InitializeSetup(): Boolean;
var
  OsVersion: TWindowsVersion;
begin
  GetWindowsVersionEx(OsVersion);

  // Require Windows 10 build 18362 or later
  if (OsVersion.Major < 10) or
     ((OsVersion.Major = 10) and (OsVersion.Build < 18362)) then
  begin
    MsgBox(
      'SoulMusic requires Windows 10 (version 1903 or later) or Windows 11.' + #13#10 +
      'Your Windows version is not supported.',
      mbError, MB_OK);
    Result := False;
    Exit;
  end;

  Result := True;
end;
