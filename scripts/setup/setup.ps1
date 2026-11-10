<#
.SYNOPSIS
  One-shot dev setup for Windows: ensures WSL + Ubuntu, installs Java/uv/deps inside
  Ubuntu, runs the tests, checks VS Code, then opens the project.

.USAGE
  From the project root in PowerShell:
    powershell -ExecutionPolicy Bypass -File scripts\setup\setup.ps1               # setup, open in VS Code
    powershell -ExecutionPolicy Bypass -File scripts\setup\setup.ps1 -Open shell   # setup, open Ubuntu shell
    powershell -ExecutionPolicy Bypass -File scripts\setup\setup.ps1 -Open none    # setup only
  Safe to re-run. Individual steps live in scripts\setup\*.sh / *.ps1 (see README).
#>
[CmdletBinding()]
param(
    [string]$Distro = "Ubuntu-24.04",
    [ValidateSet("code", "shell", "none")]
    [string]$Open = "code"
)
. "$PSScriptRoot\..\lib\wsl.ps1"

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 1. WSL itself
Write-Step "Checking WSL"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    if (-not (Test-IsAdmin)) {
        throw "WSL is not installed. Re-run this script from an *Administrator* PowerShell."
    }
    & wsl.exe --install --no-distribution
    Write-Host "WSL installed. Reboot Windows, then re-run this script." -ForegroundColor Yellow
    exit 0
}
Write-Host "WSL found."

# 2. Ubuntu distro
Write-Step "Checking for $Distro"
if ((Get-Distros) -notcontains $Distro) {
    Write-Host "$Distro not found. Installing..." -ForegroundColor Yellow
    Write-Host "You'll be asked to create a Linux username/password." -ForegroundColor Yellow
    Write-Host "When you land at the Linux prompt, type 'exit' to let setup continue." -ForegroundColor Yellow
    & wsl.exe --install -d $Distro
    if ((Get-Distros) -notcontains $Distro) {
        Write-Host "$Distro is not ready yet (a reboot may be required). Reboot and re-run this script." -ForegroundColor Yellow
        exit 1
    }
}
Write-Host "$Distro is installed."

# 3. Linux-side setup (system deps -> uv sync -> verify)
Write-Step "Running setup inside $Distro (you may be asked for your Linux sudo password)"
Invoke-InWsl $Distro @("scripts/setup/setup_wsl.sh")

# 4. VS Code + WSL extension (needed to open the project; checked even with -Open none/shell
#    so new joiners end up with a working editor)
Write-Step "Checking VS Code"
$codeReady = Install-VSCode

# 5. Open the project
Write-Step "Setup complete"
switch ($Open) {
    "code" {
        if ($codeReady) { Write-Host "Opening project in VS Code (WSL: $Distro)..."; Open-InVSCode $Distro }
        else { Write-Host "Skipping VS Code. Use: powershell -ExecutionPolicy Bypass -File scripts\setup\dev.ps1 -Shell" }
    }
    "shell" { Open-DevShell $Distro }
    "none"  { Write-Host "Open later with: powershell -ExecutionPolicy Bypass -File scripts\setup\dev.ps1 [-Shell]" }
}
