# PromptGreen V2 — Independent Backend Operations Guide

## 1. Architectural Overview

PromptGreen V2 features a fully decoupled operational architecture where the **computational backend** (FastAPI / Uvicorn) and the **user-facing frontend** (Green Prompt Studio & Evaluation Portal) operate independently of one another.

```
+-----------------------------------------------------------------------------------+
|                               PROMPTGREEN V2 TOPOLOGY                             |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|   +------------------------------------+   +------------------------------------+ |
|   |         FRONTEND SERVICE           |   |          BACKEND SERVICE           | |
|   |     Website/frontend_server.py     |   |      promptgreen.api.server:app    | |
|   |       http://127.0.0.1:8080        |   |       http://127.0.0.1:8000        | |
|   +------------------------------------+   +------------------------------------+ |
|                     |                                         |                   |
|                     | SPA Static Files                        | REST API          |
|                     | (index.html, evaluation.html)           | (/api/v2/*)       |
|                     v                                         v                   |
|   +-----------------------------------------------------------------------------+ |
|   |                       CLIENT BROWSER / CONSUMER                             | |
|   |                                                                             | |
|   |   ConnectionManager (Heartbeat, Status Pill, Disconnect/Connect, Settings)  | |
|   |   Default Target: http://127.0.0.1:8000 (Configurable via UI Modal)         | |
|   +-----------------------------------------------------------------------------+ |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Key Architectural Tenets
1. **Zero Lifecycle Coupling:** The backend does not require the frontend to run; it can be started, stopped, restarted, and scaled as an autonomous headless microservice.
2. **Resilient Frontend:** The frontend can be loaded via `http://127.0.0.1:8080` (or `file://` or custom ports) before the backend starts without crashing or hanging. It gracefully transitions between `CONNECTED`, `CONNECTING`, `DISCONNECTED`, and `ERROR` states.
3. **Safe Process Ownership:** Stop and status scripts strictly verify ownership via PID file inspection, `/api` system signature validation (`"system": "PromptGreen"`), and command-line matching. PromptGreen scripts **refuse to terminate unrelated processes occupying port 8000**.
4. **Backward Compatibility:** The legacy unified server (`Website/server.py` on port 8000) and batch files (`start_promptgreen.bat` / `stop_promptgreen.bat`) remain intact.

---

## 2. Backend Lifecycle Management (PowerShell)

Four dedicated PowerShell scripts provide complete operational control over the FastAPI backend:

| Script | Purpose | Default Port | Exit Code Behavior |
| :--- | :--- | :--- | :--- |
| `start_backend.ps1` | Launches backend in background with readiness check | `8000` | `0` = Ready; `1` = Error / Port Conflict |
| `stop_backend.ps1` | Safely terminates PromptGreen backend only | `8000` | `0` = Stopped; `1` = Not running / Error |
| `status_backend.ps1`| Inspects port 8000 and reports 4 distinct states | `8000` | `0` = Healthy; `1` = Conflict; `2` = Unhealthy; `3` = Not Running |
| `restart_backend.ps1`| Performs safe stop -> pause -> start sequence | `8000` | `0` = Successfully restarted |

### A. Starting the Backend
```powershell
.\start_backend.ps1
```

**Parameters:**
- `-HostAddress` *(string, default: "127.0.0.1")*: Interface to bind.
- `-Port` *(int, default: 8000)*: Port to listen on.
- `-LogFile` *(string, default: "logs\backend.log")*: Path for stdout/stderr logs.
- `-PidFile` *(string, default: "logs\backend.pid")*: Path to store background PID.
- `-TimeoutSeconds` *(int, default: 25)*: Seconds to poll `/api` for health before failing.

**Behavior:**
1. Checks if port 8000 is already active. If already running PromptGreen, prints `[INFO] Already running` and exits safely without spawning duplicates.
2. If port 8000 is occupied by an unrelated process, prints an error and **refuses to overwrite or terminate it**.
3. Launches `uvicorn promptgreen.api.server:app` in the background with redirected logs.
4. Polls `http://127.0.0.1:8000/api` until HTTP 200 with `"system": "PromptGreen"` is received.

### B. Stopping the Backend
```powershell
.\stop_backend.ps1
```

**Ownership Verification Flow:**
1. Checks `logs\backend.pid` and current port 8000 listeners.
2. Probes `GET http://127.0.0.1:8000/api`. If response is HTTP 200 and JSON contains `"system": "PromptGreen"`, process is confirmed as PromptGreen.
3. If probe fails (e.g. process hanging), inspects process name and command-line arguments for `promptgreen` or `uvicorn`.
4. If the process is unrelated (e.g. Node.js, IIS, Python http.server), `stop_backend.ps1` prints `[WARNING] Port 8000 is occupied by an UNRELATED process` and **exits with code 1 without touching the process**.
5. Once terminated, verifies port 8000 is fully released and removes `logs\backend.pid`.

### C. Checking Backend Status
```powershell
.\status_backend.ps1
```

The script reports one of four unambiguous states:
1. `STATE: RUNNING AND HEALTHY` (Exit code: 0): Port active, `/api` returns 200 with PromptGreen signature. Reports version, PID, and MiniLM prewarming status.
2. `STATE: RUNNING BUT UNHEALTHY` (Exit code: 2): Port active, PID identified as PromptGreen, but `/api` returned error or timed out.
3. `STATE: PORT OCCUPIED BY AN UNRELATED PROCESS` (Exit code: 1): Port active, but process does not belong to PromptGreen. Prints conflicting PID, process name, and command line.
4. `STATE: NOT RUNNING` (Exit code: 3): Port 8000 is completely free.

### D. Restarting the Backend
```powershell
.\restart_backend.ps1
```
Executes `stop_backend.ps1`, pauses 1 second, and calls `start_backend.ps1`.

---

## 3. Independent Frontend Server & Scripts

The static frontend files (`Website/index.html` and `Website/evaluation.html`) can be served via a lightweight, zero-dependency Python HTTP server (`Website/frontend_server.py`) or opened directly.

### A. Frontend Server Script (`Website/frontend_server.py`)
- **Port:** Default `8080`.
- **SPA Routing:**
  - `/`, `/app`, `/studio` -> `index.html`
  - `/evaluation`, `/evolution`, `/compare` -> `evaluation.html`
  - `/api/*` -> Returns JSON 404 clarifying that the API backend runs on port 8000.
- **Headers:** Injects CORS (`Access-Control-Allow-Origin: *`) and no-cache headers.

### B. Frontend Lifecycle Scripts
```powershell
# Start frontend (opens browser by default; pass -NoBrowser to suppress)
.\start_frontend.ps1 -NoBrowser

# Check status
.\status_frontend.ps1

# Stop frontend
.\stop_frontend.ps1
```

---

## 4. Frontend Connection Controls & State Management

The Green Prompt Studio (`Website/index.html`) and Evaluation Dossier (`Website/evaluation.html`) include a real-time `ConnectionManager` client.

### Connection States
| State | Indicator | Navbar Label | Studio Alert Banner | Optimization Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **CONNECTED** | Emerald Dot (pulsing) | `ONLINE v2.0` | Hidden | Fully operational; executes 4-stage pipeline |
| **CONNECTING** | Cyan Dot (pulsing) | `CONNECTING...`| Visible with target URL | Displays warning if optimization clicked |
| **DISCONNECTED**| Gray Dot (solid) | `DISCONNECTED` | Visible with runbook instructions | Blocks optimization with toast notification |
| **ERROR** | Rose Dot (flashing) | `ERROR` | Visible with error diagnostics | Blocks optimization with diagnostic alert |

### Interactive Controls
1. **Status Pill (`#connStatusPill`):** Clicking opens the Connection Settings Modal.
2. **Action Button (`#btnConnAction`):**
   - When connected: Displays "Disconnect" (allows manual offline mode).
   - When disconnected: Displays "Connect" (attempts immediate health probe).
3. **Settings Modal (`#connModal`):**
   - **Custom Base URL:** Allows pointing frontend to custom port, IP, or remote host (persisted in `localStorage['promptgreen_api_base']`).
   - **Timeout Configuration:** Configurable probe timeout in ms (default: 3500ms; persisted in `localStorage['promptgreen_timeout_ms']`).
   - **Live Diagnostics:** Shows real-time probe status, timestamp, target URL, and system response.
   - **Reset Defaults:** Restores `http://127.0.0.1:8000` and 3500ms timeout.
4. **Heartbeat Polling:** Checks `GET /api` every 5 seconds to detect backend state changes. Automatically reloads tiers, scenarios, and ledger metrics when backend comes online.

---

## 5. Standard Operating Procedures

### Scenario 1: Starting the Complete Decoupled Stack
```powershell
# 1. Start backend service
.\start_backend.ps1

# 2. Start frontend static server
.\start_frontend.ps1
```

### Scenario 2: Headless Backend for API Consumers / Benchmarks
```powershell
# Start backend only
.\start_backend.ps1

# Run tests or benchmarks
python scratch\verify_optimization.py
python -m pytest tests\test_api_server.py
```

### Scenario 3: Troubleshooting a Conflicting Port 8000
```powershell
# 1. Check who is using port 8000
.\status_backend.ps1

# 2. If it is an unrelated process, inspect the CommandLine reported
# PromptGreen will NOT kill it. Stop that process from its own terminal or service manager.

# 3. Once freed, start PromptGreen
.\start_backend.ps1
```

### Scenario 4: Stopping All PromptGreen Services
```powershell
.\stop_backend.ps1
.\stop_frontend.ps1
```
