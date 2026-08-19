param(
    [string]$Version = "",
    [string]$BaseCommit = "672bb14",
    [switch]$SkipPatch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot "dist\source-package"))

if (-not $Version) {
    $Version = [IO.File]::ReadAllText((Join-Path $projectRoot "VERSION")).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Invalid package version: $Version"
}

$sourceCommit = (& git -C $projectRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceCommit -notmatch '^[0-9a-f]{40}$') {
    throw "Unable to resolve the current Git commit."
}
if (-not $SkipPatch) {
    & git -C $projectRoot cat-file -e "$BaseCommit^{commit}"
    if ($LASTEXITCODE -ne 0) {
        throw "Base commit does not exist: $BaseCommit"
    }
}

$packageName = "SHIYIN-AI-Topaz-Node-v$Version"
$stageRoot = [IO.Path]::GetFullPath((Join-Path $outputRoot $packageName))
$zipPath = [IO.Path]::GetFullPath((Join-Path $outputRoot "$packageName.zip"))
$zipHashPath = [IO.Path]::GetFullPath((Join-Path $outputRoot "$packageName.zip.sha256"))

function Assert-PackageChildPath([string]$PathValue) {
    $full = [IO.Path]::GetFullPath($PathValue)
    $prefix = $outputRoot.TrimEnd('\') + '\'
    if (-not $full.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Package path escaped output root: $full"
    }
}

Assert-PackageChildPath $stageRoot
Assert-PackageChildPath $zipPath
Assert-PackageChildPath $zipHashPath

New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
foreach ($target in @($stageRoot, $zipPath, $zipHashPath)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

$sourceFiles = @(
    "VERSION",
    "README.md",
    "package.json",
    "package-lock.json",
    "src-tauri/Cargo.toml",
    "src-tauri/Cargo.lock",
    "src-tauri/tauri.conf.json",
    "canvas_core/app_config.py",
    "canvas_core/topaz_video.py",
    "main.py",
    "static/app-settings.html",
    "static/canvas.html",
    "static/css/app-settings.css",
    "static/css/canvas-topaz-node.css",
    "static/js/app-settings.js",
    "static/js/canvas-topaz-node.js",
    "static/js/canvas.js",
    "static/update-notes.json",
    "tests/test_app_config.py",
    "tests/test_desktop_updater_contract.py",
    "tests/test_topaz_video.py",
    "tests/test_topaz_video_canvas.py",
    "tests/test_topaz_video_settings.py",
    "tests/test_topaz_video_tasks.py",
    "tools/build-installer.ps1",
    "tools/build-topaz-node-source-package.ps1",
    "tools/stamp-web-cache-version.mjs"
)

foreach ($relativePath in $sourceFiles) {
    $sourcePath = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "Required source file is missing: $relativePath"
    }
    $destinationPath = Join-Path (Join-Path $stageRoot "source") $relativePath
    $destinationDirectory = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
}

$documentCandidates = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Filter "Topaz*.md" |
    Where-Object { -not $_.FullName.StartsWith($outputRoot, [StringComparison]::OrdinalIgnoreCase) }
$manualPath = $documentCandidates |
    Where-Object { ([IO.File]::ReadLines($_.FullName) | Select-Object -First 1) -match '^# Topaz ' } |
    Select-Object -First 1 -ExpandProperty FullName
$readmePath = $documentCandidates |
    Where-Object { ([IO.File]::ReadLines($_.FullName) | Select-Object -First 1) -match '^# SHIYIN AI Topaz ' } |
    Select-Object -First 1 -ExpandProperty FullName
foreach ($requiredDocument in @($manualPath, $readmePath)) {
    if (-not $requiredDocument -or -not (Test-Path -LiteralPath $requiredDocument -PathType Leaf)) {
        throw "Required package document is missing: $requiredDocument"
    }
}

$docsRoot = Join-Path $stageRoot "docs"
New-Item -ItemType Directory -Path $docsRoot -Force | Out-Null
Copy-Item -LiteralPath $manualPath -Destination (Join-Path $docsRoot "Developer-Guide.zh-CN.md") -Force
Copy-Item -LiteralPath $readmePath -Destination (Join-Path $stageRoot "README.md") -Force

[IO.File]::WriteAllText((Join-Path $stageRoot "VERSION.txt"), "$Version`n", $utf8NoBom)
[IO.File]::WriteAllText(
    (Join-Path $stageRoot "SOURCE-COMMIT.txt"),
    "commit=$sourceCommit`nbase_commit=$BaseCommit`ngenerated_at=$([DateTimeOffset]::Now.ToString('o'))`n",
    $utf8NoBom
)

if (-not $SkipPatch) {
    $patchRoot = Join-Path $stageRoot "patches"
    New-Item -ItemType Directory -Path $patchRoot -Force | Out-Null
    $patchFiles = @(
        "VERSION",
        "package.json",
        "package-lock.json",
        "src-tauri/Cargo.toml",
        "src-tauri/Cargo.lock",
        "src-tauri/tauri.conf.json",
        "canvas_core/app_config.py",
        "canvas_core/topaz_video.py",
        "main.py",
        "static/app-settings.html",
        "static/canvas.html",
        "static/css/app-settings.css",
        "static/css/canvas-topaz-node.css",
        "static/js/app-settings.js",
        "static/js/canvas-topaz-node.js",
        "static/js/canvas.js",
        "static/update-notes.json",
        "tests/test_app_config.py",
        "tests/test_desktop_updater_contract.py",
        "tests/test_topaz_video.py",
        "tests/test_topaz_video_canvas.py",
        "tests/test_topaz_video_settings.py",
        "tests/test_topaz_video_tasks.py",
        "tools/build-installer.ps1",
        "tools/stamp-web-cache-version.mjs"
    )
    $patchLines = & git -C $projectRoot diff --binary "$BaseCommit..$sourceCommit" -- @patchFiles
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to create the Topaz feature patch."
    }
    $patchText = ($patchLines -join "`n")
    if ($patchText) { $patchText += "`n" }
    [IO.File]::WriteAllText((Join-Path $patchRoot "topaz-node-feature.patch"), $patchText, $utf8NoBom)
}

$manifestPath = Join-Path $stageRoot "MANIFEST-SHA256.txt"
$manifestLines = Get-ChildItem -LiteralPath $stageRoot -Recurse -File |
    Where-Object { $_.FullName -ne $manifestPath } |
    ForEach-Object {
        $relative = $_.FullName.Substring($stageRoot.Length + 1).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        [pscustomobject]@{ Relative = $relative; Line = "$hash  $relative" }
    } |
    Sort-Object Relative |
    Select-Object -ExpandProperty Line
[IO.File]::WriteAllText($manifestPath, (($manifestLines -join "`n") + "`n"), $utf8NoBom)

Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
$zipHash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($zipHashPath, "$zipHash  $([IO.Path]::GetFileName($zipPath))`n", $utf8NoBom)

$verifyRoot = Join-Path $outputRoot ".verify-$([Guid]::NewGuid().ToString('N'))"
Assert-PackageChildPath $verifyRoot
try {
    Expand-Archive -LiteralPath $zipPath -DestinationPath $verifyRoot -Force
    $verifiedManifest = Join-Path $verifyRoot "MANIFEST-SHA256.txt"
    if (-not (Test-Path -LiteralPath $verifiedManifest -PathType Leaf)) {
        throw "Package verification failed: manifest is missing."
    }
    foreach ($line in [IO.File]::ReadAllLines($verifiedManifest)) {
        if (-not $line.Trim()) { continue }
        if ($line -notmatch '^([0-9a-f]{64})  (.+)$') {
            throw "Package verification failed: invalid manifest line: $line"
        }
        $expectedHash = $Matches[1]
        $relativePath = $Matches[2].Replace('/', '\')
        $verifiedPath = [IO.Path]::GetFullPath((Join-Path $verifyRoot $relativePath))
        $verifyPrefix = [IO.Path]::GetFullPath($verifyRoot).TrimEnd('\') + '\'
        if (-not $verifiedPath.StartsWith($verifyPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Package verification failed: manifest path escaped archive root."
        }
        if (-not (Test-Path -LiteralPath $verifiedPath -PathType Leaf)) {
            throw "Package verification failed: missing $($Matches[2])"
        }
        $actualHash = (Get-FileHash -LiteralPath $verifiedPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) {
            throw "Package verification failed: hash mismatch for $($Matches[2])"
        }
    }
}
finally {
    if (Test-Path -LiteralPath $verifyRoot) {
        Remove-Item -LiteralPath $verifyRoot -Recurse -Force
    }
}

[pscustomobject]@{
    Package = $zipPath
    Sha256 = $zipHash
    HashFile = $zipHashPath
    ExpandedSource = $stageRoot
    SourceCommit = $sourceCommit
    BaseCommit = $BaseCommit
    FileCount = (Get-ChildItem -LiteralPath $stageRoot -Recurse -File).Count
    Bytes = (Get-Item -LiteralPath $zipPath).Length
} | Format-List
