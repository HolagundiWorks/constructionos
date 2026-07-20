; Inno Setup script for Construction OS.
; Wraps the PyInstaller one-folder build (dist\ConstructionOS\) into a single
; Setup.exe with Start-menu and desktop shortcuts and an uninstaller.
;
; Build:  ISCC.exe ConstructionOS.iss   (Inno Setup 6, free — jrsoftware.org)
;         or run build.ps1, which calls this for you.

#define AppName "Construction OS"
#define AppVersion "1.0.0"
#define Publisher "Human Centric Works, Hospet"
#define ExeName "ConstructionOS.exe"

[Setup]
AppId={{6F2B9C4E-1D3A-4E77-9C2B-CONSTRUCTIONOS}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=ConstructionOS-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install: no administrator rights needed, one copy per Windows user.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\construction_app\resources\app.ico
UninstallDisplayIcon={app}\{#ExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; The entire PyInstaller one-folder build.
Source: "dist\ConstructionOS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

; NOTE: the user's data lives in %LOCALAPPDATA%\Construction OS (databases,
; company registry). It is deliberately NOT removed on uninstall, so an
; upgrade or reinstall never destroys a contractor's books. To remove it, the
; user deletes that folder by hand.
