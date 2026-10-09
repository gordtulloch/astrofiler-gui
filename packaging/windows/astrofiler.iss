; Inno Setup script: wraps dist\AstroFiler into one AstroFiler-Setup-<version>-win-x64.exe.
; Build (from the repo root):  iscc /DAppVersion=1.2.4 packaging\windows\astrofiler.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{A442D3F3-0154-48ED-A6A9-CE9D089D13D2}
AppName=AstroFiler
AppVersion={#AppVersion}
AppPublisher=Gord Tulloch
DefaultDirName={autopf}\AstroFiler
DefaultGroupName=AstroFiler
UninstallDisplayIcon={app}\AstroFiler.exe
SetupIconFile=..\..\astrofiler.ico
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=AstroFiler-Setup-{#AppVersion}-win-x64
Compression=lzma2/ultra
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

; Inno never deletes files a previous version installed, so clear the bundled runtime before copying.
; (A stale _internal\srcstrofiler folder from an older build shadows the real package and crashes start-up.)
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\AstroFiler\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\AstroFiler"; Filename: "{app}\AstroFiler.exe"
Name: "{autodesktop}\AstroFiler"; Filename: "{app}\AstroFiler.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AstroFiler.exe"; Description: "Launch AstroFiler"; Flags: nowait postinstall skipifsilent
