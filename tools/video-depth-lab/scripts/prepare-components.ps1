param([Parameter(Mandatory=$true)][string]$Root, [Parameter(Mandatory=$true)][string]$Model)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
# Rust canonicalize uses extended-length paths; Windows PowerShell 5.1's
# FileSystem provider cannot resolve their drive in Join-Path/New-Item.
if ($Root.StartsWith('\\?\UNC\', [StringComparison]::OrdinalIgnoreCase)) {
    $Root = '\\' + $Root.Substring(8)
} elseif ($Root.StartsWith('\\?\', [StringComparison]::OrdinalIgnoreCase)) {
    $Root = $Root.Substring(4)
}
$Root = [IO.Path]::GetFullPath($Root)
$cache = Join-Path $Root 'runtime/downloads'
New-Item -ItemType Directory -Force $cache | Out-Null
Write-Output 'Checking runtime and model files...'
function Get-Sha256([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}
function Get-Verified($Package, [string]$Destination) {
    if (Test-Path -LiteralPath $Destination) {
        Write-Output "Verifying $($Package.id)..."
        if ((Get-Item -LiteralPath $Destination).Length -eq $Package.size -and (Get-Sha256 $Destination) -eq $Package.sha256) { return }
        throw "Existing file failed integrity verification: $Destination"
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $Destination) | Out-Null
    Write-Output "Downloading $($Package.id) ($([math]::Round($Package.size / 1MB)) MB)..."
    $partial = "$Destination.partial"
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = (Get-Command curl.exe -ErrorAction Stop).Source
    $start.Arguments = '--silent --show-error --fail --location --retry 3 --connect-timeout 30 --speed-time 120 --speed-limit 1024 --continue-at - --output "' + $partial + '" "' + $Package.domestic_url + '"'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardError = $true
    $download = [Diagnostics.Process]::Start($start)
    $downloadError = $download.StandardError.ReadToEndAsync()
    try {
        do {
            $finished = $download.WaitForExit(1000)
            $bytes = if (Test-Path -LiteralPath $partial) { (Get-Item -LiteralPath $partial).Length } else { 0 }
            Write-Output ("Downloading {0}: {1:N1} / {2:N1} MB" -f $Package.id, ($bytes / 1MB), ($Package.size / 1MB))
        } while (!$finished)
        if ($download.ExitCode -ne 0) { throw "Download failed; restart to resume: $($Package.id). $($downloadError.Result)" }
    } finally { $download.Dispose() }
    Write-Output "Verifying $($Package.id)..."
    if ((Get-Item -LiteralPath $partial).Length -ne $Package.size -or (Get-Sha256 $partial) -ne $Package.sha256) {
        Remove-Item -LiteralPath $partial -Force
        throw "Download integrity check failed: $($Package.id)"
    }
    Move-Item -LiteralPath $partial -Destination $Destination
}
$worker = Join-Path $Root 'runtime/video-depth-worker/video-depth-worker.exe'
$devPython = Join-Path $Root 'runtime/venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $worker) -and !(Test-Path -LiteralPath $devPython)) {
    $manifest = Get-Content -LiteralPath (Join-Path $Root 'runtime-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $variantId = 'windows-x86_64-cpu'
    if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
        $rows = & nvidia-smi.exe --query-gpu=compute_cap,memory.total,driver_version --format=csv,noheader,nounits 2>$null
        foreach ($row in $rows) {
            $values = $row.Split(',').Trim()
            if ($values.Length -ne 3) { continue }
            $cap = 0.0
            if (![double]::TryParse($values[0], [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$cap)) { continue }
            if ([double]$values[1] -lt 4096) { continue }
            if ($cap -ge 12 -and [version]$values[2] -ge [version]'570.65') { $variantId = 'windows-x86_64-cuda128'; break }
            if ($cap -ge 7 -and $cap -le 9.9 -and [version]$values[2] -ge [version]'560.76') { $variantId = 'windows-x86_64-cuda126'; break }
        }
    }
    $variant = $manifest.variants | Where-Object id -EQ $variantId
    Write-Output "Preparing $variantId. First installation may take several minutes."
    $archives = @()
    foreach ($id in $variant.packages) {
        $package = $manifest.packages | Where-Object id -EQ $id
        $destination = Join-Path $cache $package.file
        Get-Verified $package $destination
        $archives += $destination
    }
    if ($variant.assemble_archive) {
        Write-Output 'Assembling runtime archive...'
        $joined = Join-Path $cache "$variantId.zip"
        $stream = [IO.File]::Create($joined)
        try { foreach ($file in $archives) { $inputStream = [IO.File]::OpenRead($file); try { $inputStream.CopyTo($stream) } finally { $inputStream.Dispose() } } } finally { $stream.Dispose() }
        if ((Get-Item -LiteralPath $joined).Length -ne $variant.assemble_archive.size -or (Get-Sha256 $joined) -ne $variant.assemble_archive.sha256) { throw 'Assembled runtime integrity failure' }
        $archives = @($joined)
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $staging = Join-Path $cache ('extract-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $staging | Out-Null
    Write-Output 'Extracting runtime archive. This may take several minutes...'
    foreach ($archive in $archives) { [IO.Compression.ZipFile]::ExtractToDirectory($archive, $staging) }
    foreach ($path in $variant.required_paths) { if (!(Test-Path -LiteralPath (Join-Path $staging $path))) { throw "Runtime file missing: $path" } }
    Set-Content -LiteralPath (Join-Path $Root 'runtime/variant.txt') -Value $variantId -Encoding ASCII
    Write-Output 'Installing runtime files...'
    foreach ($item in Get-ChildItem -LiteralPath (Join-Path $staging 'runtime')) {
        Copy-Item -LiteralPath $item.FullName -Destination (Join-Path $Root 'runtime') -Recurse -Force
    }
    # The cache is task-owned and always resolved beneath the application runtime.
    if ([IO.Path]::GetFullPath($cache).StartsWith($Root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $cache -Recurse -Force
    }
}
if (Test-Path -LiteralPath $worker) {
    $variantFile = Join-Path $Root 'runtime/variant.txt'
    if (!(Test-Path -LiteralPath $variantFile)) { throw 'Runtime variant marker missing; reinstall runtime in a clean application folder.' }
    $flavor = (Get-Content -LiteralPath $variantFile -Raw).Trim().Replace('windows-x86_64-', '')
    $overlayManifest = Get-Content -LiteralPath (Join-Path $Root 'worker-overlays/manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $overlayEntry = $overlayManifest.$flavor
    if (!$overlayEntry) { throw 'Unknown runtime variant' }
    $overlay = Join-Path $Root ('worker-overlays/' + $overlayEntry.file)
    if ((Get-Sha256 $overlay) -ne $overlayEntry.sha256) { throw 'Worker overlay integrity failure' }
    if ((Get-Sha256 $worker) -ne $overlayEntry.sha256) {
        Copy-Item -LiteralPath $overlay -Destination "$worker.updated" -Force
        Move-Item -LiteralPath "$worker.updated" -Destination $worker -Force
    }
}
$models = Get-Content -LiteralPath (Join-Path $Root 'model-download-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$modelId = if ($Model -eq 'vda_small_fp16_relative') { 'vda-small-model' } elseif ($Model -eq 'vda_base_fp16_relative') { 'vda-base-model' } else { throw 'Unsupported model' }
$package = $models.packages | Where-Object id -EQ $modelId
Get-Verified $package (Join-Path $Root ('runtime/' + $package.target_path))
Write-Output 'Runtime and model ready.'
