@echo off
setlocal enabledelayedexpansion

REM ===============================================================================
REM   PromptGreen V2 - Application Launcher
REM   Starts the unified web application and REST API server
REM ===============================================================================

echo ===============================================================================
echo   PROMPTGREEN V2: SUSTAINABLE LLM INFERENCE AND OPTIMIZATION ENGINE
echo   B.Tech Major Project Demonstration
echo ===============================================================================
echo(

cd /d "%~dp0"
echo [1/4] Project Directory: %CD%

REM 1. Locate Python Environment
set "PYTHON_EXE="
if exist "%CD%\.venv\Scripts\python.exe" (
    echo [2/4] Found local virtual environment: .venv
    set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
) else if exist "%CD%\venv\Scripts\python.exe" (
    echo [2/4] Found local virtual environment: venv
    set "PYTHON_EXE=%CD%\venv\Scripts\python.exe"
) else (
    echo [2/4] Detecting system Python environment...
    for /f "tokens=*" %%p in ('where python 2^>nul') do (
        if not defined PYTHON_EXE (
            set "PYTHON_EXE=%%p"
        )
    )
)

if not defined PYTHON_EXE (
    echo(
    echo [ERROR] Python was not found in your PATH or in a local virtual environment.
    echo Please install Python 3.10+ or activate your environment before launching.
    echo(
    pause
    exit /b 1
)

REM Verify Python runs
"%PYTHON_EXE%" --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo(
    echo [ERROR] The detected Python executable cannot run: %PYTHON_EXE%
    echo(
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%"
echo [3/4] PYTHONPATH configured: %PYTHONPATH%

REM 2. Check if PromptGreen is already running and healthy on port 8000
set "ALREADY_RUNNING=0"
for /f "tokens=5" %%p in ('netstat -ano -p tcp ^| findstr /r /c:":8000.*LISTENING"') do (
    if not "%%p"=="0" set "ALREADY_RUNNING=1"
)

if !ALREADY_RUNNING! equ 1 (
    echo [INFO] Port 8000 is currently active. Testing if PromptGreen is responding...
    "%PYTHON_EXE%" -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api', timeout=2)" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo [SUCCESS] PromptGreen V2 is already running and healthy on http://127.0.0.1:8000!
        echo Opening Green Prompt Studio in browser...
        start "" "http://127.0.0.1:8000"
        exit /b 0
    ) else (
        echo [WARNING] Port 8000 is occupied by an unresponsive process.
        echo Please run stop_promptgreen.bat first to free port 8000.
        echo(
        pause
        exit /b 1
    )
)

REM 3. Launch PromptGreen Server
echo [4/4] Starting PromptGreen Unified Web Application and API Server...
echo(
echo ===============================================================================
echo   LOCAL ACCESS URL:
echo     -- Green Prompt Studio:       http://127.0.0.1:8000
echo     -- Evolution ^& Evaluation:    http://127.0.0.1:8000/evaluation
echo     -- API Documentation:         http://127.0.0.1:8000/docs
echo(
echo   The browser will open automatically as soon as the server is ready.
echo   To stop the server at any time: press [Ctrl+C] or run stop_promptgreen.bat
echo ===============================================================================
echo(

"%PYTHON_EXE%" Website\server.py
set "SERVER_EXIT=!ERRORLEVEL!"

echo(
if !SERVER_EXIT! neq 0 (
    echo [NOTICE] PromptGreen server process exited with status !SERVER_EXIT!.
) else (
    echo [INFO] PromptGreen server stopped cleanly.
)

exit /b !SERVER_EXIT!
