<#
.SYNOPSIS
    Starts the PromptGreen V2 independent static frontend server.
.DESCRIPTION
    Runs Website\frontend_server.py on http://127.0.0.1:8080 independently of the backend API.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8080,
    [string]$LogFile = "logs\frontend.log",
    [string]$PidFile = "logs\frontend.pid",
    [switch]$NoBrowser,
    [int]$TimeoutSeconds = 10
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
        $tokens = ($netstatOut[0].Line -split '\s+') | Where-Object { $_ -ne '' }
        $ownerPid = [int]$tokens[-1]
        $isPortListening = $true
    }
}

if ($isPortListening) {
    Write-Host "[INFO] Frontend is already listening on http://${HostAddress}:${Port} (PID: $ownerPid)." -ForegroundColor Green
    Set-Content -Path (Join-Path $ProjectRoot $PidFile) -Value $ownerPid -Force
    if (-not $NoBrowser) {
        Start-Process "http://${HostAddress}:${Port}"
    }
    exit 0
}

# 4. Launch frontend server in background
Write-Host "[STARTING] Launching PromptGreen V2 independent frontend on http://${HostAddress}:${Port} ..." -ForegroundColor Cyan

$absLogPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $LogFile))
$absPidPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PidFile))
$frontendScript = Join-Path $ProjectRoot "Website\frontend_server.py"

$proc = Start-Process -FilePath $PythonExe `
    -ArgumentList "`"$frontendScript`"", "--host", $HostAddress, "--port", "$Port" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $absLogPath `
    -RedirectStandardError (Join-Path $LogDir "frontend_err.log") `
    -WindowStyle Hidden `
    -PassThru

if (-not $proc -or $proc.HasExited) {
    Write-Host "[ERROR] Failed to launch frontend process." -ForegroundColor Red
    exit 1
}

Set-Content -Path $absPidPath -Value $proc.Id -Force

# 5. Polling readiness check
Write-Host "[WAITING] Verifying frontend readiness on http://${HostAddress}:${Port} ..." -NoNewline
$ready = $false
$url = "http://${HostAddress}:${Port}/"
$sw = [System.Diagnostics.Stopwatch]::StartNew()

while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Milliseconds 300
    Write-Host "." -NoNewline

    try {
        $resp = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {}
}

Write-Host ""
if ($ready) {
    Write-Host "[SUCCESS] PromptGreen frontend is ONLINE and ACCESSIBLE!" -ForegroundColor Green
    Write-Host "          PID:        $($proc.Id)"
    Write-Host "          Studio:     http://${HostAddress}:${Port}/"
    Write-Host "          Evaluation: http://${HostAddress}:${Port}/evaluation"
    Write-Host "          Log:        $absLogPath"

    if (-not $NoBrowser) {
        Write-Host "[BROWSER] Opening Green Prompt Studio in default browser..." -ForegroundColor Cyan
        Start-Process "http://${HostAddress}:${Port}"
    }
    exit 0
} else {
    Write-Host "[ERROR] Frontend startup timed out after $TimeoutSeconds seconds." -ForegroundColor Red
    exit 1
}
