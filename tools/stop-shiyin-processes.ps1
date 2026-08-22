param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath($PortableRoot).TrimEnd('\')
$targets = @(
    [IO.Path]::GetFullPath((Join-Path $root 'SHIYIN AI.exe')),
    [IO.Path]::GetFullPath((Join-Path $root 'app\backend\canvas-backend\canvas-backend.exe'))
)

function Get-TargetProcesses {
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $path = [string]$_.ExecutablePath
        $path -and ($targets | Where-Object { [String]::Equals($path, $_, [StringComparison]::OrdinalIgnoreCase) })
    })
}

$processes = Get-TargetProcesses
foreach ($process in $processes) {
    try {
        Stop-Process -Id ([int]$process.ProcessId) -Force -ErrorAction Stop
    } catch {
        throw "Unable to stop SHIYIN AI process $($process.ProcessId): $($_.Exception.Message)"
    }
}

$deadline = [DateTime]::UtcNow.AddSeconds(8)
do {
    $remaining = Get-TargetProcesses
    if (-not $remaining.Count) { exit 0 }
    Start-Sleep -Milliseconds 200
} while ([DateTime]::UtcNow -lt $deadline)

$ids = ($remaining | ForEach-Object { $_.ProcessId }) -join ', '
throw "SHIYIN AI processes are still running: $ids"
