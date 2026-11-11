#!/usr/bin/env bash
# Step 1: Java 21 LTS and uv (user-level install). Skips what's present.
#   Linux/WSL: openjdk-21 via apt (needs sudo)
#   macOS:     openjdk@21 via Homebrew
# Python itself is managed by uv (uses system 3.12 if present, otherwise downloads it).
source "$(dirname "$0")/../lib/common.sh"

java_major() {
  command -v java >/dev/null || { echo 0; return; }
  { java -version 2>&1 || true; } | awk -F'"' '/version/ {split($2,v,"."); print (v[1]=="1") ? v[2] : v[1]}'
}

if [[ "$OS" == macos ]]; then
  step "System packages (Homebrew)"
  if ! command -v brew >/dev/null; then
    echo "Homebrew not found; installing it (may prompt for sudo)."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    command -v brew >/dev/null || die "Homebrew install failed. Install it from https://brew.sh, then re-run."
  fi
  if find_jdk_macos >/dev/null; then
    echo "JDK $MIN_JAVA already present."
  else
    brew install "openjdk@$MIN_JAVA"
  fi
  jdk="$(find_jdk_macos)" || die "JDK $MIN_JAVA not found after install."
  export JAVA_HOME="$jdk" PATH="$jdk/bin:$PATH"
  # Homebrew's JDK is keg-only, so link it where macOS (and PySpark) look for a runtime.
  jdk_link="/Library/Java/JavaVirtualMachines/openjdk-$MIN_JAVA.jdk"
  if [[ ! -e "$jdk_link" ]]; then
    sudo ln -sfn "$(brew --prefix "openjdk@$MIN_JAVA")/libexec/openjdk.jdk" "$jdk_link"
  fi
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

# uv lives in ~/.local/bin, which new shells don't have on PATH. Add it once.
if [[ "$OS" == macos ]]; then
  rc_file="$HOME/.zshrc"
else
  rc_file="$HOME/.bashrc"
fi
if ! grep -qs '\.local/bin' "$rc_file"; then
  printf '\n# uv\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc_file"
  echo "Added ~/.local/bin to PATH in $rc_file (open a new terminal to pick it up)."
fi
