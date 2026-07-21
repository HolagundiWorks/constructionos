; Inno Setup script for the Ollama Manager (companion to Construction OS).
; Build:  ISCC.exe OllamaManager.iss   — or run build.ps1, which does both apps.

#define AppName "Ollama Manager"
#define AppVersion "1.0.0"
#define Publisher "Human Centric Works, Hospet"
#define ExeName "OllamaManager.exe"

[Setup]
AppId={{9C1F7A2D-4B60-4E19-8A3C-OLLAMAMANAGER}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=OllamaManager-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\construction_app\resources\app.ico
UninstallDisplayIcon={app}\{#ExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\OllamaManager\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

; Settings live in %LOCALAPPDATA%\Ollama Manager and are left in place on
; uninstall. Ollama itself and the downloaded models are installed by Ollama's
; own installer, not this one, and are untouched here.
