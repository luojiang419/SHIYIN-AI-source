#ifndef MyAppVersion
#define MyAppVersion "2026.6.11"
#endif

#define MyAppName "ShiYingAI-原版画布"
#define MyAppPublisher "ShiYingAI"
#define MyAppExeName "ShiYingAI-原版画布.exe"

[Setup]
AppId={{A8C3D1B0-5E49-4CB8-9A44-7E0E0C7B1B31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=D:\Program Files\ShiYingAI-原版画布
UsePreviousAppDir=no
DirExistsWarning=no
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=ShiYingAI-原版画布-Setup-{#MyAppVersion}
SetupIconFile=..\src-tauri\icons\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Windows installer
VersionInfoProductName={#MyAppName}

[Dirs]
Name: "{app}\app"; Permissions: users-modify
Name: "{app}\app\assets"; Permissions: users-modify
Name: "{app}\app\output"; Permissions: users-modify
Name: "{app}\app\data"; Permissions: users-modify
Name: "{app}\app\API"; Permissions: users-modify

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Files]
Source: "..\dist\original-installer-stage\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\original-installer-stage\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\original-installer-stage\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\original-installer-stage\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
