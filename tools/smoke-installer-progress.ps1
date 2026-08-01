param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid target version: $Version" }
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$buildRoot = (Resolve-Path (Join-Path $projectRoot '.build')).Path
$stage = Join-Path $buildRoot "installer-progress-smoke-$Version"
$stagePrefix = $buildRoot.TrimEnd('\') + '\'
if (-not $stage.StartsWith($stagePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Invalid installer progress test stage path.'
}

if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$installRoot = Join-Path $stage 'installed'
$logPath = Join-Path $stage 'installer.log'
$progressPath = Join-Path $stage 'installer-progress.txt'
$success = $false
$smokeShortcutPaths = @(
    (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::CommonPrograms)) 'SHIYIN AI.lnk'),
    (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::Programs)) 'SHIYIN AI.lnk'),
    (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::CommonDesktopDirectory)) 'SHIYIN AI.lnk'),
    (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)) 'SHIYIN AI.lnk')
) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique

try {
    $arguments = @(
        '/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCANCEL',
        '/CLOSEAPPLICATIONS', '/FORCECLOSEAPPLICATIONS',
        ('/DIR="' + $installRoot + '"'),
        ('/LOG="' + $logPath + '"'),
        ('/UPDATEPROGRESS="' + $progressPath + '"')
    )
    $process = Start-Process -FilePath $installer -ArgumentList $arguments -PassThru
    $samples = [System.Collections.Generic.List[string]]::new()
    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    while (-not $process.HasExited -and [DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $progressPath) {
            $raw = (Get-Content -Raw -LiteralPath $progressPath).Trim()
            if ($raw -match '^\d+\|\d+$' -and ($samples.Count -eq 0 -or $samples[$samples.Count - 1] -ne $raw)) {
                $samples.Add($raw)
            }
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force
        throw 'Installer progress smoke test timed out.'
    }
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "Installer exited with code $($process.ExitCode)." }
    if (Test-Path -LiteralPath $progressPath) {
        $finalRaw = (Get-Content -Raw -LiteralPath $progressPath).Trim()
        if ($finalRaw -match '^\d+\|\d+$' -and ($samples.Count -eq 0 -or $samples[$samples.Count - 1] -ne $finalRaw)) {
            $samples.Add($finalRaw)
        }
    }

    $pairs = @($samples | ForEach-Object {
        $parts = $_ -split '\|'
        [pscustomobject]@{ current = [uint64]$parts[0]; total = [uint64]$parts[1] }
    })
    $percents = @($pairs | Where-Object { $_.total -gt 0 } | ForEach-Object {
        [math]::Floor($_.current * 100 / $_.total)
    })
    if ($samples.Count -lt 2 -or @($percents | Select-Object -Unique).Count -lt 2) {
        throw "Installer did not report changing realtime progress. Samples: $($samples -join ', ')"
    }
    $last = $pairs[$pairs.Count - 1]
    if ($last.current -ne $last.total) {
        throw "Installer progress did not finish at 100%: $($last.current)|$($last.total)"
    }
    $installedVersionPath = Join-Path $installRoot 'app\VERSION'
    if (-not (Test-Path -LiteralPath $installedVersionPath)) { throw 'Installed VERSION file was not found.' }
    if ((Get-Content -Raw -LiteralPath $installedVersionPath).Trim() -ne $Version) {
        throw 'Installed VERSION does not match the requested version.'
    }
    $installedExe = Join-Path $installRoot 'SHIYIN AI.exe'
    $commonPrograms = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonPrograms)
    $commonShortcutPath = Join-Path $commonPrograms 'SHIYIN AI.lnk'
    if (-not (Test-Path -LiteralPath $commonShortcutPath -PathType Leaf)) {
        throw 'Common Start Menu shortcut was not created.'
    }
    $commonShortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($commonShortcutPath)
    if ($commonShortcut.TargetPath -ne $installedExe) {
        throw "Common Start Menu shortcut target mismatch: $($commonShortcut.TargetPath)"
    }
    $success = $true
    [pscustomobject]@{
        installer = [IO.Path]::GetFileName($installer)
        target_version = $Version
        sample_count = $samples.Count
        distinct_percent_count = @($percents | Select-Object -Unique).Count
        first_sample = $samples[0]
        last_sample = $samples[$samples.Count - 1]
        realtime_progress = $true
        start_menu_shortcut = $true
    } | ConvertTo-Json -Compress
}
finally {
    $installedExe = Join-Path $installRoot 'SHIYIN AI.exe'
    foreach ($shortcutPath in $smokeShortcutPaths) {
        if (-not (Test-Path -LiteralPath $shortcutPath -PathType Leaf)) { continue }
        try {
            $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
            if ($shortcut.TargetPath -eq $installedExe) {
                Remove-Item -LiteralPath $shortcutPath -Force
            }
        }
        catch {
            # Keep the smoke-test artifact for diagnosis when shortcut inspection fails.
        }
    }
    if ($success -and (Test-Path -LiteralPath $stage)) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
