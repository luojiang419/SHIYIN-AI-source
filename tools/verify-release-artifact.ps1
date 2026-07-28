param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid version: $Version" }

function Get-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha256.Dispose(); $stream.Dispose() }
}

$root = (Resolve-Path -LiteralPath $Root).Path
$assetName = "SHIYIN-AI-v$Version-windows-x64.zip"
$assetPath = Join-Path $root "dist\$assetName"
$checksumPath = "$assetPath.sha256"
$exePath = Join-Path $root "dist\SHIYIN-AI-v$Version-windows-x64\SHIYIN AI.exe"
foreach ($path in @($assetPath, $checksumPath, $exePath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing release artifact: $path" }
}

$asset = Get-Item -LiteralPath $assetPath
if ($asset.Length -lt 5MB) { throw "Release ZIP is unexpectedly small: $($asset.Length) bytes" }
$sha256 = Get-Sha256 $assetPath
$expectedChecksum = "$sha256  $assetName"
if ((Get-Content -Raw -LiteralPath $checksumPath).Trim() -ne $expectedChecksum) {
    throw 'Checksum file does not match the release ZIP.'
}

$signatureStatus = (Get-AuthenticodeSignature -LiteralPath $exePath).Status.ToString()
if ($signatureStatus -notin @('Valid', 'NotSigned')) { throw "Executable signature validation failed: $signatureStatus" }
$values = [ordered]@{
    asset_name = $assetName
    asset_path = (Resolve-Path -LiteralPath $assetPath).Path
    checksum_path = (Resolve-Path -LiteralPath $checksumPath).Path
    sha256 = $sha256
    size = $asset.Length
    signature_status = $signatureStatus
}
if ($env:GITHUB_OUTPUT) {
    foreach ($entry in $values.GetEnumerator()) { "$($entry.Key)=$($entry.Value)" | Add-Content -LiteralPath $env:GITHUB_OUTPUT -Encoding utf8 }
}
$values | ConvertTo-Json -Compress
