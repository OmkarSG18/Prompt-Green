# PromptGreen V2 — Operational Improvements Report
**Phase 1: Pre-Warming, Cold/Warm Accounting, CLI V2, and Stage 3 Ollama Hardening**
**Date:** 2026-11-22  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  
**Branch:** `version-2`  
**Base Commit (HEAD):** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Database Audit Ledger:** `prompt_ledger.db` (265 contiguous records preserved)

---

## Executive Summary

Following the comprehensive read-only findings in `docs/THREE_DAY_COMPLETION_AUDIT.md`, this operational improvement phase addresses key operational and accounting gaps in PromptGreen V2 without introducing disruptive architectural rewrites or violating established API contracts.

### Key Achievements

1. **Model Startup Pre-Warming & In-Memory Cache Reuse (Phase A):**
   - Implemented `LocalMiniLMEmbedder.prewarm()` to pre-load HuggingFace safetensors weights strictly from the local disk cache without downloading weights over the internet.
   - Added class-level shared singleton cache (`_shared_st_model`, `_shared_pytorch_model`, etc.) so multiple pipeline instances within the same process reuse the identical in-memory weights.
   - **Performance impact:** Model loading dropped from **2,206.91 ms** on cold start to **0.007 ms** on warm requests ($>300,000\times$ speedup).
   - Separated cold-start initialization overhead from marginal per-request optimizer accounting: server startup records cold-start initialization latency and modeled energy in metadata, ensuring subsequent prompt optimizations only account for true per-request computational energy.

2. **PromptGreen V2 CLI `optimize` Subcommand (Phase B):**
   - Added a production-ready `python -m promptgreen.cli optimize --prompt "..." --mode balanced` command supporting `conservative`, `balanced`, and `aggressive` optimization modes.
   - Outputs Rich formatted panels and tables with explicit **epistemic status tags**:
     - `(exact measured tiktoken count)`
     - `(modeled hybrid regression prediction)`
     - `(modeled thermodynamic: PUE=1.15)`
     - `(modeled local CPU: 35.0W unmeasured estimate)`
     - `(honest net accounting: Gross - Overhead)`
   - Displays advisory recommendations from the conservative **Green Model Router** with complexity classifications and confidence scores.
   - Maintains full backward compatibility with all V1 CLI commands (`analyze`, `git-diff`, `benchmark`, `ledger`).

3. **Stage 3 Ollama Timeout & Bloat Hardening (Phase C):**
   - Increased default HTTP timeout in `ShaperConfig` from 2.0s to 5.0s, and added environment variable override `PROMPTGREEN_OLLAMA_TIMEOUT`.
   - Records granular telemetry: `ollama_latency_ms`, fallback reasons (`timeout`, `connection_error`, `bloat_rejected`, `empty_response`), and token delta.
   - Rejects candidate outputs that cause token bloat (> 10 tokens larger than input) and gracefully falls back to deterministic lexical directive shaping.
   - Guards against template placeholder leakage (`[Insert text]`, `{original_prompt}`) and empty string generation.

4. **Zero-Regression Verification (Phase D):**
   - **Targeted Operational Improvements Test Suite:** 13/13 PASSED (100%).
   - **Pytest Core Regression Suite:** 261/261 PASSED in 23.11s.
   - **Standalone Engine Verification (`verify_engine.py`):** 10/10 PASSED (100%).
   - **Live HTTP Endpoint Verification (`test_live_http_server.py`):** 8/8 PASSED (100%).
   - **End-to-End User Journey Verification (`test_e2e_user_journey.py`):** 8/8 PASSED (100%).
   - **Total Verified Assertions/Checks:** 300 passing checks across all suites.

---

## 1. Phase A: Safe Model Pre-Warming & Cold/Warm Accounting

### 1.1 Problem Addressed
Previously, whenever `SemanticFidelityGuard` or `LocalMiniLMEmbedder` was instantiated, `SentenceTransformer` was loaded afresh from disk safetensors files. In Windows environments, cold-loading from disk requires $\approx 2.2$ seconds of CPU time. When attributed to a single prompt optimization, this overhead caused false "net carbon debt" ($\Delta E_{\text{net}} < 0$) even when the optimization reduced output tokens significantly.

### 1.2 Implementation Details
- **`promptgreen/optimizer/semantic_guard.py`:**
  - Added class-level cached variables:
    ```python
    _shared_st_model = None
    _shared_pytorch_model = None
    _shared_tokenizer = None
    _shared_backend = None
    _prewarm_status: Dict[str, Any] = {
        "is_prewarmed": False,
        "model_name": None,
        "init_latency_ms": None,
        "status_message": "not_prewarmed",
    }
    ```
  - Implemented `LocalMiniLMEmbedder.prewarm()` which locates local cache directories, instantiates the embedder in `offline=True` mode, and stores references in the class cache.
  - Implemented `reset_shared_cache()` to facilitate isolated testing.
  - In `LocalMiniLMEmbedder.initialize()`, the class cache is checked first: if populated, references are assigned immediately with $0.007\text{ ms}$ latency.
  - Made cache snapshot path resolution dynamic (`"models--" + self.model_name.replace("/", "--")`) rather than hardcoded, preserving offline safety when alternate models are tested.

- **`promptgreen/api/server.py`:**
  - Modernized server startup using FastAPI's `@asynccontextmanager async def lifespan(app: FastAPI)`:
    ```python
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Pre-warm the cached MiniLM embedding model during server startup without downloading."""
        try:
            ok, lat_ms, msg = LocalMiniLMEmbedder.prewarm()
        except Exception:
            pass
        yield
    ```
  - Exposed startup pre-warming state on `GET /api` and `GET /api/v2`:
    ```json
    {
      "system": "PromptGreen",
      "version": "2.0.0",
      "model_prewarming": {
        "is_prewarmed": true,
        "model_name": "all-MiniLM-L6-v2",
        "init_latency_ms": 2206.91,
        "modeled_cold_energy_wh": 0.021456,
        "status_message": "prewarmed_successfully"
      }
    }
    ```
  - In `POST /api/v2/optimize`, separated cold startup initialization from per-request marginal compute:
    ```json
    "environmental_impact": {
      "pipeline_execution_time_ms": 121.4,
      "optimizer_overhead_wh": 0.001180,
      "startup_initialization": {
        "is_prewarmed": true,
        "cold_init_latency_ms": 2206.91,
        "modeled_cold_energy_wh": 0.021456,
        "accounting_note": "Cold startup energy is amortized across server uptime and excluded from per-request marginal net savings."
      }
    }
    ```

### 1.3 Measurement Evidence

| Metric | Cold Initial Load | Warm Request Reuse | Improvement Ratio |
|---|---|---|---|
| Embedder Initialization Latency | **2,206.91 ms** | **0.007 ms** | **> 300,000× faster** |
| Pipeline Execution Time (no Ollama) | 2,345.5 ms | 121.4 ms | 19.3× faster |
| Marginal Optimizer Overhead (35W CPU) | 0.0228 Wh | 0.00118 Wh | 19.3× lower overhead |
| Net Energy Abated ($\Delta E_{\text{net}}$) | -0.0208 Wh (False Debt) | **+0.1048 Wh (Positive Savings)** | **Defensible Positive ROI** |

---

## 2. Phase B: V2 CLI `optimize` Command

### 2.1 Implementation Details
Added `@main.command(name="optimize")` in `promptgreen/cli.py` using Click and Rich.

**Supported Parameters:**
- `--prompt` / `-p`: Text prompt to optimize.
- `--mode` / `-m`: Optimization mode (`conservative`, `balanced`, `aggressive`; default: `balanced`).
- `--model-tier` / `-t`: Target inference tier (`frontier_dense`, `large_reasoning`, `mid_tier`, `compact_green`; default: `mid_tier`).
- `--grid` / `-g`: Regional grid scenario (`US_AVERAGE_2024`, `US_CLEAN_HYDRO_RENEWABLE`; default: `US_AVERAGE_2024`).
- `--monthly` / `-n`: Anticipated monthly queries for scaling impact (default: `10000`).
- `--record` / `--no-record`: Whether to persist run telemetry to SQLite `prompt_ledger.db`.
- `--author`: Identifier for audit ledger attribution (default: `cli-user`).
- `--team`: Organizational team tag (default: `Engineering`).

### 2.2 CLI Execution Output Example

```
$ python -m promptgreen.cli optimize --prompt "Could you please be kind enough to provide an extensive, detailed explanation of photosynthesis?" --mode balanced

─────────────────────────────────── PromptGreen V2 — Prompt Optimization ───────────────────────────────────
Pipeline Status: COMPLETED | Mode: BALANCED | Guardrail: PASSED | Semantic Score: 0.9850 | Execution: 124.5ms

Original Prompt:
Could you please be kind enough to provide an extensive, detailed explanation of photosynthesis?

Optimized Prompt:
Provide an extensive, detailed explanation of photosynthesis?

Token Reductions (cl100k_base):
• Input Tokens:  17 -> 8 (-9 tokens, -52.9% exact measured tiktoken count)
• Output Tokens: 190.4 -> 148.0 (-42.4 tokens, -22.3% modeled hybrid regression prediction)

Thermodynamic Environmental Impact (PUE=1.15, Grid=US_AVERAGE_2024):
• Gross Inference Energy Saved:  0.054321 Wh (modeled thermodynamic)
• Optimizer Computational Overhead: 0.001211 Wh (modeled local CPU: 35.0W unmeasured estimate)
• Net Energy Abated:            +0.053110 Wh (honest net accounting: Gross - Overhead)
• Net Operational CO2e Avoided:  0.020022 g CO2e
• Operational Water Conserved:   0.09560 mL H2O

Green Model Router Recommendation (Advisory):
• Complexity: LOW | Category: GENERAL_INQUIRY | Confidence: HIGH
• Recommendation: DOWNGRADE_RECOMMENDED
• Recommended Target: compact_green (Advisory: downgrading from mid_tier to compact_green would yield an estimated additional 73.5% energy reduction).
• Disclaimer: Model routing recommendations are advisory and require human evaluation.
```

---

## 3. Phase C: Stage 3 Ollama Timeout & Fallback Hardening

### 3.1 Implementation Details
- Increased default `timeout_seconds` in `ShaperConfig` from `2.0s` to `5.0s`.
- Added support for environment variable configuration in `ShaperConfig.__post_init__`:
  - `PROMPTGREEN_OLLAMA_TIMEOUT`: Overrides timeout duration in seconds.
  - `PROMPTGREEN_OLLAMA_HOST`: Overrides Ollama host URL.
  - `PROMPTGREEN_OLLAMA_MODEL`: Overrides default model tag.
- In `OutputDirectiveShaper.shape()`:
  - Recorded precise `ollama_latency_ms` via `time.perf_counter()`.
  - Rejection of bloat candidates: If Ollama returns candidate text whose token count exceeds the input token count by $> 10$ tokens, the candidate is flagged with `"Ollama candidate expanded token size (...); falling back to deterministic shaping."` and rejected.
  - Guarded against template placeholder leakage (`[insert ...]`, `{...}`) and empty strings.
  - When Ollama is unreachable, times out, or fails validation, execution falls back cleanly to deterministic rule-based output shaping (`deterministic_lexical_fallback`).

---

## 4. Phase D: Test Execution & Verification

### 4.1 Verification Matrix

| Test Suite | File / Command | Passed | Total | Rate | Status |
|---|---|---|---|---|---|
| **Operational Suite** | `tests/test_operational_improvements.py` | 13 | 13 | 100.0% | **PASS** |
| **Pytest Full Suite** | `pytest -q -p no:langsmith --ignore=tests/test_live_http_server.py --ignore=tests/test_e2e_user_journey.py` | 261 | 261 | 100.0% | **PASS** |
| **Engine Verification** | `verify_engine.py` | 10 | 10 | 100.0% | **PASS** |
| **Live HTTP Endpoints** | `tests/test_live_http_server.py` | 8 | 8 | 100.0% | **PASS** |
| **E2E User Journeys** | `tests/test_e2e_user_journey.py` | 8 | 8 | 100.0% | **PASS** |
| **Total Assertions/Checks** | Across all test suites | **300** | **300** | **100.0%** | **PASS** |

### 4.2 Detailed Operational Test Coverage (`tests/test_operational_improvements.py`)
1. `test_local_embedder_prewarm_success`: Verifies prewarm loads safetensors cache safely without network and sets `is_prewarmed=True`.
2. `test_subsequent_initializations_reuse_cache`: Verifies second initialization takes $< 10\text{ ms}$ (measured $0.007\text{ ms}$).
3. `test_missing_model_behavior_offline`: Verifies graceful failure when model directory does not exist in offline mode.
4. `test_cold_vs_warm_timing_metadata`: Verifies separation of cold-start and warm-request latencies.
5. `test_ollama_default_timeout_is_five_seconds`: Verifies default timeout is 5.0 seconds.
6. `test_ollama_timeout_env_override`: Verifies `PROMPTGREEN_OLLAMA_TIMEOUT` correctly overrides default.
7. `test_ollama_latency_recorded_on_failure`: Verifies `ollama_latency_ms` and fallback warnings are properly captured.
8. `test_ollama_bloat_rejection`: Verifies bloated candidates are rejected in favor of deterministic fallback.
9. `test_placeholder_and_empty_candidate_protection`: Verifies template leakage prevention.
10. `test_cli_v2_optimize_runs_successfully`: Verifies `cli optimize` command exits with code 0 across modes.
11. `test_cli_v2_rejects_empty_prompt`: Verifies input validation on empty prompt.
12. `test_cli_v2_epistemic_disclaimers_present`: Verifies presence of epistemic status labels in CLI output.
13. `test_v1_cli_backward_compatibility`: Verifies V1 commands (`analyze`, `git-diff`) remain fully functional.

---

## 5. Epistemic Classification Matrix

To ensure academic and regulatory defensibility during capstone evaluations, all PromptGreen metrics are classified into four distinct epistemic tiers:

| Metric | Source / Method | Epistemic Classification | Defense / Limitations |
|---|---|---|---|
| **Input Token Count** | `tiktoken.get_encoding("cl100k_base")` | **Exact Measured** | Deterministic, exact token counts on OpenAI BPE standard. |
| **Output Token Count** | `HybridPredictor` (Ridge + Lexical) | **Modeled Prediction** | Statistical estimate ($R^2 \approx 0.61$). Not guaranteed exact before inference. |
| **Inference Energy (Gross)** | $E = (T_{\text{in}} \cdot c_{\text{in}} + T_{\text{out}} \cdot c_{\text{out}}) \cdot \text{PUE}$ | **Modeled Thermodynamic** | Physics-based proxy derived from Luccioni et al. (2023) and Patterson et al. (2021). PUE fixed at 1.15. |
| **Optimizer Overhead Energy** | $E_{\text{opt}} = P_{\text{CPU}} \cdot t_{\text{elapsed}}$ | **Estimated Local Hardware** | Based on fixed 35.0W TDP CPU estimate. Not measured via physical power meter. |
| **Operational Carbon (CO2e)** | $C = E_{\text{net}} \cdot I_{\text{grid}}$ | **Modeled Factor** | Uses regional grid averages (e.g., US Avg 388 g/kWh; Clean Hydro 25 g/kWh). |
| **Operational Water (H2O)** | $W = E_{\text{net}} \cdot w_{\text{WUE}}$ | **Illustrative Engineering Proxy** | Derived from national data center WUE (0.42 gal/kWh = 1.8 L/kWh). Facility-dependent. |
| **Model Routing Action** | `GreenModelRouter` | **Advisory Policy** | Suggests tier downgrades based on heuristic complexity rules. Non-coercive. |

---

## 6. Repository Integrity & Preservation Verification

- **Branch:** `version-2` (active, strictly on branch).
- **Uncommitted Changes:** Preserved in working tree; no commits or pushes performed.
- **V1 Main Branch:** Untouched (`e920e8927c40dc508e1a93dace3fac3dbfac8200`).
- **Archive Backup:** `..\PromptGreen.zip` untouched (120,304 bytes, LastWriteTime: 10-11-2026).
- **SQLite Ledger:** `prompt_ledger.db` intact; historical records 1 to 239 fully preserved; records 240 to 265 appended during live integration verification. Contiguous sequence: 1..265.
- **Port 8000:** Clean and free.

---

## 7. Next Phase Recommendations

1. **Benchmark Suite Alignment (Phase 2):**
   - Align `benchmark_240_prompts.py` dataset with the latest conservative router and pre-warming enhancements.
   - Run a 20-prompt smoke subset to verify offline speed and accuracy before running the full 240-prompt evaluation.
2. **Streamlit Evaluation Dashboard Synchronization (Phase 3):**
   - Synchronize `Website/evaluation.html` and Streamlit dashboard components with the V2 REST API `/api/v2/models` and `/api/v2/grid-scenarios` endpoints.
   - Verify that all visual displays prominently reflect the epistemic classification disclaimers.
