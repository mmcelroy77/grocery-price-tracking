#!/usr/bin/env bash
# Step 2: create/refresh .venv from pyproject.toml + uv.lock (project + dev group).
source "$(dirname "$0")/../lib/common.sh"
command -v uv >/dev/null || die "uv not found; run scripts/setup/install_system_deps.sh"

step "Python dependencies (uv sync)"
if [[ -e "$VENV" ]] && ! venv_ok; then
  echo "Existing .venv is broken; recreating"
  rm -rf "$VENV"
fi
uv sync

step "Activate pre-commit hooks"
uv run pre-commit install
