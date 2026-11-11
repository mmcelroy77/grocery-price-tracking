#!/usr/bin/env bash
# Run the GitHub Actions workflow locally with act, with flags that fit this machine.
#   bash scripts/act/run_act.sh            # default: workflow_dispatch
#   bash scripts/act/run_act.sh -j test    # pass any act flags through
source "$(dirname "$0")/../lib/common.sh"

command -v act >/dev/null || die "act not found; run scripts/act/install_act.sh"

args=(
  -P ubuntu-latest=catthehacker/ubuntu:act-latest
  --env UV_LINK_MODE=copy
  # Local artifact server, needed by the workflow's local upload-artifact step.
  --artifact-server-path "$PROJECT_ROOT/.git/act-artifacts"
)

# act warns (and may pick the wrong image) on Apple Silicon unless the arch is set.
if [[ "$OS" == macos && "$(uname -m)" == arm64 ]]; then
  args+=(--container-architecture linux/arm64)
fi

# The workflow is manual-only, so default to its trigger instead of act's "push".
(( $# )) || set -- workflow_dispatch

exec act "${args[@]}" "$@"
