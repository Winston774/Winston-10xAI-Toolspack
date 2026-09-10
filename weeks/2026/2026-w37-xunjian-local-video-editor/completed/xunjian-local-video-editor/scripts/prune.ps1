param(
  [Parameter(Mandatory = $true)]
  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')]
  [string]$Job
)

$ErrorActionPreference = "Stop"
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$projectsRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'projects'))
if (-not (Test-Path -LiteralPath $projectsRoot -PathType Container)) {
  throw "Projects root is missing: $projectsRoot"
}
$projectsInfo = Get-Item -LiteralPath $projectsRoot -Force
if ($projectsInfo.Attributes -band [IO.FileAttributes]::ReparsePoint) {
  throw "Refusing a reparse-point projects root: $projectsRoot"
}

$projectsPrefix = $projectsRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$jobRoot = [IO.Path]::GetFullPath((Join-Path $projectsRoot $Job))
if (-not $jobRoot.StartsWith($projectsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing job outside projects root: $Job"
}
$tmp = [IO.Path]::GetFullPath((Join-Path $jobRoot 'tmp'))
if (-not $tmp.StartsWith($jobRoot.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing tmp path outside job root: $tmp"
}
if (-not (Test-Path -LiteralPath $tmp -PathType Container)) { return }

function Assert-NoReparsePoint {
  param([Parameter(Mandatory = $true)][string]$Path)
  $attributes = [IO.File]::GetAttributes($Path)
  if ($attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw "Refusing to prune reparse point: $Path"
  }
  if ($attributes -band [IO.FileAttributes]::Directory) {
    foreach ($child in [IO.Directory]::EnumerateFileSystemEntries($Path)) {
      Assert-NoReparsePoint -Path $child
    }
  }
}

Assert-NoReparsePoint -Path $tmp
Get-ChildItem -LiteralPath $tmp -Force | Remove-Item -Recurse -Force
