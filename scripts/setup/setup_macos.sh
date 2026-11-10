#!/usr/bin/env bash
# Full macOS setup: system deps (Homebrew JDK 21 + uv) -> venv -> verify. Safe to re-run.
#   bash scripts/setup/setup_macos.sh            # setup only
#   bash scripts/setup/setup_macos.sh --shell    # setup, then open a dev shell with venv active
source "$(dirname "$0")/../lib/common.sh"
[[ "$OS" == macos ]] || die "setup_macos.sh is for macOS; on WSL/Linux use setup_wsl.sh."

bash "$SCRIPTS_DIR/setup/install_system_deps.sh"
bash "$SCRIPTS_DIR/setup/sync_deps.sh"
bash "$SCRIPTS_DIR/setup/verify.sh"
step "Setup complete"

if [[ "${1:-}" == "--shell" ]]; then
  exec bash "$SCRIPTS_DIR/setup/dev_shell.sh"
fi
echo "Open a dev shell with: bash scripts/setup/dev_shell.sh   (or: source .venv/bin/activate)"
