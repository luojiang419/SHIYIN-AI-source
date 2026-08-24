param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath $Root).Path
$version = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "VERSION must use x.y.z format: $version" }

function Read-Utf8([string]$Path) {
    return [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
}

$sources = [ordered]@{}
$package = Read-Utf8 (Join-Path $projectRoot 'package.json') | ConvertFrom-Json
$tauri = Read-Utf8 (Join-Path $projectRoot 'src-tauri\tauri.conf.json') | ConvertFrom-Json
$updateNotes = Read-Utf8 (Join-Path $projectRoot 'static\update-notes.json') | ConvertFrom-Json
$packageLockText = [IO.File]::ReadAllText((Join-Path $projectRoot 'package-lock.json'))
$packageLockRoot = [regex]::Match($packageLockText, '(?ms)\A\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"version"\s*:\s*"([^"]+)"')
$packageLockWorkspace = [regex]::Match($packageLockText, '(?ms)"packages"\s*:\s*\{\s*""\s*:\s*\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"version"\s*:\s*"([^"]+)"')
if (-not $packageLockRoot.Success -or -not $packageLockWorkspace.Success) {
    throw 'Unable to read root versions from package-lock.json.'
}

$sources['package.json'] = [string]$package.version
$sources['package-lock.json'] = $packageLockRoot.Groups[1].Value
$sources['package-lock.json packages root'] = $packageLockWorkspace.Groups[1].Value
$sources['src-tauri/tauri.conf.json'] = [string]$tauri.version
$sources['static/update-notes.json'] = [string]$updateNotes.version

$textSources = @{
    'src-tauri/Cargo.toml' = @{ Pattern = '(?ms)^\[package\].*?^version\s*=\s*"([^"]+)"'; Group = 1 }
    'src-tauri/Cargo.lock' = @{ Pattern = '(?ms)\[\[package\]\]\s*name\s*=\s*"canvas-desktop"\s*version\s*=\s*"([^"]+)"'; Group = 1 }
    'main.py' = @{ Pattern = '(?m)^APP_VERSION\s*=\s*"([^"]+)"'; Group = 1 }
    'release-notes/current.md' = @{ Pattern = '(?m)^# SHIYIN AI v(\d+\.\d+\.\d+)\s*$'; Group = 1 }
}
foreach ($entry in $textSources.GetEnumerator()) {
    $path = Join-Path $projectRoot $entry.Key
    $match = [regex]::Match([IO.File]::ReadAllText($path), $entry.Value.Pattern)
    if (-not $match.Success) { throw "Unable to read version from $($entry.Key)." }
    $sources[$entry.Key] = $match.Groups[$entry.Value.Group].Value
}

$mismatches = @($sources.GetEnumerator() | Where-Object { $_.Value -ne $version })
if ($mismatches.Count -gt 0) {
    $details = ($mismatches | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ', '
    throw "Version sources are not synchronized with VERSION=$version`: $details"
}

Write-Host "Version sources synchronized: $version ($($sources.Count) sources)"
