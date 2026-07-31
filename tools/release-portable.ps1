param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $projectRoot

$currentVersion = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
if ($currentVersion -ne '1.0.100') { throw "Legacy ZIP bridge must start from v1.0.100; use the EXE installer release flow for later versions." }
& (Join-Path $PSScriptRoot "build-portable.ps1") -IncrementVersion
if (-not $?) { throw "Portable build failed." }

$version = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
if ($version -ne '1.0.101') { throw "Legacy ZIP bridge is limited to v1.0.101; use the EXE installer release flow for later versions." }
if (-not $env:GH_TOKEN) { $env:GH_TOKEN = gh auth token }
if (-not $env:GH_TOKEN) { throw 'Unable to obtain a GitHub token for publication.' }
$latestTag = (gh release view --repo luojiang419/SHIYIN-AI --json tagName --jq .tagName).Trim()
if ($LASTEXITCODE -ne 0 -or $latestTag -notmatch '^v\d+\.\d+\.\d+$') { throw 'Cannot resolve the previous formal release for updater verification.' }
$previousDir = Join-Path $projectRoot '.build\updater-e2e-from'
New-Item -ItemType Directory -Force -Path $previousDir | Out-Null
$previousAsset = "SHIYIN-AI-$latestTag-windows-x64.zip"
gh release download $latestTag --repo luojiang419/SHIYIN-AI --pattern $previousAsset --dir $previousDir --clobber
if ($LASTEXITCODE -ne 0) { throw 'Cannot download the previous release for updater verification.' }
& (Join-Path $PSScriptRoot 'smoke-updater.ps1') -FromZip (Join-Path $previousDir $previousAsset) -ToZip (Join-Path $projectRoot "dist\SHIYIN-AI-v$version-windows-x64.zip") -ToVersion $version
if (-not $?) { throw 'Previous-version updater verification failed.' }
$sourceSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot determine the source commit SHA.' }
& (Join-Path $PSScriptRoot "publish-release.ps1") -Version $version -SourceRepo 'luojiang419/SHIYIN-AI-source' -SourceSha $sourceSha -AssetType legacyZip
if (-not $?) { throw "Release publication failed." }
