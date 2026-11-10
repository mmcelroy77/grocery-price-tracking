#!/usr/bin/env bash
# Step 4: install `act`, the local GitHub Actions runner (requires Docker).
#   Linux/WSL: Docker Engine (Docker Desktop on the WSL2 backend) + act via official install script
#   macOS:     Docker Desktop + act via Homebrew
source "$(dirname "$0")/lib/common.sh"

step "Docker (required by act)"
command -v docker >/dev/null || die "Docker not found. Install Docker Desktop (macOS/Windows) or Docker Engine (Linux), then re-run."
docker info >/dev/null 2>&1 || die "Docker daemon not running. Start Docker Desktop / the docker service, then re-run."

step "act (local GitHub Actions runner)"
if command -v act >/dev/null; then
  echo "act already present: $(act --version)"
else
  if [[ "$OS" == macos ]]; then
    command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh, then re-run."
    brew install act
  else
    curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash -s -- -b /usr/local/bin
  fi
  command -v act >/dev/null || die "act install failed"
fi
act --version
