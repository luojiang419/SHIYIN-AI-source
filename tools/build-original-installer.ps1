param(
    [switch]$SkipBackend,
    [switch]$SkipDesktop,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$originalRoot = 'E:\Infinite-Canvas-main'
if (-not (Test-Path (Join-Path $originalRoot 'main.py'))) { throw "原始版本目录不存在：$originalRoot" }
Set-Location $projectRoot

$originalVersionRaw = (Get-Content (Join-Path $originalRoot 'VERSION') -Raw).Trim()
$versionParts = $originalVersionRaw -split '\.'
if ($versionParts.Count -ne 3) { $versionParts = @('2026','6','11') }
$version = (($versionParts | ForEach-Object { [int]$_ }) -join '.')
$buildRoot = Join-Path $projectRoot '.build\original-installer'
$sourceRoot = Join-Path $buildRoot 'source'
$backendDist = Join-Path $buildRoot 'backend-dist'
$backendWork = Join-Path $buildRoot 'backend-work'
$stageRoot = Join-Path $projectRoot 'dist\original-installer-stage'
$tauriRoot = Join-Path $buildRoot 'tauri-project'
$installerPath = Join-Path $projectRoot "dist\installer\ShiYingAI-原版画布-Setup-$version.exe"

if (Test-Path $buildRoot) {
    if (-not $SkipDesktop) {
        $oldNodeModules = Join-Path $buildRoot 'node_modules'
        if (Test-Path $oldNodeModules) {
            try { [IO.Directory]::Delete($oldNodeModules, $false) } catch { }
        }
        foreach ($path in @($tauriRoot, (Join-Path $buildRoot 'desktop-placeholder'), (Join-Path $buildRoot 'package.json'))) {
            if (Test-Path $path) { Remove-Item $path -Recurse -Force }
        }
    }
    if (-not $SkipBackend) {
        foreach ($path in @($backendDist, $backendWork)) {
            if (Test-Path $path) { Remove-Item $path -Recurse -Force }
        }
    }
    if (Test-Path $sourceRoot) { Remove-Item $sourceRoot -Recurse -Force }
}
if (Test-Path $stageRoot) { Remove-Item $stageRoot -Recurse -Force }
New-Item -ItemType Directory -Force $sourceRoot, $stageRoot, (Join-Path $projectRoot 'dist\installer') | Out-Null

$mainText = [IO.File]::ReadAllText((Join-Path $originalRoot 'main.py'))
$mainText = $mainText -replace 'BASE_DIR = os\.path\.dirname\(os\.path\.abspath\(__file__\)\)', 'BASE_DIR = os.path.abspath(os.getenv("CANVAS_APP_ROOT") or os.path.dirname(os.path.abspath(__file__)))'
$mainText = $mainText -replace '<title>AI Studio</title>', '<title>ShiYingAI-原版画布</title>'
[IO.File]::WriteAllText((Join-Path $sourceRoot 'main.py'), $mainText, [Text.UTF8Encoding]::new($false))
Copy-Item (Join-Path $PSScriptRoot 'original-backend-entry.py') (Join-Path $sourceRoot 'original-backend-entry.py')
Copy-Item (Join-Path $PSScriptRoot 'original-backend.spec') (Join-Path $sourceRoot 'original-backend.spec')

if (-not $SkipBackend) {
    Push-Location $sourceRoot
    try {
        & python -m PyInstaller --noconfirm --clean --distpath $backendDist --workpath $backendWork 'original-backend.spec'
        if ($LASTEXITCODE -ne 0) { throw '原始版 PyInstaller 构建失败。' }
    } finally { Pop-Location }
}

if (-not $SkipDesktop) {
    Copy-Item (Join-Path $projectRoot 'src-tauri') $tauriRoot -Recurse
    Copy-Item (Join-Path $projectRoot 'desktop-placeholder') (Join-Path $buildRoot 'desktop-placeholder') -Recurse
    Copy-Item (Join-Path $projectRoot 'package.json') (Join-Path $buildRoot 'package.json')
    New-Item -ItemType Junction -Path (Join-Path $buildRoot 'node_modules') -Target (Join-Path $projectRoot 'node_modules') -Force | Out-Null
    $configPath = Join-Path $tauriRoot 'tauri.conf.json'
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $config.productName = 'ShiYingAI-原版画布'
    $config.version = $version
    $config.identifier = 'com.shiyingai.originalcanvas.desktop'
    $configJson = $config | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($configPath, $configJson, [Text.UTF8Encoding]::new($false))
    $cargoPath = Join-Path $tauriRoot 'Cargo.toml'
    $cargoText = [IO.File]::ReadAllText($cargoPath)
    $cargoText = $cargoText -replace '(?m)^version = "[^"]+"', "version = `"$version`""
    [IO.File]::WriteAllText($cargoPath, $cargoText, [Text.UTF8Encoding]::new($false))
    $libPath = Join-Path $tauriRoot 'src\lib.rs'
    $lib = [IO.File]::ReadAllText($libPath)
    $lib = $lib -replace 'SHIYIN AI', 'ShiYingAI-原版画布'
    $lib = $lib -replace '3000', '3001'
    $lib = $lib -replace '/api/health', '/api/app-info'
    $lib = $lib -replace 'const APP_DISPLAY_NAME: &str = concat!\("ShiYingAI-原版画布 V", env!\("CARGO_PKG_VERSION"\)\);', 'const APP_DISPLAY_NAME: &str = "ShiYingAI-原版画布";'
    $lib = $lib -replace 'http://127\.0\.0\.1:\{\}/api/auth/bootstrap\?token=\{token\}', 'http://127.0.0.1:{}/'
    [IO.File]::WriteAllText($libPath, $lib, [Text.UTF8Encoding]::new($false))
    $updaterPath = Join-Path $tauriRoot 'src\updater.rs'
    $updater = [IO.File]::ReadAllText($updaterPath)
    $updater = $updater -replace 'SHIYIN AI', 'ShiYingAI-原版画布'
    [IO.File]::WriteAllText($updaterPath, $updater, [Text.UTF8Encoding]::new($false))
    Push-Location $buildRoot
    try {
        & npx tauri build --no-bundle --config (Join-Path $tauriRoot 'tauri.conf.json')
        if ($LASTEXITCODE -ne 0) { throw '原始版 Tauri 桌面壳构建失败。' }
    } finally { Pop-Location }
}

$desktopExe = Join-Path $tauriRoot 'target\release\SHIYIN-AI.exe'
$backendSource = Join-Path $backendDist 'canvas-backend'
if (-not (Test-Path (Join-Path $backendSource 'canvas-backend.exe'))) { throw "后端 sidecar 不存在：$backendSource" }
if (-not (Test-Path $desktopExe)) { throw "桌面壳不存在：$desktopExe" }

Copy-Item $desktopExe (Join-Path $stageRoot 'ShiYingAI-原版画布.exe')
New-Item -ItemType Directory -Force (Join-Path $stageRoot 'app\backend'), (Join-Path $stageRoot 'app\assets'), (Join-Path $stageRoot 'app\output'), (Join-Path $stageRoot 'app\data'), (Join-Path $stageRoot 'app\API') | Out-Null
Copy-Item $backendSource (Join-Path $stageRoot 'app\backend\canvas-backend') -Recurse
Copy-Item (Join-Path $sourceRoot 'main.py') (Join-Path $stageRoot 'app\main.py')
Copy-Item (Join-Path $originalRoot 'static') (Join-Path $stageRoot 'app\static') -Recurse
$indexPath = Join-Path $stageRoot 'app\static\index.html'
$indexText = [IO.File]::ReadAllText($indexPath)
$indexText = $indexText -replace '<title>AI Studio</title>', '<title>ShiYingAI-原版画布</title>'
[IO.File]::WriteAllText($indexPath, $indexText, [Text.UTF8Encoding]::new($false))
Copy-Item (Join-Path $originalRoot 'workflows') (Join-Path $stageRoot 'app\workflows') -Recurse
Copy-Item (Join-Path $originalRoot 'LICENSE') (Join-Path $stageRoot 'LICENSE')
Copy-Item (Join-Path $originalRoot 'README.md') (Join-Path $stageRoot 'README.md')
[IO.File]::WriteAllText((Join-Path $stageRoot 'app\VERSION'), $originalVersionRaw + "`n", [Text.UTF8Encoding]::new($false))

if (-not $SkipInstaller) {
    if (Test-Path $installerPath) { Remove-Item $installerPath -Force }
    & ISCC.exe "/DMyAppVersion=$version" (Join-Path $projectRoot 'installer\shiyingai_original.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup 构建失败。' }
    if (-not (Test-Path $installerPath)) { throw "安装包未生成：$installerPath" }
}

Write-Host "原始版安装包已生成：$installerPath"
