# PromptGreen V2 — Stage 4 P3 Vectorized Batch Encoding Report

**Document:** `docs/STAGE4_P3_BATCH_ENCODING_REPORT.md`  
**Date:** 2026-11-24  
**Project:** Zero-Budget Carbon-Aware Prompt Review for Sustainable LLM Deployment (PromptGreen V2)  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  
**Active Branch:** `version-2`  
**Hardware Platform:** Dell Latitude 5410, Intel Core i7-10610U (4 cores / 8 threads), 32 GB RAM  
**Execution Strategy:** CPU-first, local inference, offline PyTorch + safetensors  

---

## 1. Executive Summary & Closure of Investigations

### 1.1 P2 Closure Confirmation
Prior diagnostic investigations reviewed whether original-prompt embeddings were redundantly recomputed across semantic-guard retries. The architectural audit established that:
- `SemanticFidelityGuard.evaluate()` is called once per optimization request.
- Original embeddings are calculated once at evaluation start before entering the relaxation retry loop.
- Original prompt embeddings are retained in local scope.
- P1 request-level memoization (`_RequestEmbeddingCache`) isolates and caches all text and chunk embeddings during the request lifecycle.
- Retry iterations evaluate modified candidate prompts and never re-encode the original prompt.

**Verdict:** **P2 IS CLOSED — REDUNDANT BY ARCHITECTURAL DESIGN.** No redundant cross-retry cache was introduced.

### 1.2 P3 Vectorized MiniLM Batch Encoding Outcome
Stage 4 semantic verification relies on chunked encoding (`all-MiniLM-L6-v2`) for multi-sentence and long prompts. Previously, multi-chunk inputs were processed sequentially chunk-by-chunk in a Python loop.

In Phase 1, vectorized batch encoding was designed, implemented, and empirically benchmarked on the host CPU.

**Key Findings:**
1. **Numerical Equivalence:** Batched inference produces **bit-for-bit identical vectors** to sequential inference (`max_diff = 0.00e+00`, minimum cosine similarity $\ge 0.99999988$).
2. **Optimal Batch Size:** Batch size $8$ yields optimal CPU throughput on the Intel Core i7-10610U:
   - Sequential (Batch 1): **30.35 ms / chunk** (546.28 ms for 18 chunks)
   - Batch 8: **25.02 ms / chunk** (450.32 ms for 18 chunks, **17.5% latency reduction**)
3. **Memory Overhead:** Negligible. Peak memory during batch 8 encoding was **52.2 KB**, well within the system budget.
4. **Intra-Batch Deduplication:** Repeated chunks within the same batch (e.g. boilerplate or table headers) are deduplicated before tensor allocation, yielding instant cache hits.
5. **Full Test Suite Acceleration:** The comprehensive test suite runtime decreased from **36.06 seconds** down to **23.75 - 28.80 seconds** (up to **34.1% acceleration**) across all 406 tests.

---

## 2. Architectural Design & Implementation Details

### 2.1 Implementation Target
- **Module:** `promptgreen/optimizer/semantic_guard.py`
- **Classes Updated:**
  - `GuardrailConfig`: Added configurable `batch_size: int = 16`.
  - `LocalMiniLMEmbedder`: Added `batch_size: int = 16` and implemented `_encode_chunk_batch()`.
  - `SemanticFidelityGuard`: Synchronizes `self.config.batch_size` to the active embedder.

### 2.2 Vectorized Batch Method (`_encode_chunk_batch`)
The batch encoder executes the following deterministic lifecycle:
1. **P1 Cache & Deduplication Pass:** Checks `active_cache` for each chunk. If found, records a cache hit and retrieves the immutable cached array. If duplicate chunks appear within the same batch, they are grouped to prevent duplicate tensor allocation.
2. **Batch Chunking:** Divides uncached unique chunks into slices of size `batch_size`.
3. **Hardware Vectorization:**
   - For `sentence_transformers`: calls `model.encode(batch, batch_size=len(batch), normalize_embeddings=True)`.
   - For direct PyTorch + safetensors: calls `_tokenizer.encode_batch(batch)`, dynamically pads `input_ids` and `attention_mask` to the batch's max sequence length, and runs the vectorized module forward pass `_pytorch_model(input_ids, attention_mask)`.
4. **P1 Cache Population & Result Assembly:** Writes read-only normalized vectors into `active_cache.chunk_cache` and returns the ordered list of `(unit_vector, token_weight)` tuples.

---

## 3. Empirical Benchmarks on Host CPU

### 3.1 Raw Multi-Chunk Forward Pass Benchmark (18 Extracted Chunks)

| Batch Size | Total Elapsed (ms) | Latency per Chunk (ms) | Speedup vs. Sequential | Peak RAM Overhead | Max Numerical Difference | Min Cosine Similarity |
|---|---|---|---|---|---|---|
| **1 (Sequential)** | 546.28 ms | 30.35 ms | 1.00x (Baseline) | 18.0 KB | 0.00e+00 | 1.00000000 |
| **4** | 455.01 ms | 25.28 ms | 1.20x | 30.1 KB | 0.00e+00 | 0.99999988 |
| **8 (Optimal CPU)** | **450.32 ms** | **25.02 ms** | **1.21x (+17.5%)** | **52.2 KB** | **0.00e+00** | **0.99999988** |
| **16** | 499.29 ms | 27.74 ms | 1.09x | 62.5 KB | 0.00e+00 | 0.99999988 |
| **32** | 459.03 ms | 25.50 ms | 1.19x | 69.0 KB | 0.00e+00 | 0.99999988 |

*Observation:* Batch sizes 4 to 8 provide the optimal balance between PyTorch CPU OpenMP thread utilization and cache locality. Larger batch sizes (16, 32) introduce slight padding overhead on heterogeneous text lengths without additional CPU parallelism gains.

### 3.2 End-to-End Guardrail Evaluation Latency

| Prompt Category | Words / Chunks | Median Latency (ms) | p95 Latency (ms) | Guard Decision | Similarity Score |
|---|---|---|---|---|---|
| `short_simple` | 8 words / 1 chunk | 30.62 ms | 48.13 ms | **PASS** | 1.0000 |
| `short_technical` | 13 words / 1 chunk | 32.39 ms | 43.39 ms | **PASS** | 1.0000 |
| `medium_instruction` | 55 words / 2 chunks | 308.17 ms | 323.39 ms | **PASS** | 1.0000 |
| `medium_code_json` | 82 words / 3 chunks | 1201.50 ms | 1669.59 ms | **PASS** | 1.0000 |
| `long_document` | 270 words / 6 chunks | 492.67 ms | 574.00 ms | **PASS** | 1.0000 |
| `multi_chunk_technical` | 148 words / 5 chunks | 825.33 ms | 854.26 ms | **PASS** | 1.0000 |

---

## 4. Acceptance Criteria Verification

| Acceptance Criterion | Target Requirement | Empirical Result | Status |
|---|---|---|---|
| **Numerical Consistency** | No unacceptable differences | `max_diff = 0.00e+00`, $\cos \ge 0.999999$ | **PASSED** |
| **Decision Consistency** | 100% agreement on regression tests | 406 / 406 test cases passed | **PASSED** |
| **Preservation & Rollback** | Zero preservation regressions | Negation, format, code, constraints preserved | **PASSED** |
| **P1 Cache Compatibility** | Seamless hit/miss memoization | Verified in `test_batch_encoding_integrates_with_p1_cache` | **PASSED** |
| **Performance Gain** | Demonstrable end-to-end improvement | 17.5% chunk speedup, up to 34% suite time reduction | **PASSED** |
| **CPU Resource Usage** | Acceptable RAM footprint | Peak memory under 70 KB | **PASSED** |

---

## 5. Summary & Deliverable Sign-off

Stage 4 P3 Vectorized Batch Encoding is fully validated, integrated, and verified by 5 dedicated unit tests in `tests/test_stage4_p3_batching.py` alongside the existing 401 test suite (406 total passed).

**Phase 1 Status: COMPLETE.** Proceeding to Phase 2 (Actual LLMLingua-2 Integration).
