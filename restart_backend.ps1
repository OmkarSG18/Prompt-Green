<#
.SYNOPSIS
    Restarts the PromptGreen V2 independent backend service.
.DESCRIPTION
    Executes stop_backend.ps1 safely, verifies port release, and invokes start_backend.ps1.
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

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "   RESTARTING PROMPTGREEN V2 BACKEND SERVICE (PORT $Port)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# 1. Stop existing backend
& (Join-Path $ProjectRoot "stop_backend.ps1") -HostAddress $HostAddress -Port $Port -PidFile $PidFile
Start-Sleep -Seconds 1

# 2. Start fresh backend
& (Join-Path $ProjectRoot "start_backend.ps1") -HostAddress $HostAddress -Port $Port -LogFile $LogFile -PidFile $PidFile -TimeoutSeconds $TimeoutSeconds
