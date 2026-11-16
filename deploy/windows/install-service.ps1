# ASTA as a Windows service (NSSM)
#
#   powershell -ExecutionPolicy Bypass -File .\deploy\windows\install-service.ps1
#   powershell -ExecutionPolicy Bypass -File .\deploy\windows\install-service.ps1 -Uninstall
#
# Requires an elevated PowerShell (one UAC prompt) and NSSM:
#   winget install --id NSSM.NSSM -e
#
# Runs the engine as a real service: starts before login, restarts on crash.
# data/ and .env live in the repo and are untouched by uninstall.

param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Asta = Join-Path $Root ".venv\Scripts\asta.exe"
$Logs = Join-Path $Root "data\logs"
$Service = "ASTA"

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this in an elevated PowerShell (Run as Administrator)."
}

$nssm = Get-Command nssm.exe -ErrorAction SilentlyContinue
if (-not $nssm) { throw "nssm not found. Install it with: winget install --id NSSM.NSSM -e" }

if ($Uninstall) {
    & $nssm.Source stop $Service 2>$null
    & $nssm.Source remove $Service confirm 2>$null
    Write-Host "→ service $Service removed (data\ and .env are untouched)"
    exit 0
}

if (-not (Test-Path $Asta)) {
    throw "missing $Asta — run: py -3.12 -m venv .venv; .\.venv\Scripts\pip install -e ."
}
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

# Re-install cleanly so the script is idempotent.
& $nssm.Source stop $Service 2>$null
& $nssm.Source remove $Service confirm 2>$null

& $nssm.Source install $Service $Asta serve --host 127.0.0.1 --port 4310 --no-browser
& $nssm.Source set $Service AppDirectory $Root
& $nssm.Source set $Service Start SERVICE_AUTO_START
& $nssm.Source set $Service AppStdout (Join-Path $Logs "service.out.log")
& $nssm.Source set $Service AppStderr (Join-Path $Logs "service.err.log")
& $nssm.Source set $Service AppRotateFiles 1
& $nssm.Source set $Service AppRotateBytes 5242880
& $nssm.Source set $Service AppExit Default Restart
& $nssm.Source set $Service AppRestartDelay 5000
& $nssm.Source start $Service

Start-Sleep -Seconds 3
$state = & $nssm.Source status $Service
Write-Host "→ service $Service: $state"
Write-Host "  keep the machine awake:  powercfg /change standby-timeout-ac 0"
Write-Host "  MT5 (forex) must also run: add its terminal shortcut to shell:startup"
Write-Host "  next: .\scripts\share-tailscale.ps1 -Status"
