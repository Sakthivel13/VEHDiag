; Inno Setup script for the Vehicle Diagnostics Platform.
; Build the executable first: python scripts/build_windows.py

#define AppName "Vehicle Diagnostics Platform"
#define AppVersion "0.1.0"
#define AppPublisher "Vehicle Diagnostics Platform Team"
#define AppExeName "VehicleDiagnosticsPlatform.exe"

[Setup]
AppId={{8F3C1E42-5B7A-4D19-9C6E-2A1F7B4D8E30}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\VehicleDiagnosticsPlatform
DefaultGroupName={#AppName}
OutputDir=..\..\dist\installer
OutputBaseFilename=VehicleDiagnosticsPlatform-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
LicenseFile=..\..\LICENSE
ChangesAssociations=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons"
Name: "associate"; Description: "Associate .vdp project files"; GroupDescription: "File associations"

[Files]
Source: "..\..\dist\VehicleDiagnosticsPlatform\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs
Source: "..\..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs
Source: "..\..\sample_test_scripts\*"; DestDir: "{app}\sample_test_scripts"; Flags: ignoreversion recursesubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Documentation"; Filename: "{app}\docs\user_guide\getting_started.md"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.vdp"; ValueType: string; ValueName: ""; ValueData: "VDPProject"; Flags: uninsdeletevalue; Tasks: associate
Root: HKA; Subkey: "Software\Classes\VDPProject"; ValueType: string; ValueName: ""; ValueData: "Vehicle diagnostics project"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\Classes\VDPProject\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associate

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent
