param(
    [Parameter(Mandatory = $true)]
    [string]$FromZip,
    [Parameter(Mandatory = $true)]
    [string]$ToZip,
    [Parameter(Mandatory = $true)]
    [string]$ToVersion
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$fromZip = (Resolve-Path -LiteralPath $FromZip).Path
$toZip = (Resolve-Path -LiteralPath $ToZip).Path
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

$buildRoot = (Resolve-Path (Join-Path $projectRoot '.build')).Path
$stage = Join-Path $buildRoot 'updater-e2e'
$stagePrefix = $buildRoot.TrimEnd('\') + '\'
if (-not $stage.StartsWith($stagePrefix, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid updater test stage path.' }
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$source = Join-Path $stage 'source'
$installRoot = Join-Path $stage 'installed'
$helper = Join-Path $installRoot 'data\update\helper\SHIYIN-AI-updater-e2e.exe'
$desktopExe = Join-Path $installRoot 'SHIYIN AI.exe'
$dataRoot = Join-Path $installRoot 'data'
$pending = Join-Path $dataRoot 'update\pending.json'
$success = $false

try {
    Expand-Archive -LiteralPath $fromZip -DestinationPath $source -Force
    $roots = @(Get-ChildItem -LiteralPath $source -Directory)
    if ($roots.Count -ne 1 -or -not (Test-Path -LiteralPath (Join-Path $roots[0].FullName 'app\VERSION'))) {
        throw 'Source release ZIP does not contain one portable application root.'
    }
    Move-Item -LiteralPath $roots[0].FullName -Destination $installRoot
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
        '--apply-update',
        "--root=$installRoot",
        "--data=$dataRoot",
        "--zip=$toZip",
        "--version=$ToVersion",
        "--sha256=$(Get-Sha256 $toZip)",
        "--old-pid=$oldPid"
    )
    $processInfo.Arguments = ($arguments | ForEach-Object { '"' + ($_ -replace '"', '\"') + '"' }) -join ' '
    $process = [Diagnostics.Process]::Start($processInfo)
    if (-not $process.WaitForExit(120000)) {
        $process.Kill()
        throw 'Updater helper did not finish within 120 seconds.'
    }
    if ($process.ExitCode -ne 0) {
        $logPath = Join-Path $dataRoot 'update\updater.log'
        $log = if (Test-Path -LiteralPath $logPath) { Get-Content -LiteralPath $logPath -Raw } else { '' }
        throw "Updater helper failed with exit code $($process.ExitCode). $log"
    }
    Start-Sleep -Milliseconds 800
    if ((Get-Content -LiteralPath (Join-Path $installRoot 'app\VERSION') -Raw).Trim() -ne $ToVersion) {
        throw 'Updated application version does not match the release version.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataRoot 'e2e-user-data.txt'))) { throw 'Updater removed user data.' }
    if (Test-Path -LiteralPath $pending) { throw 'Updater did not clear pending update state.' }
    if (Test-Path -LiteralPath (Join-Path $installRoot 'app\obsolete-runtime-file.txt')) { throw 'Updater did not replace the app directory.' }
    $success = $true
    [pscustomobject]@{ from_zip = [IO.Path]::GetFileName($fromZip); to_zip = [IO.Path]::GetFileName($toZip); target_version = $ToVersion; data_preserved = $true; app_replaced = $true } | ConvertTo-Json -Compress
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
        if (-not $removed) { Write-Warning "Unable to remove updater test stage: $stage" }
    }
}
