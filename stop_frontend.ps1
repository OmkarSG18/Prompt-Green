<#
.SYNOPSIS
    Stops the PromptGreen V2 independent frontend server.
.DESCRIPTION
    Terminates the frontend process listening on port 8080 and releases the port.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8080,
    [string]$PidFile = "logs\frontend.pid",
    [int]$TimeoutSeconds = 8
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$absPidPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $PidFile))
$recordedPid = $null
if (Test-Path $absPidPath) {
    $raw = (Get-Content $absPidPath -Raw).Trim()
    if ($raw -match '^\d+$') {
        $recordedPid = [int]$raw
    }
}

# Check listener on port 8080
$listeningPid = $null
try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($conns) {
        $listeningPid = $conns[0].OwningProcess
    }
} catch {
    $netstatOut = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING"
    if ($netstatOut) {
        $tokens = ($netstatOut[0].Line -split '\s+') | Where-Object { $_ -ne '' }
        $listeningPid = [int]$tokens[-1]
    }
}

if (-not $listeningPid -and -not $recordedPid) {
    Write-Host "[INFO] Frontend server is not running on port $Port." -ForegroundColor Yellow
    exit 0
}

$targetPid = if ($listeningPid) { $listeningPid } else { $recordedPid }
$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue

Write-Host "[STOPPING] Stopping PromptGreen frontend process (PID: $targetPid) on port $Port ..." -ForegroundColor Cyan
if ($proc) {
    try {
        Stop-Process -Id $targetPid -Force -ErrorAction Stop
    } catch {
        Write-Host "[WARNING] Could not terminate process: $_" -ForegroundColor Yellow
    }
}

# Wait for release
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$released = $false
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Milliseconds 300
    $stillListening = $false
    try {
        $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($c) { $stillListening = $true }
    } catch {
        $ns = netstat -ano -p tcp | Select-String ":$Port\s+.*LISTENING"
        if ($ns) { $stillListening = $true }
    }

    if (-not $stillListening) {
        $released = $true
        break
    }
}

if (Test-Path $absPidPath) {
    Remove-Item $absPidPath -Force -ErrorAction SilentlyContinue
}

if ($released) {
    Write-Host "[SUCCESS] Frontend stopped cleanly. Port $Port is released." -ForegroundColor Green
    exit 0
} else {
    Write-Host "[WARNING] Frontend process stopped, but port $Port may still be in teardown." -ForegroundColor Yellow
    exit 1
}
