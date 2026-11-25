# PromptGreen V2 — Phase 0 Baseline Preservation and Architectural Control Audit

**Document:** `docs/PHASE0_BASELINE_PRESERVATION_AUDIT.md`  
**Date:** 2026-11-24  
**Project:** Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment (PromptGreen V2)  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  
**Active Branch:** `version-2`  
**Base Commit (HEAD):** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Hardware Platform:** Dell Latitude 5410, Intel Core i7-10610U (8 threads), 32 GB RAM, Intel UHD Graphics  
**Execution Strategy:** CPU-first, local inference, zero-budget development  

---

## 1. Executive Summary & Audit Purpose

Phase 0 of the Master Implementation and Completion Roadmap establishes an audited, immutable baseline prior to executing any functional or architectural enhancements across Stages 1 through 4, database modernization, and background infrastructure.

This audit establishes that:
1. **Repository and Branch Control:** Active branch is verified as `version-2` tracking `origin/version-2`. Zero files are staged for commit.
2. **Working Tree Inventory:** 13 tracked modified files are inventoried. Untracked files (historical datasets, prior benchmark outputs, test suites, scripts) are fully cataloged.
3. **Historical Benchmark Preservation:** All historical datasets (`240`, `1200`, `IGE-1000`) and result ledgers (`benchmark_v2`, `benchmark_v2_corrected`, `benchmark_1200`, `ige_1000`) are frozen, intact, and will not be overwritten.
4. **V1 Archive Verification:** `PromptGreen.zip` is verified at `D:\EDU\DSU\Major project\PromptGreen.zip` (120,304 bytes, SHA-256 `dc8b78a3371efbcb1066169222ad98053ff4f36e1d49f79974246e0243d08808`).
5. **Production SQLite Ledger Integrity:** `prompt_ledger.db` is verified with 413 production records in table `prompt_records` (file size: 167,936 bytes).
6. **Existing Test Suite Baseline:** Full suite of **401 unit and regression tests passed** in 36.06 seconds with zero failures.
7. **P1 Embedding Memoization Baseline:** Verified active in `promptgreen/optimizer/semantic_guard.py` (`_RequestEmbeddingCache`) with 11 dedicated unit tests passing.
8. **Isolated Experimental Space:** New directory `results/master_v2/` is initialized to house all forthcoming experimental evaluation outputs independently.

---

## 2. Git Working Tree and Branch Audit

### 2.1 Branch and Commit Identity
- **Active Branch:** `version-2`
- **Upstream Tracking:** `origin/version-2` (up to date)
- **HEAD Commit Hash:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`
- **Commit History (Last 3):**
  - `0a40971`: feat(v2): integrate four-stage prompt optimization pipeline
  - `e63f879`: feat(v2): implement semantic fidelity guardrail with chunked MiniLM validation
  - `a5570c2`: feat(v2): add Stage 3 output directive shaper and Ollama evaluation

### 2.2 Staging and Working Tree State
- **Staged Files Count:** 0 (Confirmed zero staged files)
- **Modified Tracked Files (13 files):**
  - `Website/index.html`
  - `Website/server.py`
  - `promptgreen/api/server.py`
  - `promptgreen/cli.py`
  - `promptgreen/engine/__init__.py`
  - `promptgreen/engine/carbon_engine.py`
  - `promptgreen/ledger/database.py`
  - `promptgreen/optimizer/compressor.py`
  - `promptgreen/optimizer/output_shaper.py`
  - `promptgreen/optimizer/pipeline.py`
  - `promptgreen/optimizer/rule_pruner.py`
  - `promptgreen/optimizer/semantic_guard.py`
  - `promptgreen/predictor/hybrid_predictor.py`

*Policy Enforcement:* No automatic git staging, commits, pushes, or branch switches will be executed.

---

## 3. Historical Artifact & Data Preservation Inventory

| Artifact Item | Location | Size / Records | Integrity / Hash | Status |
|---|---|---|---|---|
| **Original V1 Backup Archive** | `D:\EDU\DSU\Major project\PromptGreen.zip` | 120,304 bytes | SHA256: `dc8b78a3371efbcb1066169222ad98053ff4f36e1d49f79974246e0243d08808` | **FROZEN & PRESERVED** |
| **Historical 240 Dataset** | `data/benchmark_240_independent.json` | 190,426 bytes | 240 prompts | **FROZEN & PRESERVED** |
| **Historical 1200 Dataset** | `data/benchmark_1200_independent.json` | 1,285,552 bytes | 1,200 prompts | **FROZEN & PRESERVED** |
| **IGE-1000 Frozen Dataset** | `data/benchmark_ige_1000_unseen.json` | 1,109,310 bytes | 1,000 prompts | **FROZEN & PRESERVED** |
| **IGE-1000 Pre-Correction** | `data/benchmark_ige_1000_unseen_pre_correction.json` | 1,102,538 bytes | 1,000 prompts | **FROZEN & PRESERVED** |
| **Original Suite** | `data/benchmark_suite.json` | 27,174 bytes | Original test suite | **FROZEN & PRESERVED** |
| **Production SQLite Ledger** | `prompt_ledger.db` | 167,936 bytes | 413 rows in `prompt_records` | **FROZEN & PRESERVED** |
| **240 Benchmark Ledger** | `results/benchmark_v2/` | Full directory | 720 runs (3 modes) | **FROZEN & PRESERVED** |
| **240 Corrected Ledger** | `results/benchmark_v2_corrected/` | Full directory | Grounded physics records | **FROZEN & PRESERVED** |
| **1200 Benchmark Ledger** | `results/benchmark_1200/` | Full directory | 3,600 runs | **FROZEN & PRESERVED** |
| **IGE-1000 Ledger** | `results/ige_1000/` | Full directory | 3,000 runs | **FROZEN & PRESERVED** |

---

## 4. Development Environment & Runtime Capability Audit

### 4.1 System and Runtime
- **Operating System:** Windows 10/11 x64 on Dell Latitude 5410
- **CPU:** Intel Core i7-10610U @ 1.80GHz (4 cores, 8 logical processors)
- **RAM:** 32.0 GB installed RAM
- **Python Version:** Python 3.11.9 (`C:\Users\Renuk\AppData\Local\Programs\Python\Python311\python.exe`)

### 4.2 Installed Python Packages
- `torch`: 2.11.0+cpu (CPU-only build, verified)
- `numpy`: 2.4.2
- `scipy`: 1.17.0
- `scikit-learn`: 1.8.0
- `fastapi`: 0.141.1
- `uvicorn`: 0.52.4
- `pydantic`: 2.12.5
- `sqlalchemy`: 2.1.6
- `alembic`: 1.20.1

### 4.3 External Services & Toolchain Assessment
- **Ollama:** Installed at `C:\Users\Renuk\AppData\Local\Programs\Ollama\ollama.exe` (client v0.40.17). Daemon not currently running in background. Model `qwen2.5:0.5b` planned for Stage 3.
- **Docker / WSL:** Not installed on host. 
- **PostgreSQL / Redis:** Native daemon binaries not present on standard PATH.
  - *Architectural Directive:* As required by the roadmap, database and caching layers must support both full persistent service configurations (PostgreSQL/TimescaleDB/Redis) and robust, graceful local SQLite / in-memory fallbacks to guarantee 100% operational uptime in zero-budget CPU-only environments.

---

## 5. Baseline Test Suite Verification

Execution of `PYTHONPATH="." pytest tests/ -v`:
- **Total Tests Collected:** 401
- **Passed:** 401 (100%)
- **Failed / Errored:** 0
- **Duration:** 36.06 seconds
- **Key Modules Tested:**
  - `tests/test_stage4_memoization.py`: 11 passed (P1 thread-isolated request-scoped cache verified)
  - `tests/test_semantic_guard.py`: 68 passed (Cosine similarity, threshold gating, fallback, rollback)
  - `tests/test_optimizer_correctness_fixes.py`: 113 passed (Preservation rules, casing, numbers, code, JSON)
  - `tests/test_output_shaper.py`: 30 passed (Stage 3 deterministic shaping & expansion guard)
  - `tests/test_compressor.py`: 25 passed (Stage 2 compression presets & fallback)
  - `tests/test_rule_pruner.py`: 22 passed (Stage 1 deterministic structural rule pruner)
  - `tests/test_carbon_engine.py`: 27 passed (Thermodynamics, prefill/decode energy, regional grid)
  - `tests/test_model_router.py`: 28 passed (Advisory routing & model tiers)
  - `tests/test_api_server.py`: 18 passed (FastAPI endpoints and schemas)
  - `tests/test_all.py`: 8 passed (End-to-end integration)

---

## 6. Exit Criteria Sign-off

| Exit Criteria | Verification Status | Notes |
|---|---|---|
| Repository baseline documented | **COMPLETE** | Branch `version-2`, HEAD `0a40971`, 0 staged |
| Existing changes identified | **COMPLETE** | 13 modified files documented; clean separation planned |
| Historical artifacts verified | **COMPLETE** | V1 ZIP hash match; datasets & ledgers frozen |
| Development environment documented | **COMPLETE** | Python 3.11.9, CPU torch, Ollama located, service fallbacks planned |
| Baseline tests passing | **COMPLETE** | 401 / 401 tests pass cleanly |
| Dedicated experimental workspace | **COMPLETE** | `results/master_v2/` initialized |

**Phase 0 Status: COMPLETE AND AUDITED.** Proceeding to Phase 1.
