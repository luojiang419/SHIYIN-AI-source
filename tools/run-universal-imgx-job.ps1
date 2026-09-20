param([Parameter(Mandatory=$true)][string]$JobFile)
$ErrorActionPreference = 'Stop'
$jobSpec = Get-Content -LiteralPath $JobFile -Raw -Encoding UTF8 | ConvertFrom-Json
$generationArgs = @('--aspect-ratio', $jobSpec.aspect_ratio, '--resolution', $jobSpec.resolution, '--count', [string]$jobSpec.count, '--output-dir', $jobSpec.output_dir)
foreach ($promptText in $jobSpec.prompts) { $generationArgs += @('--prompt', $promptText) }
foreach ($referencePath in $jobSpec.references) { $generationArgs += @('--reference-image', $referencePath) }
& 'C:\Users\jiang\.codex\skills\imgx\scripts\generate-images.ps1' @generationArgs
exit $LASTEXITCODE
