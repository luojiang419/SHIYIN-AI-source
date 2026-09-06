param(
    [switch]$SkipSources,
    [switch]$SkipModels
)

$ErrorActionPreference = 'Stop'
$LabRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $LabRoot 'runtime'
$SourcesRoot = Join-Path $RuntimeRoot 'sources'
$ModelsRoot = Join-Path $RuntimeRoot 'models'
$VenvRoot = Join-Path $RuntimeRoot 'venv'

# 明确禁用进程级代理，避免消耗用户代理流量。
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
Remove-Item Env:all_proxy -ErrorAction SilentlyContinue
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

New-Item -ItemType Directory -Force -Path $RuntimeRoot, $SourcesRoot, $ModelsRoot | Out-Null

function Invoke-GitCloneWithFallback {
    param([string]$Name, [string]$Destination, [string]$Revision, [string[]]$Urls)
    if (Test-Path -LiteralPath (Join-Path $Destination '.git')) {
        $CurrentRevision = (& git -C $Destination rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0 -or $CurrentRevision -ne $Revision) {
            throw "$Name 源码 revision 不匹配：实际 $CurrentRevision，预期 $Revision"
        }
        Write-Host "[source] $Name 已存在且 revision 正确，跳过下载"
        return
    }
    foreach ($Url in $Urls) {
        Write-Host "[source] 尝试 $Url"
        & git clone --filter=blob:none --depth 1 $Url $Destination
        if ($LASTEXITCODE -eq 0) {
            & git -C $Destination checkout --detach $Revision
            if ($LASTEXITCODE -eq 0) { return }
        }
        if (Test-Path -LiteralPath $Destination) {
            [System.IO.Directory]::Delete($Destination, $true)
        }
    }
    throw "$Name 源码下载失败"
}

function Invoke-ModelDownloadWithFallback {
    param([string]$Name, [string]$Destination, [long]$MinimumBytes, [string]$ExpectedSha256, [string[]]$Urls)
    if ((Test-Path -LiteralPath $Destination) -and (Get-Item -LiteralPath $Destination).Length -ge $MinimumBytes) {
        $ExistingHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash
        if ($ExistingHash -eq $ExpectedSha256) {
            Write-Host "[model] $Name 已存在且 SHA-256 正确，跳过下载"
            return
        }
        throw "$Name 已存在但 SHA-256 不匹配，请人工核对后移走该文件再重新运行"
    }
    $Parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $Parent | Out-Null
    foreach ($Url in $Urls) {
        Write-Host "[model] 尝试 $Url（直连、禁用代理、支持断点续传）"
        & curl.exe --noproxy '*' -L --fail --retry 4 --retry-delay 3 -C - -o $Destination $Url
        if ($LASTEXITCODE -eq 0 -and (Get-Item -LiteralPath $Destination).Length -ge $MinimumBytes) {
            $DownloadedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash
            if ($DownloadedHash -eq $ExpectedSha256) { return }
            throw "$Name 下载完成但 SHA-256 不匹配"
        }
    }
    throw "$Name 权重下载失败或文件尺寸异常"
}

if (-not $SkipSources) {
    Invoke-GitCloneWithFallback -Name 'GemDepth' -Destination (Join-Path $SourcesRoot 'gemdepth') -Revision '652865b0ed20e727784a6b77314da1dca2f14e36' -Urls @(
        'https://gitclone.com/github.com/Yuecheng919/GemDepth.git',
        'https://github.com/Yuecheng919/GemDepth.git'
    )
    Invoke-GitCloneWithFallback -Name 'Video Depth Anything' -Destination (Join-Path $SourcesRoot 'video-depth-anything') -Revision '4f5ae23172ba60fd7bc11ef671cca678842c7072' -Urls @(
        'https://gitclone.com/github.com/DepthAnything/Video-Depth-Anything.git',
        'https://github.com/DepthAnything/Video-Depth-Anything.git'
    )
}

if (-not (Test-Path -LiteralPath (Join-Path $VenvRoot 'Scripts\python.exe'))) {
    Write-Host '[python] 创建复用本机 CUDA PyTorch 的隔离环境'
    & python -m venv --system-site-packages $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw 'Python 虚拟环境创建失败' }
}
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
Write-Host '[python] 使用清华 PyPI 镜像安装最小补充依赖'
& $VenvPython -m pip install --disable-pip-version-check --index-url 'https://pypi.tuna.tsinghua.edu.cn/simple' -r (Join-Path $LabRoot 'requirements-runtime.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python 补充依赖安装失败' }
& $VenvPython -c "import torch, torchvision, cv2, numpy, PIL, imageio, einops, easydict; assert torch.cuda.is_available(), 'CUDA unavailable'; print('Torch', torch.__version__, 'CUDA', torch.version.cuda, torch.cuda.get_device_name(0))"
if ($LASTEXITCODE -ne 0) { throw '本机 CUDA PyTorch 或基础依赖不可用；本脚本不会自动重复下载大型 Torch 包' }

if (-not $SkipModels) {
    Invoke-ModelDownloadWithFallback -Name 'GemDepth' -Destination (Join-Path $ModelsRoot 'gemdepth\gemdepth.pth') -MinimumBytes 2000000000 -ExpectedSha256 'F7C3FB7791862CC82684DDB1804480FB0314FDDBA4CF0E3B706553D98292FCAD' -Urls @(
        'https://hf-mirror.com/YuechengLiu/GemDepth/resolve/main/gemdepth.pth',
        'https://huggingface.co/YuechengLiu/GemDepth/resolve/main/gemdepth.pth'
    )
    Invoke-ModelDownloadWithFallback -Name 'Video Depth Anything Base' -Destination (Join-Path $ModelsRoot 'video-depth-anything-base\video_depth_anything_vitb.pth') -MinimumBytes 300000000 -ExpectedSha256 '775E578E8F9431EC0496514AA466BD0A1F67C28D0F518267809F35A43C04329B' -Urls @(
        'https://hf-mirror.com/depth-anything/Video-Depth-Anything-Base/resolve/main/video_depth_anything_vitb.pth',
        'https://huggingface.co/depth-anything/Video-Depth-Anything-Base/resolve/main/video_depth_anything_vitb.pth'
    )
}

$StatusLine = & $VenvPython (Join-Path $LabRoot 'worker\main.py') status | Select-Object -Last 1
if ($LASTEXITCODE -ne 0) { throw '运行环境状态检查失败' }
$Status = ($StatusLine | ConvertFrom-Json).result
$Status | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'deployment.json') -Encoding utf8
Write-Host "[done] ready=$($Status.ready) gpu=$($Status.gpu)"
if (-not $Status.ready) { throw '部署结束但运行环境仍不完整，请查看 runtime/deployment.json' }
