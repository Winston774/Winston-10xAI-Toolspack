param(
  [Parameter(Mandatory = $true)]
  [string]$Job,
  [string]$Format = "short-explainer",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$CommandArgs = @("-m", "agent_video_editor.cli", "run", $Job, "--format", $Format)
if ($DryRun) {
  $CommandArgs += "--dry-run"
}
python @CommandArgs
