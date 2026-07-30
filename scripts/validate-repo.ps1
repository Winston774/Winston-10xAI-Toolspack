$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$requiredRootFiles = @('README.md', 'CATALOG.md', 'CHANGELOG.md', 'CONTRIBUTING.md')
$errors = [System.Collections.Generic.List[string]]::new()

function Get-MetadataValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Content,
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $match = [regex]::Match($Content, "(?m)^$([regex]::Escape($Key)):\s*(.+?)\s*$")
    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}

foreach ($file in $requiredRootFiles) {
    $path = Join-Path $repoRoot $file
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        $errors.Add("Missing required file: $file")
    }
}

$skillTemplate = Join-Path $repoRoot 'templates/skill/SKILL.md'
$extensionManifest = Join-Path $repoRoot 'templates/chrome-extension/manifest.json'
$localToolTemplate = Join-Path $repoRoot 'templates/local-ai-tool/README.md'
$weeklyTemplate = Join-Path $repoRoot 'templates/weekly-unit/metadata.yml'

foreach ($path in @($skillTemplate, $extensionManifest, $localToolTemplate, $weeklyTemplate)) {
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
if (-not (Test-Path -LiteralPath $weekRoot -PathType Container)) {
    $errors.Add('Missing weeks directory.')
}

$catalogPath = Join-Path $repoRoot 'CATALOG.md'
$catalog = if (Test-Path -LiteralPath $catalogPath -PathType Leaf) {
    Get-Content -LiteralPath $catalogPath -Raw -Encoding UTF8
}
else {
    ''
}

$allYearDirectories = Get-ChildItem -LiteralPath $weekRoot -Directory -Force -ErrorAction SilentlyContinue
$invalidYearDirectories = $allYearDirectories | Where-Object { $_.Name -notmatch '^\d{4}$' }
foreach ($invalidYearDirectory in $invalidYearDirectories) {
    $errors.Add("Invalid year directory: $($invalidYearDirectory.Name)")
}

$yearDirectories = $allYearDirectories | Where-Object { $_.Name -match '^\d{4}$' }
$formalWeekCount = 0

foreach ($yearDirectory in $yearDirectories) {
    if ($yearDirectory.LinkType -or ($yearDirectory.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        $errors.Add("Linked year directory is not allowed: $($yearDirectory.FullName)")
    }

    if (-not (Test-Path -LiteralPath (Join-Path $yearDirectory.FullName 'README.md') -PathType Leaf)) {
        $errors.Add("$($yearDirectory.Name) is missing README.md")
    }

    $weekDirectories = Get-ChildItem -LiteralPath $yearDirectory.FullName -Directory -Force -ErrorAction SilentlyContinue
    foreach ($unit in $weekDirectories) {
        $formalWeekCount++
        if ($unit.Name -notmatch '^\d{4}-w\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$') {
            $errors.Add("Invalid week directory name: $($unit.Name)")
        }

        $metadataPath = Join-Path $unit.FullName 'metadata.yml'
        foreach ($requiredFile in @('README.md', 'lesson.md', 'metadata.yml')) {
            if (-not (Test-Path -LiteralPath (Join-Path $unit.FullName $requiredFile) -PathType Leaf)) {
                $errors.Add("$($unit.Name) is missing $requiredFile")
            }
        }
        foreach ($requiredDirectory in @('completed')) {
            if (-not (Test-Path -LiteralPath (Join-Path $unit.FullName $requiredDirectory) -PathType Container)) {
                $errors.Add("$($unit.Name) is missing $requiredDirectory")
            }
        }

        $catalogReference = "weeks/$($yearDirectory.Name)/$($unit.Name)/README.md"
        if (-not $catalog.Contains($catalogReference)) {
            $errors.Add("CATALOG.md is missing $catalogReference")
        }

        if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
            continue
        }

        $metadataContent = Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8
        $metadataValues = @{}
        foreach ($key in @('id', 'title', 'type', 'difficulty', 'estimated_minutes', 'status', 'version')) {
            $metadataValues[$key] = Get-MetadataValue -Content $metadataContent -Key $key
            if ([string]::IsNullOrWhiteSpace($metadataValues[$key])) {
                $errors.Add("$($unit.Name) metadata is missing $key")
            }
        }

        if ($metadataValues.id -and -not $unit.Name.StartsWith("$($metadataValues.id)-")) {
            $errors.Add("$($unit.Name) does not match metadata id $($metadataValues.id)")
        }
        if ($metadataValues.type -and $metadataValues.type -notin @('skill', 'chrome-extension', 'local-ai-tool')) {
            $errors.Add("$($unit.Name) has invalid type $($metadataValues.type)")
        }
        if ($metadataValues.difficulty -and $metadataValues.difficulty -notin @('beginner', 'intermediate', 'advanced')) {
            $errors.Add("$($unit.Name) has invalid difficulty $($metadataValues.difficulty)")
        }
        if ($metadataValues.status -and $metadataValues.status -notin @('draft', 'preview', 'stable', 'archived')) {
            $errors.Add("$($unit.Name) has invalid status $($metadataValues.status)")
        }
        if (
            $metadataValues.estimated_minutes -and
            ($metadataValues.estimated_minutes -notmatch '^\d+$' -or [int]$metadataValues.estimated_minutes -le 0)
        ) {
            $errors.Add("$($unit.Name) estimated_minutes must be a positive integer")
        }
        if ($metadataValues.version -and $metadataValues.version -notmatch '^\d+\.\d+\.\d+$') {
            $errors.Add("$($unit.Name) version must use MAJOR.MINOR.PATCH")
        }

        if ($metadataValues.type -eq 'chrome-extension') {
            $completedPath = Join-Path $unit.FullName 'completed'
            $manifests = Get-ChildItem -LiteralPath $completedPath -Filter manifest.json -Recurse -File -ErrorAction SilentlyContinue
            if (-not $manifests) {
                $errors.Add("$($unit.Name) has no completed Chrome manifest")
            }

            foreach ($completedManifest in $manifests) {
                try {
                    $manifest = Get-Content -LiteralPath $completedManifest.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($manifest.manifest_version -ne 3) {
                        $errors.Add("$($unit.Name) completed extension must use Manifest V3")
                    }
                    if ([string]::IsNullOrWhiteSpace($manifest.name) -or [string]::IsNullOrWhiteSpace($manifest.version)) {
                        $errors.Add("$($unit.Name) completed manifest must include name and version")
                    }
                    if (-not (Test-Path -LiteralPath (Join-Path $completedManifest.Directory.FullName 'README.md') -PathType Leaf)) {
                        $errors.Add("$($unit.Name) completed extension is missing README.md")
                    }
                }
                catch {
                    $errors.Add("Invalid completed Chrome manifest $($completedManifest.FullName): $($_.Exception.Message)")
                }
            }

            foreach ($requiredDoc in @('docs/permissions-and-privacy.md', 'docs/troubleshooting.md', 'docs/verification.md')) {
                if (-not (Test-Path -LiteralPath (Join-Path $unit.FullName $requiredDoc) -PathType Leaf)) {
                    $errors.Add("$($unit.Name) is missing $requiredDoc")
                }
            }
        }

        if ($metadataValues.type -eq 'local-ai-tool') {
            $completedPath = Join-Path $unit.FullName 'completed'
            $packages = Get-ChildItem -LiteralPath $completedPath -Filter package.json -Recurse -File -ErrorAction SilentlyContinue
            if (-not $packages) {
                $errors.Add("$($unit.Name) has no completed Node.js package")
            }

            foreach ($packageFile in $packages) {
                try {
                    $package = Get-Content -LiteralPath $packageFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ([string]::IsNullOrWhiteSpace($package.name) -or [string]::IsNullOrWhiteSpace($package.version)) {
                        $errors.Add("$($unit.Name) completed package must include name and version")
                    }
                    if ($package.version -ne $metadataValues.version) {
                        $errors.Add("$($unit.Name) completed package version must match metadata version")
                    }
                    if (-not $package.scripts.test -or -not $package.scripts.validate) {
                        $errors.Add("$($unit.Name) completed package must include test and validate scripts")
                    }
                    if (-not (Test-Path -LiteralPath (Join-Path $packageFile.Directory.FullName 'README.md') -PathType Leaf)) {
                        $errors.Add("$($unit.Name) completed local tool is missing README.md")
                    }
                }
                catch {
                    $errors.Add("Invalid completed package $($packageFile.FullName): $($_.Exception.Message)")
                }
            }

            foreach ($requiredDoc in @('docs/privacy-and-content-rights.md', 'docs/troubleshooting.md', 'docs/verification.md')) {
                if (-not (Test-Path -LiteralPath (Join-Path $unit.FullName $requiredDoc) -PathType Leaf)) {
                    $errors.Add("$($unit.Name) is missing $requiredDoc")
                }
            }
        }

        $publishedItems = Get-ChildItem -LiteralPath $unit.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $linkedItems = @($unit) + @($publishedItems) | Where-Object {
            $_.LinkType -or ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
        }
        foreach ($linkedItem in $linkedItems) {
            $errors.Add("Linked publish item is not allowed: $($linkedItem.FullName)")
        }

        $forbiddenFiles = $publishedItems | Where-Object { -not $_.PSIsContainer } |
            Where-Object {
                $_.Name -eq 'AGENTS.md' -or
                $_.Name -eq 'SKOOL-POST.md' -or
                $_.Name -eq '.env' -or
                ($_.Name -like '.env.*' -and $_.Name -ne '.env.example') -or
                $_.Name -match '\.(?:pem|key|p12|pfx|crx|zip|log)$'
            }
        foreach ($forbidden in $forbiddenFiles) {
            $errors.Add("Forbidden publish file: $($forbidden.FullName)")
        }

        $forbiddenDirectories = $publishedItems | Where-Object { $_.PSIsContainer } |
            Where-Object {
                $_.Name -in @('.git', '.idea', '.vscode', '__pycache__', 'node_modules', 'dist', 'build', 'qa-evidence', 'qa-preview')
            }
        foreach ($forbiddenDirectory in $forbiddenDirectories) {
            $errors.Add("Forbidden publish directory: $($forbiddenDirectory.FullName)")
        }

        $secretPatterns = @(
            'AIza[0-9A-Za-z_-]{20,}',
            'gh[pousr]_[0-9A-Za-z]{20,}',
            'github_pat_[0-9A-Za-z_]{20,}',
            'sk-[0-9A-Za-z_-]{20,}',
            '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'
        )
        $textFiles = $publishedItems | Where-Object { -not $_.PSIsContainer } |
            Where-Object {
                $_.Name -eq '.env.example' -or
                $_.Extension -eq '' -or
                $_.Extension -in @(
                    '.md', '.txt', '.json', '.yml', '.yaml', '.toml', '.xml', '.csv', '.svg',
                    '.js', '.mjs', '.cjs', '.ts', '.tsx', '.html', '.css', '.ps1'
                )
            }
        foreach ($textFile in $textFiles) {
            $content = Get-Content -LiteralPath $textFile.FullName -Raw -Encoding UTF8
            foreach ($pattern in $secretPatterns) {
                if ($content -match $pattern) {
                    $errors.Add("Possible secret in $($textFile.FullName)")
                    break
                }
            }
        }
    }
}

if ($formalWeekCount -eq 0) {
    $errors.Add('Repository must contain at least one formal week directory.')
}

if ($errors.Count -gt 0) {
    Write-Host 'Repository validation failed:' -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}

Write-Host 'Repository validation passed.' -ForegroundColor Green
