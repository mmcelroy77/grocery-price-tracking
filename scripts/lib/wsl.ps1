# Shared helpers for the Windows-side scripts. Dot-source it.
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"  # make wsl.exe print UTF-8 instead of UTF-16

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path  # lib -> scripts -> root
# The working copy lives in the distro's Linux home, not /mnt/c (the Windows file system is slow for uv, Spark and pytest).
$WslProjectName = "grocery-price-tracking"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Get-Distros {
    $out = & wsl.exe --list --quiet 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $out) { return @() }
    return @($out | ForEach-Object { ($_ -replace "`0", "").Trim() } | Where-Object { $_ })
}

function Assert-Distro($Distro) {
    if ((Get-Distros) -notcontains $Distro) {
        throw "$Distro is not installed. Run scripts\setup\setup.ps1 first."
    }
}

# Linux path of the project inside the distro, e.g. /home/you/projects/grocery-price-tracking.
function Get-WslProjectDir($Distro) {
    $linuxHome = (& wsl.exe -d $Distro -- printenv HOME | Out-String).Trim()
    return "$linuxHome/projects/$WslProjectName"
}

function Assert-WslProject($Distro) {
    $dir = Get-WslProjectDir $Distro
    & wsl.exe -d $Distro -- test -d $dir
    if ($LASTEXITCODE -ne 0) { throw "No project at $dir. Run scripts\setup\setup.ps1 first." }
}

# Run a script from scripts/ inside the distro, in the project root (or -Dir, a Linux path).
function Invoke-InWsl($Distro, [string[]]$ScriptArgs, [string]$Dir = $ProjectRoot) {
    & wsl.exe -d $Distro --cd "$Dir" -- bash @ScriptArgs
    if ($LASTEXITCODE -ne 0) { throw "'$($ScriptArgs -join ' ')' failed with exit code $LASTEXITCODE" }
}

# --- VS Code ---------------------------------------------------------------
function Update-SessionPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

# Make sure the `code` CLI exists (installing VS Code via winget if needed) and that the
# WSL extension is present. Returns $true if VS Code is ready to use.
function Install-VSCode {
    if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Host "VS Code not found and winget is unavailable. Install it from https://code.visualstudio.com" -ForegroundColor Yellow
            return $false
        }
        Write-Host "VS Code not found. Installing via winget..." -ForegroundColor Yellow
        & winget install --id Microsoft.VisualStudioCode -e --scope user `
            --accept-package-agreements --accept-source-agreements | Out-Host
        Update-SessionPath
        if (-not (Get-Command code -ErrorAction SilentlyContinue)) {
            Write-Host "VS Code installed but 'code' isn't on PATH yet. Open a new terminal and re-run." -ForegroundColor Yellow
            return $false
        }
    }
    Write-Host "VS Code found."

    $ext = "ms-vscode-remote.remote-wsl"
    if ((& code --list-extensions) -notcontains $ext) {
        Write-Host "Installing VS Code WSL extension..."
        & code --install-extension $ext | Out-Null
    }
    Write-Host "WSL extension present."
    return $true
}

# Open the project in VS Code, connected to the distro (so the terminal, Python and venv are Linux).
function Open-InVSCode($Distro) {
    & code --remote "wsl+$Distro" (Get-WslProjectDir $Distro)
}

# Open an interactive Ubuntu shell in the project with .venv active.
function Open-DevShell($Distro) {
    & wsl.exe -d $Distro --cd (Get-WslProjectDir $Distro) -- bash scripts/setup/dev_shell.sh
}
