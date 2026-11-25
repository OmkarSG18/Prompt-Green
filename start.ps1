<#
.SYNOPSIS
    Starts PromptGreen V2 in a single step.
.DESCRIPTION
    Starts the FastAPI backend service on port 8000, verifies health,
    starts the frontend server on port 8080, and opens the Green Prompt Studio in your browser.
#>
[CmdletBinding()]
param(
    [switch]$NoBrowser
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================================================" -ForegroundColor Green
Write-Host "   PROMPTGREEN V2: 1-STEP LAUNCHER" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green

# 1. Start backend service
& (Join-Path $ProjectRoot "start_backend.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Backend service failed to start." -ForegroundColor Red
    exit 1
}

# 2. Start frontend server and open browser
if ($NoBrowser) {
    & (Join-Path $ProjectRoot "start_frontend.ps1") -NoBrowser
} else {
    & (Join-Path $ProjectRoot "start_frontend.ps1")
}

Write-Host "`n[SUCCESS] PromptGreen V2 is ONLINE and fully connected!" -ForegroundColor Green
Write-Host "          Backend: http://127.0.0.1:8000"
Write-Host "          Studio:  http://127.0.0.1:8080"
