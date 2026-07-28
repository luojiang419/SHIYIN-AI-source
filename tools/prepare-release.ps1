param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = 'Stop'
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid version: $Version" }

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'increment-version.ps1') -Version $Version
if (-not $?) { throw 'Version source injection failed.' }

$notesPath = Join-Path $projectRoot 'release-notes\current.md'
$notes = [IO.File]::ReadAllText($notesPath)
$updated = [regex]::Replace($notes, '(?m)^# SHIYIN AI v\d+\.\d+\.\d+\s*$', "# SHIYIN AI v$Version")
if ($updated -eq $notes) { throw "Release note title was not found: $notesPath" }
[IO.File]::WriteAllText($notesPath, $updated, [Text.UTF8Encoding]::new($false))
