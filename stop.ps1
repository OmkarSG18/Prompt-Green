<#
.SYNOPSIS
    Stops all PromptGreen V2 services in a single step.
.DESCRIPTION
    Safely terminates both the port 8000 backend service and the port 8080 frontend server.
#>
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================================================" -ForegroundColor Yellow
Write-Host "   STOPPING ALL PROMPTGREEN V2 SERVICES" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Yellow

& (Join-Path $ProjectRoot "stop_backend.ps1")
& (Join-Path $ProjectRoot "stop_frontend.ps1")

Write-Host "`n[SUCCESS] All PromptGreen services stopped cleanly." -ForegroundColor Green
