param(
    [Parameter(Mandatory = $true)]
    [string]$WeekPath
)

$ErrorActionPreference = 'Stop'
$resolvedWeek = Resolve-Path -LiteralPath $WeekPath
$repoRoot = Split-Path -Parent $PSScriptRoot
$releaseRoot = Join-Path $repoRoot 'dist'
$weekName = Split-Path -Leaf $resolvedWeek
$archivePath = Join-Path $releaseRoot "$weekName.zip"

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
Compress-Archive -Path (Join-Path $resolvedWeek '*') -DestinationPath $archivePath -Force
Write-Host "Created $archivePath"
