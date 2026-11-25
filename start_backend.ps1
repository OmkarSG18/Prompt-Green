<#
.SYNOPSIS
    Starts the PromptGreen V2 independent FastAPI/Uvicorn backend service.
.DESCRIPTION
    Launches Uvicorn with verified ASGI application import path 'promptgreen.api.server:app'.
    Runs as an independent background process, redirects logs to logs\backend.log, records PID,
    and performs an HTTP health check against /api to ensure readiness.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [string]$LogFile = "logs\backend.log",
    [string]$PidFile = "logs\backend.pid",
    [int]$TimeoutSeconds = 25
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

# 1. Ensure logs directory exists
$LogDir = Split-Path -Parent (Join-Path $ProjectRoot $LogFile)
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# 2. Locate Python executable
$PythonExe = $null
if (Test-Path (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) {
    $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
} elseif (Test-Path (Join-Path $ProjectRoot "venv\Scripts\python.exe")) {
    $PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
} else {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $PythonExe = $sysPython.Source
    }
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python interpreter was not found in .venv, venv, or system PATH." -ForegroundColor Red
    exit 1
}

# 3. Check if port is already active
$isPortListening = $false
$ownerPid = $null
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $isPortListening = $true
        $ownerPid = $conns[0].OwningProcess
    }
} catch {
    $netstatOut = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING"
    if ($netstatOut) {
        $isPortListening = $true
        $tokens = ($netstatOut[0].Line -split '\s+') | Where-Object { $_ -ne '' }
        $ownerPid = [int]$tokens[-1]
    }
}

if ($isPortListening) {
    # Probe the port to see if it is already a healthy PromptGreen instance
    $healthUrl = "http://${HostAddress}:${Port}/api"
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp.system -eq "PromptGreen") {
            Write-Host "[INFO] PromptGreen backend is already running and healthy on $healthUrl (PID: $ownerPid)." -ForegroundColor Green
            Set-Content -Path (Join-Path $ProjectRoot $PidFile) -Value $ownerPid -Force
            exit 0
        }
    } catch {}

    $procName = "Unknown"
    try {
        $p = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
        if ($p) { $procName = $p.ProcessName }
    } catch {}

    Write-Host "[ERROR] Port $Port is currently occupied by an UNRELATED or UNRESPONSIVE process (PID: $ownerPid, Process: $procName)." -ForegroundColor Red
    Write-Host "        PromptGreen safety policy REFUSES to kill unrelated processes." -ForegroundColor Red
    Write-Host "        Please free port $Port or stop the conflicting service before starting PromptGreen." -ForegroundColor Yellow
    exit 1
}

# 4. Launch backend in background
Write-Host "[STARTING] Launching PromptGreen V2 backend (promptgreen.api.server:app) on http://${HostAddress}:${Port} ..." -ForegroundColor Cyan

$env:PYTHONPATH = $ProjectRoot
$absLogPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $LogFile))
$absPidPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PidFile))

$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList "-m", "uvicorn", "promptgreen.api.server:app", "--host", $HostAddress, "--port", "$Port" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $absLogPath `
    -RedirectStandardError (Join-Path $LogDir "backend_err.log") `
    -WindowStyle Hidden `
    -PassThru

if (-not $proc -or $proc.HasExited) {
    Write-Host "[ERROR] Failed to launch backend process or it exited immediately." -ForegroundColor Red
    if (Test-Path $absLogPath) { Get-Content $absLogPath -Tail 15 }
    exit 1
}

Set-Content -Path $absPidPath -Value $proc.Id -Force

# 5. Polling Health Check Loop
Write-Host "[WAITING] Verifying backend readiness on http://${HostAddress}:${Port}/api ..." -NoNewline
$ready = $false
$healthUrl = "http://${HostAddress}:${Port}/api"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Milliseconds 500
    Write-Host "." -NoNewline

    if ($proc.HasExited) {
        Write-Host ""
        Write-Host "[ERROR] Backend process (PID: $($proc.Id)) crashed during startup." -ForegroundColor Red
        if (Test-Path $absLogPath) { Get-Content $absLogPath -Tail 20 }
        if (Test-Path (Join-Path $LogDir "backend_err.log")) { Get-Content (Join-Path $LogDir "backend_err.log") -Tail 20 }
        exit 1
    }

    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 1 -ErrorAction Stop
        if ($resp.system -eq "PromptGreen" -and $resp.status -eq "active") {
            $ready = $true
            break
        }
    } catch {}
}

Write-Host ""
if ($ready) {
    Write-Host "[SUCCESS] PromptGreen backend is ONLINE and HEALTHY!" -ForegroundColor Green
    Write-Host "          PID:      $($proc.Id)"
    Write-Host "          URL:      http://${HostAddress}:${Port}"
    Write-Host "          Health:   $healthUrl"
    Write-Host "          Log file: $absLogPath"
    Write-Host "          PID file: $absPidPath"
    exit 0
} else {
    Write-Host "[ERROR] Startup health check timed out after $TimeoutSeconds seconds." -ForegroundColor Red
    Write-Host "        Process PID: $($proc.Id) is running, but $healthUrl did not respond." -ForegroundColor Red
    exit 1
}
