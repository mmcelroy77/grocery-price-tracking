#!/usr/bin/env bash
# Run the release workflow (.github/workflows/release.yml) locally with act.
# Only the deploy job's local-safe steps run (terraform fmt, init without backend, validate): act has no
# GitHub OIDC, so AWS access and the approval gate can only be exercised on GitHub.
#   bash scripts/act/run_release.sh          # default: workflow_dispatch event, -j deploy
#   bash scripts/act/run_release.sh -n       # dry run (parse the workflow only)
source "$(dirname "$0")/../lib/act.sh"

# Default to the deploy job unless a job was chosen.
[[ " $* " == *" -j "* ]] || set -- "$@" -j deploy
run_act release.yml workflow_dispatch "$@"
