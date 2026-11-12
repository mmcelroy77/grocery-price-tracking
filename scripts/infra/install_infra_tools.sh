#!/usr/bin/env bash
# Install the CLIs for deploying to AWS + Databricks: Terraform, AWS CLI, Databricks CLI.
#   Linux/WSL: HashiCorp apt repo + AWS CLI v2 zip + Databricks install script (needs sudo)
#   macOS:     Homebrew
# Skips anything already installed. Safe to re-run.
#   bash scripts/infra/install_infra_tools.sh
source "$(dirname "$0")/../lib/common.sh"

# Each installer is a no-op if the command is already on PATH, so the script is safe to re-run.
if [[ "$OS" == macos ]]; then
  command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh, then re-run."
fi

# install <command> <installer function>
install() {
  local cmd="$1" installer="$2"
  step "$cmd"
  if command -v "$cmd" >/dev/null; then
    echo "$cmd already present."
    return
  fi
  "$installer"
  command -v "$cmd" >/dev/null || die "$cmd install failed"
}

# --- macOS (Homebrew) ---
# Terraform moved out of homebrew-core when HashiCorp changed its license; use their tap.
install_terraform_macos()   { brew tap hashicorp/tap && brew install hashicorp/tap/terraform; }
install_aws_macos()         { brew install awscli; }
install_databricks_macos()  { brew tap databricks/tap && brew install databricks/tap/databricks; }

# --- Linux/WSL (Ubuntu/Debian, needs sudo) ---
install_terraform_linux() {
  sudo apt-get update -y
  sudo apt-get install -y curl gpg lsb-release ca-certificates
  curl -fsSL https://apt.releases.hashicorp.com/gpg \
    | sudo gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/hashicorp.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y terraform
}

install_aws_linux() {
  local arch tmp
  case "$(uname -m)" in
    x86_64)  arch=x86_64 ;;
    aarch64) arch=aarch64 ;;
    *) die "Unsupported CPU architecture for AWS CLI: $(uname -m)" ;;
  esac
  command -v unzip >/dev/null || { sudo apt-get update -y; sudo apt-get install -y unzip curl; }
  tmp="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$arch.zip" -o "$tmp/awscliv2.zip"
  unzip -q "$tmp/awscliv2.zip" -d "$tmp"
  sudo "$tmp/aws/install" --update
  rm -rf "$tmp"
}

# Databricks' official installer puts the binary in /usr/local/bin (uses sudo itself if needed).
install_databricks_linux() {
  curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
}

install terraform "install_terraform_$OS"
install aws "install_aws_$OS"
install databricks "install_databricks_$OS"

step "Installed"
terraform version | head -1
aws --version
databricks --version

cat <<'MSG'

Next (interactive, so not automated here):
  aws configure sso && aws sso login     # AWS credentials
  databricks auth login --host <workspace-url>
  terraform -chdir=infra init && terraform -chdir=infra plan
MSG
