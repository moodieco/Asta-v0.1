# asta share-tailscale (Windows) — a STABLE public https URL through Tailscale Funnel.
#
#   .\scripts\share-tailscale.ps1            # dashboard (if needed) + funnel + links
#   .\scripts\share-tailscale.ps1 -Status    # what the funnel is serving now
#   .\scripts\share-tailscale.ps1 -Off       # stop serving publicly
#
# The hostname does not change: https://<machine>.<tailnet>.ts.net
# Prerequisites, once per machine:
#   * Tailscale installed and logged in              -> tailscale up
#   * MagicDNS + HTTPS Certificates enabled          -> https://login.tailscale.com/admin/dns

param(
    [switch]$Off,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Port = if ($env:ASTA_PORT) { $env:ASTA_PORT } else { "4310" }
$Logs = Join-Path $Root "data\logs"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Asta = Join-Path $Root ".venv\Scripts\asta.exe"

function Get-Tailscale {
    $cmd = Get-Command tailscale.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $fallback = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $fallback) { return $fallback }
    throw "tailscale not found. Install it with: winget install --id Tailscale.Tailscale -e"
}

function Test-Port {
    param([int]$Port)
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $client.Connect("127.0.0.1", $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

$ts = Get-Tailscale

if ($Off) {
    & $ts funnel reset
    Write-Host "funnel stopped — the dashboard is local-only again (http://127.0.0.1:$Port)"
    exit 0
}

if ($Status) {
    & $ts funnel status
    exit 0
}

& $ts status *> $null
if ($LASTEXITCODE -ne 0) {
    throw "tailscale is installed but not connected — run: & `"$ts`" up"
}

if (-not (Test-Port -Port $Port)) {
    if (-not (Test-Path $Asta)) { throw "missing $Asta — run: py -3.12 -m venv .venv; .\.venv\Scripts\pip install -e ." }
    Write-Host "→ starting dashboard on 127.0.0.1:$Port"
    New-Item -ItemType Directory -Force -Path $Logs | Out-Null
    Start-Process -FilePath $Asta `
        -ArgumentList "serve", "--host", "127.0.0.1", "--port", $Port, "--no-browser" `
        -WorkingDirectory $Root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $Logs "dashboard.log") `
        -RedirectStandardError (Join-Path $Logs "dashboard.err.log")
    $deadline = (Get-Date).AddSeconds(25)
    while ((Get-Date) -lt $deadline -and -not (Test-Port -Port $Port)) { Start-Sleep -Milliseconds 500 }
    if (-not (Test-Port -Port $Port)) { throw "dashboard did not start — see data\logs\dashboard.log" }
} else {
    Write-Host "→ dashboard already listening on :$Port"
}

& $ts funnel --bg $Port *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host @"
funnel failed. The usual cause is HTTPS certificates being disabled for the tailnet.
Open https://login.tailscale.com/admin/dns and enable:
  * MagicDNS
  * HTTPS Certificates
then re-run this script.
"@ -ForegroundColor Yellow
    exit 1
}

$status = & $ts status --json | ConvertFrom-Json
$HostName = $status.Self.DNSName.TrimEnd('.')

$share = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/share" -TimeoutSec 10
$editor = $share.editorToken
$viewer = $share.viewerToken

Write-Host ""
Write-Host "Stable (Tailscale Funnel):"
Write-Host "  viewer  https://$HostName/?token=$viewer"
Write-Host "  editor  https://$HostName/?token=$editor"
Write-Host ""
Write-Host "Local (this machine only):"
Write-Host "  http://127.0.0.1:$Port/?token=$editor"
Write-Host ""
Write-Host "Viewer = read-only. Editor = full control, only share it if you mean it."
Write-Host "Funnel is PUBLIC: anyone with the URL reaches the token page. Keep the editor link private."
Write-Host "Stop sharing with: .\scripts\share-tailscale.ps1 -Off"
