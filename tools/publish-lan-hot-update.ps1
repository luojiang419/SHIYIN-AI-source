param(
    [string]$Version = (Get-Date -Format 'yyyyMMddHHmmss'),
    [string]$Notes = '局域网热更新',
    [switch]$WebOnly
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$taskArguments = @('tools/build-hot-update.py', '--version', $Version, '--notes', $Notes, '--publish')
if ($WebOnly) { $taskArguments += '--web-only' }
python @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Hot update build or publication failed' }
