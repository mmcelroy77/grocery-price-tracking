#!/usr/bin/env bash
# Step 1: Java 21 LTS and uv (user-level install). Skips what's present.
#   Linux/WSL: openjdk-21 via apt (needs sudo)
#   macOS:     openjdk@21 via Homebrew
# Python itself is managed by uv (uses system 3.12 if present, otherwise downloads it).
source "$(dirname "$0")/lib/common.sh"

java_major() {
  command -v java >/dev/null || { echo 0; return; }
  { java -version 2>&1 || true; } | awk -F'"' '/version/ {split($2,v,"."); print (v[1]=="1") ? v[2] : v[1]}'
}

if [[ "$OS" == macos ]]; then
  step "System packages (Homebrew)"
  command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh, then re-run."
  if find_jdk_macos >/dev/null; then
    echo "JDK $MIN_JAVA already present."
  else
    brew install "openjdk@$MIN_JAVA"
  fi
  jdk="$(find_jdk_macos)" || die "JDK $MIN_JAVA not found after install."
  export JAVA_HOME="$jdk" PATH="$jdk/bin:$PATH"
  echo "Java $(java_major) at $JAVA_HOME"
else
  step "System packages"
  pkgs=()
  (( $(java_major) >= MIN_JAVA )) || pkgs+=(openjdk-21-jdk-headless)
  command -v curl >/dev/null || pkgs+=(curl)

  if (( ${#pkgs[@]} )); then
    echo "Installing: ${pkgs[*]}"
    sudo apt-get update -y
    sudo apt-get install -y "${pkgs[@]}"
  else
    echo "Java $(java_major) and curl already present."
  fi
fi

step "uv"
if command -v uv >/dev/null; then
  echo "$(uv --version) already present."
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  command -v uv >/dev/null || die "uv install failed"
  echo "Installed $(uv --version)"
fi
