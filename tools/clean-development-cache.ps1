param()

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targets = @(
    (Join-Path $projectRoot ".npm-cache"),
    (Join-Path $projectRoot ".pytest_cache"),
    (Join-Path $projectRoot ".build\sidecar-smoke-data"),
    (Join-Path $projectRoot ".build\kling-backend-smoke"),
    (Join-Path $projectRoot ".build\kling-backend-smoke.stdout.log"),
    (Join-Path $projectRoot ".build\kling-backend-smoke.stderr.log"),
    (Join-Path $projectRoot ".build\dwpose-ui-repro"),
    (Join-Path $projectRoot ".build\installer"),
    (Join-Path $projectRoot "dist\installer-stage"),
    (Join-Path $projectRoot ".build\desktop-smoke"),
    (Join-Path $projectRoot ".build\ecommerce-params-browser"),
    (Join-Path $projectRoot ".build\vision-live-smoke-data"),
    (Join-Path $projectRoot ".build\works-layout-profile"),
    (Join-Path $projectRoot ".build\compact-layout-chrome-profile"),
    (Join-Path $projectRoot ".build\feature-browser-smoke"),
    (Join-Path $projectRoot ".build\close-behavior-smoke"),
    (Join-Path $projectRoot "src-tauri\target\debug"),
    (Join-Path $projectRoot "src-tauri\target\release\data"),
    (Join-Path $projectRoot "__pycache__"),
    (Join-Path $projectRoot "canvas_core\__pycache__"),
    (Join-Path $projectRoot "tests\__pycache__"),
    (Join-Path $projectRoot "tools\__pycache__")
)
$browserSmokeState = Join-Path $projectRoot ".build\browser-smoke-state.json"
$targets += $browserSmokeState
$browserSmokeResultFiles = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -File -Filter "browser-smoke-*.json" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $browserSmokeResultFiles
$browserSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "browser-smoke-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $browserSmokeDirs
$ecommerceSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "ecommerce-browser-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $ecommerceSmokeDirs
$ecommerceSmokeResultFiles = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -File -Filter "ecommerce-browser-*.json" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $ecommerceSmokeResultFiles
$artifactBrowserSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "artifact-browser-smoke-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $artifactBrowserSmokeDirs
$browserValidationDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "browser-validation-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $browserValidationDirs
$previewNavigationProfileDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "preview-nav-profile*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $previewNavigationProfileDirs
$themeValidationDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "theme-validation-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $themeValidationDirs
$resultPreviewThemeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "result-preview-theme-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $resultPreviewThemeDirs
$lightThemeStyleCheckDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "light-theme-style-check-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $lightThemeStyleCheckDirs
$canvasPageDiagnosticDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "canvas-page-diagnostic*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $canvasPageDiagnosticDirs
$tryOnLayoutValidationDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "tryon-layout-validation-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $tryOnLayoutValidationDirs
$tryOnDressupValidationDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "tryon-dressup-validation-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $tryOnDressupValidationDirs
$dragStuckSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "drag-stuck-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $dragStuckSmokeDirs
$dragStuckSmokeResults = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -File -Filter "drag-stuck-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $dragStuckSmokeResults
$dragDropSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "drag-drop-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $dragDropSmokeDirs
$dragDropSmokeResults = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -File -Filter "drag-drop-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $dragDropSmokeResults
$poseBackdropSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "pose-backdrop-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $poseBackdropSmokeDirs
$poseBackdropSmokeResults = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -File -Filter "pose-backdrop-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $poseBackdropSmokeResults
$releaseSourceStages = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "release-source-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $releaseSourceStages
$installerProgressSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "installer-progress-smoke-*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $installerProgressSmokeDirs
$installerUpdaterSmokeDirs = @(Get-ChildItem -LiteralPath (Join-Path $projectRoot ".build") -Directory -Filter "installer-updater-e2e*" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
$targets += $installerUpdaterSmokeDirs
$prefix = $projectRoot.TrimEnd('\') + '\'
foreach ($target in $targets) {
    $fullPath = [System.IO.Path]::GetFullPath($target)
    if (-not $fullPath.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean path outside project root: $fullPath"
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
        Write-Host "Removed $fullPath"
    }
}

$cacheRoots = @(
    (Join-Path $projectRoot ".build"),
    (Join-Path $projectRoot "node_modules"),
    (Join-Path $projectRoot "src-tauri\target")
)
$remaining = 0L
foreach ($cacheRoot in $cacheRoots) {
    if (Test-Path -LiteralPath $cacheRoot) {
        $size = (Get-ChildItem -LiteralPath $cacheRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        if ($size) { $remaining += [long]$size }
    }
}
if ($remaining -gt 20GB) { throw "Reusable development caches exceed 20 GiB" }
Write-Host ("Reusable development cache: {0:N2} MiB" -f ($remaining / 1MB))
