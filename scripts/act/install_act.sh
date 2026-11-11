#!/usr/bin/env bash
# Install `act`, the local GitHub Actions runner, plus Docker (its only requirement).
#   Linux/WSL: Docker Engine (Docker Desktop on the WSL2 backend) + act via official install script
#   macOS:     Docker Desktop + act via Homebrew
source "$(dirname "$0")/../lib/common.sh"

# --- Docker: required by act (it runs workflows in containers) ---
step "Docker (required by act)"
if ! command -v docker >/dev/null; then
  if [[ "$OS" == macos ]]; then
    command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh, then re-run."
    brew install --cask docker
  else
    sudo apt-get update -y
    sudo apt-get install -y docker.io
  fi
fi
command -v docker >/dev/null || die "Docker install failed"
docker_ok() { docker info >/dev/null 2>&1; }

if ! docker_ok; then
  if [[ "$OS" == linux ]]; then
    # Start the daemon. Output is left visible so a real failure is diagnosable.
    if [[ -d /run/systemd/system ]]; then
      sudo systemctl enable --now docker || echo "WARN: systemctl could not start docker" >&2
    else
      sudo service docker start || echo "WARN: 'service docker start' failed" >&2
    fi
    # The socket takes a few seconds to appear after start.
    for _ in $(seq 1 20); do
      docker_ok && break
      sudo docker info >/dev/null 2>&1 && break
      sleep 1
    done
  fi

  if ! docker_ok; then
    if [[ "$OS" == linux ]] && sudo docker info >/dev/null 2>&1; then
      # Daemon is up, but this user can't reach the socket (docker.io doesn't add you to the group).
      echo "Docker is running, but '$USER' can't access /var/run/docker.sock. Fixing..."
      # Permanent: group membership (applies to new login sessions only).
      sudo usermod -aG docker "$USER"
      # Immediate: ACL on the socket, so this and every open shell works right now.
      # (Lasts until the docker service recreates the socket; the group covers that case.)
      if ! command -v setfacl >/dev/null; then
        sudo apt-get install -y acl
      fi
      sudo setfacl -m "u:$USER:rw" /var/run/docker.sock || true
      if docker_ok; then
        echo "Docker access granted. Group membership will apply to new shells."
      else
        echo "WARN: still no socket access. Open a new WSL shell (or run: wsl --shutdown from PowerShell) before using act." >&2
      fi
    else
      if [[ "$OS" == macos ]]; then
        die "Docker daemon not running. Open Docker Desktop, wait for it to start, then re-run."
      else
        die "Docker daemon not running. Start Docker Desktop (enable WSL integration for this distro) or run: sudo service docker start"
      fi
    fi
  fi
fi

# --- act: the local GitHub Actions runner ---
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
