; Inno Setup script for Construction OS.
; Wraps the PyInstaller one-folder build (dist\ConstructionOS\) into a single
; Setup.exe with Start-menu and desktop shortcuts and an uninstaller.
;
; Build:  ISCC.exe ConstructionOS.iss   (Inno Setup 6, free — jrsoftware.org)
;         or run build.ps1, which calls this for you.

#define AppName "Construction OS"
#define AppVersion "1.0.0"
#define Publisher "Human Centric Works, Hospet"
#define AppURL "https://github.com/HolagundiWorks/constructionos"
#define ExeName "ConstructionOS.exe"

[Setup]
AppId={{6F2B9C4E-1D3A-4E77-9C2B-CONSTRUCTIONOS}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#Publisher}
VersionInfoProductName={#AppName}
; The AGPL-3.0 licence, shown and accepted during install.
LicenseFile=..\LICENSE
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
; Ollama powers the OPTIONAL AI assistant. Off by default — the app is fully
; usable without it. If the builder placed vendor\OllamaSetup.exe next to this
; script it is installed locally; otherwise the official download page is
; opened so the user gets the current build. (Ollama is a separate product with
; its own licence; we never silently redistribute it.)
Name: "ollama"; Description: "Set up Ollama for the AI assistant (optional)"; GroupDescription: "AI assistant (optional):"; Flags: unchecked

[Files]
; The entire PyInstaller one-folder build.
Source: "dist\ConstructionOS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Optional, bundled only if the builder dropped it here (skipped otherwise).
Source: "vendor\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: skipifsourcedoesntexist deleteafterinstall; Tasks: ollama

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
; Ollama, only if the user ticked the task. Run the bundled installer when it
; was shipped; otherwise open the official download page. Both are post-install
; so the user sees them as optional check-boxes on the final page.
Filename: "{tmp}\OllamaSetup.exe"; Description: "Install Ollama now"; Tasks: ollama; Check: OllamaBundled; Flags: postinstall skipifsilent
Filename: "https://ollama.com/download"; Description: "Open the Ollama download page"; Tasks: ollama; Check: OllamaNotBundled; Flags: postinstall shellexec skipifsilent nowait
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

; NOTE: the user's data lives in %LOCALAPPDATA%\Construction OS (databases,
; company registry). It is deliberately NOT removed on uninstall, so an
; upgrade or reinstall never destroys a contractor's books. To remove it, the
; user deletes that folder by hand.

[Code]
function OllamaBundled: Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\OllamaSetup.exe'));
end;

function OllamaNotBundled: Boolean;
begin
  Result := not OllamaBundled;
end;
