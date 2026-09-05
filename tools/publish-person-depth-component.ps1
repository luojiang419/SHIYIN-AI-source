param(
    [Parameter(Mandatory = $true)]
    [string]$ComponentRoot,
    [string]$ReleaseRepo = "luojiang419/SHIYIN-AI-source",
    [string]$ManifestDestination = "canvas_core\person_depth_manifest.json",
    [string]$ReleaseNotesPath = "release-notes\person-depth-1.0.0.md"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$componentPath = (Resolve-Path -LiteralPath $ComponentRoot).Path
$candidatePath = Join-Path $componentPath "candidate-manifest.json"
$candidate = Get-Content -Raw -Encoding UTF8 -LiteralPath $candidatePath | ConvertFrom-Json
if ($candidate.component -ne "person-depth" -or $candidate.release_status -ne "candidate" -or $candidate.enabled -ne $false) {
    throw "Expected a disabled person-depth candidate manifest."
}
if ($candidate.version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Only a stable semantic component version can be published: $($candidate.version)"
}

$packages = @($candidate.packages)
if ($packages.Count -lt 2) { throw "The component must contain split runtime packages and a models package." }
foreach ($package in $packages) {
    $asset = (Resolve-Path -LiteralPath (Join-Path $componentPath $package.local_file)).Path
    $item = Get-Item -LiteralPath $asset
    if ($item.Length -ne [int64]$package.size) { throw "Package size mismatch: $($package.id)" }
    if ($item.Length -ge 2000000000) { throw "Package exceeds the GitHub safe asset limit: $($package.id)" }
    $digest = (Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($digest -ne $package.sha256) { throw "Package SHA-256 mismatch: $($package.id)" }
}

$tag = "person-depth-v$($candidate.version)"
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $existing = gh release view $tag --repo $ReleaseRepo --json isDraft,tagName 2>$null
    $releaseViewExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
}
if ($releaseViewExitCode -eq 0) { throw "Release already exists: $ReleaseRepo/$tag" }
if ($releaseViewExitCode -ne 1) { throw "Unable to check whether component release exists (exit $releaseViewExitCode)." }
$notes = (Resolve-Path -LiteralPath (Join-Path $projectRoot $ReleaseNotesPath)).Path
$target = (git -C $projectRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $target -notmatch '^[0-9a-f]{40}$') { throw "Cannot resolve source commit." }

$created = $false
try {
    gh release create $tag --repo $ReleaseRepo --target $target --title "SHIYIN AI person-depth $($candidate.version)" --notes-file $notes --draft
    if ($LASTEXITCODE -ne 0) { throw "Failed to create component release draft." }
    $created = $true
    foreach ($package in $packages) {
        $asset = (Resolve-Path -LiteralPath (Join-Path $componentPath $package.local_file)).Path
        gh release upload $tag $asset --repo $ReleaseRepo
        if ($LASTEXITCODE -ne 0) { throw "Failed to upload package: $($package.id)" }
    }
    gh release edit $tag --repo $ReleaseRepo --draft=false --prerelease
    if ($LASTEXITCODE -ne 0) { throw "Failed to publish component prerelease." }

    $remote = gh release view $tag --repo $ReleaseRepo --json assets,isDraft,isPrerelease | ConvertFrom-Json
    if ($remote.isDraft -or -not $remote.isPrerelease) { throw "Component release state verification failed." }
    foreach ($package in $packages) {
        $asset = @($remote.assets | Where-Object { $_.name -eq $package.local_file })
        if ($asset.Count -ne 1 -or [int64]$asset[0].size -ne [int64]$package.size) {
            throw "Remote package verification failed: $($package.id)"
        }
        if ($asset[0].digest -and $asset[0].digest -ne "sha256:$($package.sha256)") {
            throw "Remote package digest verification failed: $($package.id)"
        }
        $url = "https://github.com/$ReleaseRepo/releases/download/$tag/$($package.local_file)"
        $package.domestic_url = ""
        $package.official_url = $url
        $package.PSObject.Properties.Remove("local_file")
    }

    $candidate.enabled = $true
    $candidate.release_status = "released"
    $candidate.message = ('"\u9ad8\u7cbe\u5ea6\u4eba\u7269\u6df1\u5ea6\u7ec4\u4ef6\u5c1a\u672a\u5b89\u88c5\uff0c\u5c06\u5728\u9700\u8981\u65f6\u81ea\u52a8\u4e0b\u8f7d"' | ConvertFrom-Json)
    $candidate.license_notice = "Depth Anything V2 Large: CC-BY-NC-4.0; BiRefNet: MIT. This optional component is for noncommercial use only; model weights are redistributed unchanged."
    $destination = Join-Path $projectRoot $ManifestDestination
    $json = ($candidate | ConvertTo-Json -Depth 20) + "`n"
    [IO.File]::WriteAllText($destination, $json, [Text.UTF8Encoding]::new($false))
    Write-Output ([ordered]@{ release = "https://github.com/$ReleaseRepo/releases/tag/$tag"; manifest = $destination } | ConvertTo-Json)
} catch {
    if ($created) { Write-Warning "Draft or partial release $tag was retained so the multi-gigabyte upload can be inspected or resumed." }
    throw
}
