param(
    [Parameter(Mandatory = $true)]
    [string]$WeekPath
)

$ErrorActionPreference = 'Stop'
$resolvedWeek = (Resolve-Path -LiteralPath $WeekPath).Path
$repoRoot = Split-Path -Parent $PSScriptRoot
$weeksRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot 'weeks') + [System.IO.Path]::DirectorySeparatorChar)
$resolvedWeekPath = [System.IO.Path]::GetFullPath($resolvedWeek)
$pathComparison = if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    [System.StringComparison]::OrdinalIgnoreCase
}
else {
    [System.StringComparison]::Ordinal
}

if (-not $resolvedWeekPath.StartsWith($weeksRoot, $pathComparison)) {
    throw "WeekPath must be inside $weeksRoot"
}

foreach ($requiredFile in @('README.md', 'lesson.md', 'metadata.yml')) {
    if (-not (Test-Path -LiteralPath (Join-Path $resolvedWeekPath $requiredFile) -PathType Leaf)) {
        throw "WeekPath is missing $requiredFile"
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $resolvedWeekPath 'completed') -PathType Container)) {
    throw 'WeekPath is missing completed'
}

$metadataContent = Get-Content -LiteralPath (Join-Path $resolvedWeekPath 'metadata.yml') -Raw -Encoding UTF8
$isChromeExtension = $metadataContent -match '(?m)^type:\s*chrome-extension\s*$'

$weekName = Split-Path -Leaf $resolvedWeekPath
$yearName = Split-Path -Leaf (Split-Path -Parent $resolvedWeekPath)
if ($yearName -notmatch '^\d{4}$' -or $weekName -notmatch '^\d{4}-w\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$') {
    throw 'WeekPath must use weeks/YYYY/YYYY-wNN-kebab-case-topic.'
}

& (Join-Path $PSScriptRoot 'validate-repo.ps1')

$releaseRoot = Join-Path $repoRoot 'dist'
$archivePath = Join-Path $releaseRoot "$weekName.zip"
$temporaryArchivePath = Join-Path $releaseRoot ".$weekName-$([System.Guid]::NewGuid().ToString('N')).tmp"

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

try {
    $archiveStream = [System.IO.File]::Open($temporaryArchivePath, [System.IO.FileMode]::CreateNew)
    $archive = [System.IO.Compression.ZipArchive]::new(
        $archiveStream,
        [System.IO.Compression.ZipArchiveMode]::Create,
        $false
    )

    try {
        $files = Get-ChildItem -LiteralPath $resolvedWeekPath -Recurse -File -Force | Sort-Object FullName
        foreach ($file in $files) {
            $entryName = $file.FullName.Substring($resolvedWeekPath.Length + 1).Replace('\', '/')
            $entry = $archive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $entry.LastWriteTime = $file.LastWriteTime

            $inputStream = $file.OpenRead()
            $outputStream = $entry.Open()
            try {
                $inputStream.CopyTo($outputStream)
            }
            finally {
                $outputStream.Dispose()
                $inputStream.Dispose()
            }
        }
    }
    finally {
        $archive.Dispose()
        $archiveStream.Dispose()
    }

    $verificationArchive = [System.IO.Compression.ZipFile]::OpenRead($temporaryArchivePath)
    try {
        $entries = @($verificationArchive.Entries | ForEach-Object { $_.FullName })
        $requiredEntries = @(
            'README.md',
            'lesson.md',
            'metadata.yml'
        )
        $missingEntries = $requiredEntries | Where-Object { $_ -notin $entries }
        $manifestEntries = @($entries | Where-Object { $_ -match '^completed/.+/manifest\.json$' })
        $invalidEntries = @($entries | Where-Object {
            $_.Contains('\') -or
            $_ -match '(^|/)(AGENTS\.md|\.git|\.idea|\.vscode|__pycache__|node_modules|dist|build|qa-evidence|qa-preview)(/|$)' -or
            $_ -match '(^|/)\.env(?:\.(?!example$).+)?$|\.(?:pem|key|p12|pfx|crx|zip|log)$'
        })

        if ($missingEntries) {
            throw "Release archive is missing: $($missingEntries -join ', ')"
        }
        if ($isChromeExtension -and -not $manifestEntries) {
            throw 'Release archive has no completed Chrome manifest.'
        }
        if ($invalidEntries) {
            throw "Release archive contains forbidden entries: $($invalidEntries -join ', ')"
        }
    }
    finally {
        $verificationArchive.Dispose()
    }

    Move-Item -LiteralPath $temporaryArchivePath -Destination $archivePath -Force
}
catch {
    if (Test-Path -LiteralPath $temporaryArchivePath -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryArchivePath -Force
    }
    throw
}

Write-Host "Created $archivePath"
