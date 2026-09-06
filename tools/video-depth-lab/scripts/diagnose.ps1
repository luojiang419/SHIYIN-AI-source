$ErrorActionPreference = 'Stop'
$LabRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $LabRoot 'runtime\venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    throw '未找到 runtime/venv，请先运行 setup.ps1'
}
& $Python (Join-Path $LabRoot 'worker\main.py') status
exit $LASTEXITCODE
