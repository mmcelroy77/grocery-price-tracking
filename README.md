# Grocery Price Tracking

PySpark project that runs locally in WSL.

## Layout
```
src/grocery_price_tracking/
  spark.py          # SparkSession factory (one place for config)
  transforms/       # pure DataFrame -> DataFrame logic (unit-tested)
  jobs/             # entry points: read input, call transforms, write output
tests/              # pytest, shared `spark` fixture in conftest.py
data/raw/           # input data
scripts/            # dev setup (see below)
```

## Setup (one time)
From the project root in PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```
Installs WSL + Ubuntu 24.04 if missing (admin shell needed the first time), installs Java 17 and
[uv](https://docs.astral.sh/uv/), runs `uv sync` to build `.venv`, runs the tests, and drops you
checks VS Code (installs it via winget plus the WSL extension if missing), and opens the project
in VS Code connected to Ubuntu. Use `-Open shell` for a terminal instead, or `-Open none`.
Safe to re-run. The first time VS Code opens, accept the recommended Python extensions so they
install on the WSL side.

Dependencies are managed with uv: `uv add <pkg>` (or `uv add --dev <pkg>`) updates
`pyproject.toml` and `uv.lock`; commit both. `uv sync` brings your `.venv` up to date.

### Setup scripts
Every script is safe to re-run; pick only the parts you want.

| Script | Where | Does |
|---|---|---|
| `setup.ps1 [-Open code\|shell\|none]` | Windows | WSL + Ubuntu, `setup_wsl.sh`, VS Code check, then open project |
| `dev.ps1 [-Shell]` | Windows | Open project in VS Code (WSL), or an Ubuntu shell with venv active |
| `setup_wsl.sh [--shell]` | Linux | Runs the three steps below in order |
| `install_system_deps.sh` | Linux | Java 17 (apt, sudo) + uv |
| `sync_deps.sh` | Linux | `uv sync`: `.venv` + project/dev deps (rebuilds if broken) |
| `verify.sh` | Linux | Java/PySpark check + `uv run pytest` |
| `dev_shell.sh` | Linux | Interactive shell with venv active |

Linux scripts are run as `bash scripts/<name>.sh`; Windows ones as
`powershell -ExecutionPolicy Bypass -File scripts\<name>.ps1`.

## Run
In the VS Code terminal or a dev shell (`scripts\dev.ps1 [-Shell]`):
```bash
gpt-sample        # or: python -m grocery_price_tracking.jobs.sample_job
pytest
```
Or from any Ubuntu shell in the project, without activating: `uv run gpt-sample`, `uv run pytest`.
