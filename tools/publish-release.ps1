param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [Parameter(Mandatory = $true)]
    [string]$SourceRepo,
    [Parameter(Mandatory = $true)]
    [string]$SourceSha,
    [string]$ReleaseRepo = 'luojiang419/SHIYIN-AI',
    [string]$AssetPath,
    [string]$ChecksumPath,
    [string]$ReleaseNotesPath = 'release-notes\current.md',
    [string]$SignatureStatus = 'NotSigned'
)

$ErrorActionPreference = 'Stop'
if (-not $env:GH_TOKEN) { throw 'GH_TOKEN is required for cross-repository publishing.' }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid version: $Version" }
if ($SourceSha -notmatch '^[0-9a-fA-F]{40}$') { throw "Invalid source commit SHA: $SourceSha" }

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$assetName = "SHIYIN-AI-v$Version-windows-x64.zip"
if (-not $AssetPath) { $AssetPath = Join-Path $projectRoot "dist\$assetName" }
$assetPath = (Resolve-Path -LiteralPath $AssetPath).Path
if ([IO.Path]::GetFileName($assetPath) -ne $assetName) { throw "Unexpected release asset name: $([IO.Path]::GetFileName($assetPath))" }
if (-not $ChecksumPath) { $ChecksumPath = "$assetPath.sha256" }
$checksumPath = (Resolve-Path -LiteralPath $ChecksumPath).Path
$notesPath = (Resolve-Path -LiteralPath (Join-Path $projectRoot $ReleaseNotesPath)).Path
if ((Get-Item -LiteralPath $assetPath).Length -lt 5MB) { throw 'Release asset is unexpectedly small.' }

function Get-Sha256([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha256 = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha256.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha256.Dispose(); $stream.Dispose() }
}

$sha256 = Get-Sha256 $assetPath
$expectedChecksum = "$sha256  $assetName"
if ((Get-Content -Raw -LiteralPath $checksumPath).Trim() -ne $expectedChecksum) { throw 'Checksum does not match release asset.' }

$headers = @{
    Accept = 'application/vnd.github+json'
    Authorization = "Bearer $env:GH_TOKEN"
    'X-GitHub-Api-Version' = '2022-11-28'
    'User-Agent' = 'SHIYIN-AI-Release-Workflow'
}
$apiBase = "https://api.github.com/repos/$ReleaseRepo"
$tag = "v$Version"
$tagPath = [Uri]::EscapeDataString($tag)
$manifestPath = "releases/$tag.json"
$releaseId = $null
$targetSha = $null
$tagCreated = $false
$published = $false

function Invoke-GitHubApi {
    param([string]$Method, [string]$Uri, [object]$Body, [string]$InFile, [string]$ContentType = 'application/json')
    $parameters = @{ Method = $Method; Uri = $Uri; Headers = $headers }
    if ($null -ne $Body) { $parameters.Body = ($Body | ConvertTo-Json -Depth 10 -Compress); $parameters.ContentType = $ContentType }
    if ($InFile) { $parameters.InFile = $InFile; $parameters.ContentType = $ContentType }
    Invoke-RestMethod @parameters
}

function Try-GetGitHubApi([string]$Uri) {
    try { return Invoke-GitHubApi -Method Get -Uri $Uri }
    catch { if ($_.Exception.Response.StatusCode -eq 404) { return $null }; throw }
}

try {
    $releases = @(Invoke-GitHubApi -Method Get -Uri "$apiBase/releases?per_page=100")
    foreach ($existing in @($releases | Where-Object { $_.tag_name -eq $tag })) {
        if (-not $existing.draft) { throw "A published release already exists for $tag." }
        if ($existing.body -notlike "*source-sha:$SourceSha*") { throw "A draft for $tag belongs to another source commit." }
        Invoke-GitHubApi -Method Delete -Uri "$apiBase/releases/$($existing.id)" | Out-Null
    }

    $manifest = [ordered]@{
        version = $Version; tag = $tag; sourceRepository = $SourceRepo; sourceSha = $SourceSha
        assetName = $assetName; assetSize = (Get-Item -LiteralPath $assetPath).Length
        sha256 = $sha256; signatureStatus = $SignatureStatus; generatedAtUtc = [DateTime]::UtcNow.ToString('o')
    }
    $manifestJson = ($manifest | ConvertTo-Json -Depth 5) + "`n"
    $existingManifest = Try-GetGitHubApi -Uri "$apiBase/contents/$manifestPath"
    if ($null -eq $existingManifest) {
        $content = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($manifestJson))
        $created = Invoke-GitHubApi -Method Put -Uri "$apiBase/contents/$manifestPath" -Body @{ message = "release: $tag"; content = $content; branch = 'main' }
        $targetSha = $created.commit.sha
    } else {
        $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(($existingManifest.content -replace '\s', ''))) | ConvertFrom-Json
        if ($decoded.sourceSha -ne $SourceSha) { throw "Existing manifest for $tag belongs to another source commit." }
        $commits = @(Invoke-GitHubApi -Method Get -Uri "$apiBase/commits?path=$([Uri]::EscapeDataString($manifestPath))&per_page=1")
        if ($commits.Count -ne 1) { throw "Cannot resolve the manifest commit for $tag." }
        $targetSha = $commits[0].sha
    }

    $tagRef = Try-GetGitHubApi -Uri "$apiBase/git/ref/tags/$tagPath"
    if ($null -eq $tagRef) {
        Invoke-GitHubApi -Method Post -Uri "$apiBase/git/refs" -Body @{ ref = "refs/tags/$tag"; sha = $targetSha } | Out-Null
        $tagCreated = $true
    } elseif ($tagRef.object.sha -ne $targetSha) { throw "Tag $tag already points to $($tagRef.object.sha)." }

    $runUrl = if ($env:GITHUB_RUN_ID) { "https://github.com/$SourceRepo/actions/runs/$env:GITHUB_RUN_ID" } else { 'local-release-run' }
    $body = @"
$(Get-Content -Raw -LiteralPath $notesPath)

---

- 源提交：$SourceSha
- 云端构建：$runUrl
- SHA-256：$sha256
- 签名状态：$SignatureStatus

<!-- source-sha:$SourceSha -->
"@
    $draft = Invoke-GitHubApi -Method Post -Uri "$apiBase/releases" -Body @{
        tag_name = $tag; target_commitish = $targetSha; name = "SHIYIN AI $tag"; body = $body; draft = $true; prerelease = $false
    }
    $releaseId = $draft.id
    $uploadBase = $draft.upload_url -replace '\{\?name,label\}$', ''
    Invoke-GitHubApi -Method Post -Uri "${uploadBase}?name=$([Uri]::EscapeDataString($assetName))" -InFile $assetPath -ContentType 'application/octet-stream' | Out-Null
    $checksumName = [IO.Path]::GetFileName($checksumPath)
    Invoke-GitHubApi -Method Post -Uri "${uploadBase}?name=$([Uri]::EscapeDataString($checksumName))" -InFile $checksumPath -ContentType 'text/plain' | Out-Null

    $draftCheck = Invoke-GitHubApi -Method Get -Uri "$apiBase/releases/$releaseId"
    $remoteAsset = @($draftCheck.assets | Where-Object { $_.name -eq $assetName })
    $remoteChecksum = @($draftCheck.assets | Where-Object { $_.name -eq $checksumName })
    if ($remoteAsset.Count -ne 1 -or $remoteChecksum.Count -ne 1 -or $remoteAsset[0].state -ne 'uploaded' -or $remoteAsset[0].size -ne (Get-Item -LiteralPath $assetPath).Length -or $remoteChecksum[0].state -ne 'uploaded') { throw 'Draft release assets failed validation.' }
    if ($remoteAsset[0].digest -and $remoteAsset[0].digest -ne "sha256:$sha256") { throw 'GitHub asset digest mismatch.' }

    $branchRef = Invoke-GitHubApi -Method Get -Uri "$apiBase/git/ref/heads/main"
    $verifiedTag = Invoke-GitHubApi -Method Get -Uri "$apiBase/git/ref/tags/$tagPath"
    if ($branchRef.object.sha -ne $targetSha -or $verifiedTag.object.sha -ne $targetSha) { throw 'Release manifest branch and tag do not point to the same SHA.' }
    $formal = Invoke-GitHubApi -Method Patch -Uri "$apiBase/releases/$releaseId" -Body @{ draft = $false; prerelease = $false; make_latest = 'true' }
    $published = $true

    $latest = Invoke-GitHubApi -Method Get -Uri "$apiBase/releases/latest"
    $latestAsset = @($latest.assets | Where-Object { $_.name -eq $assetName })
    $latestChecksum = @($latest.assets | Where-Object { $_.name -eq $checksumName })
    if ($latest.tag_name -ne $tag -or $latest.draft -or $latest.prerelease -or $latestAsset.Count -ne 1 -or $latestChecksum.Count -ne 1) { throw 'Latest Release does not expose the exact update contract.' }

    $values = [ordered]@{ tag = $tag; release_url = $formal.html_url; asset_url = $latestAsset[0].browser_download_url; sha256 = $sha256; target_sha = $targetSha }
    if ($env:GITHUB_OUTPUT) { foreach ($entry in $values.GetEnumerator()) { "$($entry.Key)=$($entry.Value)" | Add-Content -LiteralPath $env:GITHUB_OUTPUT -Encoding utf8 } }
    $values | ConvertTo-Json -Compress
} catch {
    if ($releaseId -and -not $published) { try { Invoke-GitHubApi -Method Delete -Uri "$apiBase/releases/$releaseId" | Out-Null } catch { Write-Warning "Failed to remove draft release $releaseId." } }
    if ($tagCreated -and $targetSha) { try { $currentTag = Try-GetGitHubApi -Uri "$apiBase/git/ref/tags/$tagPath"; if ($currentTag -and $currentTag.object.sha -eq $targetSha) { Invoke-GitHubApi -Method Delete -Uri "$apiBase/git/refs/tags/$tagPath" | Out-Null } } catch { Write-Warning "Failed to remove tag $tag." } }
    throw
}
