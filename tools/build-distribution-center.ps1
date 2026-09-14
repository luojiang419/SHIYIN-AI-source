$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$distributionBuild = Join-Path $projectRoot ('dist/distribution-builds/' + (Get-Date -Format 'yyyyMMddHHmmss'))
python -m PyInstaller --noconfirm --windowed --onedir --name SHIYIN-Distribution-Center --distpath $distributionBuild --workpath .build/distribution --specpath .build --paths $projectRoot --add-data "$projectRoot/distribution/panel.html;distribution" --add-data "$projectRoot/distribution/panel.css;distribution" --add-data "$projectRoot/distribution/panel.js;distribution" --hidden-import zeroconf --hidden-import webview.platforms.winforms --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 "$projectRoot/distribution/entry.py"
if ($LASTEXITCODE -ne 0) { throw 'Distribution center build failed' }
$resultPath = Join-Path $distributionBuild 'SHIYIN-Distribution-Center'
[IO.File]::WriteAllText((Join-Path $projectRoot 'dist/distribution-latest.txt'), $resultPath, [Text.UTF8Encoding]::new($false))
Write-Host "Control panel: $resultPath/SHIYIN-Distribution-Center.exe"
