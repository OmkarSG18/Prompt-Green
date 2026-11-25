# Final Technical Audit: Stage 4 Request-Level Embedding Memoization

**Audit Date:** November 24, 2026  
**Audited Artifact:** Stage 4 Request-Level MiniLM Embedding Memoization (P1)  
**Primary Target File:** [`promptgreen/optimizer/semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/semantic_guard.py)  
**Supporting Files:**  
- [`tests/test_stage4_memoization.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/tests/test_stage4_memoization.py)  
- [`tests/test_semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/tests/test_semantic_guard.py)  
- [`tests/test_optimizer_correctness_fixes.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/tests/test_optimizer_correctness_fixes.py)  
- [`docs/STAGE4_MEMOIZATION_IMPLEMENTATION_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_MEMOIZATION_IMPLEMENTATION_REPORT.md)  
- [`docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md)  
- [`scratch/measure_memoization_performance.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/scratch/measure_memoization_performance.py)  
- [`scratch/memoization_benchmark_results.json`](file:///d:/EDU/DSU/Major%20project/PromptGreen/scratch/memoization_benchmark_results.json)  

---

## 1. Executive Summary & Overall Verdict

### Verdict: **PASS WITH CAVEATS**

The implementation of Stage 4 Request-Level Embedding Memoization (**P1**) in PromptGreen v2.0 successfully resolves the primary computational bottleneck identified in [`docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md). It eliminates redundant neural forward passes on identical text snippets, slashing Stage 4 latency by **$65.65\%$ on long prompts** ($>2.1\text{ s}$ saved per prompt) and reducing total pipeline latency by **$65.03\%$**.

The implementation is numerically exact (**$0.00000000\text{e}+00$ maximum difference** across all empirical trials), preserves 100% of guardrail decisions and safety thresholds, introduces zero cross-request state leakage, and passes all **204 regression tests**.

The verdict is qualified as **PASS WITH CAVEATS** due to three specific engineering observations:
1. **Cache-Key vs. Forward-Pass Argument Discrepancy:** In `_encode_single_chunk(chunk)`, `key = chunk.strip()` is used as the dictionary key, while the unstripped `chunk` is passed to the underlying model/tokenizer. Although BERT's WordPiece tokenizer treats stripped and unstripped strings identically, passing `key` directly to the model is mathematically cleaner.
2. **Benchmark Metric Reporting Artifact on Short Prompts:** In `scratch/measure_memoization_performance.py`, short prompts show a **$54.45\%$ latency reduction** ($163.99\text{ ms} \to 74.69\text{ ms}$), yet the report lists `Chunk Forward Passes Saved: 0.0%`. Forensic investigation revealed that short prompts hit `text_cache` at the pipeline level (eliminating 3 out of 5 physical BERT forward passes), but because `_encode_single_chunk` was bypassed, `chunk_hits` was recorded as 0.
3. **Concurrency Boundary:** `threading.local` guarantees OS-thread isolation (matching FastAPI's synchronous threadpool execution), but does not isolate asynchronous coroutines interleaved on a single event loop thread (which would require `contextvars.ContextVar`).

**Retention Decision:** P1 is **safe, robust, and verified for retention**. Optimization **P2** (Cross-Retry Retention) is authorized to proceed.

---

## 2. Cache-Key Correctness & Normalization Analysis

### 2.1 Key Formation & Model Input Alignment
- In `embed(text)`:
  - Cache key: `key = text.strip()`.
  - Single-chunk text: delegates to `_encode_single_chunk(chunks[0])`, where `chunks[0]` is stripped by `chunk_text()`.
  - Multi-chunk text: `chunk_text(text)` strips outer whitespace at line 476 (`text = text.strip()`).
- In `_encode_single_chunk(chunk)`:
  - Cache key: `key = chunk.strip()`.
  - Model forward pass: lines 639, 654, and 668 invoke `self.custom_client(chunk)`, `self._st_model.encode(chunk)`, and `self._tokenizer.encode(chunk)`.
  - **Empirical Tokenizer Check:** We tested whether the BERT WordPiece tokenizer generates identical token IDs for `chunk` vs. `chunk.strip()`. The token sequences for `'  hello world  '` and `'hello world'` are bit-for-bit identical: `[101, 7592, 2088, 102]`.
  - **Audit Finding:** Because the BERT WordPiece tokenizer ignores leading and trailing whitespace, no semantic discrepancy exists in production. However, to eliminate any potential divergence with custom mock clients, `key` (or `chunk.strip()`) should be passed to the tokenizer in future refactoring.

### 2.2 Collision and False-Positive Risks
- **Internal Whitespace:** `text.strip()` removes only leading and trailing whitespace. Internal whitespace is preserved:
  `"select * from tbl"` and `"select  *  from tbl"` produce distinct keys. No collisions occur.
- **Case Sensitivity:** Case is preserved: `"Hello"` and `"hello"` produce distinct keys. No collisions occur.
- **Punctuation & Formatting:** Punctuation is preserved. No lossy hash compression is applied.
- **Unicode Representations:** Python strings use code-point equality. Composed (`café`, NFC) vs. decomposed (`cafe\u0301`, NFD) would produce distinct keys, meaning a decomposed form would result in a cache miss rather than an incorrect collision.

### 2.3 Model Configuration Isolation
- The cache container `_RequestEmbeddingCache` is instantiated per `LocalMiniLMEmbedder` instance and scoped to a single `evaluate()` call.
- Because model weights, dimensions (384), and hyperparameters remain immutable during a request, no cross-configuration pollution can occur.

---

## 3. Request Lifecycle, Concurrency & Scope Analysis

### 3.1 Ephemeral Lifecycle & State Leakage
- **Instantiation:** On entry to `SemanticFidelityGuard.evaluate()`, `with self.embedder.request_cache() as req_cache:` initializes a new `_RequestEmbeddingCache`.
- **Termination:** When `evaluate()` exits via return or exception, the `finally:` block of `request_cache()` executes:
  ```python
  finally:
      new_cache.clear()
      self._local.cache = prev_cache
  ```
  This immediately clears internal dictionary references and resets `self._local.cache = None`.
- **Cross-Request Leakage:** Verified via `test_request_isolation_and_zero_cross_request_leakage`. Before `evaluate()`, `active_cache is None`. After `evaluate()`, `active_cache is None`. Consequent evaluations on distinct prompts start with zero cached items.

### 3.2 Thread Isolation
- `self._local` is an instance of Python's standard `threading.local()`.
- Verified via `test_thread_isolation_concurrent_contexts`, where two OS threads running simultaneously with synchronized barrier starts exhibited completely independent keys, hit counts, and miss counts.

### 3.3 Nested Contexts
- In `request_cache()`, lines 418–421 explicitly check if `prev_cache is not None`. If an outer context already opened a cache (e.g., if a pipeline-level request wrapper is established), the inner context yields `prev_cache` directly without re-allocating or prematurely clearing the cache.
- Verified via `test_nested_request_cache_reuses_outer_context`.

### 3.4 Telemetry Snapshots
- `GuardrailResult.cache_stats` receives `req_cache.stats()`.
- `stats()` constructs a new dictionary composed solely of primitive integers and floats (`total_hits`, `total_misses`, `hit_rate`, `forward_passes_executed`). It holds no references to the underlying NumPy arrays or cache dictionaries, preventing memory retention.

### 3.5 Architectural Limitation: Async Coroutines
- `threading.local` is bound to the operating system thread. In FastAPI, endpoints defined with standard `def` (such as `/v2/optimize` in `promptgreen/api/server.py`) execute in dedicated threadpool threads, where `threading.local` provides complete isolation.
- However, if the optimizer is ever invoked inside an `async def` coroutine where multiple requests are cooperatively scheduled on the *same* OS thread, `threading.local` would be shared across coroutines.
- **Recommendation:** If PromptGreen migrates to native asynchronous pipeline execution, `self._local` should be complemented with Python's `contextvars.ContextVar`.

---

## 4. Numerical Equivalence & Decisional Invariance

### 4.1 Numerical Equivalence Verification
- **Bit-Exact Arrays:** Cache storage and retrieval utilize NumPy's `.copy()`:
  - Vector values on cache hits match forward-pass computations bit-for-bit.
  - In `test_repeated_text_hits_cache_and_avoids_forward_pass`, `np.testing.assert_array_equal(vec1, vec2)` confirmed identical IEEE 754 representations.
- **Cosine Similarity Invariance:** Across all 45 empirical evaluations in `scratch/memoization_benchmark_results.json`, the maximum absolute difference between uncached and cached similarity scores was:
  $$\max |\text{sim}_{\text{cached}} - \text{sim}_{\text{uncached}}| = \mathbf{0.00000000\text{e}+00}$$
- **Decisional Invariance:** In 100% of evaluated trials, the guardrail decision (`passed`, `accepted`, `rollback_occurred`, `rollback_stage`) remained perfectly invariant.

### 4.2 Array Immutability
- All cached arrays are write-protected at storage time (`arr.setflags(write=False)`).
- Verified via `test_immutability_defensive_copies`:
  - An external caller mutating `vec[0] = 999.0` did not alter subsequent cached returns.
  - Direct in-place mutation attempts on `cache.text_cache[key]` raised `ValueError: assignment destination is read-only`.

---

## 5. Performance Benchmark Methodology & Data Verification

### 5.1 Benchmark Design & Baseline Generation
- **Script:** [`scratch/measure_memoization_performance.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/scratch/measure_memoization_performance.py)
- **Baseline Generation:** The uncached baseline was generated by patching `LocalMiniLMEmbedder.active_cache` to return `None`, forcing the system to execute the exact pre-memoization code path.
- **Pre-Warming:** `LocalMiniLMEmbedder.prewarm()` and an explicit warmup evaluation were run prior to timing loops.
- **Workload Coverage:** 15 prompts (5 short, 5 medium, 5 long) were evaluated across Conservative, Balanced, and Aggressive modes (45 empirical pairs = 90 full pipeline runs).

### 5.2 Latency and Throughput Audit

| Metric | Short Prompts ($<50$ tok) | Medium Prompts ($50-200$ tok) | Long Prompts ($>200$ tok) |
|---|:---:|:---:|:---:|
| **Uncached Stage 4 Mean** | $163.99\text{ ms}$ | $484.10\text{ ms}$ | $3,498.13\text{ ms}$ |
| **Cached Stage 4 Mean** | $74.69\text{ ms}$ | $247.50\text{ ms}$ | $1,201.72\text{ ms}$ |
| **Stage 4 Latency Reduction** | **$-54.45\%$** | **$-48.87\%$** | **$-65.65\%$** |
| **Stage 4 Speedup** | **$2.20\times$** | **$1.96\times$** | **$2.91\times$** |
| **Uncached Pipeline Mean** | $191.87\text{ ms}$ | $515.50\text{ ms}$ | $3,531.00\text{ ms}$ |
| **Cached Pipeline Mean** | $97.09\text{ ms}$ | $270.39\text{ ms}$ | $1,234.85\text{ ms}$ |
| **Pipeline Latency Reduction** | **$-49.40\%$** | **$-47.55\%$** | **$-65.03\%$** |
| **Mean Time Saved Per Prompt** | $94.78\text{ ms}$ | $245.11\text{ ms}$ | **$2,296.15\text{ ms}$** |

### 5.3 Forensic Analysis: Why Short Prompts Save Latency Despite 0% Reported Chunk Savings
The benchmark summary reported:
- Short Prompts: Latency reduced by **$54.45\%$** ($163.99\text{ ms} \to 74.69\text{ ms}$)
- Short Prompts: `Chunk Forward Passes Saved: 0.0%`

Our forensic audit determined the exact cause of this apparent paradox:
1. **Pipeline Execution Flow:** During an end-to-end pipeline run, Stage 4 evaluates 5 embedding strings: `original_prompt`, `stage_1`, `stage_2`, `stage_3`, and `candidate_to_verify`.
2. **Intermediate Stage Invariance:** On short prompts, earlier stages frequently make zero modifications (e.g. Compressor finds nothing to compress so `stage_2 == stage_1`, Shaper finds no formatting rules to apply so `stage_3 == stage_2`, and `candidate_to_verify == stage_3`).
3. **`text_cache` Interception:** In the cached run, when `embed(stage_2)`, `embed(stage_3)`, and `embed(candidate_to_verify)` are called, they hit `text_cache` directly at line 699 of `semantic_guard.py` and return immediately.
4. **Physical Forward Passes Reduced by 60%:** In our diagnostic instrumented run on `ige-0001`:
   - Uncached pipeline: **5 physical BERT forward passes** ($\sim 140\text{ ms}$).
   - Cached pipeline: **2 physical BERT forward passes** ($\sim 56\text{ ms}$).
   - Actual forward passes were reduced from 5 to 2 (**60% physical compute eliminated**).
5. **The Reporting Artifact:** Because the hit occurred at the `text_cache` level, execution returned before `_encode_single_chunk` was reached. Thus, `text_hits` was incremented, but `chunk_hits` remained 0. The benchmark script computed `chunk_hits / (chunk_hits + chunk_misses)`, which mathematically yielded `0.0%`, obscuring the fact that `text_cache` had eliminated 3 out of 5 forward passes!
6. Furthermore, to collect `cstats`, line 105 of the benchmark script executed `direct_guard.evaluate(orig_text, res_cached.final_prompt)` without `intermediate_stages`, which measured only a direct 2-string comparison rather than capturing the live pipeline's intermediate hits.

### 5.4 Methodological Limitations
1. **Execution Order Bias:** In the benchmark script, the uncached trial was consistently run immediately before the cached trial for each prompt. While the model was pre-warmed, standard benchmarking protocol recommends alternating order (A/B vs. B/A) to avoid sequential cache bias.
2. **Missing p95 Measurements:** The benchmark script reported mean and median, but did not record multi-iteration variance or 95th percentile metrics for individual prompts.

---

## 6. Scope, Integrity & Regression Verification

### 6.1 Scope Enforcement
- **Modified Production File:** Only [`promptgreen/optimizer/semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/semantic_guard.py) was altered.
- **Unmodified Files:** `pipeline.py`, `rule_pruner.py`, `compressor.py`, `output_shaper.py`, and `carbon_engine.py` were completely untouched.
- **No Optimization Creep:** No batching (P3), no cross-retry retention (P2), and no intermediate stage removal (P4) were introduced.
- **Threshold Integrity:** Mode thresholds ($0.96, 0.92, 0.86$) and chunk thresholds ($0.82, 0.75, 0.65$) remain strictly identical.

### 6.2 Full Regression Test Suite Audit
All 204 tests were executed and confirmed passing:
- `tests/test_optimizer_correctness_fixes.py`: **115 / 115 passed** in $9.09\text{ s}$ (down from $22.03\text{ s}$).
- `tests/test_semantic_guard.py`: **70 / 70 passed** in $8.74\text{ s}$ (down from $15.35\text{ s}$).
- `tests/test_benchmark_v2.py`: **8 / 8 passed** in $8.65\text{ s}$.
- `tests/test_stage4_memoization.py`: **11 / 11 passed** in $4.65\text{ s}$.
- **Total Test Suite Runtime:** Dropped from **$46.58\text{ s}$ to $31.13\text{ s}$** (**$-33.17\%$**).

### 6.3 Cryptographic Hash and Ledger Verification
All system assets were verified via SHA-256 and SQLite row counts:
- `data/benchmark_ige_1000_unseen.json`: `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3` (**MATCH**)
- `data/benchmark_1200_independent.json`: `13dd7cece5794e4071f2987ef7aa3971b5f8bf86d97e466807afc330ab01363e` (**MATCH**)
- `data/benchmark_240_independent.json`: `977f52289f073afe5f7db536063a3080cef36699987ecbac5b690270ead1176f` (**MATCH**)
- `../PromptGreen.zip`: `dc8b78a3371efbcb1066169222ad98053ff4f36e1d49f79974246e0243d08808` (**MATCH**)
- `prompt_ledger.db`: **413 rows** (**MATCH**)
- `results/benchmark_1200/benchmark_ledger.db`: **3,600 rows** (**MATCH**)
- `results/ige_1000/{conservative,balanced,aggressive}/benchmark_ledger.db`: **1,000 rows each** (**MATCH**)
- **Git State:** On branch `version-2`, HEAD `0a4097172c6cd1f75cc20abe8dc591f17092a455`, **zero staged files**.

---

## 7. Unresolved Limitations & Engineering Observations

1. **Model Tokenizer Input:** Passing `key` (`chunk.strip()`) rather than `chunk` to `_encode_single_chunk` is recommended for future cleanup to maintain pure key-to-input bijection.
2. **Benchmark Reporting Metric:** Future benchmark reports should define total forward pass reduction as:
   $$\text{Reduction} = \frac{\text{Chunk Hits} + \text{Text Hits}}{\text{Total Chunk Requests} + \text{Text Requests}}$$
   to capture both chunk-level and composite text-level savings.
3. **Async Support:** If PromptGreen moves from sync FastAPI endpoints to async pipelines, `threading.local` should be replaced or augmented with `contextvars.ContextVar`.

---

## 8. Safety Verdict for P1 Retention

### Verdict: **APPROVED FOR RETENTION**
The Stage 4 Request-Level Embedding Memoization implementation is:
- **Operationally Safe:** Ephemeral, write-protected, thread-isolated, and exception-safe.
- **Mathematically Sound:** Generates $0.00000000\text{e}+00$ numerical deviation from uncached inference.
- **Highly Impactful:** Reduces Stage 4 long-prompt latency by **$65.65\%$** ($>2.1\text{ s}$ saved per prompt) and cuts test suite runtimes by over **$33\%$**.
- **Non-Invasive:** Confined to `semantic_guard.py` without touching any external contracts or thresholds.

---

## 9. Recommendation & Authorization Path for P2

### Recommendation: **PROCEED TO P2**

With P1 stably landed and verified, the project should advance to **Optimization P2: Cross-Retry Original Prompt Retention**:
- **Objective:** Within `SemanticFidelityGuard.evaluate()`, retain `orig_emb`, `orig_chunks`, and `orig_windows` across iterations of the adaptive relaxation retry loop (`while True:`).
- **Rationale:** When an adaptive retry occurs (e.g. relaxing from Aggressive to Balanced), the original prompt is immutable. Currently, `orig_emb` is cached by P1's `text_cache`, but multi-chunk window data structures (`orig_windows`, `orig_windows_vecs`) are re-instantiated. Retaining these across loop iterations will eliminate redundant window construction and achieve an additional $200-400\text{ ms}$ latency reduction on retried prompts.
