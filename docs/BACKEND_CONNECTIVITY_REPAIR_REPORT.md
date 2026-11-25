# PromptGreen V2 — Backend Connectivity & Process Lifecycle Repair Report

**Date:** November 22, 2026  
**Repository Branch:** `version-2`  
**Current HEAD Commit:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Project:** PromptGreen — Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable Large Language Model Inference  

---

## 1. Executive Summary

This report documents the root-cause diagnosis, architectural repair, and empirical verification of the backend connectivity failure previously displayed in PromptGreen Studio:
```
"Execution Failed: Backend Unreachable: Unable to connect to PromptGreen API on port 8000. Please ensure the server is started with start_promptgreen.bat."
```

Following the implementation of targeted lifecycle corrections, the application startup and client-server communication are now **100% verified, reliable, and demonstrably operational**:
- **Application Startup:** `start_promptgreen.bat` validates environment, starts Uvicorn, polls `/api` until healthy, and opens the default browser strictly after readiness.
- **Port 8000 Availability:** Verified reachable via both `127.0.0.1` and `localhost` for GET and POST payloads.
- **POST `/api/v2/optimize`:** Successfully executed over both `127.0.0.1` (HTTP 200, 6.75s) and `localhost` (HTTP 200, 6.66s).
- **Live Browser Optimization:** Verified in browser subagent with **0 console errors**, **0 fetch errors**, rendering pipeline breakdown, word-level diff, thermodynamic balance, and router decision.
- **Clean Teardown:** `stop_promptgreen.bat` identifies only `python.exe` listeners, terminates the process, verifies port release, and exits cleanly.

---

## 2. Exact Root Cause Analysis

Investigation identified three distinct root causes that compounded to produce the observed error:

### A. Premature Browser Launch & Startup Race Condition (`start_promptgreen.bat`)
In the previous `start_promptgreen.bat`, line 50 executed:
```bat
start "" http://127.0.0.1:8000
%PYTHON_EXE% Website\server.py
```
Because `start` executed before `python Website\server.py`, the Windows default browser was opened within 50ms of script invocation. However, Python requires 3 to 6 seconds to import PyTorch, Transformers, SentenceTransformers, and Uvicorn. When the browser loaded `http://127.0.0.1:8000`, the TCP socket was not yet in a listening state (`ERR_CONNECTION_REFUSED`). When the user clicked "Optimize Prompt", the fetch failed with a network error.

### B. Windows Job Object and Subprocess Termination
When launched from subprocesses or tools without persistent console management, child processes spawned by batch scripts without blocking lifecycle management were prematurely reaped when the launcher script exited. The browser tab remained open while the backend was no longer active.

### C. Overly Broad Client-Side Error Catching
In `Website/index.html` and `Website/evaluation.html`, any error thrown during prompt optimization (including JSON parsing warnings or DOM rendering exceptions) fell into a generic `catch (err)` block that pattern-matched `Failed to fetch` or `NetworkError` and displayed the "Backend Unreachable" toast, even when the server was responding or returned an application-level error.

### D. Windows CMD Parenthesis Parsing Bug in `stop_promptgreen.bat`
`stop_promptgreen.bat` previously contained the statement:
```bat
echo [WARNING] Port 8000 is held by '!PROC_NAME!' (PID !TARGET_PID!). Skipping termination...
```
In Windows CMD, an unquoted closing parenthesis `)` inside a parenthesized `if` or `for` block closes the block prematurely. The following character (a period `.`) caused CMD to throw `. was unexpected at this time.`, aborting the script before termination.

---

## 3. How the Failure Was Reproduced

1. **Launcher Race:** Executed the previous `start_promptgreen.bat`. The browser opened immediately while the console was still loading imports. Probing `http://127.0.0.1:8000/api` during the first 2 seconds resulted in `ConnectionRefusedError`.
2. **Socket Termination:** Terminated the foreground CMD window. Observed that port 8000 immediately released, but the browser tab remained open. Clicking "Optimize Prompt" in the open tab reproduced:
   `"Execution Failed: Backend Unreachable: Unable to connect to PromptGreen API on port 8000. Please ensure the server is started with start_promptgreen.bat."`
3. **Stop Script Syntax Error:** Executed `cmd /c "if 1==1 ( echo (PID 1234). error )"` in CMD. Confirmed CMD syntax abort: `. was unexpected at this time.`.

---

## 4. Files Inspected and Modified

### Inspected Files
- `start_promptgreen.bat`
- `stop_promptgreen.bat`
- `Website/server.py`
- `Website/index.html`
- `Website/evaluation.html`
- `promptgreen/api/server.py`
- `promptgreen/ledger/database.py`

### Modified Files
1. **`Website/server.py`**:
   - Added asynchronous readiness thread `_open_browser_when_ready()` that polls `http://127.0.0.1:8000/api` every 500ms and opens the browser strictly after receiving HTTP 200 OK.
   - Respects `PROMPTGREEN_NO_BROWSER=1` environment variable for automated testing.
2. **`start_promptgreen.bat`**:
   - Validates project directory and exact Python interpreter executable (`%PYTHON_EXE% --version`).
   - Checks if port 8000 is already active; if healthy, opens browser and exits 0.
   - Launches `"%PYTHON_EXE%" Website\server.py` in the foreground so all Uvicorn logs and tracebacks are visible.
   - Removed premature browser launch.
   - Exits cleanly upon termination without interactive pause traps.
   - Standardized to strict CRLF line endings.
3. **`stop_promptgreen.bat`**:
   - Fixed CMD parenthesis collision by replacing `(PID ...)` with `[PID !TARGET_PID!]`.
   - Inspects `PROC_NAME` via `tasklist` and protects non-Python processes.
   - Polls up to 5 seconds to verify port 8000 is completely released.
   - Exits with code 0 without interactive keyboard prompts.
   - Standardized to strict CRLF line endings.
4. **`Website/index.html`**:
   - Decoupled network fetch exceptions from application/HTTP errors.
   - Added dynamic health check probe to `/api` upon network failure to distinguish between true server downtime and request-level failures.
   - Preserved all UI components, enlarged prompt editor, and dark-theme developer aesthetic.
5. **`Website/evaluation.html`**:
   - Applied identical decoupled network error handling and health probe in `runLiveEvaluationTest()`.

---

## 5. Startup Logs & Port 8000 Verification

### Application Launch Output (`start_promptgreen.bat`)
```
===============================================================================
  PROMPTGREEN V2: SUSTAINABLE LLM INFERENCE AND OPTIMIZATION ENGINE
  B.Tech Major Project Demonstration
===============================================================================

[1/4] Project Directory: D:\EDU\DSU\Major project\PromptGreen
[2/4] Detecting system Python environment...
[3/4] PYTHONPATH configured: D:\EDU\DSU\Major project\PromptGreen
[4/4] Starting PromptGreen Unified Web Application and API Server...

===============================================================================
  LOCAL ACCESS URL:
    -- Green Prompt Studio:       http://127.0.0.1:8000
    -- Evolution & Evaluation:    http://127.0.0.1:8000/evaluation
    -- API Documentation:         http://127.0.0.1:8000/docs

  The browser will open automatically as soon as the server is ready.
  To stop the server at any time: press [Ctrl+C] or run stop_promptgreen.bat
===============================================================================

INFO:     Started server process [17324]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Starting PromptGreen Production Web Application on http://127.0.0.1:8000 ...
INFO:     127.0.0.1:49972 - "GET /api HTTP/1.1" 200 OK

[READY] PromptGreen V2 is online and operational at http://127.0.0.1:8000
INFO:     127.0.0.1:57898 - "GET / HTTP/1.1" 200 OK
INFO:     127.0.0.1:57898 - "GET /api/v2/models HTTP/1.1" 200 OK
INFO:     127.0.0.1:57898 - "GET /api/v2/grid-scenarios HTTP/1.1" 200 OK
INFO:     127.0.0.1:57898 - "GET /api/v2/ledger/summary HTTP/1.1" 200 OK
INFO:     127.0.0.1:57898 - "GET /api/v2/ledger/recent?limit=50 HTTP/1.1" 200 OK
```

---

## 6. Endpoint Connectivity Results

### GET Endpoints (Dual-Host Validation)
| Endpoint | `127.0.0.1:8000` | `localhost:8000` | Status |
| :--- | :--- | :--- | :--- |
| `GET /api` | HTTP 200 (300 B) | HTTP 200 (300 B) | PASS |
| `GET /api/v2/models` | HTTP 200 (2,008 B) | HTTP 200 (2,008 B) | PASS |
| `GET /api/v2/grid-scenarios` | HTTP 200 (2,357 B) | HTTP 200 (2,357 B) | PASS |
| `GET /evaluation` | HTTP 200 (57,833 B) | HTTP 200 (57,833 B) | PASS |

### POST `/api/v2/optimize` Payload Results
```json
{
  "prompt": "Hello dear assistant! Could you please explain machine learning in a clear and comprehensive way, including its main types and practical applications?",
  "mode": "balanced",
  "target_model": "mid_tier",
  "grid_scenario": "ILLUSTRATIVE_385",
  "custom_grid_intensity": null,
  "custom_grid_provenance": null,
  "monthly_inferences": 10000,
  "author": "diagnostic-test",
  "team": "Engineering",
  "record_in_ledger": false
}
```

- **`http://127.0.0.1:8000/api/v2/optimize`**:
  - Response: HTTP 200 OK in **6.75s**
  - Tokens: 25 -> 21 (-16.0%)
  - Optimized: `"Dear assistant! Explain machine learning in a clea..."`
  - Net Energy Abated: `-0.023953 Wh` (Honest net carbon debt logged)
- **`http://localhost:8000/api/v2/optimize`**:
  - Response: HTTP 200 OK in **6.66s**
  - Tokens: 25 -> 21 (-16.0%)
  - Optimized: `"Dear assistant! Explain machine learning in a clea..."`
  - Net Energy Abated: `-0.003147 Wh`

---

## 7. Actual Browser-Based Optimization Results

Verified via automated live webview browser agent on `http://127.0.0.1:8000/`:
- **Console Errors:** 0 errors (clean JavaScript runtime).
- **Prompt Tested:** "Climate Query (Fluff)" preset chip (277 characters, 48 tokens).
- **Execution:** Clicked "Optimize Prompt (v2.0 Pipeline)" in Balanced mode.
- **Latency & Status:** **4045.9 ms**, Status **PASS**.
- **Error Toasts:** **0 error toasts** (zero "Backend Unreachable" or fetch errors).
- **Rendered Outputs:**
  - 4-Stage Pipeline Strip: Rule Pruner (completed, -9 tok), Compressor (fallback, -2 tok), Directive Shaper (completed, +4 tok), Semantic Guard (completed, score 0.927).
  - Diff: 48 tokens -> 41 tokens (-14.58%).
  - Thermodynamic Balance: Gross saved 0.0454 Wh, CPU overhead -0.0393 Wh, Net energy abated +0.006081 Wh (+2.83%), Water saved 0.0109 mL.
  - Model Router: INSUFFICIENT_INFORMATION -> Keep Current Tier (`mid_tier`).
- **Persistent Recording:** Verified saved as Record #196 in `prompt_ledger.db`.
- **Evidence Screenshot:** `docs/evidence/final_demo/final_step_107.png`.

---

## 8. Complete Regression Suite Results

All four automated verification suites executed with a 100% pass rate:
```
================================================================================
PROMPTGREEN V2 REGRESSION VERIFICATION MATRIX
================================================================================
Test Suite                                  Assertions       Result
--------------------------------------------------------------------------------
1. Standalone Core Engine (verify_engine.py)  10 / 10        PASS (100%)
2. Pytest Unit & Integration Suite           248 / 248       PASS (100%)
3. Live HTTP Server Suite (test_live_http)     8 / 8         PASS (100%)
4. End-to-End User Journeys (test_e2e)         8 / 8         PASS (100%)
--------------------------------------------------------------------------------
TOTAL VERIFIED AUTOMATED ASSERTIONS          274 / 274       PASS (100%)
================================================================================
Browser Console Errors                       0 errors        PASS (100%)
Socket Release Verification                  Port 8000 clean PASS (100%)
================================================================================
```

---

## 9. Shutdown & Socket Release Verification

Executed `cmd /c stop_promptgreen.bat`:
```
===============================================================================
  PROMPTGREEN V2: STOPPING LOCAL SERVICES
===============================================================================

Searching for active processes listening on port 8000...
Terminating PromptGreen server process: python.exe [PID 17324] on port 8000...

[SUCCESS] Terminated 1 PromptGreen server process. Port 8000 is now free.
```
- Verified via `netstat -ano -p tcp | findstr ":8000"`: returned exit code 1 (no active listener).
- Verified `start_promptgreen.bat` detected process exit and terminated cleanly without interactive pause prompts.

---

## 10. Integrity Verification

- **Git Branch:** `version-2`
- **HEAD Commit:** `0a4097172c6cd1f75cc20abe8dc591f17092a455` (strictly unchanged).
- **Protected `main` Branch:** Untouched.
- **Backup Archive Integrity:** `..\PromptGreen.zip` verified at exactly **120,304 bytes**.
- **SQLite Ledger Integrity:** `prompt_ledger.db` contains **218 persistent audit records** (all historical runs preserved without data loss or corruption).

---

## 11. Final Demonstration-Readiness Verdict

PromptGreen V2 has resolved the underlying startup race condition, stabilized the Windows process lifecycle, and hardened client-server error handling. Both `127.0.0.1` and `localhost` are verified operational.

**Verdict: FULLY OPERATIONAL, HARDENED, AND DEMONSTRATION-READY.**
