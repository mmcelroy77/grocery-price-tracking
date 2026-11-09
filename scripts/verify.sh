#!/usr/bin/env bash
# Step 3: smoke test that Java, PySpark and the test suite all work.
source "$(dirname "$0")/lib/common.sh"
venv_ok || die ".venv missing or broken; run scripts/sync_deps.sh"

step "Verifying"
java -version 2>&1 | head -n1
uv run --frozen python -c "import pyspark; print('pyspark', pyspark.__version__)"
uv run --frozen pytest -q
