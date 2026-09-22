#define AppName "SHIYIN 批量深度视频提取器"
#define AppExeName "SHIYIN-Depth-Batch.exe"

[Setup]
AppId={{8A9F70CB-3FEC-44C7-8A2A-D895EAB0C445}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=SHIYIN AI
DefaultDirName=D:\Program Files\SHIYIN-Depth-Batch
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir={#OutputRoot}
OutputBaseFilename=SHIYIN-Depth-Batch-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#AppExeName}
SetupIconFile={#IconFile}

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Excludes: "__pycache__\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项："; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent
