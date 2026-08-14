param(
    [switch]$IncrementVersion,
    [switch]$SkipBackend,
    [switch]$SkipDesktop,
    [switch]$SkipRuntimeSmoke,
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
$connectors = Join-Path $stageRoot 'app\connectors'
New-Item -ItemType Directory -Force $connectors | Out-Null
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\chrome-local-asset-importer') -Destination (Join-Path $connectors 'chrome') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\photoshop-asset-connector') -Destination (Join-Path $connectors 'photoshop') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'tools\blender-addon') -Destination (Join-Path $connectors 'blender') -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'VERSION') -Destination (Join-Path $stageRoot 'app\VERSION')
Copy-Item -LiteralPath (Join-Path $projectRoot 'LICENSE') -Destination (Join-Path $stageRoot 'LICENSE')
Copy-Item -LiteralPath (Join-Path $projectRoot 'README.md') -Destination (Join-Path $stageRoot 'README.md')

$utf8 = [Text.UTF8Encoding]::new($false)
Get-ChildItem -LiteralPath (Join-Path $stageRoot 'app\web') -Recurse -File -Include *.html,*.js | ForEach-Object {
    $content = [IO.File]::ReadAllText($_.FullName)
    $updated = [regex]::Replace($content, '\?v=[0-9A-Za-z._-]+', "?v=$version")
    if ($updated -ne $content) { [IO.File]::WriteAllText($_.FullName, $updated, $utf8) }
}

if (-not $SkipRuntimeSmoke) {
    & (Join-Path $PSScriptRoot 'smoke-desktop.ps1') -Stage $stageRoot -Port $SmokePort -IdleSeconds 1 | Out-Host
    $runtimeSmokeSucceeded = $?
    if (-not $runtimeSmokeSucceeded) { throw 'Packaged desktop runtime smoke test failed.' }
}

New-Item -ItemType Directory -Force (Join-Path $projectRoot 'dist\installer') | Out-Null
if (Test-Path -LiteralPath $installerPath) { Remove-Item -LiteralPath $installerPath -Force }
$iscc = (Get-Command ISCC.exe -ErrorAction Stop).Source
& $iscc "/DMyAppVersion=$version" (Join-Path $projectRoot 'installer\shiyin_ai.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) { throw "Installer not found: $installerPath" }

Write-Host "Installer built: $installerPath"
