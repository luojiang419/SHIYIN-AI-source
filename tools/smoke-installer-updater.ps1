[CmdletBinding(DefaultParameterSetName = 'Zip')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Zip')]
    [string]$FromZip,
    [Parameter(Mandatory = $true, ParameterSetName = 'Installer')]
    [string]$FromInstaller,
    [Parameter(Mandatory = $true)]
    [string]$ToInstaller,
    [Parameter(Mandatory = $true)]
    [string]$ToVersion
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($ToVersion -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid target version: $ToVersion" }

function Get-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha256.Dispose(); $stream.Dispose() }
}

function Stop-TestProcesses([string]$Root) {
    $prefix = $Root.TrimEnd('\') + '\'
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $path = $_.Path
            if ($path -and $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
}

$toInstallerPath = (Resolve-Path -LiteralPath $ToInstaller).Path
$buildRoot = (Resolve-Path (Join-Path $projectRoot '.build')).Path
$stage = Join-Path $buildRoot 'installer-updater-e2e'
$stagePrefix = $buildRoot.TrimEnd('\') + '\'
if (-not $stage.StartsWith($stagePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid installer test stage path.' }
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$source = Join-Path $stage 'source'
$installRoot = Join-Path $stage 'installed'
$helper = Join-Path $installRoot 'data\update\helper\SHIYIN-AI-updater-installer-e2e.exe'
$desktopExe = Join-Path $installRoot 'SHIYIN AI.exe'
$dataRoot = Join-Path $installRoot 'data'
$pending = Join-Path $dataRoot 'update\pending.json'
$success = $false

try {
    if ($PSCmdlet.ParameterSetName -eq 'Zip') {
        $fromZipPath = (Resolve-Path -LiteralPath $FromZip).Path
        New-Item -ItemType Directory -Force -Path $source | Out-Null
        Expand-Archive -LiteralPath $fromZipPath -DestinationPath $source -Force
        $roots = @(Get-ChildItem -LiteralPath $source -Directory)
        if ($roots.Count -ne 1 -or -not (Test-Path -LiteralPath (Join-Path $roots[0].FullName 'app\VERSION'))) {
            throw 'Source release ZIP does not contain one portable application root.'
        }
        Move-Item -LiteralPath $roots[0].FullName -Destination $installRoot
    } else {
        $fromInstallerPath = (Resolve-Path -LiteralPath $FromInstaller).Path
        New-Item -ItemType Directory -Force -Path $installRoot | Out-Null
        $logPath = Join-Path $stage 'source-install.log'
        $sourceInstall = Start-Process -FilePath $fromInstallerPath -ArgumentList @(
            '/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL',
            "/DIR=$installRoot", "/LOG=$logPath"
        ) -Wait -PassThru
        if ($sourceInstall.ExitCode -ne 0) { throw "Source installer failed with exit code $($sourceInstall.ExitCode)." }
    }

    if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf)) { throw 'Installed source executable was not found.' }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot 'app\VERSION') -PathType Leaf)) { throw 'Installed source runtime was not found.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $helper) | Out-Null
    New-Item -ItemType Directory -Force -Path $dataRoot | Out-Null
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pending) | Out-Null
    [IO.File]::WriteAllText((Join-Path $dataRoot 'e2e-user-data.txt'), 'keep')
    [IO.File]::WriteAllText($pending, '{"test":true}')
    [IO.File]::WriteAllText((Join-Path $installRoot 'app\obsolete-runtime-file.txt'), 'replace-me')
    Copy-Item -LiteralPath $desktopExe -Destination $helper

    $exitedProcess = Start-Process -FilePath $env:ComSpec -ArgumentList '/c', 'exit 0' -PassThru -Wait
    $oldPid = $exitedProcess.Id
    $processInfo = [Diagnostics.ProcessStartInfo]::new($helper)
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $arguments = @(
        '--run-update-session',
        '--session-id=installer-e2e',
        "--root=$installRoot",
        "--data=$dataRoot",
        "--update-installer=$toInstallerPath",
        "--version=$ToVersion",
        "--sha256=$(Get-Sha256 $toInstallerPath)",
        "--old-pid=$oldPid"
    )
    $processInfo.Arguments = ($arguments | ForEach-Object { '"' + ($_ -replace '"', '\"') + '"' }) -join ' '
    $process = [Diagnostics.Process]::Start($processInfo)
    if (-not $process.WaitForExit(180000)) {
        $process.Kill()
        throw 'Installer updater helper did not finish within 180 seconds.'
    }
    if ($process.ExitCode -ne 0) {
        $logPath = Join-Path $dataRoot 'update\updater.log'
        $log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { '' }
        throw "Installer updater helper failed with exit code $($process.ExitCode). $log"
    }
    Start-Sleep -Milliseconds 1000
    if ((Get-Content -LiteralPath (Join-Path $installRoot 'app\VERSION') -Raw).Trim() -ne $ToVersion) {
        throw 'Updated application version does not match the installer version.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataRoot 'e2e-user-data.txt'))) { throw 'Installer updater removed user data.' }
    if (Test-Path -LiteralPath $pending) { throw 'Installer updater did not clear pending update state.' }
    if (Test-Path -LiteralPath (Join-Path $installRoot 'app\obsolete-runtime-file.txt')) { throw 'Installer did not replace the app directory.' }
    $success = $true
    [pscustomobject]@{
        source_kind = $PSCmdlet.ParameterSetName
        to_installer = [IO.Path]::GetFileName($toInstallerPath)
        target_version = $ToVersion
        installer_installed = $true
        data_preserved = $true
        app_replaced = $true
    } | ConvertTo-Json -Compress
} finally {
    Stop-TestProcesses $installRoot
    if ($success -and (Test-Path -LiteralPath $stage)) {
        $removed = $false
        foreach ($attempt in 1..5) {
            try {
                Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction Stop
                $removed = $true
                break
            } catch {
                if ($attempt -lt 5) { Start-Sleep -Milliseconds 250 }
            }
        }
        if (-not $removed) { Write-Warning "Unable to remove installer updater test stage: $stage" }
    }
}
