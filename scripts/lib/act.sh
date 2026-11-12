# Shared by scripts/act/run_*.sh. Source it; don't run it.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# run_act <workflow file name> <default event> [act args...]
# With no args, or only flags, the default event is used (act's own default, "push", matches none of our workflows).
run_act() {
  local workflow="$1" default_event="$2"
  shift 2

  command -v act >/dev/null || die "act not found; run scripts/act/install_act.sh"

  local args=(
    -P ubuntu-latest=catthehacker/ubuntu:act-latest
    -W ".github/workflows/$workflow"
    --env UV_LINK_MODE=copy
    # Local artifact server, needed by the build workflow's local upload-artifact step.
    --artifact-server-path "$PROJECT_ROOT/.git/act-artifacts"
  )

  # act warns (and may pick the wrong image) on Apple Silicon unless the arch is set.
  if [[ "$OS" == macos && "$(uname -m)" == arm64 ]]; then
    args+=(--container-architecture linux/arm64)
  fi

  case "${1:-}" in "" | -*) set -- "$default_event" "$@" ;; esac

  exec act "${args[@]}" "$@"
}
