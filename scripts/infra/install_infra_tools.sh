#!/usr/bin/env bash
# Install the CLIs for deploying to AWS + Databricks: Terraform, AWS CLI, Databricks CLI.
# macOS only for now (Homebrew). Skips anything already installed. Safe to re-run.
#   bash scripts/infra/install_infra_tools.sh
source "$(dirname "$0")/../lib/common.sh"
[[ "$OS" == macos ]] || die "install_infra_tools.sh supports macOS only (Homebrew) for now."
command -v brew >/dev/null || die "Homebrew not found. Install it from https://brew.sh, then re-run."

# install <command> <brew formula> [tap]
install() {
  local cmd="$1" formula="$2" tap="${3:-}"
  step "$cmd"
  if command -v "$cmd" >/dev/null; then
    echo "$cmd already present."
    return
  fi
  [[ -z "$tap" ]] || brew tap "$tap"
  brew install "$formula"
  command -v "$cmd" >/dev/null || die "$cmd install failed"
}

# Terraform moved out of homebrew-core when HashiCorp changed its license; use their tap.
install terraform hashicorp/tap/terraform hashicorp/tap
install aws awscli
install databricks databricks/tap/databricks databricks/tap

step "Installed"
terraform version | head -1
aws --version
databricks --version

cat <<'MSG'

Next (interactive, so not automated here):
  aws configure sso && aws sso login     # AWS credentials
  databricks auth login --host <workspace-url>
  cd infra && terraform init && terraform plan
MSG
