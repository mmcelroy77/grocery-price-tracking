# Shared helpers for the Windows-side scripts. Dot-source it.
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"  # make wsl.exe print UTF-8 instead of UTF-16

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path  # lib -> scripts -> root

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

# Run a script from scripts/ inside the distro, in the project root.
function Invoke-InWsl($Distro, [string[]]$ScriptArgs) {
    & wsl.exe -d $Distro --cd "$ProjectRoot" -- bash @ScriptArgs
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
    $linuxPath = (& wsl.exe -d $Distro -- wslpath -a "$ProjectRoot" | Out-String).Trim()
    & code --remote "wsl+$Distro" "$linuxPath"
}

# Open an interactive Ubuntu shell in the project with .venv active.
function Open-DevShell($Distro) {
    & wsl.exe -d $Distro --cd "$ProjectRoot" -- bash scripts/setup/dev_shell.sh
}
