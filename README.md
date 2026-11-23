# Grocery Price Tracking

PySpark project that runs locally in WSL.

## Layout
```
src/grocery_price_tracking/
  spark.py          # SparkSession factory (one place for config; Delta always on)
  common/           # shared helpers: aws_auth.py (credentials -> S3A), storage.py (read/write)
  transforms/       # pure DataFrame -> DataFrame logic (unit-tested)
  jobs/             # entry points: read input, call transforms, write output
  orchestration/    # Dagster definitions: the jobs as assets (retries, run metadata)
tests/              # pytest, shared `spark` fixture in conftest.py
data/raw/           # input data
infra/              # Terraform for AWS (architecture diagram in infra/README.md)
scripts/
  setup/            # project setup (see below)
  act/              # local CI: act + actionlint
```

## Setup (one time)
From the project root in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup\setup.ps1
```
Installs WSL + Ubuntu 24.04 if missing (admin shell needed the first time), installs Java 21 and
[uv](https://docs.astral.sh/uv/), runs `uv sync` to build `.venv`, runs the tests, and drops you
checks VS Code (installs it via winget plus the WSL extension if missing), and opens the project
in VS Code connected to Ubuntu. Use `-Open shell` for a terminal instead, or `-Open none`.
Safe to re-run. The first time VS Code opens, accept the recommended Python extensions so they
install on the WSL side.

The project is copied to `~/projects/grocery-price-tracking` inside Ubuntu, and all work happens
there. Don't work from the Windows copy under `/mnt/c`: uv, Spark and pytest are much slower on it.
Setup never overwrites an existing copy in `~/projects`, so re-running it is safe.

Dependencies are managed with uv: `uv add <pkg>` (or `uv add --dev <pkg>`) updates
`pyproject.toml` and `uv.lock`; commit both. `uv sync` brings your `.venv` up to date.

### Setup scripts
Every script is safe to re-run; pick only the parts you want.

| Script | Where | Does |
|---|---|---|
| `setup.ps1 [-Open code\|shell\|none]` | Windows | WSL + Ubuntu, `setup_wsl.sh`, VS Code check, then open project |
| `dev.ps1 [-Shell]` | Windows | Open project in VS Code (WSL), or an Ubuntu shell with venv active |
| `setup_wsl.sh [--shell]` | Linux/WSL | Runs the three steps below in order |
| `setup_macos.sh [--shell]` | macOS | Same steps as `setup_wsl.sh`, using Homebrew for Java |
| `install_system_deps.sh` | Linux/macOS | Java 21 (apt on Linux, Homebrew `openjdk@21` on macOS) + uv |
| `sync_deps.sh` | Linux/macOS | `uv sync`: `.venv` + project/dev deps (rebuilds if broken) |
| `verify.sh` | Linux/macOS | Java/PySpark check + `uv run pytest` |
| `act/install_act.sh` | Linux/macOS | Installs Docker + [`act`](https://github.com/nektos/act) (local GitHub Actions runner) |
| `infra/install_infra_tools.sh` | Linux/macOS | Installs Terraform, AWS CLI, and Databricks CLI (apt/official installers on Linux, Homebrew on macOS) for deploying to AWS/Databricks |
| `dev_shell.sh` | Linux/macOS | Interactive shell with venv active |

Project setup scripts live in `scripts/setup/` (run as `bash scripts/setup/<name>.sh`); local CI
scripts live in `scripts/act/` and deploy tooling in `scripts/infra/` (run as `bash scripts/<dir>/<name>.sh`). Windows project setup scripts
are run as `powershell -ExecutionPolicy Bypass -File scripts\setup\<name>.ps1`.

On macOS, [Homebrew](https://brew.sh) is installed automatically if missing (may prompt for sudo).

## Run
In the VS Code terminal or a dev shell (`scripts\setup\dev.ps1 [-Shell]`):
```bash
gpt-sample        # or: python -m grocery_price_tracking.jobs.sample_job
gpt-eggs          # or: python -m grocery_price_tracking.jobs.qfc_eggs_job
pytest
```
Or from any Ubuntu shell in the project, without activating: `uv run gpt-sample`, `uv run pytest`.

Jobs write Delta tables by path only (e.g. `sample/avg_price_by_item`); `common/storage.py`
resolves where that lives. By default that's the S3 data bucket for your AWS account
(`s3a://grocery-price-tracking-<account id>-data`), using whatever credentials the AWS CLI would
(`aws login`, `aws configure`, SSO, env vars; set `AWS_PROFILE` for a non-default profile).
To keep everything on local disk instead:
```bash
GROCERY_LAKE_ROOT=data/processed gpt-sample
```
The first S3 run downloads `hadoop-aws` and the AWS SDK bundle (~600 MB) into `~/.ivy2.5.2`.

The session requests a 2 GB driver heap (`spark.driver.memory`) because Parquet reserves a
row group in memory for every writer it runs in parallel. Override it with
`SPARK_DRIVER_MEMORY` (e.g. `SPARK_DRIVER_MEMORY=4g`) on machines with many cores or for
larger writes.

## QFC egg search snapshots near 98012

`gpt-eggs` snapshots the product search results behind egg prices for the nearest
QFC to ZIP 98012 using the [Kroger public API](https://developer.kroger.com) (QFC
is a Kroger chain). Every product the search returns is kept, unfiltered, in the
Bronze table `bronze/kroger/products`. The store is resolved at runtime, so a
closed or renamed store does not break the job.

One-time setup:

1. Create a free app at <https://developer.kroger.com> with the Products and Locations APIs.
2. Copy `.env.example` to `.env` and fill in the two values:
   ```bash
   cp .env.example .env
   ```
   `.env` is ignored by git, and the job reads it from the project root. Real
   environment variables win, so CI should set `KROGER_CLIENT_ID` and
   `KROGER_CLIENT_SECRET` as secrets instead of using a file. You can also export
   them directly:
   ```bash
   export KROGER_CLIENT_ID=...
   export KROGER_CLIENT_SECRET=...
   ```
   In PowerShell use `$env:KROGER_CLIENT_ID = "..."` and `$env:KROGER_CLIENT_SECRET = "..."`.
3. Run `gpt-eggs` (or `uv run gpt-eggs`).

Optional settings: `KROGER_STORE_ZIP` (default `98012`) and `KROGER_CHAIN` (default `QFC`;
use `FREDMEYER` for a Fred Meyer store).

Each run writes one snapshot per store, search term and day to
`bronze/kroger/products`, partitioned by `captured_date`
(`bronze/kroger/products/captured_date=YYYY-MM-DD/`). Rows carry `store_location_id`,
`store_name`, `search_term` and `captured_date` alongside the API payload, so price
changes can be compared across days. Re-running on the same day replaces that day's
partition instead of appending a duplicate snapshot.

Egg filtering and effective-price calculation are the Silver step
(`egg_prices` in `transforms/kroger.py`); the job does not write Silver yet.

## Dagster

[Dagster](https://dagster.io) wraps the jobs as *assets*: `kroger_bronze_products` runs the egg
snapshot above, retries it twice if it fails (after 1 and 2 minutes), and records what it wrote
(table location, Delta version, rows, bytes, files). The definitions are in
`orchestration/definitions.py`, and `[tool.dagster]` in `pyproject.toml` points Dagster at them.

Open the UI, then click **Materialize** on the asset (it reads `.env` like `gpt-eggs` does):
```bash
export DAGSTER_HOME=$PWD/.dagster      # keeps run history in a git-ignored folder
uv run dagster dev                     # http://localhost:3000
```
Or run it once without the UI:
```bash
uv run dagster asset materialize -m grocery_price_tracking.orchestration.definitions \
    --select kroger_bronze_products
```
Add `GROCERY_LAKE_ROOT=data/processed` to either command to write to local disk instead of S3.
`.dagster/dagster.yaml` is the instance config (committed, so Dagster doesn't warn about a
missing one); the run history next to it is git-ignored. Dagster prints a one-time telemetry
notice when it first creates `DAGSTER_HOME`; add `telemetry: {enabled: false}` to
`.dagster/dagster.yaml` to opt out.

## Container image

The `Dockerfile` packages the project to run one Dagster asset and exit, which is how it will
run in AWS. It contains Java 21, Python 3.12, the project's dependencies (the Dagster CLI but
not its web UI) and the Spark jars, so a run doesn't download ~600 MB. It runs as a non-root
user. Secrets are never baked in: `.dockerignore` keeps `.env` out of the build, and you pass
credentials when you run it.

```bash
docker build -t grocery-price-tracking .       # ~4 minutes the first time
```

Run it on local disk (Kroger credentials from `.env`, output inside the container):
```bash
docker run --rm --env-file .env -e GROCERY_LAKE_ROOT=/tmp/lake grocery-price-tracking
```
Run it against the S3 data bucket, passing your current AWS credentials through the environment
(`aws login`, SSO and static keys all work; nothing is written to disk):
```bash
eval "$(aws configure export-credentials --format env)"
docker run --rm --env-file .env -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN \
    grocery-price-tracking
```
The entrypoint is `dagster asset materialize -m grocery_price_tracking.orchestration.definitions`
and the default argument is `--select kroger_bronze_products`, so another asset is just
`docker run ... grocery-price-tracking --select <asset>`.

The image is large (about 2.6 GB uncompressed, 1.4 GB of it Spark jars) because Spark needs the
Delta and S3 jars on disk. The build runs in the Build workflow and is skipped under `act`.

## Local CI (before you push a build pipeline)

Before adding a GitHub Actions build pipeline, you can validate it locally:

- **Static checks**: the pre-commit `actionlint` hook lints `.github/workflows/*.yml` locally (catches YAML, action reference, and expression errors before anything runs).
- **Full local run**: [`act`](https://github.com/nektos/act) runs your workflows in Docker containers that mirror the GitHub-hosted runners:
  ```bash
  bash scripts/act/install_act.sh        # Docker + act
  bash scripts/act/run_build.sh -j test  # build workflow: run the "test" job locally
  bash scripts/act/run_release.sh        # release workflow: terraform fmt/init/validate only (no AWS or OIDC under act)
  ```

`act` needs Docker running (Docker Desktop on macOS/Windows, Docker Engine on Linux/WSL) — `scripts/act/install_act.sh` installs it if missing. See the [act user guide](https://nektosact.com) for events, matrices, secrets, and inputs.

## Ruff & PEP 8 formatting standards
This project uses **Ruff** as a fast Python linter and formatter. It ensures all code follows PEP 8 style conventions consistently.

**What Ruff does:**
- Checks for errors (`E`), style issues (`F`), and best practices (`B`)
- Formats code to match PEP 8 (the Python style guide)
- Auto-fixes many issues on save

**How it works:**
- `ruff format` - reformats code (adds blank lines after docstrings, consistent indentation, etc.)
- `ruff check` - lints code for potential errors and style violations
- Pre-commit hooks run automatically on every commit to catch issues early
- Configuration is in `pyproject.toml` (line-length 88, pycache/venv exclusions)

**Running locally:**
To check formatting: `ruff format .`
To lint for errors: `ruff check .`
To fix what auto-fix can and show what can't: `ruff check . && ruff format .`

If a file fails Ruff checks, it **cannot be committed** — the pre-commit hook will block the commit until the code passes formatting and linting.