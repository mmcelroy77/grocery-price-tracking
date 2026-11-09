#!/usr/bin/env bash
# Open an interactive shell in the project with .venv activated.
source "$(dirname "$0")/lib/common.sh"
venv_ok || die ".venv missing or broken; run scripts/setup_wsl.sh first"
export PROJECT_ROOT
exec bash --rcfile "$SCRIPTS_DIR/lib/dev_bashrc" -i
