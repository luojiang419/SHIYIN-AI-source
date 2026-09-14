param([string]$InstallRoot = 'D:\Program Files\SHIYIN Distribution Center')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$builtRoot = [IO.File]::ReadAllText((Join-Path $projectRoot 'dist/distribution-latest.txt')).Trim()
if (-not (Test-Path -LiteralPath (Join-Path $builtRoot 'SHIYIN-Distribution-Center.exe'))) { throw 'Build the distribution center first.' }
$dataRoot = 'D:\SHIYIN-Distribution'
$tokenPath = Join-Path $dataRoot 'admin-token'
if (Test-Path -LiteralPath $tokenPath) {
    $headers = @{Authorization = 'Bearer ' + [IO.File]::ReadAllText($tokenPath).Trim()}
    try {
        $status = Invoke-RestMethod 'http://127.0.0.1:3013/api/status' -Headers $headers
        if ($status.job.running) { throw 'An import job is still running. Wait for it to finish.' }
        Invoke-RestMethod 'http://127.0.0.1:3013/api/stop' -Method Post -Headers $headers -Body '{}' -ContentType 'application/json' | Out-Null
    } catch [System.Net.WebException] { }
}
$centerProcesses = Get-Process -Name SHIYIN-Distribution-Center -ErrorAction SilentlyContinue
foreach ($process in $centerProcesses) {
    if ($process.Path -and ($process.Path.StartsWith($InstallRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or $process.Path.StartsWith($projectRoot + '\dist\', [StringComparison]::OrdinalIgnoreCase))) {
        Stop-Process -Id $process.Id
        $process.WaitForExit(10000) | Out-Null
    }
}
New-Item -ItemType Directory -Force $InstallRoot | Out-Null
Get-ChildItem -LiteralPath $builtRoot -Force | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $InstallRoot -Recurse -Force }
$executable = Join-Path $InstallRoot 'SHIYIN-Distribution-Center.exe'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'SHIYIN 分发中心.lnk'))
$shortcut.TargetPath = $executable
$shortcut.WorkingDirectory = $InstallRoot
$shortcut.Save()
# 同步已保存的用户偏好，不在重新部署时强制重新开启自启动。
$startupSync = Start-Process -FilePath $executable -ArgumentList '--sync-startup' -WorkingDirectory $InstallRoot -WindowStyle Hidden -Wait -PassThru
if ($startupSync.ExitCode -ne 0) { throw 'Failed to synchronize startup preference' }
foreach ($rule in @(@{Name='SHIYIN Distribution TCP';Protocol='TCP';Port=3011},@{Name='SHIYIN Distribution UDP';Protocol='UDP';Port=3012})) {
    if (-not (Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Action Allow -Protocol $rule.Protocol -LocalPort $rule.Port -Profile Private -RemoteAddress LocalSubnet | Out-Null
    }
}
Start-Process -FilePath $executable -ArgumentList '--service' -WorkingDirectory $InstallRoot -WindowStyle Hidden
Write-Host "Distribution center deployed: $executable"
