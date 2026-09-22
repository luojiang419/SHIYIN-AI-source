$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$distributionBuild = Join-Path $projectRoot ('dist/distribution-builds/' + (Get-Date -Format 'yyyyMMddHHmmss'))
python -m PyInstaller --noconfirm --windowed --onedir --name SHIYIN-Distribution-Center --distpath $distributionBuild --workpath .build/distribution --specpath .build --paths $projectRoot --add-data "$projectRoot/distribution/panel.html;distribution" --add-data "$projectRoot/distribution/panel.css;distribution" --add-data "$projectRoot/distribution/panel.js;distribution" --add-data "$projectRoot/distribution/assets;distribution/assets" --icon "$projectRoot/distribution/assets/distribution.ico" --hidden-import zeroconf --hidden-import webview.platforms.winforms --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 "$projectRoot/distribution/entry.py"
if ($LASTEXITCODE -ne 0) { throw 'Distribution center build failed' }
$resultPath = Join-Path $distributionBuild 'SHIYIN-Distribution-Center'
[IO.File]::WriteAllText((Join-Path $projectRoot 'dist/distribution-latest.txt'), $resultPath, [Text.UTF8Encoding]::new($false))
Write-Host "Control panel: $resultPath/SHIYIN-Distribution-Center.exe"
foreach ($cacheName in @('.build', '.codex-tmp')) {
    $cachePath = [IO.Path]::GetFullPath((Join-Path $projectRoot $cacheName))
    if (-not $cachePath.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Cache path is outside the workspace' }
    if (Test-Path -LiteralPath $cachePath) {
        $cacheBytes = (Get-ChildItem -LiteralPath $cachePath -Recurse -File -ErrorAction Stop | Measure-Object -Property Length -Sum).Sum
        Write-Host ("Cache {0}: {1:N2} GiB" -f $cacheName, ($cacheBytes / 1GB))
        if ($cacheBytes -gt 20GB) {
            Remove-Item -LiteralPath $cachePath -Recurse -Force -ErrorAction Stop
            Write-Host "Cleared over-limit cache: $cacheName"
        }
    }
}
