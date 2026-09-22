param(
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$labRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$projectRoot = (Resolve-Path (Join-Path $labRoot '..\..')).Path
$version = (& node -p "require(process.argv[1]).version" (Join-Path $labRoot 'package.json')).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid version: $version" }

if (-not $SkipBuild) {
    Push-Location $labRoot
    $tauriCli = Join-Path $projectRoot 'node_modules\@tauri-apps\cli\tauri.js'
    & node $tauriCli build --no-bundle
    $buildExitCode = $LASTEXITCODE
    Pop-Location
    if ($buildExitCode -ne 0) { throw 'Tauri release build failed.' }
}

$exe = Join-Path $labRoot 'src-tauri\target\release\SHIYIN-Video-Depth-Lab.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Desktop executable not found: $exe" }
$stage = Join-Path $projectRoot '.build\depth-batch-installer-stage'
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $stage 'SHIYIN-Depth-Batch.exe')
foreach ($directory in @('worker', 'worker-overlays')) {
    Copy-Item -LiteralPath (Join-Path $labRoot $directory) -Destination (Join-Path $stage $directory) -Recurse
}
New-Item -ItemType Directory -Force (Join-Path $stage 'scripts') | Out-Null
Copy-Item -LiteralPath (Join-Path $labRoot 'scripts\prepare-components.ps1') -Destination (Join-Path $stage 'scripts')
foreach ($file in @('runtime-manifest.json', 'model-download-manifest.json', 'PORTABLE.md')) {
    Copy-Item -LiteralPath (Join-Path $labRoot $file) -Destination $stage
}

$iscc = (Get-Command ISCC.exe -ErrorAction Stop).Source
& $iscc "/DAppVersion=$version" "/DSourceRoot=$stage" "/DOutputRoot=$projectRoot\dist\installer" "$labRoot\installer\SHIYIN-Depth-Batch.iss"
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup build failed.' }
Get-FileHash -LiteralPath (Join-Path $projectRoot "dist\installer\SHIYIN-Depth-Batch-Setup-$version.exe") -Algorithm SHA256
