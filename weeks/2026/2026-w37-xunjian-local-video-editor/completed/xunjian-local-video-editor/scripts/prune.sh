#!/usr/bin/env bash
set -euo pipefail

job="${1:?usage: scripts/prune.sh <job>}"
if [[ ! "$job" =~ ^[A-Za-z0-9][A-Za-z0-9_-]*$ ]]; then
  echo "Refusing invalid job name: $job" >&2
  exit 2
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(CDPATH= cd -- "$script_dir/.." && pwd -P)"
projects_root="$(CDPATH= cd -- "$project_root/projects" && pwd -P)"
job_root="$projects_root/$job"
tmp="$job_root/tmp"

[[ -d "$tmp" ]] || exit 0
[[ ! -L "$tmp" ]] || { echo "Refusing symlink tmp directory" >&2; exit 2; }
tmp_real="$(CDPATH= cd -- "$tmp" && pwd -P)"
[[ "$tmp_real" == "$projects_root/$job/tmp" ]] || { echo "Refusing tmp path outside projects root" >&2; exit 2; }
if [[ -n "$(find -P "$tmp" -mindepth 1 -type l -print -quit)" ]]; then
  echo "Refusing tmp directory containing symlinks" >&2
  exit 2
fi

find -P "$tmp" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
