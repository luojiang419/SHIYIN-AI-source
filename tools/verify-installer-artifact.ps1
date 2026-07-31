param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid version: $Version" }

$rootPath = (Resolve-Path -LiteralPath $Root).Path
$assetName = "SHIYIN-AI-Setup-$Version.exe"
$assetPath = Join-Path $rootPath "dist\installer\$assetName"
if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) { throw "Missing release artifact: $assetPath" }

$asset = Get-Item -LiteralPath $assetPath
if ($asset.Length -lt 5MB) { throw "Installer is unexpectedly small: $($asset.Length) bytes" }
$productVersion = $asset.VersionInfo.ProductVersion.Trim()
if ($productVersion -ne $Version) { throw "Installer version mismatch: expected $Version, got $productVersion" }

$signatureStatus = (Get-AuthenticodeSignature -LiteralPath $assetPath).Status.ToString()
if ($signatureStatus -notin @('Valid', 'NotSigned')) { throw "Installer signature validation failed: $signatureStatus" }
$sha256 = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
$checksumPath = "$assetPath.sha256"
[IO.File]::WriteAllText($checksumPath, "$sha256  $assetName`n", [Text.UTF8Encoding]::new($false))

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
