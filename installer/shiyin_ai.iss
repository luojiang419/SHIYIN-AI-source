#ifndef MyAppVersion
#define MyAppVersion "0.0.0"
#endif

#define MyAppName "SHIYIN AI"
#define MyAppPublisher "SHIYIN AI"
#define MyAppExeName "SHIYIN AI.exe"

[Setup]
AppId={{5D7C3DA8-5D77-4C9A-BF1E-0F1A22D6A4A5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName=D:\Program Files\SHIYIN AI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=SHIYIN-AI-Setup-{#MyAppVersion}
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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{app}\data"; Permissions: users-modify

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Files]
Source: "..\dist\installer-stage\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\installer-stage\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\installer-stage\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\installer-stage\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  UpdateProgressFile: String;

procedure WriteUpdateProgress(CurProgress, MaxProgress: Integer);
begin
  if UpdateProgressFile <> '' then
    SaveStringToFile(
      UpdateProgressFile,
      IntToStr(CurProgress) + '|' + IntToStr(MaxProgress),
      False);
end;

function InitializeSetup(): Boolean;
begin
  UpdateProgressFile := ExpandConstant('{param:UPDATEPROGRESS|}');
  Result := True;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  WriteUpdateProgress(CurProgress, MaxProgress);
end;
