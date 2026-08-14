[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )

    if (-not $Condition) {
        throw "断言失败：$Message"
    }
}

function Assert-Utf8Bom {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    Assert-True ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) `
        '安装脚本必须使用 UTF-8 BOM，避免 Windows PowerShell 5.1 误解析中文'
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$installer = Join-Path $projectRoot 'tools\blender-addon\windows\Install-SHIYINBlenderAddon.ps1'
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('shiyin-blender-installer-test-' + [Guid]::NewGuid().ToString('N'))
$fakeBlender = Join-Path $testRoot 'Program Files\Blender Foundation\Blender 5.2\blender.exe'
$resultPath = Join-Path $testRoot 'discovery.txt'
$errorPath = Join-Path $testRoot 'error.txt'
$windowsPowerShell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

try {
    Assert-Utf8Bom $installer
    New-Item -ItemType Directory -Path (Split-Path -Parent $fakeBlender) -Force | Out-Null
    [System.IO.File]::WriteAllBytes($fakeBlender, [byte[]](0x4D, 0x5A))

    & $windowsPowerShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer `
        -DiscoverOnly -OnlySearchRoots -SearchRoot $testRoot -ResultPath $resultPath
    Assert-True ($LASTEXITCODE -eq 0) 'Windows PowerShell 5.1 发现流程应成功'
    $result = [System.IO.File]::ReadAllText($resultPath, [System.Text.Encoding]::UTF8)
    Assert-True ($result -match 'status=found') '应发现伪造的 Blender 5.2 路径'
    Assert-True ($result -match [regex]::Escape($fakeBlender)) '发现结果应包含完整 blender.exe 路径'

    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $failureOutput = & $windowsPowerShell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $installer `
        -OnlySearchRoots -SearchRoot $testRoot -AddonSource (Join-Path $testRoot 'missing-addon') `
        -SkipBlenderProcessCheck -ErrorLogPath $errorPath 2>&1
    $failureExitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    Assert-True ($failureExitCode -ne 0) '缺少插件源目录时必须失败'
    Assert-True (Test-Path -LiteralPath $errorPath -PathType Leaf) '失败时必须写入错误日志'
    $errorText = [System.IO.File]::ReadAllText($errorPath, [System.Text.Encoding]::UTF8)
    Assert-True ($errorText -match '插件源目录不存在') '错误日志应包含可操作原因'
    Assert-True ([bool](($failureOutput -join "`n") -match '插件源目录不存在')) '标准错误应保留真实失败原因'

    Write-Output 'SHIYIN Blender 插件安装脚本测试通过。'
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
