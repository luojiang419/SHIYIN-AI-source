param(
    [string]$RemoteHost = "64.90.17.178",
    [int]$Port = 419,
    [string]$User = "root",
    [string]$KeyPath = "",
    [int]$MediaPort = 18080
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $KeyPath) {
    $KeyPath = Join-Path $projectRoot "api文档\香港云key\id_ed25519_1panel"
}
if (-not (Test-Path -LiteralPath $KeyPath -PathType Leaf)) {
    throw "SSH key not found: $KeyPath"
}

$ssh = Get-Command ssh.exe -ErrorAction Stop
$scp = Get-Command scp.exe -ErrorAction Stop
$serviceRoot = Join-Path $projectRoot "tools\remote-clip-service"
$stage = Join-Path $projectRoot ".build\remote-clip-service"
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item -LiteralPath (Join-Path $serviceRoot "clip_media_server.py") -Destination $stage -Force
Copy-Item -LiteralPath (Join-Path $serviceRoot "clip_media_gc.py") -Destination $stage -Force
Copy-Item -LiteralPath (Join-Path $serviceRoot "clip-media.service") -Destination $stage -Force
Copy-Item -LiteralPath (Join-Path $serviceRoot "clip-media-gc.service") -Destination $stage -Force
Copy-Item -LiteralPath (Join-Path $serviceRoot "clip-media-gc.timer") -Destination $stage -Force

$sshArgs = @(
    "-i", $KeyPath, "-p", $Port, "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
    "-o", "StrictHostKeyChecking=accept-new", "$User@$RemoteHost"
)
$portCheck = & $ssh.Source @sshArgs "ss -ltn | grep -E ':$MediaPort( |$)' || true"
if ($portCheck) {
    throw "Remote media port $MediaPort is already occupied; refusing to touch existing services."
}

$target = "$User@$RemoteHost`:/tmp/shiyin-remote-clip-service"
& $scp.Source -r -i $KeyPath -P $Port -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new $stage "$target"
if ($LASTEXITCODE -ne 0) { throw "Failed to upload remote clip service files." }

$install = @"
set -eu
install -d -m 700 /opt/clipdata/.service
install -m 755 /tmp/shiyin-remote-clip-service/clip_media_server.py /opt/clipdata/.service/clip_media_server.py
install -m 755 /tmp/shiyin-remote-clip-service/clip_media_gc.py /opt/clipdata/.service/clip_media_gc.py
install -m 644 /tmp/shiyin-remote-clip-service/clip-media.service /etc/systemd/system/clip-media.service
install -m 644 /tmp/shiyin-remote-clip-service/clip-media-gc.service /etc/systemd/system/clip-media-gc.service
install -m 644 /tmp/shiyin-remote-clip-service/clip-media-gc.timer /etc/systemd/system/clip-media-gc.timer
sed -i 's/--port 18080/--port $MediaPort/' /etc/systemd/system/clip-media.service
rm -rf /tmp/shiyin-remote-clip-service
systemctl daemon-reload
systemctl enable --now clip-media.service
systemctl enable --now clip-media-gc.timer
systemctl is-active clip-media.service
systemctl is-active clip-media-gc.timer
ss -ltn | grep -E ':$MediaPort( |$)'
"@
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($install))
& $ssh.Source @sshArgs "echo $encoded | base64 -d | bash"
if ($LASTEXITCODE -ne 0) { throw "Remote clip service installation failed." }
Write-Host "Remote clip service is listening on $MediaPort without changing existing ports."
