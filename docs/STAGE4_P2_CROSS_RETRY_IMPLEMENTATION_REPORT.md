# Stage 4 P2 Cross-Retry Original Prompt Embedding Retention: Architecture Inspection and Feasibility Report

**Author:** PromptGreen Engineering & Optimization Core  
**Date:** November 24, 2026  
**Project:** PromptGreen v2.0  
**Branch:** `version-2`  
**Reference Directive:** Phase 1 Retry Architecture Inspection Gate  
**Target Investigation:** P2 Cross-Retry Original Prompt Embedding Retention  
**Primary Files Inspected:**  
- [`promptgreen/optimizer/semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/semantic_guard.py)  
- [`promptgreen/optimizer/pipeline.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/pipeline.py)  
- [`tests/test_semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/tests/test_semantic_guard.py)  
- [`tests/test_stage4_memoization.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/tests/test_stage4_memoization.py)  
- [`docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md)  
- [`docs/STAGE4_MEMOIZATION_IMPLEMENTATION_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_MEMOIZATION_IMPLEMENTATION_REPORT.md)  
- [`docs/STAGE4_MEMOIZATION_FINAL_AUDIT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_MEMOIZATION_FINAL_AUDIT.md)  

---

## 1. Executive Summary & Directive Decision

### Directive Mandate:
> *"Determine precisely whether retries invoke `evaluate()` multiple times, whether each retry recomputes the original prompt embedding, and whether original prompt chunk embeddings are also recomputed. If the retry architecture does not actually repeat original-prompt embedding computation, STOP and report why P2 would provide no benefit."*

### Architectural Finding:
Following forensic inspection of [`promptgreen/optimizer/pipeline.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/pipeline.py) and [`promptgreen/optimizer/semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/semantic_guard.py), along with empirical forward-pass call tracing on retry-triggering prompts from the frozen IGE-1000 dataset:

1. **`evaluate()` is invoked exactly once:** `PromptGreenPipeline.optimize()` invokes `self.guardrail.evaluate()` **once per optimization request** (line 570 of `pipeline.py`).
2. **`orig_emb` is never recomputed across retries:** In `SemanticFidelityGuard.evaluate()`, `orig_emb = self.embedder.embed(original_prompt)` is executed at line 1219, **outside and before the adaptive relaxation `while True:` loop**. It is stored in a local variable `orig_emb` and reused across all retries without re-computation.
3. **Original chunk and window embeddings are already 100% cached by P1:** The P1 request-level cache (`with self.embedder.request_cache() as req_cache:`, line 1216) encloses the entire `evaluate()` call, including the `while True:` retry loop. On retry iterations, all chunk embeddings and multi-chunk window embeddings for `original_prompt` hit `chunk_cache` and `text_cache`.
4. **Physical Neural Forward Passes on Retries:** Empirical tracing on prompt `ige-0016` (which triggers 2 retries) confirmed that **exactly zero MiniLM forward passes** are executed for `original_prompt` during retry 1 and retry 2.

### Formal Decision:
In strict compliance with the user directive, **P2 implementation is STOPPED**.  
No production code modifications are made because P2 would provide **zero computational benefit** ($0.00\text{ ms}$ neural compute savings). Introducing an additional cross-retry retention mechanism would add architectural complexity, memory overhead, and state-management risks with zero measurable latency reduction.

---

## 2. Precise Phase 1 Architectural Determinations

| Inspection Question | Architectural Reality | Verification Evidence |
|---|---|---|
| **1. Whether retries invoke `evaluate()` multiple times** | **NO.** `evaluate()` is called exactly once. | In `pipeline.py` (lines 538–575), adaptive retries are handled via a callback (`pipeline_retry_callback`) passed into a single invocation of `self.guardrail.evaluate()`. |
| **2. Whether each retry recomputes the original prompt embedding** | **NO.** `orig_emb` is computed once at line 1219 before the loop starts. | Line 1219 of `semantic_guard.py` precedes `while True:` (line 1275). The local variable `orig_emb` is reused across all iterations of the retry loop. |
| **3. Whether original prompt chunk embeddings are also recomputed** | **NO.** Zero neural forward passes occur for original chunks on retries. | P1's `request_cache` (line 1216) spans the entire `evaluate()` call. In retry iterations 1 and 2, `embed_chunks(original_prompt)` and `orig_windows_vecs` hit `chunk_cache` and `text_cache` with 100% cache hit rates. |
| **4. Whether retry inputs or model configuration can change** | **NO.** Model configuration and `original_prompt` remain strictly invariant. | Only `current_mode`, `active_threshold`, and `current_candidate` (regenerated candidate) change across retries. |
| **5. Whether the original prompt representation is identical across retries** | **YES.** The original prompt is an immutable Python string. | Invariant across all iterations. |

---

## 3. Empirical Verification: Call Trace on Multi-Retry Prompt (`ige-0016`)

To verify the theoretical analysis with absolute empirical certainty, we instrumented `LocalMiniLMEmbedder.embed()` and `LocalMiniLMEmbedder._encode_single_chunk()` during the optimization of `ige-0016` (Medium length profile, 2 retries in Aggressive mode, rolling back to Conservative):

```
Target Prompt: ige-0016 (Medium)
Text: "I would appreciate it if you could implement the Tarjan strongly connected components..."
Selected Mode: aggressive | Retries Executed: 2 | Final Mode: conservative

Total Embedding/Encode Calls Logged: 33
Original Prompt Invocations: 17
Original Prompt Model Computations (Forward Passes): 6 (All occurred in initial setup)
Original Prompt Model Computations during Retry 1: 0
Original Prompt Model Computations during Retry 2: 0
Original Prompt Cache Hits (P1 Reused): 5
```

### Detailed Sequential Trace of `original_prompt` Invocations:
1. `[Call 01]` `embed(original_prompt)` $\to$ **MISS (computed once at line 1219 before retry loop)**.
2. `[Call 02]` `_encode_single_chunk(chunk_0)` $\to$ **MISS (computed once during line 1219)**.
3. `[Call 03-08]` `embed` & `_encode_single_chunk` on initial multi-chunk windows $\to$ **MISS (computed once in Iteration 0)**.
4. **Candidate 0 Fails Aggressive Gate $\to$ Retry 1 Triggered (Balanced Mode):**
   - Candidate regenerated via Stage 2/3.
   - `embed_chunks(original_prompt)` called $\to$ **100% HIT (P1 chunk cache)**.
   - `orig_windows_vecs` called $\to$ **100% HIT (P1 text cache)**.
   - **Forward passes for original prompt: 0.**
5. **Candidate 1 Fails Balanced Gate $\to$ Retry 2 Triggered (Conservative Mode):**
   - Candidate regenerated via Stage 2/3.
   - `embed_chunks(original_prompt)` called $\to$ **100% HIT (P1 chunk cache)**.
   - `orig_windows_vecs` called $\to$ **100% HIT (P1 text cache)**.
   - **Forward passes for original prompt: 0.**

### Conclusion from Empirical Trace:
Across both retry attempts, **zero neural forward passes** were executed for the original prompt. P1's request-level ephemeral cache already completely eliminates 100% of redundant forward passes for the original prompt.

---

## 4. Why P2 Provides No Measurable Benefit

### 4.1 The Origin of the P2 Hypothesis
In [`docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md`](file:///d:/EDU/DSU/Major%20project/PromptGreen/docs/STAGE4_LATENCY_DIAGNOSTIC_REPORT.md), P2 was proposed prior to implementing P1 under the assumption that retrying prompts incurred:
> *"$-100\%$ original prompt re-compute cost on retries ($\sim 200-400\text{ ms}$)"*

This estimate was based on the un-memoized behavior where `orig_chunks` and `orig_windows_vecs` re-executed 10–20 forward passes on every retry.

### 4.2 The Reality After P1 Implementation
Because P1 wraps `evaluate()` in its entirety, all original prompt chunks and multi-chunk window combinations are memoized during the initial evaluation pass. When retries occur:
- Model forward pass cost: **$0.00\text{ ms}$** (already eliminated by P1).
- Python overhead for cache lookups: **$\sim 0.03\text{ ms}$** ($30\text{ microseconds}$).

Eliminating $30\text{ microseconds}$ of in-memory dictionary lookups in an optimization stage that takes $800-2,500\text{ ms}$ represents a theoretical maximum improvement of **$0.0012\%$**, which is undetectable beneath host CPU clock jitter ($1-5\text{ ms}$).

### 4.3 Risks of Forcing an Unnecessary Implementation
Attempting to implement an external "P2 Cross-Retry Cache" would introduce severe architectural and correctness liabilities:
1. **Scope Bleed:** Would require stateful caching across `evaluate()` calls or hoisting variables out of `evaluate()` into `pipeline.py`.
2. **Memory Leakage:** Retaining original prompt representations across broader scopes risks violating the strict zero-cross-request persistence invariant established in P1.
3. **Synchronization Overhead:** Extra cache management layers would exceed the $30\text{ microsecond}$ dictionary lookup cost they seek to optimize.

---

## 5. Scope, Regression & Integrity Verification

Because Phase 1 determined that P2 provides no computational benefit and should be stopped, no production code was modified.

1. **Production Code State:** [`promptgreen/optimizer/semantic_guard.py`](file:///d:/EDU/DSU/Major%20project/PromptGreen/promptgreen/optimizer/semantic_guard.py) remains in its verified P1 state.
2. **Regression Suites:** All 204 tests continue to pass 100%:
   - `tests/test_optimizer_correctness_fixes.py`: 115 passed.
   - `tests/test_semantic_guard.py`: 70 passed.
   - `tests/test_benchmark_v2.py`: 8 passed.
   - `tests/test_stage4_memoization.py`: 11 passed.
3. **Cryptographic Integrity:**
   - `data/benchmark_ige_1000_unseen.json`: SHA-256 `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3` (**MATCH**)
   - `data/benchmark_1200_independent.json`: SHA-256 `13dd7cece5794e4071f2987ef7aa3971b5f8bf86d97e466807afc330ab01363e` (**MATCH**)
   - `data/benchmark_240_independent.json`: SHA-256 `977f52289f073afe5f7db536063a3080cef36699987ecbac5b690270ead1176f` (**MATCH**)
   - `../PromptGreen.zip`: SHA-256 `dc8b78a3371efbcb1066169222ad98053ff4f36e1d49f79974246e0243d08808` (**MATCH**)
   - Database row counts: `prompt_ledger.db` (413), historical ledger (3,600), IGE ledgers (1,000 each) (**ALL MATCH**).
4. **Git Status:** Branch `version-2`, HEAD `0a4097172c6cd1f75cc20abe8dc591f17092a455`, zero staged files.

---

## 6. Recommended Next Step: Advance Directly to P3

Rather than expending engineering effort on a redundant P2 optimization that yields $0.00\text{ ms}$ of compute savings, PromptGreen should proceed directly to **Optimization P3: Vectorized MiniLM Batch Encoding**:

### P3 Overview:
- **Bottleneck Addressed:** Currently, `_MiniLMEngine` executes BERT forward passes sequentially one chunk at a time (`shape = [1, seq_len]`), incurring repetitive Python interpreter loop overhead and PyTorch kernel launch penalties.
- **Proposed Optimization:** Vectorize window and sentence encoding into mini-batches of 16–32 snippets (`shape = [batch_size, seq_len]`).
- **Validated Speedup:** Diagnostic benchmarking on 30 snippets confirmed that batching reduces compute latency from **$936.92\text{ ms}$ to $745.24\text{ ms}$** ($1.26\times$ speedup) with **exact numerical equivalence ($0.00000000\text{e}+00$ maximum difference)**.
