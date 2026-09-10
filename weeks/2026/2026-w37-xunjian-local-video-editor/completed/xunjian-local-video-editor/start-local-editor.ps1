param(
    [int]$Port = 8321,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$editorPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $editorPython)) {
    $editorPython = (Get-Command python -ErrorAction Stop).Source
}
$editorArgs = @('-m', 'local_editor', 'serve', '--port', "$Port", '--data-dir', (Join-Path $PSScriptRoot '.local-editor'))
if (-not $NoBrowser) { $editorArgs += '--open' }
& $editorPython @editorArgs
exit $LASTEXITCODE
