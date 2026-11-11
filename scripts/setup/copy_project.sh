#!/usr/bin/env bash
# Copy this project into the Linux home (default ~/projects/grocery-price-tracking) so uv, Spark
# and pytest run on the WSL filesystem instead of /mnt/c. Skips .venv (setup_wsl.sh rebuilds it).
# If the destination already exists it is left alone, so edits made there are never overwritten.
#   bash scripts/setup/copy_project.sh [DEST]
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEST="${1:-$HOME/projects/grocery-price-tracking}"

if [[ -e "$DEST" ]]; then
  echo "$DEST already exists; leaving it as is."
  exit 0
fi
if [[ "$SRC" == "$DEST" ]]; then
  echo "Project is already at $DEST."
  exit 0
fi

mkdir -p "$DEST"
tar -C "$SRC" --exclude=.venv --exclude=.pytest_cache -cf - . | tar -C "$DEST" -xf -
echo "Copied project to $DEST"
