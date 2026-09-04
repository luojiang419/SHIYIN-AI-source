param(
    [string]$OutputRoot = "",
    [string]$DepthSnapshot = "",
    [string]$BiRefNetSnapshot = "",
    [string]$Version = "1.0.0-candidate.1",
    [switch]$AllowNonCommercialModel,
    [switch]$Resume,
    [switch]$KeepBuildDirectories
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$depthRevision = "7581137eff8d4e94f6e796d3baea0e9fa79b22d2"
$biRefNetRevision = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"

if (-not $AllowNonCommercialModel) {
    throw "Depth Anything V2 Large is CC-BY-NC-4.0. Pass -AllowNonCommercialModel only for a local candidate build."
}
if (-not $OutputRoot) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = Join-Path $projectRoot ".build\person-depth-component-$stamp"
}
$outputPath = [IO.Path]::GetFullPath($OutputRoot)
if ((Test-Path -LiteralPath $outputPath) -and -not $Resume) {
    throw "Output directory already exists; refusing to overwrite: $outputPath"
}

$hubRoot = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
if (-not $DepthSnapshot) {
    $DepthSnapshot = Join-Path $hubRoot "models--depth-anything--Depth-Anything-V2-Large-hf\snapshots\$depthRevision"
}
if (-not $BiRefNetSnapshot) {
    $BiRefNetSnapshot = Join-Path $hubRoot "models--ZhengPeng7--BiRefNet\snapshots\$biRefNetRevision"
}
$depthSource = (Resolve-Path -LiteralPath $DepthSnapshot).Path
$biRefNetSource = (Resolve-Path -LiteralPath $BiRefNetSnapshot).Path
if ((Split-Path -Leaf $depthSource) -ne $depthRevision) { throw "Depth Anything revision mismatch" }
if ((Split-Path -Leaf $biRefNetSource) -ne $biRefNetRevision) { throw "BiRefNet revision mismatch" }

function Write-Utf8Json([string]$Path, [object]$Value) {
    $json = ($Value | ConvertTo-Json -Depth 12) + "`n"
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
}

function Copy-SnapshotMaterialized([string]$Source, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $sourceRoot = [IO.Path]::GetFullPath($Source)
    foreach ($file in Get-ChildItem -LiteralPath $sourceRoot -Recurse -File) {
        $relative = $file.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        $resolved = $file.FullName
        if ($file.Target) {
            $linkTarget = [string]($file.Target | Select-Object -First 1)
            $resolved = [IO.Path]::GetFullPath((Join-Path $file.DirectoryName $linkTarget))
        }
        Copy-Item -LiteralPath $resolved -Destination $target -Force
    }
}

function Get-PackageInfo([string]$Id, [string]$Path, [string]$LocalFile) {
    $item = Get-Item -LiteralPath $Path
    return [pscustomobject][ordered]@{
        id = $Id
        size = [int64]$item.Length
        sha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        domestic_url = ""
        official_url = ""
        local_file = $LocalFile
    }
}

New-Item -ItemType Directory -Path $outputPath -Force | Out-Null
$runtimeDist = Join-Path $outputPath "runtime-dist"
$runtimeWork = Join-Path $outputPath "runtime-work"
$runtimeSource = Join-Path $runtimeDist "person-depth-worker"
$workerExe = Join-Path $runtimeSource "person-depth-worker.exe"
if (-not ($Resume -and (Test-Path -LiteralPath $workerExe -PathType Leaf))) {
    & python -m PyInstaller --noconfirm --clean --distpath $runtimeDist --workpath $runtimeWork (Join-Path $projectRoot "person-depth-worker.spec")
    if ($LASTEXITCODE -ne 0) { throw "person-depth worker PyInstaller build failed" }
}
if (-not (Test-Path -LiteralPath $workerExe -PathType Leaf)) { throw "worker EXE was not generated" }

$runtimeStage = Join-Path $outputPath "runtime-stage"
$runtimeTarget = Join-Path $runtimeStage "runtime"
New-Item -ItemType Directory -Path $runtimeTarget -Force | Out-Null
Copy-Item -Path (Join-Path $runtimeSource "*") -Destination $runtimeTarget -Recurse -Force

$modelStage = Join-Path $outputPath "models-stage"
$modelsRoot = Join-Path $modelStage "models"
Copy-SnapshotMaterialized $depthSource (Join-Path $modelsRoot "depth-anything-v2-large")
Copy-SnapshotMaterialized $biRefNetSource (Join-Path $modelsRoot "birefnet")
$modelSources = [ordered]@{
    depth = [ordered]@{
        id = "depth-anything/Depth-Anything-V2-Large-hf"
        revision = $depthRevision
        license = "CC-BY-NC-4.0"
    }
    segmentation = [ordered]@{
        id = "ZhengPeng7/BiRefNet"
        revision = $biRefNetRevision
        license = "MIT"
        trusted_files = [ordered]@{
            "BiRefNet_config.py" = "e7b8c2a74f6cea6a59553d517f71d47f2c1d90e670a13416af17c25fe2f3dc52"
            "birefnet.py" = "208771ae626f653d64128fbf2d6ac9f8e645c5cc5e286258a73ec3322bbfe5ef"
            "config.json" = "c97ea21569daf66b205491a4635147dd3bc42c7c168b89d7d75b53f67ef548ae"
        }
    }
}
Write-Utf8Json (Join-Path $modelsRoot "model-sources.json") $modelSources

Add-Type -AssemblyName System.IO.Compression.FileSystem
$runtimeArchive = Join-Path $outputPath "person-depth-runtime-$Version-windows-x64.zip"
$modelsArchive = Join-Path $outputPath "person-depth-models-$Version.zip"
$runtimeArchiveExists = Test-Path -LiteralPath $runtimeArchive -PathType Leaf
$modelsArchiveExists = Test-Path -LiteralPath $modelsArchive -PathType Leaf
if ($Resume -and $runtimeArchiveExists -and $modelsArchiveExists) {
    Write-Output "Reusing existing candidate archives."
} elseif ($runtimeArchiveExists -or $modelsArchiveExists) {
    throw "Candidate archives already exist; refusing to overwrite"
} else {
    [IO.Compression.ZipFile]::CreateFromDirectory($runtimeStage, $runtimeArchive, [IO.Compression.CompressionLevel]::NoCompression, $false)
    [IO.Compression.ZipFile]::CreateFromDirectory($modelStage, $modelsArchive, [IO.Compression.CompressionLevel]::NoCompression, $false)
}

$packages = @(
    (Get-PackageInfo "runtime-windows-x64" $runtimeArchive (Split-Path -Leaf $runtimeArchive)),
    (Get-PackageInfo "models" $modelsArchive (Split-Path -Leaf $modelsArchive))
)
$totalBytes = [int64](($packages | Measure-Object -Property size -Sum).Sum)
$manifest = [ordered]@{
    schema_version = 1
    component = "person-depth"
    version = $Version
    enabled = $false
    release_status = "candidate"
    message = "Local candidate built; Depth Anything V2 Large license approval and release URLs remain pending"
    license_notice = "Depth Anything V2 Large: CC-BY-NC-4.0; BiRefNet: MIT. Do not publish or commercially distribute this candidate."
    required_free_bytes = [int64]($totalBytes * 2.2)
    command = @("runtime/person-depth-worker.exe")
    required_paths = @(
        "runtime/person-depth-worker.exe",
        "models/depth-anything-v2-large/config.json",
        "models/depth-anything-v2-large/model.safetensors",
        "models/birefnet/config.json",
        "models/birefnet/model.safetensors",
        "models/birefnet/BiRefNet_config.py",
        "models/birefnet/birefnet.py",
        "models/model-sources.json"
    )
    model_sources = $modelSources
    packages = $packages
}
Write-Utf8Json (Join-Path $outputPath "candidate-manifest.json") $manifest

$versions = & python -c "import importlib.metadata as m,json; names=['torch','torchvision','transformers','pillow','numpy','opencv-python-headless','timm','einops','safetensors','pyinstaller']; print(json.dumps({n:m.version(n) for n in names},sort_keys=True))"
$metadata = [ordered]@{
    component = "person-depth"
    version = $Version
    built_at_utc = [DateTime]::UtcNow.ToString("o")
    python = (& python --version 2>&1).ToString()
    dependencies = ($versions | ConvertFrom-Json)
    packages = $packages
}
Write-Utf8Json (Join-Path $outputPath "build-metadata.json") $metadata

if (-not $KeepBuildDirectories) {
    foreach ($temporaryPath in @($runtimeDist, $runtimeWork, $runtimeStage, $modelStage)) {
        if (-not (Test-Path -LiteralPath $temporaryPath)) { continue }
        $resolvedTemporary = (Resolve-Path -LiteralPath $temporaryPath).Path
        if (-not $resolvedTemporary.StartsWith($outputPath + [IO.Path]::DirectorySeparatorChar)) {
            throw "Refusing to clean a path outside the candidate output root: $resolvedTemporary"
        }
        Remove-Item -LiteralPath $resolvedTemporary -Recurse -Force
    }
}

Write-Output ([ordered]@{
    output_root = $outputPath
    manifest = (Join-Path $outputPath "candidate-manifest.json")
    runtime_archive = $runtimeArchive
    models_archive = $modelsArchive
    total_bytes = $totalBytes
} | ConvertTo-Json -Depth 5)
