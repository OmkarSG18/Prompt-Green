<#
.SYNOPSIS
    Reports the status of the PromptGreen V2 independent frontend server.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8080,
    [string]$PidFile = "logs\frontend.pid"
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$listeningPid = $null
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) { $listeningPid = $conns[0].OwningProcess }
} catch {
    $netstatOut = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING"
    if ($netstatOut) {
        $tokens = ($netstatOut[0].Line -split '\s+') | Where-Object { $_ -ne '' }
        $listeningPid = [int]$tokens[-1]
    }
}

if (-not $listeningPid) {
    Write-Host "STATE: NOT RUNNING" -ForegroundColor Gray
    Write-Host "Detail: Port $Port is not listening."
    exit 0
}

$url = "http://${HostAddress}:${Port}/"
$isHealthy = $false
try {
    $resp = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $isHealthy = $true }
} catch {}

if ($isHealthy) {
    Write-Host "STATE: RUNNING AND HEALTHY" -ForegroundColor Green
    Write-Host "PID:   $listeningPid"
    Write-Host "Port:  $Port"
    Write-Host "URL:   $url"
    exit 0
} else {
    Write-Host "STATE: RUNNING BUT UNHEALTHY / OCCUPIED" -ForegroundColor Yellow
    Write-Host "PID:   $listeningPid"
    Write-Host "Port:  $Port"
    exit 2
}
