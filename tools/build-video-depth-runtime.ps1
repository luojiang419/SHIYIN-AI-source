param(
    [string]$Version = "1.0.0",
    [string]$CudaPython = "python",
    [string]$Cuda128Python = "",
    [string]$CpuPython = "",
    [string]$Output = "dist\video-depth-runtime",
    [string]$FfmpegRoot = "C:\ProgramData\chocolatey\lib\ffmpeg\tools\ffmpeg\bin",
    [switch]$ReuseExisting
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$outputRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $Output))
$buildRoot = Join-Path $projectRoot '.build\video-depth-runtime'

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Build-Profile([string]$Profile, [string]$Python) {
    if ([string]::IsNullOrWhiteSpace($Python)) { return $null }
    New-Item -ItemType Directory -Force $outputRoot | Out-Null
    $archive = Join-Path $outputRoot "video-depth-runtime-$Version-$Profile.zip"
    if ($ReuseExisting -and (Test-Path -LiteralPath $archive -PathType Leaf)) {
        return [ordered]@{
            id = "runtime-$Profile"; file = (Split-Path -Leaf $archive)
            size = (Get-Item -LiteralPath $archive).Length; sha256 = Get-Sha256 $archive
        }
    }
    $profileBuild = Join-Path $buildRoot $Profile
    $dist = Join-Path $profileBuild 'dist'
    $work = Join-Path $profileBuild 'work'
    $stage = Join-Path $profileBuild 'stage'
    foreach ($path in @($dist, $work, $stage)) {
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    }
    New-Item -ItemType Directory -Force (Join-Path $stage 'runtime') | Out-Null
    & $Python -m PyInstaller --noconfirm --clean --distpath $dist --workpath $work (Join-Path $projectRoot 'video-depth-worker.spec')
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $Profile" }
    $worker = Join-Path $dist 'video-depth-worker'
    if (-not (Test-Path -LiteralPath (Join-Path $worker 'video-depth-worker.exe'))) {
        throw "Worker executable is missing for $Profile"
    }
    Copy-Item -LiteralPath $worker -Destination (Join-Path $stage 'runtime\video-depth-worker') -Recurse
    $source = Join-Path $projectRoot 'tools\video-depth-lab\runtime\sources\video-depth-anything'
    $target = Join-Path $stage 'runtime\sources\video-depth-anything'
    New-Item -ItemType Directory -Force $target | Out-Null
    foreach ($name in @('video_depth_anything', 'utils', 'LICENSE')) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $target -Recurse -Force
    }
    Get-ChildItem $target -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Remove-Item -Recurse -Force
    New-Item -ItemType Directory -Force (Join-Path $stage 'runtime\bin') | Out-Null
    foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
        $tool = Join-Path $FfmpegRoot $name
        if (-not (Test-Path -LiteralPath $tool)) { throw "FFmpeg tool is missing: $tool" }
        Copy-Item -LiteralPath $tool -Destination (Join-Path $stage "runtime\bin\$name")
    }
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory(
        $stage, $archive, [IO.Compression.CompressionLevel]::NoCompression, $false
    )
    return [ordered]@{
        id = "runtime-$Profile"
        file = (Split-Path -Leaf $archive)
        size = (Get-Item -LiteralPath $archive).Length
        sha256 = Get-Sha256 $archive
    }
}

$packages = [Collections.Generic.List[object]]::new()
$variants = [Collections.Generic.List[object]]::new()
$cuda128Package = Build-Profile 'windows-x86_64-cuda128' $Cuda128Python
if ($cuda128Package) {
    $packages.Add($cuda128Package)
    $variants.Add([ordered]@{
        id = 'windows-x86_64-cuda128'; priority = 110
        constraints = [ordered]@{ os='windows'; arch='x86_64'; accelerator='cuda'; min_compute_capability=12.0; min_gpu_memory_bytes=4294967296; min_driver_version='570.65' }
        packages = @($cuda128Package.id)
    })
}
$cudaPackage = Build-Profile 'windows-x86_64-cuda126' $CudaPython
if ($cudaPackage) {
    $packages.Add($cudaPackage)
    $variants.Add([ordered]@{
        id = 'windows-x86_64-cuda126'; priority = 100
        constraints = [ordered]@{ os='windows'; arch='x86_64'; accelerator='cuda'; min_compute_capability=7.0; max_compute_capability=9.9; min_gpu_memory_bytes=4294967296; min_driver_version='560.76' }
        packages = @($cudaPackage.id)
    })
}
$cpuPackage = Build-Profile 'windows-x86_64-cpu' $CpuPython
if ($cpuPackage) {
    $packages.Add($cpuPackage)
    $variants.Add([ordered]@{
        id = 'windows-x86_64-cpu'; priority = 10
        constraints = [ordered]@{ os='windows'; arch='x86_64'; accelerator='cpu' }
        packages = @($cpuPackage.id)
    })
}
if (-not $packages.Count) { throw 'At least one runtime Python must be supplied.' }
$manifest = [ordered]@{
    schema_version = 2
    component = 'video-depth-runtime'
    version = $Version
    license_notice = 'PyTorch, TorchVision, FFmpeg and Video Depth Anything runtime; model weights are distributed separately.'
    packages = @($packages)
    variants = @($variants)
}
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot 'manifest.json') -Encoding utf8
$manifest | ConvertTo-Json -Depth 8
