[CmdletBinding()]
param(
    [string]$AddonSource,
    [string[]]$BlenderPath,
    [string[]]$SearchRoot,
    [string]$ResultPath,
    [string]$ErrorLogPath,
    [switch]$DiscoverOnly,
    [switch]$CheckProcessOnly,
    [switch]$OnlySearchRoots,
    [switch]$SkipBlenderProcessCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Utf8BomLines {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Lines
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [System.IO.File]::WriteAllLines(
        $Path,
        $Lines,
        [System.Text.UTF8Encoding]::new($true)
    )
}

function Write-ResultLines {
    param([Parameter(Mandatory = $true)][string[]]$Lines)

    if (-not [string]::IsNullOrWhiteSpace($ResultPath)) {
        Write-Utf8BomLines -Path $ResultPath -Lines $Lines
    }
}

function Write-ErrorDetail {
    param([Parameter(Mandatory = $true)][string]$Message)

    if (-not [string]::IsNullOrWhiteSpace($ErrorLogPath)) {
        Write-Utf8BomLines -Path $ErrorLogPath -Lines @($Message)
    }
}

function ConvertTo-QuotedArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value.Contains('"')) {
        throw "命令参数不能包含双引号：$Value"
    }
    return '"' + $Value + '"'
}

function Add-BlenderCandidate {
    param(
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][System.Collections.ArrayList]$Candidates,
        [string]$Path
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    $clean = $Path.Trim().Trim('"')
    if ($clean.Contains(',')) {
        $clean = $clean.Split(',')[0].Trim().Trim('"')
    }
    if ((Test-Path -LiteralPath $clean -PathType Container)) {
        $clean = Join-Path $clean 'blender.exe'
    }
    if (Test-Path -LiteralPath $clean -PathType Leaf) {
        [void]$Candidates.Add([System.IO.Path]::GetFullPath($clean))
    }
}

function Get-BlenderInstallations {
    $candidates = [System.Collections.ArrayList]::new()
    foreach ($path in @($BlenderPath)) {
        Add-BlenderCandidate -Candidates $candidates -Path $path
    }

    if (-not $OnlySearchRoots) {
        $command = Get-Command 'blender.exe' -ErrorAction SilentlyContinue
        if ($command) {
            Add-BlenderCandidate -Candidates $candidates -Path $command.Source
        }

        $uninstallRoots = @(
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall',
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall'
        )
        foreach ($root in $uninstallRoots) {
            if (-not (Test-Path -LiteralPath $root)) {
                continue
            }
            Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | ForEach-Object {
                $entry = Get-ItemProperty -LiteralPath $_.PSPath -ErrorAction SilentlyContinue
                $displayName = if ($entry -and $entry.PSObject.Properties['DisplayName']) { [string]$entry.DisplayName } else { '' }
                if ($displayName -match '^Blender(?:\s|$)') {
                    $displayIcon = if ($entry.PSObject.Properties['DisplayIcon']) { [string]$entry.DisplayIcon } else { '' }
                    $installLocation = if ($entry.PSObject.Properties['InstallLocation']) { [string]$entry.InstallLocation } else { '' }
                    Add-BlenderCandidate -Candidates $candidates -Path $displayIcon
                    Add-BlenderCandidate -Candidates $candidates -Path $installLocation
                }
            }
        }
    }

    $roots = @($SearchRoot)
    if ($roots.Count -eq 0 -and -not $OnlySearchRoots) {
        $roots = @(Get-PSDrive -PSProvider FileSystem -ErrorAction SilentlyContinue | ForEach-Object { $_.Root })
    }
    foreach ($root in $roots) {
        if ([string]::IsNullOrWhiteSpace($root)) {
            continue
        }
        $rootPath = [System.IO.Path]::GetFullPath($root)
        foreach ($relative in @(
            'Program Files\Blender Foundation',
            'Program Files (x86)\Blender Foundation',
            'Program Files (x86)\Steam\steamapps\common'
        )) {
            $parent = Join-Path $rootPath $relative
            if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
                continue
            }
            Get-ChildItem -LiteralPath $parent -Directory -Filter 'Blender*' -ErrorAction SilentlyContinue | ForEach-Object {
                Add-BlenderCandidate -Candidates $candidates -Path (Join-Path $_.FullName 'blender.exe')
            }
        }
    }

    $seen = @{}
    $installations = @()
    foreach ($candidate in $candidates) {
        $key = $candidate.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            continue
        }
        $seen[$key] = $true
        $item = Get-Item -LiteralPath $candidate
        $versionText = [string]$item.VersionInfo.ProductVersion
        if ([string]::IsNullOrWhiteSpace($versionText)) {
            $versionText = Split-Path -Leaf (Split-Path -Parent $candidate)
        }
        $match = [regex]::Match($versionText, '(\d+)\.(\d+)')
        if (-not $match.Success) {
            $match = [regex]::Match((Split-Path -Leaf (Split-Path -Parent $candidate)), '(\d+)\.(\d+)')
        }
        if ($match.Success) {
            $major = [int]$match.Groups[1].Value
            $minor = [int]$match.Groups[2].Value
            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 6)) {
                continue
            }
        }
        $installations += [pscustomobject]@{
            Path = $candidate
            Version = if ([string]::IsNullOrWhiteSpace($versionText)) { '未知版本' } else { $versionText.Trim() }
        }
    }
    return @($installations | Sort-Object Version, Path -Unique)
}

trap {
    $errorText = ($_ | Out-String).Trim()
    $singleLine = ($errorText -replace '[\r\n]+', ' ').Trim()
    Write-ErrorDetail -Message $errorText
    Write-ResultLines -Lines @('status=error', ('message=' + $singleLine))
    [Console]::Error.WriteLine($errorText)
    exit 1
}

if (-not [string]::IsNullOrWhiteSpace($ResultPath) -and (Test-Path -LiteralPath $ResultPath -PathType Leaf)) {
    [System.IO.File]::Delete($ResultPath)
}
if (-not [string]::IsNullOrWhiteSpace($ErrorLogPath) -and (Test-Path -LiteralPath $ErrorLogPath -PathType Leaf)) {
    [System.IO.File]::Delete($ErrorLogPath)
}

if ($CheckProcessOnly) {
    if (Get-Process -Name 'blender' -ErrorAction SilentlyContinue) {
        throw 'Blender 正在运行。请保存工程并关闭所有 Blender 窗口后重试。'
    }
    Write-ResultLines -Lines @('status=closed')
    exit 0
}

$installations = @(Get-BlenderInstallations)
if ($DiscoverOnly) {
    $lines = @('status=' + $(if ($installations.Count -gt 0) { 'found' } else { 'not_found' }))
    $lines += 'count=' + $installations.Count
    foreach ($installation in $installations) {
        $lines += 'blender=' + $installation.Version + '|' + $installation.Path
    }
    Write-ResultLines -Lines $lines
    $lines | ForEach-Object { Write-Output $_ }
    exit 0
}

if (-not $SkipBlenderProcessCheck -and (Get-Process -Name 'blender' -ErrorAction SilentlyContinue)) {
    throw 'Blender 正在运行。请保存工程并关闭所有 Blender 窗口后重试插件安装。'
}
if ($installations.Count -eq 0) {
    throw '未检测到 Blender 3.6 或更高版本。插件包已保留，可在安装 Blender 后手动安装。'
}
if ([string]::IsNullOrWhiteSpace($AddonSource)) {
    $AddonSource = Join-Path $PSScriptRoot '..\shiyin_blender_bridge'
}
$AddonSource = [System.IO.Path]::GetFullPath($AddonSource.TrimEnd('\', '/'))
if (-not (Test-Path -LiteralPath $AddonSource -PathType Container)) {
    throw "Blender 插件源目录不存在：$AddonSource"
}
if (-not (Test-Path -LiteralPath (Join-Path $AddonSource '__init__.py') -PathType Leaf)) {
    throw "Blender 插件源目录缺少 __init__.py：$AddonSource"
}

$operationRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('shiyin-blender-addon-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $operationRoot | Out-Null
$pythonScript = Join-Path $operationRoot 'install_addon.py'
$pythonSource = @'
import addon_utils
import bpy
import shutil
import stat
import sys
import uuid
from pathlib import Path

args = sys.argv[sys.argv.index("--") + 1 :]
source = Path(args[0]).resolve()
module = source.name
addons_root = Path(bpy.utils.user_resource("SCRIPTS", path="addons", create=True)).resolve()
target = addons_root / module
if target.parent.resolve() != addons_root:
    raise RuntimeError("Unsafe Blender add-on destination")
reparse_mask = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
target_is_reparse_point = False
if target.exists():
    try:
        target_is_reparse_point = bool(
            reparse_mask and (target.lstat().st_file_attributes & reparse_mask)
        )
    except (AttributeError, OSError):
        target_is_reparse_point = target.is_symlink()
if target_is_reparse_point:
    raise RuntimeError("Refusing to replace a linked Blender add-on")

was_enabled = bool(addon_utils.check(module)[1])
if was_enabled:
    bpy.ops.preferences.addon_disable(module=module)

operation_id = uuid.uuid4().hex
stage = addons_root / (".%s.install-%s" % (module, operation_id))
backup = addons_root / (".%s.backup-%s" % (module, operation_id))
old_moved = False
committed = False
try:
    shutil.copytree(source, stage)
    if target.exists():
        target.rename(backup)
        old_moved = True
    stage.rename(target)
    committed = True
    addon_utils.modules_refresh()
    bpy.ops.preferences.addon_enable(module=module)
    bpy.ops.wm.save_userpref()
    if not addon_utils.check(module)[1]:
        raise RuntimeError("Blender reported that the add-on is not enabled")
    if backup.exists():
        shutil.rmtree(backup)
        old_moved = False
except Exception:
    if committed and target.exists():
        shutil.rmtree(target)
    if old_moved and backup.exists():
        backup.rename(target)
        addon_utils.modules_refresh()
        if was_enabled:
            bpy.ops.preferences.addon_enable(module=module)
            bpy.ops.wm.save_userpref()
    raise
finally:
    if stage.exists():
        shutil.rmtree(stage)

print("SHIYIN_ADDON_ENABLED=True")
print("SHIYIN_ADDON_MODULE=" + module)
print("SHIYIN_ADDON_PATH=" + str(target))
print("SHIYIN_BLENDER_VERSION=" + bpy.app.version_string)
'@
[System.IO.File]::WriteAllText($pythonScript, $pythonSource, [System.Text.UTF8Encoding]::new($false))

$installed = @()
try {
    foreach ($installation in $installations) {
        $stdoutPath = Join-Path $operationRoot ([Guid]::NewGuid().ToString('N') + '.stdout.log')
        $stderrPath = Join-Path $operationRoot ([Guid]::NewGuid().ToString('N') + '.stderr.log')
        $arguments = '--background --python ' +
            (ConvertTo-QuotedArgument -Value $pythonScript) + ' -- ' +
            (ConvertTo-QuotedArgument -Value $AddonSource)
        $process = Start-Process `
            -FilePath $installation.Path `
            -ArgumentList $arguments `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -Wait `
            -PassThru
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { [System.IO.File]::ReadAllText($stdoutPath) } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { [System.IO.File]::ReadAllText($stderrPath) } else { '' }
        if ($process.ExitCode -ne 0 -or $stdout -notmatch 'SHIYIN_ADDON_ENABLED=True') {
            throw "Blender 插件安装失败：$($installation.Path)`r`n$stdout`r`n$stderr"
        }
        $installed += 'installed=' + $installation.Version + '|' + $installation.Path
    }
} finally {
    if (Test-Path -LiteralPath $operationRoot) {
        Remove-Item -LiteralPath $operationRoot -Recurse -Force
    }
}

$resultLines = @('status=installed', ('count=' + $installed.Count)) + $installed
Write-ResultLines -Lines $resultLines
$resultLines | ForEach-Object { Write-Output $_ }
