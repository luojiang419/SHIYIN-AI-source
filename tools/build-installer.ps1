param(
    [switch]$IncrementVersion,
    [switch]$SkipBackend,
    [switch]$SkipDesktop,
    [switch]$SkipRuntimeSmoke,
    [string]$DwposeSmokeInput = "",
    [switch]$SkipDwposeFreshDownloadSmoke,
    [int]$SmokePort = 3118
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot

if ($IncrementVersion) {
    & (Join-Path $PSScriptRoot 'increment-version.ps1')
    if (-not $?) { throw 'Version increment failed.' }
}

$version = (Get-Content -LiteralPath (Join-Path $projectRoot 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid VERSION: $version" }
& (Join-Path $PSScriptRoot 'assert-version-sync.ps1') -Root $projectRoot
if (-not $?) { throw 'Version synchronization check failed.' }

$buildRoot = Join-Path $projectRoot '.build\installer'
$backendDist = Join-Path $buildRoot 'backend-dist'
$backendWork = Join-Path $buildRoot 'backend-work'
$stageRoot = Join-Path $projectRoot 'dist\installer-stage'
$installerPath = Join-Path $projectRoot "dist\installer\SHIYIN-AI-Setup-$version.exe"

function Remove-BuildPath([string]$Path, [string]$AllowedRoot) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $fullRoot = [IO.Path]::GetFullPath($AllowedRoot).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($fullRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean path outside build root: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) { Remove-Item -LiteralPath $fullPath -Recurse -Force }
}

function Assert-StagedWebAssets([string]$Root, [string]$ExpectedVersion) {
    $canvasPath = Join-Path $Root 'app\web\canvas.html'
    $canvasListPath = Join-Path $Root 'app\web\js\canvas-list.js'
    $specialNodesPath = Join-Path $Root 'app\web\js\canvas-special-nodes.js'
    $topazPath = Join-Path $Root 'app\web\js\canvas-topaz-node.js'
    $personDepthManifestPath = Join-Path $Root 'app\backend\canvas-backend\_internal\canvas_core\person_depth_manifest.json'
    foreach ($requiredPath in @($canvasPath, $canvasListPath, $specialNodesPath, $topazPath, $personDepthManifestPath)) {
        if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
            throw "Staged web asset is missing: $requiredPath"
        }
        if ((Get-Item -LiteralPath $requiredPath).Length -le 0) {
            throw "Staged web asset is empty: $requiredPath"
        }
    }
    $canvasHtml = [IO.File]::ReadAllText($canvasPath)
    if (-not $canvasHtml.Contains("menuAdd('topazVideo')")) {
        throw 'Staged canvas is missing the Topaz create-menu entry.'
    }
    $h3SkillPath = Join-Path $Root 'app\skills\video-prompt-polish\minimax-h3\SKILL.md'
    $h3BaseGuidePath = Join-Path $Root 'app\skills\video-prompt-polish\minimax-h3\references\base-en.txt'
    $h3RefGuidePath = Join-Path $Root 'app\skills\video-prompt-polish\minimax-h3\references\ref-en.txt'
    $imagePromptSkillPath = Join-Path $Root 'app\skills\image-prompt-polish\SKILL.md'
    $imagePromptRegistryPath = Join-Path $Root 'app\skills\image-prompt-polish\registry.json'
    foreach ($requiredSkillPath in @($h3SkillPath, $h3BaseGuidePath, $h3RefGuidePath, $imagePromptSkillPath, $imagePromptRegistryPath)) {
        if (-not (Test-Path -LiteralPath $requiredSkillPath -PathType Leaf)) {
            throw "Staged prompt skill is missing: $requiredSkillPath"
        }
        if ((Get-Item -LiteralPath $requiredSkillPath).Length -le 0) {
            throw "Staged prompt skill is empty: $requiredSkillPath"
        }
    }
    if (-not $canvasHtml.Contains("canvas-topaz-node.js?v=$ExpectedVersion")) {
        throw "Staged canvas Topaz script cache version is not $ExpectedVersion."
    }
    $canvasListJs = [IO.File]::ReadAllText($canvasListPath)
    if (-not $canvasListJs.Contains("&v=$ExpectedVersion")) {
        throw "Staged canvas navigation cache version is not $ExpectedVersion."
    }
    $specialNodesJs = [IO.File]::ReadAllText($specialNodesPath)
    if (-not $specialNodesJs.Contains('maybeAutoInstallPersonDepth')) {
        throw 'Staged canvas special nodes are missing person-depth automatic installation.'
    }
    $personDepthManifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $personDepthManifestPath | ConvertFrom-Json
    if (-not $personDepthManifest.enabled -or @($personDepthManifest.packages).Count -lt 3) {
        throw 'Staged person-depth release manifest is disabled or incomplete.'
    }
}

New-Item -ItemType Directory -Force (Join-Path $projectRoot 'dist') | Out-Null
New-Item -ItemType Directory -Force $buildRoot | Out-Null

if (-not $SkipBackend) {
    Remove-BuildPath $backendDist $buildRoot
    Remove-BuildPath $backendWork $buildRoot
    $pythonExe = Join-Path $projectRoot 'python\python.exe'
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { $pythonExe = 'python' }
    & $pythonExe -m PyInstaller --noconfirm --clean --distpath $backendDist --workpath $backendWork (Join-Path $projectRoot 'canvas-backend.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
}

if (-not $SkipDesktop) {
    & npm run desktop:host-build
    if ($LASTEXITCODE -ne 0) { throw 'Tauri build failed.' }
}

$desktopExe = Join-Path $projectRoot 'src-tauri\target\release\SHIYIN-AI.exe'
$backendSource = Join-Path $backendDist 'canvas-backend'
if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf)) { throw "Desktop executable not found: $desktopExe" }
if (-not (Test-Path -LiteralPath (Join-Path $backendSource 'canvas-backend.exe') -PathType Leaf)) { throw "Sidecar not found: $backendSource" }

Remove-BuildPath $stageRoot (Join-Path $projectRoot 'dist')
New-Item -ItemType Directory -Force (Join-Path $stageRoot 'app\backend') | Out-Null
Copy-Item -LiteralPath $desktopExe -Destination (Join-Path $stageRoot 'SHIYIN AI.exe')
Copy-Item -LiteralPath $backendSource -Destination (Join-Path $stageRoot 'app\backend\canvas-backend') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'static') -Destination (Join-Path $stageRoot 'app\web') -Recurse
# 视频提示词 skill 由后端按 app_root/skills 读取，必须随安装包一起发布。
New-Item -ItemType Directory -Force (Join-Path $stageRoot 'app\skills\video-prompt-polish') | Out-Null
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'skills\video-prompt-polish') -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stageRoot 'app\skills\video-prompt-polish') -Recurse -Force
}
# 图片提示词 profile 同样由后端按 app_root/skills 读取，必须随安装包一起发布。
New-Item -ItemType Directory -Force (Join-Path $stageRoot 'app\skills\image-prompt-polish') | Out-Null
$imageSkillSource = Join-Path $projectRoot 'skills\image-prompt-polish'
$imageSkillDestination = Join-Path $stageRoot 'app\skills\image-prompt-polish'
& robocopy $imageSkillSource $imageSkillDestination /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -gt 7) { throw "Image prompt skill copy failed: exit $LASTEXITCODE" }
$global:LASTEXITCODE = 0
$connectors = Join-Path $stageRoot 'app\connectors'
New-Item -ItemType Directory -Force $connectors | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\chrome-local-asset-importer') -Destination (Join-Path $connectors 'chrome') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\photoshop-asset-connector') -Destination (Join-Path $connectors 'photoshop') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\blender-addon') -Destination (Join-Path $connectors 'blender') -Recurse
Get-ChildItem -LiteralPath $connectors -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @('.pyc', '.pyo') } |
    Remove-Item -Force
Get-ChildItem -LiteralPath $connectors -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending |
    Remove-Item -Recurse -Force
$licenses = Join-Path $stageRoot 'app\licenses'
New-Item -ItemType Directory -Force $licenses | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'third_party\dwpose') -Destination (Join-Path $licenses 'dwpose') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'VERSION') -Destination (Join-Path $stageRoot 'app\VERSION')
Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path $stageRoot 'LICENSE')
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $stageRoot 'README.md')

$webRoot = Join-Path $stageRoot 'app\web'
& node (Join-Path $PSScriptRoot 'stamp-web-cache-version.mjs') --root $webRoot --version $version | Out-Host
if ($LASTEXITCODE -ne 0) { throw 'Web cache-version stamping failed.' }
Assert-StagedWebAssets $stageRoot $version

if (-not $SkipRuntimeSmoke) {
    & (Join-Path $PSScriptRoot 'smoke-desktop.ps1') -Stage $stageRoot -Port $SmokePort -IdleSeconds 1 | Out-Host
    $runtimeSmokeSucceeded = $?
    if (-not $runtimeSmokeSucceeded) { throw 'Packaged desktop runtime smoke test failed.' }
    if ($DwposeSmokeInput) {
        $dwposeSmoke = Join-Path $PSScriptRoot 'smoke-dwpose-packaged.py'
        & python $dwposeSmoke --stage $stageRoot --input $DwposeSmokeInput --port ($SmokePort + 1) --output (Join-Path $projectRoot '.build\dwpose-packaged-output.png') | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Packaged DWPose cached-model smoke test failed.' }
        if (-not $SkipDwposeFreshDownloadSmoke) {
            & python $dwposeSmoke --stage $stageRoot --input $DwposeSmokeInput --port ($SmokePort + 2) --download-models --output (Join-Path $projectRoot '.build\dwpose-fresh-install-output.png') | Out-Host
            if ($LASTEXITCODE -ne 0) { throw 'Packaged DWPose fresh-install smoke test failed.' }
        }
    } else {
        Write-Warning 'DWPose real-person runtime smoke was skipped. Supply -DwposeSmokeInput before publishing an update.'
    }
    Assert-StagedWebAssets $stageRoot $version
}

New-Item -ItemType Directory -Force (Join-Path $projectRoot 'dist\installer') | Out-Null
if (Test-Path -LiteralPath $installerPath) { Remove-Item -LiteralPath $installerPath -Force }
$iscc = (Get-Command ISCC.exe -ErrorAction Stop).Source
& $iscc "/DMyAppVersion=$version" (Join-Path $projectRoot 'installer\shiyin_ai.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) { throw "Installer not found: $installerPath" }

Write-Host "Installer built: $installerPath"
