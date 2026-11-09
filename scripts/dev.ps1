<#
.SYNOPSIS
  Open the project for day-to-day work: VS Code connected to WSL (default),
  or an Ubuntu shell with .venv active (-Shell).
.USAGE
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1           # VS Code
  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 -Shell    # terminal
#>
param(
    [string]$Distro = "Ubuntu-24.04",
    [switch]$Shell
)
. "$PSScriptRoot\lib\wsl.ps1"

Assert-Distro $Distro
if ($Shell) {
    Open-DevShell $Distro
} elseif (Install-VSCode) {
    Open-InVSCode $Distro
} else {
    throw "VS Code isn't available. Install it, or use -Shell."
}
