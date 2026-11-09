#!/usr/bin/env bash
# Step 1: Java 17 (apt, needs sudo) and uv (user-level install). Skips what's present.
# Python itself is managed by uv (uses system 3.12 if present, otherwise downloads it).
source "$(dirname "$0")/lib/common.sh"

java_major() {
  command -v java >/dev/null || { echo 0; return; }
  java -version 2>&1 | awk -F'"' '/version/ {split($2,v,"."); print (v[1]=="1") ? v[2] : v[1]}'
}

step "System packages"
pkgs=()
(( $(java_major) >= MIN_JAVA )) || pkgs+=(openjdk-17-jdk-headless)
command -v curl >/dev/null || pkgs+=(curl)

if (( ${#pkgs[@]} )); then
  echo "Installing: ${pkgs[*]}"
  sudo apt-get update -y
  sudo apt-get install -y "${pkgs[@]}"
else
  echo "Java $(java_major) and curl already present."
fi

step "uv"
if command -v uv >/dev/null; then
  echo "$(uv --version) already present."
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  command -v uv >/dev/null || die "uv install failed"
  echo "Installed $(uv --version)"
fi
