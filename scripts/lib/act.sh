# Shared by scripts/act/run_*.sh. Source it; don't run it.
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

# Make sure the Docker daemon is up (act runs workflows in containers). Starts it if it's
# installed but stopped; points at the install script if it isn't installed.
ensure_docker() {
  command -v docker >/dev/null || die "Docker not found; run scripts/act/install_act.sh"
  docker info >/dev/null 2>&1 && return 0

  step "Docker isn't running; starting it"
  if [[ "$OS" == macos ]]; then
    open -a Docker || die "Could not open Docker Desktop; run scripts/act/install_act.sh"
  elif [[ -d /run/systemd/system ]]; then
    sudo systemctl start docker || true
  else
    sudo service docker start || true
  fi

  # Docker Desktop can take a minute to come up.
  local _
  for _ in $(seq 1 60); do
    docker info >/dev/null 2>&1 && { echo "Docker is running."; return 0; }
    sleep 2
  done
  die "Docker didn't start within 2 minutes. Start it manually (see scripts/act/install_act.sh), then re-run."
}

# run_act <workflow file name> <default event> [act args...]
# With no args, or only flags, the default event is used (act's own default, "push", matches none of our workflows).
run_act() {
  local workflow="$1" default_event="$2"
  shift 2

  command -v act >/dev/null || die "act not found; run scripts/act/install_act.sh"
  ensure_docker

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
