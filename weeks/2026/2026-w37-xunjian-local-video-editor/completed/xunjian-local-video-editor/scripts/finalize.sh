#!/usr/bin/env bash
set -euo pipefail

job="${1:?usage: scripts/finalize.sh <job> [format]}"
format="${2:-short-explainer}"
python -m agent_video_editor.cli run "$job" --format "$format"
