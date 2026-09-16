param(
    [string]$DataDir = '',
    [int]$Port = 0,
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$bundledPython = Join-Path $projectRoot 'python\python.exe'

if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
    $pythonExe = $bundledPython
} elseif ($env:CANVAS_PYTHON_EXECUTABLE) {
    $pythonExe = [IO.Path]::GetFullPath($env:CANVAS_PYTHON_EXECUTABLE)
    if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) {
        throw "CANVAS_PYTHON_EXECUTABLE 指向的 Python 不存在：$pythonExe"
    }
} else {
    $pythonCommand = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $pythonCommand) {
        throw '源码运行缺少 Python；请安装 Python 并加入 PATH，或设置 CANVAS_PYTHON_EXECUTABLE'
    }
    $pythonExe = $pythonCommand.Source
}

& $pythonExe -c 'import fastapi, uvicorn'
if ($LASTEXITCODE -ne 0) {
    throw "Python 缺少源码后端基础依赖：$pythonExe"
}

if (-not $DataDir) {
    $baseDir = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { [IO.Path]::GetTempPath() }
    $DataDir = Join-Path $baseDir 'SHIYIN-AI\source-dev'
}
$dataRoot = [IO.Path]::GetFullPath($DataDir)
$configDir = Join-Path $dataRoot 'config'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$configPath = Join-Path $configDir 'app.json'

function Test-DevPortAvailable([int]$Candidate) {
    foreach ($address in @('127.0.0.1', '0.0.0.0')) {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Parse($address), $Candidate)
        try {
            $listener.Start()
        } catch {
            return $false
        } finally {
            $listener.Stop()
        }
    }
    return $true
}

if (Test-Path -LiteralPath $configPath -PathType Leaf) {
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
} else {
    $config = [pscustomobject]@{ host = '127.0.0.1'; lan_enabled = $false; close_behavior = 'exit' }
}
$existingPort = $config.PSObject.Properties['port']

if ($Port) {
    if ($Port -lt 1 -or $Port -gt 65535 -or -not (Test-DevPortAvailable $Port)) {
        throw "源码开发端口不可用：$Port"
    }
    $chosenPort = $Port
} else {
    $preferredPort = if ($existingPort) { [int]$config.port } else { 3000 }
    $chosenPort = @($preferredPort) + @(13170..13220) |
        Where-Object { $_ -ge 1 -and $_ -le 65535 -and (Test-DevPortAvailable $_) } |
        Select-Object -First 1
    if (-not $chosenPort) { throw '没有可用的源码开发端口（3000、13170-13220）' }
}

if (-not $existingPort -or [int]$config.port -ne $chosenPort) {
    if ($existingPort) { $config.port = [int]$chosenPort }
    else { $config | Add-Member -NotePropertyName port -NotePropertyValue ([int]$chosenPort) }
    $json = $config | ConvertTo-Json -Depth 20
    [IO.File]::WriteAllText($configPath, $json + "`n", [Text.UTF8Encoding]::new($false))
}

$env:CANVAS_DEV_ROOT = $projectRoot
$env:CANVAS_DATA_DIR = $dataRoot
$env:CANVAS_PYTHON_EXECUTABLE = $pythonExe
Write-Host "源码桌面运行：Python=$pythonExe；端口=$chosenPort；数据=$dataRoot"
if ($PrepareOnly) { return }

& npm run css:build
if ($LASTEXITCODE -ne 0) { throw 'CSS 构建失败' }
& npm run canvas:engine-build
if ($LASTEXITCODE -ne 0) { throw '画布引擎构建失败' }

& (Join-Path $projectRoot 'node_modules\.bin\tauri.cmd') dev
if ($LASTEXITCODE -ne 0) { throw 'Tauri 源码开发宿主启动失败' }
