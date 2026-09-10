param(
    [ValidateSet('small', 'base')][string]$Model = 'small',
    [ValidateRange(30, 600)][int]$TimeoutSeconds = 420
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw 'Please create the project .venv first.' }
$env:PYTHONUTF8 = '1'
& $pythonExecutable -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('faster_whisper') and importlib.util.find_spec('huggingface_hub') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $pythonExecutable -m pip install --disable-pip-version-check --no-input --timeout 20 --retries 1 faster-whisper
    if ($LASTEXITCODE -ne 0) { throw 'faster-whisper installation failed.' }
}
& $pythonExecutable -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('opencc') else 1)"
if ($LASTEXITCODE -ne 0) {
    & $pythonExecutable -m pip install --disable-pip-version-check --no-input --timeout 20 --retries 1 opencc-python-reimplemented==0.1.7
    if ($LASTEXITCODE -ne 0) { throw 'Traditional Chinese conversion installation failed.' }
}
& $pythonExecutable (Join-Path $PSScriptRoot 'setup_local_asr.py') --model $Model --timeout $TimeoutSeconds
if ($LASTEXITCODE -ne 0) { throw 'Model download failed; rerun this script to resume.' }
Write-Output 'Local ASR is ready. The workbench discovers this model automatically; no restart is required.'
