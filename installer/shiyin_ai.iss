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
DefaultDirName={code:ResolveDefaultInstallDir}
UsePreviousAppDir=no
; 已有安装目录直接覆盖，不弹出“目录已存在”确认；下方 InstallDelete 仍只替换 app，data 保持原位。
DirExistsWarning=no
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
Name: "{app}\data\logs"; Permissions: users-modify

[InstallDelete]
Type: filesandordirs; Name: "{app}\app"

[Files]
Source: "..\dist\installer-stage\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\installer-stage\app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\installer-stage\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\installer-stage\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\tools\blender-addon\windows\Install-SHIYINBlenderAddon.ps1"; Flags: dontcopy
Source: "..\tools\stop-shiyin-processes.ps1"; Flags: dontcopy

[Icons]
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  DefaultInstallDir = 'D:\Program Files\SHIYIN AI';
  UninstallRegistryKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{5D7C3DA8-5D77-4C9A-BF1E-0F1A22D6A4A5}_is1';

var
  UpdateProgressFile: String;
  BlenderPluginPage: TInputOptionWizardPage;
  BlenderDetected: Boolean;
  BlenderDiscoveryText: String;
  BlenderHelperPath: String;

function NormalizeInstallDir(const Value: String): String;
begin
  Result := RemoveBackslashUnlessRoot(Trim(Value));
end;

function IsInstallerTestPath(const Value: String): Boolean;
var
  Normalized: String;
begin
  Normalized := NormalizeInstallDir(Value);
  StringChangeEx(Normalized, '/', '\', True);
  Normalized := Lowercase(Normalized);
  Result :=
    (Pos('\.build\installer-updater-e2e', Normalized) > 0) or
    (Pos('\.build\installer-progress-smoke-', Normalized) > 0);
end;

function IsExistingInstallDir(const Value: String): Boolean;
var
  Candidate: String;
begin
  Candidate := NormalizeInstallDir(Value);
  Result :=
    (Candidate <> '') and
    (not IsInstallerTestPath(Candidate)) and
    (FileExists(AddBackslash(Candidate) + '{#MyAppExeName}') or
      FileExists(AddBackslash(Candidate) + 'data\database\canvas.db'));
end;

function ReadRegisteredInstallDir(var Value: String): Boolean;
begin
  Result :=
    RegQueryStringValue(HKLM64, UninstallRegistryKey, 'InstallLocation', Value) or
    RegQueryStringValue(HKLM32, UninstallRegistryKey, 'InstallLocation', Value) or
    RegQueryStringValue(HKCU, UninstallRegistryKey, 'InstallLocation', Value);
end;

function ResolveDefaultInstallDir(Param: String): String;
var
  RegisteredDir: String;
begin
  Result := DefaultInstallDir;
  if ReadRegisteredInstallDir(RegisteredDir) then
  begin
    if IsExistingInstallDir(RegisteredDir) then
    begin
      Result := NormalizeInstallDir(RegisteredDir);
      Log('复用已验证的 SHIYIN AI 安装目录：' + Result);
    end
    else
      Log('忽略无效或测试安装目录，恢复正式默认目录：' + RegisteredDir);
  end;
end;

function ReadTextFileForMessage(const FileName: String): String;
var
  Lines: TArrayOfString;
  I: Integer;
begin
  Result := '';
  if not LoadStringsFromFile(FileName, Lines) then
    exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    if Result <> '' then
      Result := Result + #13#10;
    Result := Result + Lines[I];
  end;
end;

function RunBlenderHelper(const HelperPath, ExtraParameters: String;
  AsOriginalUser: Boolean; var ResultCode: Integer): Boolean;
var
  PowerShellPath: String;
  Parameters: String;
begin
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Parameters := '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    HelperPath + '" ' + ExtraParameters;
  Log('运行 Blender 插件辅助脚本：' + HelperPath);
  if AsOriginalUser then
    Result := ExecAsOriginalUser(PowerShellPath, Parameters, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode)
  else
    Result := Exec(PowerShellPath, Parameters, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode);
end;

function DiscoverBlenderInstallations(): String;
var
  ResultCode: Integer;
  ResultPath: String;
  Lines: TArrayOfString;
  I: Integer;
  Line: String;
  ItemText: String;
begin
  Result := '未检测到 Blender 3.6 或更高版本。插件包仍会随 SHIYIN AI 安装，可在以后安装 Blender 后手动部署。';
  BlenderDetected := False;
  BlenderHelperPath := ExpandConstant('{tmp}\Install-SHIYINBlenderAddon.ps1');
  ResultPath := ExpandConstant('{tmp}\shiyin-blender-discovery.txt');
  DeleteFile(ResultPath);
  try
    ExtractTemporaryFile('Install-SHIYINBlenderAddon.ps1');
  except
    Log('无法提取 Blender 插件发现脚本：' + GetExceptionMessage);
    exit;
  end;
  ResultCode := -1;
  if (not RunBlenderHelper(
      BlenderHelperPath,
      '-DiscoverOnly -ResultPath "' + ResultPath + '"',
      False,
      ResultCode)) or (ResultCode <> 0) then
  begin
    Log(Format('Blender 发现脚本失败，退出码 %d。', [ResultCode]));
    exit;
  end;
  if not LoadStringsFromFile(ResultPath, Lines) then
    exit;
  ItemText := '';
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Lines[I];
    if Pos('blender=', Line) = 1 then
    begin
      BlenderDetected := True;
      if ItemText <> '' then
        ItemText := ItemText + #13#10;
      ItemText := ItemText + '  • ' + Copy(Line, 9, Length(Line));
    end;
  end;
  if BlenderDetected then
    Result := '已检测到以下 Blender，将安装并启用 SHIYIN AI Bridge：' + #13#10 +
      ItemText + #13#10 + #13#10 +
      '安装时会以当前桌面用户身份运行 Blender 内置 Python，不会打开或保存任何 .blend 工程。' + #13#10 +
      '安装后无需配对码，3D 导演台节点可自动连接，并可在 Blender 未运行时一键启动。';
end;

procedure InitializeWizard;
begin
  BlenderDiscoveryText := DiscoverBlenderInstallations();
  BlenderPluginPage := CreateInputOptionPage(
    wpSelectTasks,
    'Blender 联动插件',
    '是否安装或更新 SHIYIN AI Blender Bridge？',
    BlenderDiscoveryText,
    True,
    True);
  BlenderPluginPage.Add('安装到检测到的 Blender（推荐）');
  BlenderPluginPage.Add('暂不安装，仅保留插件包');
  if BlenderDetected then
    BlenderPluginPage.SelectedValueIndex := 0
  else
  begin
    BlenderPluginPage.SelectedValueIndex := 1;
    BlenderPluginPage.CheckListBox.ItemEnabled[0] := False;
  end;
end;

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

function StopRunningShiyinProcesses(): Boolean;
var
  PowerShellPath: String;
  HelperPath: String;
  Parameters: String;
  ResultCode: Integer;
begin
  Result := True;
  HelperPath := ExpandConstant('{tmp}\stop-shiyin-processes.ps1');
  try
    ExtractTemporaryFile('stop-shiyin-processes.ps1');
  except
    Log('Unable to extract SHIYIN AI process cleanup helper: ' + GetExceptionMessage);
    Result := False;
    exit;
  end;
  PowerShellPath := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');
  Parameters := '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    HelperPath + '" -PortableRoot "' + ExpandConstant('{app}') + '"';
  ResultCode := -1;
  if (not Exec(PowerShellPath, Parameters, '', SW_HIDE,
      ewWaitUntilTerminated, ResultCode)) or (ResultCode <> 0) then
  begin
    Log(Format('SHIYIN AI process cleanup failed, exit code %d.', [ResultCode]));
    Result := False;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  NeedsRestart := False;
  Result := '';
  if not StopRunningShiyinProcesses() then
    Result := 'Unable to close the old SHIYIN AI process. End SHIYIN AI.exe or app\\backend\\canvas-backend\\canvas-backend.exe in Task Manager and retry.';
end;

function BlenderPluginRequested(): Boolean;
begin
  if CompareText(ExpandConstant('{param:NOBLENDERPLUGIN|0}'), '1') = 0 then
    Result := False
  else if CompareText(ExpandConstant('{param:INSTALLBLENDERPLUGIN|0}'), '1') = 0 then
    Result := True
  else if WizardSilent then
    Result := False
  else
    Result := BlenderDetected and (BlenderPluginPage.SelectedValueIndex = 0);
end;

function CheckBlenderClosed(): Boolean;
var
  ResultCode: Integer;
  ErrorPath: String;
  Detail: String;
begin
  Result := True;
  if not BlenderPluginRequested() then
    exit;
  ErrorPath := ExpandConstant('{tmp}\shiyin-blender-process-check.log');
  DeleteFile(ErrorPath);
  ResultCode := -1;
  if (not RunBlenderHelper(
      BlenderHelperPath,
      '-CheckProcessOnly -ErrorLogPath "' + ErrorPath + '"',
      False,
      ResultCode)) or (ResultCode <> 0) then
  begin
    Detail := ReadTextFileForMessage(ErrorPath);
    if Detail = '' then
      Detail := 'Blender 正在运行或进程检查失败。';
    if not WizardSilent then
      MsgBox(
        Detail + #13#10 + #13#10 +
        '请保存工程并关闭所有 Blender 窗口，然后再次点击“下一步”；也可以选择“暂不安装”。',
        mbError,
        MB_OK);
    Result := False;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = BlenderPluginPage.ID then
    Result := CheckBlenderClosed();
end;

procedure InstallBlenderPlugin;
var
  ResultCode: Integer;
  ScriptPath: String;
  AddonSource: String;
  ResultPath: String;
  ErrorPath: String;
  ErrorDetail: String;
  ErrorMessage: String;
begin
  if not BlenderPluginRequested() then
  begin
    Log('用户或静默安装参数选择跳过 Blender 插件；插件包已保留在 app\connectors\blender。');
    exit;
  end;
  ScriptPath := ExpandConstant('{app}\app\connectors\blender\windows\Install-SHIYINBlenderAddon.ps1');
  AddonSource := ExpandConstant('{app}\app\connectors\blender\shiyin_blender_bridge');
  ResultPath := ExpandConstant('{app}\data\logs\blender-addon-install-result.log');
  ErrorPath := ExpandConstant('{app}\data\logs\blender-addon-install-error.log');
  ForceDirectories(ExpandConstant('{app}\data\logs'));
  DeleteFile(ResultPath);
  DeleteFile(ErrorPath);
  ResultCode := -1;
  if (not RunBlenderHelper(
      ScriptPath,
      '-AddonSource "' + AddonSource + '" -ResultPath "' + ResultPath +
      '" -ErrorLogPath "' + ErrorPath + '"',
      True,
      ResultCode)) or (ResultCode <> 0) then
  begin
    ErrorDetail := ReadTextFileForMessage(ErrorPath);
    ErrorMessage := Format(
      'SHIYIN AI 主程序已安装，但 Blender 插件安装失败（退出码 %d）。' + #13#10 +
      '主程序和插件包均已保留，可稍后关闭 Blender 后手动重试：' + #13#10 +
      '%s', [ResultCode, ScriptPath]);
    if ErrorDetail <> '' then
      ErrorMessage := ErrorMessage + #13#10 + #13#10 +
        '实际错误：' + #13#10 + Copy(ErrorDetail, 1, 2000);
    Log(ErrorMessage);
    if not WizardSilent then
      MsgBox(ErrorMessage, mbError, MB_OK);
  end
  else
  begin
    Log('Blender 插件安装并启用成功。结果：' + ReadTextFileForMessage(ResultPath));
  end;
  BringToFrontAndRestore();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    InstallBlenderPlugin();
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  WriteUpdateProgress(CurProgress, MaxProgress);
end;
