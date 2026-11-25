@echo off
setlocal enabledelayedexpansion

REM ===============================================================================
REM   PromptGreen V2 - Application Stopper
REM   Terminate local PromptGreen server process listening on port 8000
REM ===============================================================================

echo ===============================================================================
echo   PROMPTGREEN V2: STOPPING LOCAL SERVICES
echo ===============================================================================
echo(

cd /d "%~dp0"

echo Searching for active processes listening on port 8000...
set KILLED_COUNT=0

REM Locate and inspect TCP LISTENING processes on port 8000
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:":8000.*LISTENING"') do (
    set "TARGET_PID=%%p"
    if defined TARGET_PID if not "!TARGET_PID!"=="0" (
        set "PROC_NAME=unknown"
        for /f "tokens=1 delims=," %%a in ('tasklist /fi "PID eq !TARGET_PID!" /fo csv /nh 2^>nul') do (
            set "PROC_NAME=%%~a"
        )
        
        set "SHOULD_KILL=1"
        REM If process name is known and not python, protect it
        if defined PROC_NAME (
            if /i not "!PROC_NAME!"=="unknown" (
                if /i not "!PROC_NAME!"=="python.exe" (
                    if /i not "!PROC_NAME!"=="pythonw.exe" (
                        set "SHOULD_KILL=0"
                        echo [WARNING] Port 8000 is held by !PROC_NAME! [PID !TARGET_PID!]. Skipping termination to protect unrelated applications.
                    )
                )
            )
        )
        
        if !SHOULD_KILL! equ 1 (
            echo Terminating PromptGreen server process: !PROC_NAME! [PID !TARGET_PID!] on port 8000...
            taskkill /F /PID !TARGET_PID! >nul 2>&1
            set /a KILLED_COUNT+=1
        )
    )
)

REM Verify that the TCP listener on port 8000 has been released
set "STILL_LISTENING=0"
for /l %%w in (1,1,5) do (
    set "CHECK_LISTEN=0"
    for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:":8000.*LISTENING"') do (
        if not "%%p"=="0" set "CHECK_LISTEN=1"
    )
    if !CHECK_LISTEN! equ 0 (
        goto PORT_FREE
    )
    timeout /t 1 /nobreak >nul 2>&1
)

set "STILL_LISTENING=1"

:PORT_FREE
echo(
if !STILL_LISTENING! equ 1 (
    echo [ERROR] Port 8000 is still listening after termination attempt.
    exit /b 1
)

if !KILLED_COUNT! gtr 0 (
    echo [SUCCESS] Terminated !KILLED_COUNT! PromptGreen server process. Port 8000 is now free.
) else (
    echo [INFO] No active listener found on port 8000. Port is free.
)

exit /b 0
