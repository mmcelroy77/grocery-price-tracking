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
| `act/run_act.sh` | Linux/macOS | Run workflows locally via `act` (e.g. `bash scripts/act/run_act.sh -j test`) |
| `dev_shell.sh` | Linux/macOS | Interactive shell with venv active |

Project setup scripts live in `scripts/setup/` (run as `bash scripts/setup/<name>.sh`); local CI
scripts live in `scripts/act/` (run as `bash scripts/act/<name>.sh`). Windows project setup scripts
are run as `powershell -ExecutionPolicy Bypass -File scripts\setup\<name>.ps1`.

macOS needs [Homebrew](https://brew.sh) installed first. The macOS scripts have not been tested on a Mac yet.

## Run
In the VS Code terminal or a dev shell (`scripts\setup\dev.ps1 [-Shell]`):
```bash
gpt-sample        # or: python -m grocery_price_tracking.jobs.sample_job
pytest
```
Or from any Ubuntu shell in the project, without activating: `uv run gpt-sample`, `uv run pytest`.

## Local CI (before you push a build pipeline)

Before adding a GitHub Actions build pipeline, you can validate it locally:

- **Static checks**: the pre-commit `actionlint` hook lints `.github/workflows/*.yml` locally (catches YAML, action reference, and expression errors before anything runs).
- **Full local run**: [`act`](https://github.com/nektos/act) runs your workflows in Docker containers that mirror the GitHub-hosted runners:
  ```bash
  bash scripts/act/install_act.sh      # Docker + act
  bash scripts/act/run_act.sh -j test  # run the "test" job locally
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