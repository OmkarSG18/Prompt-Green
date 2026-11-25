<#
.SYNOPSIS
    Reports the operational health and lifecycle status of the PromptGreen V2 backend.
.DESCRIPTION
    Distinguishes four distinct operational states:
    1. RUNNING AND HEALTHY
    2. RUNNING BUT UNHEALTHY
    3. NOT RUNNING
    4. PORT OCCUPIED BY AN UNRELATED PROCESS
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PidFile = "logs\backend.pid"
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$absPidPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PidFile))

$recordedPid = $null
if (Test-Path $absPidPath) {
    $raw = (Get-Content $absPidPath -Raw).Trim()
    if ($raw -match '^\d+$') {
        $recordedPid = [int]$raw
    }
}

# 1. Check port listener
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
    Write-Host "Detail: Port $Port is not in use."
    if ($recordedPid) {
        Write-Host "Notice: Stale PID file exists with recorded PID $recordedPid." -ForegroundColor DarkGray
    }
    exit 0
}

# 2. Check health endpoint
$healthUrl = "http://${HostAddress}:${Port}/api"
$healthOk = $false
$resp = $null
try {
    $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
    if ($resp.system -eq "PromptGreen") {
        $healthOk = $true
    }
} catch {}

if ($healthOk) {
    Write-Host "STATE: RUNNING AND HEALTHY" -ForegroundColor Green
    Write-Host "System:    $($resp.system) v$($resp.version)"
    Write-Host "Status:    $($resp.status)"
    Write-Host "PID:       $listeningPid"
    Write-Host "Port:      $Port"
    Write-Host "URL:       http://${HostAddress}:${Port}"
    Write-Host "Health:    $healthUrl"
    if ($resp.model_prewarming) {
        Write-Host "Prewarmed: $($resp.model_prewarming.is_prewarmed) ($($resp.model_prewarming.model_name))"
    }
    exit 0
}

# 3. Port is listening but health probe failed: determine whether PromptGreen or unrelated
$isPromptGreenProc = $false
$pName = "Unknown"
$cmdLine = ""
try {
    $proc = Get-Process -Id $listeningPid -ErrorAction SilentlyContinue
    if ($proc) { $pName = $proc.ProcessName }
    $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $listeningPid" -ErrorAction SilentlyContinue
    if ($wmi) { $cmdLine = $wmi.CommandLine }
} catch {}

if ($cmdLine -like "*promptgreen*" -or $cmdLine -like "*uvicorn*" -or ($recordedPid -and $listeningPid -eq $recordedPid)) {
    $isPromptGreenProc = $true
}

if ($isPromptGreenProc) {
    Write-Host "STATE: RUNNING BUT UNHEALTHY" -ForegroundColor Yellow
    Write-Host "Detail: PromptGreen process (PID: $listeningPid, Name: $pName) is active on port $Port, but health check $healthUrl did not respond."
    exit 2
} else {
    Write-Host "STATE: PORT OCCUPIED BY AN UNRELATED PROCESS" -ForegroundColor Red
    Write-Host "Detail: Port $Port is currently occupied by PID $listeningPid ($pName)."
    if ($cmdLine) {
        Write-Host "CommandLine: $cmdLine"
    }
    exit 3
}
