# PROMPTGREEN V2 — FULL SYSTEM INTEGRATION REPORT
## Multi-Interface Operational Audit: FastAPI Backend, CLI, and Green Prompt Studio

**Project:** PromptGreen V2 — Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment  
**Document Version:** 1.0.0  
**Date:** November 24, 2026  
**Status:** COMPLETE, AUDITED & VERIFIED  
**Repository Branch:** `version-2`  
**Execution Environment:** Intel Core i7-10610U CPU (4 cores / 8 threads @ 1.80GHz–4.90GHz), 32 GB RAM, Windows 11, Python 3.11.9 (CPU-first, zero-budget)  
**Deliverable ID:** R6 / Phase 6 of Master Implementation Roadmap  

---

## 1. Executive Summary

Phase 6 validates the seamless end-to-end integration of all PromptGreen V2 engineering components across its three primary user interfaces:
1. **FastAPI RESTful Backend (`promptgreen/api/server.py`):**
   - Serves unified endpoints for active 4-stage optimization, thermodynamic energy modeling, conservative model routing, and persistent telemetry.
   - Verified non-blocking ASGI launch via `start_backend.ps1` and 4-state diagnostic health reporting via `status_backend.ps1`.
   - Robust Cross-Origin Resource Sharing (CORS) configured across all `localhost` and `127.0.0.1` ports.
2. **Command Line Interface (`promptgreen/cli.py`):**
   - Commands audited and verified: `optimize`, `review`, `analyze`, `diff`, `git-diff`, and `ledger`.
   - Rich terminal formatting with multi-scenario thermodynamic tables, epistemic status annotations, and advisory routing notices.
   - Backward-compatible option flags and command aliases ensure zero workflow disruption for developer automation.
3. **Green Prompt Studio (`Website/index.html` & `Website/frontend_server.py`):**
   - Decoupled static frontend served on port 8080 with strict POSIX path-traversal and drive-letter sandboxing.
   - Communicates dynamically with the backend API on port 8000, fetching live model tier profiles, illustrative grid intensities, recent telemetry records, and cumulative carbon debt metrics.

---

## 2. FastAPI Backend Verification

### 2.1 Route Map and ASGI Specification
The backend service exposes standard RESTful interfaces conforming to OpenAPI 3.0:

| Route | Method | Purpose |
|---|---|---|
| `/api` / `/health` | `GET` | System health check and model pre-warming diagnostic |
| `/api/v2/optimize` | `POST` | Core 4-stage optimization, energy modeling, and routing |
| `/api/v2/models` | `GET` | Active model tier profiles and energy coefficients |
| `/api/v2/grid-scenarios` | `GET` | Supported power grid carbon intensity scenarios |
| `/api/v2/ledger/summary` | `GET` | Cumulative carbon debt and environmental savings summary |
| `/api/v2/ledger/recent` | `GET` | Recent prompt review records (limit configurable) |
| `/api/v2/telemetry/events` | `GET` | Granular time-series optimization events with filtering |
| `/api/v2/telemetry/time-series` | `GET` | Hourly/daily aggregated time-series buckets |
| `/api/v2/telemetry/stats` | `GET` | Combined persistence statistics and ledger totals |
| `/api/v2/telemetry/status` | `GET` | Database backend status (SQLite / PostgreSQL / TimescaleDB) |
| `/` / `/app` | `GET` | Embedded Green Prompt Studio single-page application |
| `/evaluation` | `GET` | V1 vs V2 Evolution & Evaluation portal |

### 2.2 Lifecycle Scripts Verification
- **`start_backend.ps1`:**
  - Locates Python interpreter across `.venv`, `venv`, and system PATH.
  - Verifies port 8000 availability; refuses to kill unrelated processes.
  - Launches Uvicorn in background with log redirection to `logs\backend.log`.
  - Performs polling readiness check against `http://127.0.0.1:8000/api` until `status == "active"`.
- **`status_backend.ps1`:**
  - Reliably distinguishes 4 states: `RUNNING AND HEALTHY`, `RUNNING BUT UNHEALTHY`, `NOT RUNNING`, and `PORT OCCUPIED BY AN UNRELATED PROCESS`.

---

## 3. CLI Command Verification

The command-line interface was audited to confirm both legacy V1 workflows and modern V2 active optimization:

### 3.1 `promptgreen review` / `promptgreen analyze`
Evaluates a baseline (old) prompt against a proposed (new) prompt:
```bash
python -m promptgreen.cli review \
  --old "Please write a comprehensive and exhaustive summary of photosynthesis in biology." \
  --new "Summarize photosynthesis in 3 bullet points."
```
- **Output:**
  - Evaluates carbon gate policy (PASS / WARN / FAIL).
  - Displays token delta table ($13 \to 11$ input, $190.4 \to 35.6$ modeled output).
  - Calculates modeled energy per inference ($-46.64\text{ mJ}$) and carbon delta ($-0.0050\text{ gCO}_2 / 1\text{K}$).
  - Automatically records review result to `prompt_ledger.db`.

### 3.2 `promptgreen optimize`
Executes the four-stage prompt optimization pipeline with full neural inference:
```bash
python -m promptgreen.cli optimize -p "Please summarize the core advantages of microservices architecture in bullet points."
```
- **Output:**
  - Mode selection: BALANCED ($0.60$ retention target).
  - Multi-scenario thermodynamic accounting:
    - Scenario 1 (Verified Input-Only): Gross input energy, local CPU overhead ($35.0\text{W}$ estimate), net energy delta ($\Delta E_{\text{net}}$), and net abated carbon.
    - Scenario 2 (Exploratory Modeled Downstream): Hybrid output prediction and zero-diff downstream guard.
  - Conservative Green Model Router: Advisory tier recommendation, confidence level, and governance disclaimers.

### 3.3 `promptgreen ledger`
Displays tabular ledger history:
```bash
python -m promptgreen.cli ledger --limit 5
```
- Formatted Rich table with review IDs, commit hashes, team attribution, token deltas, carbon impact, and cumulative totals.

---

## 4. Green Prompt Studio (Frontend UI) Integration

### 4.1 Independent Frontend Server (`Website/frontend_server.py`)
- Standard library HTTP server (`http.server`) running on `http://127.0.0.1:8080`.
- Path sanitization prevents path-traversal attacks and Windows drive-letter escapes.
- Lifecycle management provided via `start_frontend.ps1` with optional automatic browser launch.

### 4.2 Dynamic Frontend-Backend Telemetry Flow
1. **Configuration Initialization:** Green Prompt Studio probes `http://127.0.0.1:8000/api` on page load.
2. **Model Tier Dropdown:** Populated via `/api/v2/models` (Frontier Dense, Large Reasoning, Mid Tier, Compact Green).
3. **Grid Scenarios:** Populated via `/api/v2/grid-scenarios` (Illustrative Global 385 g/kWh, US Clean 100 g/kWh, Coal-Heavy 800 g/kWh).
4. **Interactive Prompt Optimization:**
   - User inputs prompt text and selects optimization mode (Conservative, Balanced, Aggressive).
   - Studio issues POST request to `/api/v2/optimize`.
   - Visualizes live token comparison, stage execution breakdown badges, thermodynamic energy graphs, and router recommendation cards.
5. **Ledger & Telemetry Visualizer:**
   - Telemetry tab polls `/api/v2/ledger/recent` and `/api/v2/ledger/summary`.
   - Displays cumulative carbon debt savings gauge, passed/failed run counts, and team carbon leaderboards.

---

## 5. Architectural Integrity & Phase 6 Sign-Off

All integration interfaces have been verified and documented. No existing benchmark results, historical SQLite records, or previous deliverables were modified.

**Phase 6 is complete, audited, and verified.** Deliverables:
- Backend Server: `promptgreen/api/server.py`
- Backend Control Scripts: `start_backend.ps1`, `status_backend.ps1`
- Frontend Server & UI: `Website/frontend_server.py`, `start_frontend.ps1`, `Website/index.html`
- CLI Suite: `promptgreen/cli.py` (with aliases `review`, `diff`, `optimize`, `ledger`)
- Architectural Deliverable: `docs/FULL_SYSTEM_INTEGRATION_REPORT.md`
