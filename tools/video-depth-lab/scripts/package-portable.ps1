param([string]$Destination = '')
$ErrorActionPreference = 'Stop'
$lab = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (!$Destination) { $Destination = Join-Path $lab '../../dist/video-depth-batch/SHIYIN-Depth-Batch-0.3.2' }
$Destination = [IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force $Destination | Out-Null
Copy-Item -LiteralPath (Join-Path $lab 'src-tauri/target/release/SHIYIN-Video-Depth-Lab.exe') -Destination (Join-Path $Destination 'SHIYIN-Depth-Batch.exe') -Force
foreach ($dir in @('worker', 'worker-overlays')) {
    $target = Join-Path $Destination $dir
    New-Item -ItemType Directory -Force $target | Out-Null
    Get-ChildItem -LiteralPath (Join-Path $lab $dir) -File | Where-Object Extension -In @('.py','.exe','.json') | Copy-Item -Destination $target -Force
}
New-Item -ItemType Directory -Force (Join-Path $Destination 'scripts') | Out-Null
Copy-Item -LiteralPath (Join-Path $lab 'scripts/prepare-components.ps1') -Destination (Join-Path $Destination 'scripts') -Force
foreach ($file in @('runtime-manifest.json', 'model-download-manifest.json', 'PORTABLE.md')) { Copy-Item -LiteralPath (Join-Path $lab $file) -Destination $Destination -Force }
$archive = "$Destination.zip"
if (Test-Path -LiteralPath $archive) { throw "Archive already exists: $archive" }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($Destination, $archive, [IO.Compression.CompressionLevel]::Optimal, $true)
Get-FileHash -LiteralPath $archive -Algorithm SHA256
