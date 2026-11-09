# Shared helpers for the Linux-side scripts. Source it; don't run it.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
VENV="$PROJECT_ROOT/.venv"
MIN_JAVA=17

# uv installs to ~/.local/bin, which may not be on PATH in a non-login shell yet.
export PATH="$HOME/.local/bin:$PATH"
# uv's cache is on the Linux fs; the project may be on /mnt/c, where hardlinks can't cross.
export UV_LINK_MODE=copy

cd "$PROJECT_ROOT"

step() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

[[ "$(uname -s)" == "Linux" ]] || die "Run this inside WSL/Linux (or use scripts/setup.ps1 from Windows)."

# A venv interrupted mid-creation can be missing pieces, so check python + activate.
venv_ok() { [[ -x "$VENV/bin/python" && -f "$VENV/bin/activate" ]]; }
