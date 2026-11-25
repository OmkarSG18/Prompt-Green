# PromptGreen V2 — Day 2 Frontend Architecture Audit

**Date:** November 22, 2026  
**Auditor:** PromptGreen V2 Engineering  
**Target Event:** Academic Thesis Evaluation & External Evaluator Technical Demonstration  
**Active Branch:** `version-2`  
**Base Commit (HEAD):** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  

---

## 1. Executive Summary

This architecture audit evaluates the user interface landscape across the PromptGreen codebase. We inspected the four existing frontend surfaces:
1. `Website/index.html` (served via `Website/server.py` on port 8000)
2. `gui_simulator.html` (standalone HTML prototype)
3. `dashboard/app.py` (Streamlit analytics application on port 8501)
4. `promptgreen/api/server.py` (FastAPI backend providing REST endpoints)

The audit concludes that **`Website/index.html` (hosted on `http://127.0.0.1:8000` by `Website/server.py`) is the primary demonstration interface**. It directly mounts both the web UI and the unified FastAPI backend in a single unified Python process. However, the current `Website/index.html` is largely a V1 shell: it still contains client-side regexes, calls legacy V1 review endpoints in mJ, lacks the 4-stage pipeline visualization, lacks thermodynamic Wh and water impact metrics, and does not surface the Green Model Router or the SQLite ledger history.

This document details the architecture, identifies gaps, and defines the unification strategy for Day 2.

---

## 2. Assessment of Existing Frontend Surfaces

| Interface | Technology Stack | Hosting / Port | Primary Purpose & Functional Status |
|---|---|---|---|
| **`Website/index.html`** | HTML5, Tailwind CSS, Vanilla JS, Chart.js | Port 8000 via `Website/server.py` (FastAPI/Uvicorn) | **PRIMARY APPLICATION.** Full-featured web portal with hero banner, live interactive optimizer, benchmark visualizations, CI/CD explanation, and ledger display. Currently partially connected to legacy V1 `/api/v1/review` with client-side fallback regexes. |
| **`dashboard/app.py`** | Streamlit, Plotly, Pandas | Port 8501 (`streamlit run dashboard/app.py`) | **SECONDARY ANALYTICAL TOOL.** Multi-tab engineering dashboard for team leaderboards, historical carbon trends, and parameter sensitivity exploration. Functional, but uses legacy V1 `CarbonEngine` and `PromptLedger` methods. |
| **`gui_simulator.html`** | Single-file HTML, Tailwind, Mock JS | Local file (`file:///...`) or static file | **SIMULATION TOY.** Standalone client-side parameter tuner with hardcoded mock dataset and slider-based calculations. Not connected to any backend API. Useful as a conceptual sandbox, but not the primary demo interface. |
| **`promptgreen/api/server.py`** | FastAPI, Pydantic, Uvicorn | Port 8000 (direct or via `Website/server.py`) | **BACKEND REST API.** Fully integrated V2 endpoints (`/api/v2/optimize`, `/api/v2/models`, `/api/v2/grid-scenarios`, `/api/v2/ledger/*`) plus legacy V1 endpoints. Includes interactive Swagger UI at `/docs`. |

---

## 3. Detailed Audit Questions & Findings

### 1. Which interface is intended to be the primary application?
**Decision: `Website/index.html` served by `Website/server.py` on port 8000.**  
*Rationale:*
- `Website/server.py` imports `app` from `promptgreen.api.server` and mounts `Website/index.html` at `/`, `/app`, and `/website`.
- A single command (`python Website/server.py`) starts the complete application on `http://127.0.0.1:8000`.
- Zero port collisions, zero cross-origin (CORS) complexity, and minimal memory footprint suitable for local execution on a standard laptop.
- The interface layout provides the complete narrative required for academic evaluators: live prompt optimization, stage-by-stage pipeline inspection, thermodynamic environmental telemetry, green model routing, and persistent ledger history.

### 2. Is it static HTML/JavaScript, Streamlit, or another framework?
- The primary interface is **HTML5, Tailwind CSS, and Vanilla JavaScript** running in the browser. It communicates asynchronously via standard `fetch()` calls to the FastAPI backend.
- The secondary interface is **Streamlit** in `dashboard/app.py`.

### 3. Which screens are functional and which are demonstrations or simulations?
- **Functional:**
  - `/api/v2/optimize`, `/api/v2/models`, `/api/v2/grid-scenarios`, `/api/v2/ledger/*` on FastAPI backend (100% verified via 246 passing tests).
  - Streamlit dashboard (`dashboard/app.py`): functional against SQLite ledger, but needs metric alignment with V2 thermodynamic units.
- **Simulation / Mock:**
  - `gui_simulator.html`: Purely mock JavaScript formulas with hardcoded mock category metrics.
  - In `Website/index.html`: `debouncedAutoGreen()` and `autoGreen()` contains client-side regex search-and-replace scripts (lines 373–427) that silently override server optimization when fallback triggers!
  - In `Website/index.html`: The benchmark charts (`chartAccuracy`, `chartEnergy`) use hardcoded static data in JavaScript rather than dynamic API data.

### 4. Which API endpoints does the frontend currently call?
- Currently, `Website/index.html` calls:
  - `POST /api/v1/generate-green` (legacy regex alternative generator)
  - `POST /api/v1/review` (legacy carbon gate checking mJ and old grid scenarios)
- It **does not yet call**:
  - `POST /api/v2/optimize`
  - `GET /api/v2/models`
  - `GET /api/v2/grid-scenarios`
  - `GET /api/v2/ledger/summary`
  - `GET /api/v2/ledger/recent`

### 5. Which V1 components are still being used?
- `PromptDiffAnalyzer.generate_green_alternative()` was previously invoked.
- `CarbonEngine.calculate()` was previously reporting energy in mJ.
- `PromptLedger.record_prompt_review()` was recording only input/output tokens and mJ deltas.

### 6. Can the frontend run locally without internet access?
- **Current Limitation:** `Website/index.html` links to external CDNs for:
  - Tailwind CSS (`https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js`)
  - Chart.js (`https://cdn.jsdelivr.net/npm/chart.js`)
  - FontAwesome icons (`https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css`)
  - Google Fonts Inter & JetBrains Mono (`https://fonts.googleapis.com/...`)
- If Wi-Fi is disconnected during an evaluation, font rendering and styling could degrade if not cached.
- **Remediation for Day 2:** Add embedded defensive fallback CSS styling and SVG icons directly within `Website/index.html` so that even if all external CDN requests fail completely, the studio renders with high visual polish, complete responsiveness, clean typography, and zero layout breakage.

### 7. Are dependencies and startup commands documented?
- Previously, `README.md` documented CLI and basic installation, but did not provide a single one-line startup script for the combined Web Application.
- On Day 2, we will provide `start_promptgreen.bat` and explicit instructions in `docs/DEMO_STARTUP_GUIDE.md`.

---

## 4. Primary Interface Architecture & Enhancement Plan

We will upgrade `Website/index.html` into the **Green Prompt Studio**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PROMPTGREEN V2 STUDIO                           │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Header & Navigation (Studio, Model Profiles, History, Ledger, Docs) │
│ 2. System Status Bar (Backend: 127.0.0.1:8000 | Engine: V2 Active)     │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PROMPT INPUT PANEL                                                  │
│    - Large prompt textarea with character/token counter                │
│    - Mode Selector (Conservative, Balanced, Aggressive)                │
│    - Target Model Selector (Frontier Dense, Large Reasoning, etc.)    │
│    - Grid Scenario Selector (ILLUSTRATIVE_385, THESIS_367, Custom)     │
│    - Optimize Prompt CTA & Reset Button                                │
├────────────────────────────────────────────────────────────────────────┤
│ 4. FOUR-STAGE PIPELINE EXECUTION STRIP                                 │
│    [Stage 1: Rule Pruner] ──> [Stage 2: Compressor]                    │
│           ──> [Stage 3: Output Shaper] ──> [Stage 4: Semantic Guard]   │
│    - Status badges (Completed, Skipped, Fallback, Rolled Back)         │
│    - Stage latencies (ms) & token deltas                               │
├────────────────────────────────────────────────────────────────────────┤
│ 5. OPTIMIZATION & SEMANTIC FIDELITY RESULTS                            │
│    - Side-by-side prompt diff (Original vs. Optimized)                 │
│    - One-click copy optimized prompt button                            │
│    - Token reduction count & compression ratio                         │
│    - MiniLM semantic similarity score badge (e.g. 0.942 - PASSED)      │
├────────────────────────────────────────────────────────────────────────┤
│ 6. THERMODYNAMIC & ENVIRONMENTAL TELEMETRY                             │
│    - Gross inference energy saved (Wh)                                 │
│    - Optimizer CPU overhead deducted (Wh)                              │
│    - Net energy abated (Wh) [Honest reporting of negative savings]    │
│    - Carbon abated (gCO2e per request & per 1K)                       │
│    - Datacenter water footprint saved (mL)                             │
│    - Epistemic transparency & assumptions expandable modal             │
├────────────────────────────────────────────────────────────────────────┤
│ 7. GREEN MODEL ROUTER RECOMMENDATION CARD                              │
│    - Current tier vs Recommended tier                                  │
│    - Routing decision outcome badge (RECOMMEND_DOWNGRADE, KEEP, etc.)   │
│    - Task suitability, confidence rating, physical energy comparison   │
│    - Explicit disclaimer: advisory recommendation, no auto-switch      │
├────────────────────────────────────────────────────────────────────────┤
│ 8. PERSISTENT AUDIT LEDGER & ANALYTICS                                 │
│    - Live historical table of previous optimization runs from SQLite  │
│    - Cumulative savings counter (Runs, Net Wh, Net gCO2e, Water mL)   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Audit Conclusions & Immediate Action Items

1. **Retain and upgrade `Website/index.html`** as the single primary application served via `Website/server.py`.
2. **Remove client-side mock regexes** in `Website/index.html`; wire directly to `/api/v2/optimize`.
3. **Document `dashboard/app.py`** as the secondary analytical dashboard for extended metrics.
4. **Document `gui_simulator.html`** as an offline educational parameter sandbox.
5. **Verify live HTTP connectivity** using a dedicated verification script to eliminate any possibility of socket or connection hangs.
