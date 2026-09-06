param(
    [string]$InputVideo = '',
    [int]$Frames = 8,
    [int]$Fps = 6,
    [int]$MaxResolution = 320
)

$ErrorActionPreference = 'Stop'
$LabRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $LabRoot 'runtime\venv\Scripts\python.exe'
if (-not $InputVideo) {
    $InputVideo = Join-Path $LabRoot 'runtime\sources\video-depth-anything\assets\example_videos\davis_rollercoaster.mp4'
}
if (-not (Test-Path -LiteralPath $Python)) { throw '未部署 runtime/venv，请先运行 setup.ps1' }
if (-not (Test-Path -LiteralPath $InputVideo)) { throw "输入视频不存在：$InputVideo" }

$OutputRoot = Join-Path $LabRoot 'runtime\outputs\model-smoke'
$Parameters = '{"farPoint":0,"nearPoint":100,"midtone":0,"contrast":100,"brightness":0,"smooth":0,"invert":false}'
$Cases = @(
    @{ Key = 'gemdepth_vda_8f'; InputSize = 392; Directory = 'gemdepth-8f' },
    @{ Key = 'vda_base_fp16_relative'; InputSize = 322; Directory = 'vda-base-fp16-relative' }
)

foreach ($Case in $Cases) {
    $Destination = Join-Path $OutputRoot $Case.Directory
    & $Python (Join-Path $LabRoot 'worker\main.py') infer `
        --model $Case.Key `
        --input $InputVideo `
        --output-dir $Destination `
        --input-size $Case.InputSize `
        --target-fps $Fps `
        --max-frames $Frames `
        --max-resolution $MaxResolution `
        --params-json $Parameters
    if ($LASTEXITCODE -ne 0) { throw "$($Case.Key) 真实推理 smoke 失败" }
    & ffprobe -v error -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_frames -of json (Join-Path $Destination 'depth-preview.mp4')
    if ($LASTEXITCODE -ne 0) { throw "$($Case.Key) 输出视频校验失败" }
}

Write-Host "[done] 双模型 smoke 已通过：$OutputRoot"
