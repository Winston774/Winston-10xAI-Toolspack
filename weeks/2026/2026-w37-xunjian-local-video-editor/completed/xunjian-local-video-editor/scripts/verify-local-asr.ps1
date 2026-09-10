param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $projectRoot 'output/local-editor-demo' }
$outputRoot = [System.IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null
$audioPath = Join-Path $outputRoot 'windows-local-speech.wav'
$textPath = Join-Path $PSScriptRoot 'fixtures/local-asr-zh-TW.txt'
Add-Type -AssemblyName System.Speech
$speech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $voice = $speech.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1
    if (-not $voice) { throw 'No installed Chinese Windows speech voice; speech quality test cannot run.' }
    Write-Output ('Local speech fixture voice: ' + $voice.VoiceInfo.Name)
    $speech.SelectVoice($voice.VoiceInfo.Name)
    $speech.Rate = -1
    $speech.SetOutputToWaveFile($audioPath)
    $speech.Speak((Get-Content -LiteralPath $textPath -Encoding UTF8 -Raw))
} finally {
    $speech.Dispose()
}
$env:PYTHONUTF8 = '1'
& (Join-Path $projectRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'verify_local_asr.py') $audioPath
if ($LASTEXITCODE -ne 0) { throw 'Offline speech verification failed.' }
