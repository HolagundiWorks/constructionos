; Inno Setup script for Construction OS.
; Wraps the PyInstaller one-folder build (dist\ConstructionOS\) into a single
; Setup.exe with Start-menu and desktop shortcuts and an uninstaller.
;
; Build:  ISCC.exe ConstructionOS.iss   (Inno Setup 6, free — jrsoftware.org)
;         or run build.ps1, which calls this for you.
;
; INBUILT AI (optional payload): if the builder ran fetch_payload.ps1 first,
; this also carries the offline AI engine — Ollama's official installer
; (vendor\OllamaSetup.exe) and the assistant model weights (ai\*.gguf). With
; those present the installer sets Ollama up silently and lays the model beside
; the app, so the Assistant answers with no internet, out of the box. Without
; them the app still installs and runs fine; the Assistant just pulls a model
; on first use instead. Both Ollama and the Qwen2.5-Coder model are permissively
; licensed (MIT / Apache-2.0), so shipping their official artefacts is fine.

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
; The offline AI assistant. Ticked by default when the AI payload is bundled —
; Ollama installs silently and the model is laid beside the app (a one-time
; ~1 min setup finishes on first launch). Untick to skip AI entirely. When no
; payload was bundled, ticking it just opens Ollama's download page.
Name: "ollama"; Description: "Set up the offline AI assistant (Ollama + inbuilt model)"; GroupDescription: "AI assistant:"

[Files]
; The entire PyInstaller one-folder build.
Source: "dist\ConstructionOS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; The inbuilt model, laid down NEXT TO the exe (not packed by PyInstaller — a
; ~1 GB GGUF should not go through the freezer). The Modelfile is always here;
; the GGUF only when fetch_payload.ps1 was run. Both skip cleanly if absent.
Source: "ai\Modelfile"; DestDir: "{app}\ai"; Flags: skipifsourcedoesntexist ignoreversion; Tasks: ollama
Source: "ai\*.gguf"; DestDir: "{app}\ai"; Flags: skipifsourcedoesntexist ignoreversion; Tasks: ollama
; Ollama's official installer, bundled only if the builder dropped it here.
Source: "vendor\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: skipifsourcedoesntexist deleteafterinstall; Tasks: ollama

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
; When the AI payload was NOT bundled but the user still wants AI, point them at
; the official download (they can then pull a model from inside the app).
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

// When the AI payload is bundled and the user kept the task ticked, install
// Ollama silently as part of setup. Failures are non-fatal: the app can still
// install Ollama later from Assistant > AI Engine, and the model is imported on
// first run once Ollama is present. The model import itself is done in-app (it
// needs the Ollama server running and the right PATH), not here.
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('ollama')
     and OllamaBundled then
  begin
    WizardForm.StatusLabel.Caption := 'Setting up the offline AI engine (Ollama)...';
    Exec(ExpandConstant('{tmp}\OllamaSetup.exe'),
         '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART', '',
         SW_HIDE, ewWaitUntilTerminated, ResultCode);
    // ResultCode intentionally ignored — see note above.
  end;
end;
