[CmdletBinding()]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 7861,

    [switch]$NoBrowser,

    [switch]$FullPrecision
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'uv was not found. Install uv as described in README.md, then run this script again.'
}

$serverArgs = @(
    'run',
    '--extra', 'htmlui',
    'python', 'htmlui_server.py',
    '--port', $Port
)

if ($NoBrowser) {
    $serverArgs += '--no-open-browser'
}

if ($FullPrecision) {
    $serverArgs += '--no-bf16'
}

Write-Host "Index Studio will start at http://127.0.0.1:$Port."
Write-Host 'The first run creates the Python environment and downloads missing model files.'
& uv @serverArgs
