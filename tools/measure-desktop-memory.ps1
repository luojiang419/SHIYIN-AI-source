param(
    [Parameter(Mandatory = $true)]
    [string]$Stage,
    [int]$Port = 3128,
    [int]$WarmupSeconds = 15,
    [int]$IntervalSeconds = 15,
    [int]$SampleCount = 7
)

$ErrorActionPreference = "Stop"
if ($WarmupSeconds -lt 0) { throw "WarmupSeconds cannot be negative" }
if ($IntervalSeconds -lt 1) { throw "IntervalSeconds must be at least 1" }
if ($SampleCount -lt 2) { throw "SampleCount must be at least 2" }

$stageRoot = (Resolve-Path -LiteralPath $Stage).Path
$desktopExe = Join-Path $stageRoot "SHIYIN AI.exe"
if (-not (Test-Path -LiteralPath $desktopExe -PathType Leaf)) {
    throw "Desktop executable not found: $desktopExe"
}
if (@(Get-Process -Name "SHIYIN AI" -ErrorAction SilentlyContinue).Count -gt 0) {
    throw "Memory sampling requires all existing SHIYIN AI instances to be closed"
}

$configRoot = Join-Path $stageRoot "data\config"
New-Item -ItemType Directory -Force $configRoot | Out-Null
$appConfig = [ordered]@{
    host = "127.0.0.1"
    port = $Port
    lan_enabled = $false
    cache_max_bytes = 10737418240
} | ConvertTo-Json
[System.IO.File]::WriteAllText(
    (Join-Path $configRoot "app.json"),
    "$appConfig`n",
    [System.Text.UTF8Encoding]::new($false)
)

function Get-ProcessTree([int]$RootPid, [int]$SidecarPid) {
    $processTable = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId
    $ownedIds = @($RootPid)
    do {
        $beforeCount = $ownedIds.Count
        $children = $processTable |
            Where-Object { $ownedIds -contains [int]$_.ParentProcessId } |
            ForEach-Object { [int]$_.ProcessId }
        $ownedIds = @($ownedIds + $children | Sort-Object -Unique)
    } while ($ownedIds.Count -gt $beforeCount)
    if ($ownedIds -notcontains $SidecarPid) { $ownedIds += $SidecarPid }
    return @(Get-Process -Id $ownedIds -ErrorAction SilentlyContinue)
}

$desktop = Start-Process -FilePath $desktopExe -WorkingDirectory $stageRoot -WindowStyle Hidden -PassThru
$sidecarPid = 0
try {
    $health = $null
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($desktop.HasExited) {
            throw "SHIYIN AI.exe exited before the backend became healthy (code $($desktop.ExitCode))"
        }
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 1
            break
        } catch {
            Start-Sleep -Milliseconds 100
        }
    }
    if (-not $health) { throw "Desktop backend health check timed out" }

    $statePath = Join-Path $stageRoot "data\run\backend.json"
    $sidecarPid = [int](Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json).pid
    if ($WarmupSeconds -gt 0) { Start-Sleep -Seconds $WarmupSeconds }
    $samples = @()
    for ($index = 0; $index -lt $SampleCount; $index++) {
        if ($index -gt 0) { Start-Sleep -Seconds $IntervalSeconds }
        $processes = @(Get-ProcessTree $desktop.Id $sidecarPid)
        $privateBytes = ($processes | Measure-Object -Property PrivateMemorySize64 -Sum).Sum
        $samples += [ordered]@{
            elapsed_seconds = $index * $IntervalSeconds
            private_memory_mb = [math]::Round($privateBytes / 1MB, 2)
            process_count = $processes.Count
        }
    }

    $firstMb = [double]$samples[0].private_memory_mb
    $lastMb = [double]$samples[-1].private_memory_mb
    [ordered]@{
        health = $health.status
        warmup_seconds = $WarmupSeconds
        samples = $samples
        delta_mb = [math]::Round($lastMb - $firstMb, 2)
        delta_percent = [math]::Round((($lastMb - $firstMb) / $firstMb) * 100, 2)
    } | ConvertTo-Json -Depth 4
} finally {
    if (-not $desktop.HasExited) {
        $desktop.Kill()
        [void]$desktop.WaitForExit(5000)
    }
    if ($sidecarPid -gt 0) {
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            if (-not (Get-Process -Id $sidecarPid -ErrorAction SilentlyContinue)) { break }
            Start-Sleep -Milliseconds 100
        }
    }
}
