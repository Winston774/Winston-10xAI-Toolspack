$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$requiredRootFiles = @('README.md', 'CATALOG.md', 'CHANGELOG.md', 'CONTRIBUTING.md')
$errors = [System.Collections.Generic.List[string]]::new()

foreach ($file in $requiredRootFiles) {
    $path = Join-Path $repoRoot $file
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $errors.Add("Missing required file: $file")
    }
}

$skillTemplate = Join-Path $repoRoot 'templates/skill/SKILL.md'
$extensionManifest = Join-Path $repoRoot 'templates/chrome-extension/manifest.json'
$weeklyTemplate = Join-Path $repoRoot 'templates/weekly-unit/metadata.yml'

foreach ($path in @($skillTemplate, $extensionManifest, $weeklyTemplate)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $errors.Add("Missing template: $path")
    }
}

if (Test-Path -LiteralPath $extensionManifest -PathType Leaf) {
    try {
        $manifest = Get-Content -LiteralPath $extensionManifest -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($manifest.manifest_version -ne 3) {
            $errors.Add('Chrome template must use Manifest V3.')
        }
    }
    catch {
        $errors.Add("Invalid Chrome manifest JSON: $($_.Exception.Message)")
    }
}

$weekRoot = Join-Path $repoRoot 'weeks'
$weekMetadata = Get-ChildItem -LiteralPath $weekRoot -Filter metadata.yml -Recurse -File -ErrorAction SilentlyContinue
foreach ($metadata in $weekMetadata) {
    $unitRoot = Split-Path -Parent $metadata.FullName
    foreach ($required in @('README.md', 'lesson.md')) {
        if (-not (Test-Path -LiteralPath (Join-Path $unitRoot $required) -PathType Leaf)) {
            $errors.Add("$($metadata.Directory.Name) is missing $required")
        }
    }
}

if ($errors.Count -gt 0) {
    Write-Host 'Repository validation failed:' -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}

Write-Host 'Repository validation passed.' -ForegroundColor Green
