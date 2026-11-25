<#
.SYNOPSIS
    Stops the PromptGreen V2 independent backend service safely.
.DESCRIPTION
    Verifies process ownership before terminating, releases port 8000,
    and protects unrelated applications from accidental termination.
#>
[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8000,
    [string]$PidFile = "logs\backend.pid",
    [int]$TimeoutSeconds = 10
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

# 1. Determine who is listening on port 8000
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

if (-not $listeningPid) {
    if ($recordedPid) {
        $staleProc = Get-Process -Id $recordedPid -ErrorAction SilentlyContinue
        if (-not $staleProc) {
            Remove-Item $absPidPath -Force -ErrorAction SilentlyContinue
            Write-Host "[INFO] PromptGreen backend is not running. Port $Port is free (stale PID file cleaned up)." -ForegroundColor Yellow
            exit 0
        }
    } else {
        Write-Host "[INFO] PromptGreen backend is not running. Port $Port is free." -ForegroundColor Yellow
        exit 0
    }
}

# 2. Ownership Verification
$targetPid = if ($listeningPid) { $listeningPid } else { $recordedPid }
$isPromptGreen = $false
$proc = Get-Process -Id $targetPid -ErrorAction SilentlyContinue

if ($proc) {
    if ($recordedPid -and $targetPid -eq $recordedPid) {
        $isPromptGreen = $true
    }

    if (-not $isPromptGreen) {
        try {
            $resp = Invoke-RestMethod -Uri "http://${HostAddress}:${Port}/api" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp.system -eq "PromptGreen") {
                $isPromptGreen = $true
            }
        } catch {}
    }

    if (-not $isPromptGreen) {
        try {
            $wmi = Get-CimInstance Win32_Process -Filter "ProcessId = $targetPid" -ErrorAction SilentlyContinue
            if ($wmi -and ($wmi.CommandLine -like "*promptgreen*" -or $wmi.CommandLine -like "*uvicorn*")) {
                $isPromptGreen = $true
            }
        } catch {}
    }
}

if (-not $isPromptGreen) {
    $pName = if ($proc) { $proc.ProcessName } else { "Unknown" }
    Write-Host "[WARNING] Port $Port is occupied by an UNRELATED process (PID: $targetPid, Name: $pName)." -ForegroundColor Red
    Write-Host "          PromptGreen stop script will NOT terminate unrelated services." -ForegroundColor Red
    exit 1
}

# 3. Terminate PromptGreen process safely
Write-Host "[STOPPING] Terminating PromptGreen backend process (PID: $targetPid, Name: $($proc.ProcessName)) ..." -ForegroundColor Cyan
try {
    Stop-Process -Id $targetPid -Force -ErrorAction Stop
} catch {
    Write-Host "[WARNING] Could not stop process directly: $_" -ForegroundColor Yellow
}

# 4. Wait for port release
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

# 5. Clean up PID file
if (Test-Path $absPidPath) {
    Remove-Item $absPidPath -Force -ErrorAction SilentlyContinue
}

if ($released) {
    Write-Host "[SUCCESS] PromptGreen backend stopped cleanly. Port $Port is now released." -ForegroundColor Green
    exit 0
} else {
    Write-Host "[WARNING] PromptGreen process was signaled, but port $Port is still in use." -ForegroundColor Yellow
    exit 1
}
