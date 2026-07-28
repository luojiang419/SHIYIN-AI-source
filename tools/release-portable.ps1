param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

& (Join-Path $PSScriptRoot "build-portable.ps1") -IncrementVersion
if (-not $?) { throw "Portable build failed." }

$version = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
if (-not $env:GH_TOKEN) { $env:GH_TOKEN = gh auth token }
if (-not $env:GH_TOKEN) { throw 'Unable to obtain a GitHub token for publication.' }
$sourceSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot determine the source commit SHA.' }
& (Join-Path $PSScriptRoot "publish-release.ps1") -Version $version -SourceRepo 'luojiang419/SHIYIN-AI-source' -SourceSha $sourceSha
if (-not $?) { throw "Release publication failed." }
