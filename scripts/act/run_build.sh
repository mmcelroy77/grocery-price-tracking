#!/usr/bin/env bash
# Run the build workflow (.github/workflows/build.yml) locally with act.
#   bash scripts/act/run_build.sh            # default event: workflow_dispatch
#   bash scripts/act/run_build.sh -j test    # pass any act flags through
source "$(dirname "$0")/../lib/act.sh"

run_act build.yml workflow_dispatch "$@"
