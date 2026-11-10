#!/usr/bin/env bash
# Run GitHub Actions workflows locally via act (needs Docker + act installed).
# Usage: bash scripts/run_act.sh [act args...]
#   bash scripts/run_act.sh -j test
#   bash scripts/run_act.sh -W .github/workflows/ci.yml
source "$(dirname "$0")/lib/common.sh"
command -v act >/dev/null || die "act not found; run scripts/install_act.sh first"

step "Running GitHub Actions workflow locally (act)"
exec act "$@"
