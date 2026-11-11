# Shared helpers for the Linux/macOS scripts. Source it; don't run it.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
VENV="$PROJECT_ROOT/.venv"
MIN_JAVA=21

# uv installs to ~/.local/bin, which may not be on PATH in a non-login shell yet.
export PATH="$HOME/.local/bin:$PATH"
# uv's cache is on the Linux fs; the project may be on /mnt/c, where hardlinks can't cross.
export UV_LINK_MODE=copy

cd "$PROJECT_ROOT"

step() { printf '\n\033[36m==> %s\033[0m\n' "$*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

case "$(uname -s)" in
  Linux)  OS=linux ;;
  Darwin) OS=macos ;;
  *) die "Unsupported OS. Use WSL/Linux, macOS, or scripts\\setup\\setup.ps1 on Windows." ;;
esac

# Print the path of an installed JDK $MIN_JAVA on macOS, or fail if there isn't one.
find_jdk_macos() {
  local jh prefix
  jh="$(/usr/libexec/java_home -v "$MIN_JAVA" 2>/dev/null)" && { echo "$jh"; return 0; }
  prefix="$(brew --prefix "openjdk@$MIN_JAVA" 2>/dev/null || true)"
  jh="$prefix/libexec/openjdk.jdk/Contents/Home"
  [[ -n "$prefix" && -d "$jh" ]] && echo "$jh"
}

# On macOS, use the JDK we found (Homebrew's openjdk is keg-only, so it isn't on PATH).
if [[ "$OS" == macos ]]; then
  # Homebrew may have just been installed, so it isn't on PATH in this non-login shell yet.
  # Both prefixes cover Apple Silicon (/opt/homebrew) and Intel (/usr/local).
  export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
  if jdk="$(find_jdk_macos)"; then
    export JAVA_HOME="$jdk"
    export PATH="$JAVA_HOME/bin:$PATH"
  fi
fi

# A venv interrupted mid-creation can be missing pieces, so check python + activate.
venv_ok() { [[ -x "$VENV/bin/python" && -f "$VENV/bin/activate" ]]; }
