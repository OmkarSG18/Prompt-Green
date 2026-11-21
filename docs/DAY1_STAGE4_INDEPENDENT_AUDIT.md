# PROMPTGREEN v2.0 — STAGE 4 INDEPENDENT TECHNICAL AUDIT
## Semantic Fidelity Guardrail & Embedding Verification Audit

**Date:** November 21, 2026
**Auditor:** Independent Technical Reviewer (PromptGreen Capstone Project Verification Team)
**Host Environment:** Windows 11, Intel Core i7-10610U CPU (4 cores, 8 threads), 32 GB RAM
**Active Branch:** `version-2` (Tracking `origin/version-2`)
**Audit Scope:** Read-only inspection of source code, configurations, math, and benchmarks for Day 1 Stage 4.

---

## 1. Executive Summary

An independent, rigorous source code audit was conducted on the Stage 4 implementation:
- `promptgreen/optimizer/semantic_guard.py`
- `promptgreen/optimizer/__init__.py`
- `tests/test_semantic_guard.py`
- `tests/benchmark_semantic_guard.py`
- `docs/DAY1_STAGE4_REPORT.md`

### Audit Verdict: **PASS WITH NOTED ARCHITECTURAL CONCERNS**
The implementation successfully implements a fail-safe, offline-capable, CPU-first semantic guardrail adhering to thesis requirements. It reliably enforces the Balanced $0.92$ threshold, executes bounded adaptive relaxation retries, and protects critical keywords.

However, the audit identified **two High-priority** and **three Medium-priority** design characteristics and edge-case limitations that must be formally documented and addressed prior to unified pipeline integration.

---

## 2. Detailed Audit Findings

### Audit 1 — Native MiniLM Implementation

Because the `transformers` and `sentence_transformers` packages are not installed in the host Python environment, Stage 4 implements a direct PyTorch forward pass (`_build_minilm_pytorch_module`) reading the locally cached `model.safetensors` weights and `tokenizer.json` for `sentence-transformers/all-MiniLM-L6-v2`.

| Subsystem Component | Audit Finding | Verification Status |
| :--- | :--- | :---: |
| **1. Word Embeddings** | Word embedding weights loaded from `embeddings.word_embeddings.weight` (shape: `[30522, 384]`). Uses `F.embedding`. | **VERIFIED** |
| **2. Position Embeddings** | Position embeddings loaded from `embeddings.position_embeddings.weight` (shape: `[512, 384]`). Generated via `torch.arange(seq_len)`. Matches BERT standard. | **VERIFIED** |
| **3. Token Type Embeddings** | Token type embeddings loaded from `embeddings.token_type_embeddings.weight` (shape: `[2, 384]`). Default zeros used for single sequence. | **VERIFIED** |
| **4. Transformer Layers** | 6 post-LayerNorm encoder layers matching MiniLM-L6 architecture: 12 attention heads ($d_k = 32$), hidden dimension 384, intermediate dimension 1536, GELU activation, and $\epsilon = 10^{-12}$ LayerNorm. | **VERIFIED** |
| **5. Attention Masking** | Attention mask extended to additive bias: `ext_mask = (1.0 - attention_mask) * -10000.0`. Padding tokens receive effectively zero attention weight after softmax. | **VERIFIED** |
| **6. Padding Behavior** | `tokenizer.json` applies a fixed right-padding strategy of 128 tokens (`pad_id: 0`, token `[PAD]`). Unpadded tokens receive `attention_mask = 1.0`. | **VERIFIED** |
| **7. Mean Pooling** | Computes attention-weighted token average: $\frac{\sum (\mathbf{h}_i \cdot m_i)}{\sum m_i}$. Matches sentence-transformers `1_Pooling/config.json` (`pooling_mode_mean_tokens: true`). Clamped by $\epsilon = 10^{-9}$. | **VERIFIED** |
| **8. L2 Normalization** | Applied via `F.normalize(mean_pooled, p=2, dim=1)` to ensure unit sphere projection. | **VERIFIED** |
| **9. Special Tokens** | `tokenizer.json` built-in `TemplateProcessing` automatically injects `[CLS]` (ID 101) at index 0 and `[SEP]` (ID 102) after sequence. Both are included in mean pooling as per Sentence-BERT specification. | **VERIFIED** |
| **10. Truncation & Max Length** | `tokenizer.json` sets `max_length: 128` with `strategy: LongestFirst`. Prompts exceeding 128 tokens are truncated at 128 tokens. While underlying BERT supports 512, the cached tokenizer configuration enforces 128. | **VERIFIED (Noted Limitation)** |
| **11. Model Evaluation Mode** | Forward pass is wrapped in `with torch.no_grad():`. Because `_MiniLMEngine` omits Dropout layers, output is deterministic across evaluation and training contexts. | **VERIFIED** |
| **12. CPU Inference** | Operates strictly on CPU in ~20 ms per forward pass. | **VERIFIED** |

*Independent Parity Note:* Exact floating-point parity against official `sentence_transformers.SentenceTransformer.encode()` could not be measured directly on this host because `sentence_transformers` is uninstalled. However, vector normalization, dimensionality, semantic separation ($S_{\text{cos}} = 1.000$ identical, $0.561$ related, $0.096$ unrelated), and architecture configuration are verified.

---

### Audit 2 — Cosine Similarity Implementation

Inspected `compute_cosine_similarity(vec_a, vec_b)`:

```python
def compute_cosine_similarity(vec_a: Any, vec_b: Any) -> float:
    if vec_a is None or vec_b is None:
        return 0.0
    a = np.asarray(vec_a, dtype=np.float32).flatten()
    b = np.asarray(vec_b, dtype=np.float32).flatten()
    if a.size == 0 or b.size == 0 or a.shape != b.shape:
        return 0.0
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = float(np.dot(a, b))
    sim = dot / (norm_a * norm_b)
    return float(np.clip(sim, -1.0, 1.0))
```

#### Findings:
1. **Dimension Checking:** Handles `None`, empty arrays, and dimension mismatches by returning `0.0`.
2. **Zero Vector Handling:** Explicitly guards against division by zero when $\|\mathbf{a}\| = 0$ or $\|\mathbf{b}\| = 0$, returning `0.0`.
3. **Numerical Clipping:** Clips float range to $[-1.0, 1.0]$ to eliminate floating-point precision overshoot (e.g. $1.0000002$).
4. **NaN and Infinity Edge Case (High Concern):**
   - If an input vector contains `NaN` or `Inf`, `norm` and `dot` evaluate to `NaN`.
   - `sim` evaluates to `NaN`.
   - In `evaluate()`: `similarity_score >= active_threshold` evaluates `float('nan') >= 0.92` as `False`, which correctly prevents accidental acceptance.
   - **Flaw:** `similarity_score` retains `nan` rather than being caught and sanitized to `0.0` or raising an explicit calculation error.

---

### Audit 3 — Retry and Adaptive Fallback Logic

Inspected `evaluate()` retry mechanism (lines 660–723):

```python
mode_relaxation_chain = {
    "aggressive": "balanced",
    "balanced": "conservative",
    "conservative": None,
}
```

#### Findings:
1. **Genuine Configuration Regeneration vs. Threshold Shifting:**
   - When a candidate fails, `evaluate()` checks if `retry_callback` is provided.
   - If provided, it queries `retry_callback(current_mode, retries_used)` with the relaxed mode (`current_mode`).
   - In Stage 2 (`compressor.py`), changing mode from `aggressive` to `balanced` relaxes the retention rate from $0.40$ to $0.55$ and $\tau$ from $0.40$ to $0.60$. From `balanced` to `conservative`, rate relaxes to $0.75$ and $\tau$ to $0.80$.
   - **Verdict:** When connected to Stage 2 via `retry_callback`, the retry mechanism **genuinely regenerates candidates with less aggressive compression**, rather than merely adjusting the guardrail threshold.
2. **Standalone Invocation Behavior:**
   - If the caller passes static strings without a `retry_callback` (`retry_callback is None`), no regeneration is possible. The loop breaks immediately and safely rolls back to the original prompt.
3. **Bounded Iteration:**
   - Retries are strictly bounded by `max_retries` (default: 2), guaranteeing no infinite loops.
4. **Scope of Retries:**
   - Stage 1 (rule pruner) is deterministic and has no modes.
   - Stage 3 (output shaper) has no modes.
   - Therefore, **Stage 2 (compressor) is the sole stage whose compression parameters relax during retries**.

---

### Audit 4 — Multi-Stage Prompt Comparisons

Inspected prompt comparison targets (lines 623–658, 680–695):

#### Findings:
1. **Target of Evaluation:** The final candidate prompt is compared **directly against the raw original prompt** ($S_{\text{cos}}(P_{\text{orig}}, P_{\text{cand}})$).
2. **Intermediate Diagnostics:** Intermediate prompts passed via `intermediate_stages` (e.g. `stage_1`, `stage_2`, `stage_3`) are evaluated against $P_{\text{orig}}$ and recorded in `result.stage_similarities` for telemetry, but do not gate candidate acceptance.
3. **Stage 3 Directive Dilution on Short Prompts (High Concern):**
   - On the benchmark short prompt:
     - Original (7 tokens): `"Explain the concept of database indexing in simple terms."`
     - Stage 3 Shaped (16 tokens): `"Explain database indexing. Use clear, simple language. Organize the explanation into short sections."`
     - Measured Cosine Similarity: **$0.8013$**.
     - Balanced Threshold: **$0.92$**.
     - **Result:** REJECTED ($0.8013 < 0.92$) and rolled back to original prompt.
   - **Root Cause:** In short prompts, Stage 3 adds 9 tokens of structural formatting directives (+128% token increase). In dense sentence embedding models (MiniLM), mean pooling averages representations across all tokens. Because more than half the tokens are generic directive phrases rather than domain terms ("database indexing"), the pooled vector drifts substantially away from the short original prompt.
   - On medium and long prompts, directive tokens represent $< 10\%$ of the prompt, resulting in $S_{\text{cos}} \ge 0.95$.
   - **Conclusion:** Dense embedding similarity against the original unshaped prompt inherently penalizes short prompts that receive clarifying output directives. The $0.92$ threshold must not be lowered globally; rather, the pipeline orchestrator should evaluate Stage 2 vs. original for compression fidelity and Stage 3 vs. Stage 2 for directive fidelity.

---

### Audit 5 — Critical Preservation Checks

Inspected `verify_preservation()` (lines 444–546):

```python
# Negations, numbers, units, ranges, conditions, exceptions, JSON keys, URLs, paths, identifiers, code, format
```

#### Findings:
1. **Keyword Presence vs. Semantic Scope:**
   - The preservation checks are **regex keyword presence filters**, not semantic dependency parse trees.
2. **Vulnerabilities & False Negative Scenarios:**
   - **Polarity Inversion / Scope Shift:** If an optimization swaps clauses, e.g.:
     - Original: `"Do not delete production tables, but delete staging tables."`
     - Candidate: `"Delete production tables, but do not delete staging tables."`
     - Because `"do not"`, `"delete"`, and all nouns are present, the presence filter passes! However, the operational meaning was completely inverted.
   - **Multiplicity of Identical Negations:** If the original contains multiple instances of the same negation word (e.g. `"Do not format C: and do not wipe D:"`) and the candidate drops one (`"Do not format C: and wipe D:"`), `re.search(r"\bdo not\b", cand_lower)` succeeds because at least one instance remains.
   - **JSON Key Extraction Limitation:** `re.search(r"keys\s+([a-zA-Z0-9_,\s]+)", original)` only extracts keys when preceded by the literal word `"keys"`. Prompts specifying `"fields: hostname, port"` or containing inline JSON schemas are not extracted by this rule.
   - **Format Indicator Negation:** If original has `"in a table"` and candidate has `"never use a table"`, the candidate contains the word `"table"`, passing the format presence check despite inverting the instruction.
3. **Audit Conclusion:** The checks reliably catch accidental keyword pruning by extractive models (e.g. LLMLingua-2 dropping `"not"` or `"65s"`), but they cannot guarantee semantic scope invariance. Claims of "exhaustive semantic preservation" must be avoided.

---

### Audit 6 — Benchmark Suite Validity

Inspected `tests/benchmark_semantic_guard.py`:

#### Findings:
1. **Real Model Execution:** The benchmark initializes `LocalMiniLMEmbedder` with `custom_client=None`. It executes the real native PyTorch forward pass on cached `model.safetensors` weights.
2. **Warmup Integrity:** Executes an initial unmeasured evaluation pass before timing starts, eliminating cold-start initialization noise.
3. **Latency Disaggregation:**
   - `emb_latency_ms` isolates the `embed()` call.
   - `guardrail_latency_ms` measures end-to-end execution (preservation checks + embeddings + cosine similarity + threshold gating).
4. **Latency Profiles:**
   - Short: 36.74 ms total (18.09 ms embedding)
   - Medium: 45.89 ms total (23.12 ms embedding)
   - Long: 50.87 ms total (24.70 ms embedding)
5. **Accuracy of Reporting:** The Short prompt's failure ($S_{\text{cos}} = 0.8013$) is faithfully reported as `FAIL` without suppression. Latency profiles strictly reflect the host CPU and the three evaluated benchmark prompts.

---

## 3. Severity Classification & Findings Matrix

| Finding ID | Description | Severity | Impact |
| :--- | :--- | :---: | :--- |
| **SEC-01** | Stage 3 directive addition on short prompts causes false-positive rejection ($S_{\text{cos}} = 0.8013 < 0.92$). | **HIGH** | Short prompts receiving output directives roll back unnecessarily to original prompts. |
| **SEC-02** | `compute_cosine_similarity` does not sanitize `NaN`/`Inf` inputs, propagating `NaN` to `similarity_score`. | **HIGH** | While rejected by `>= 0.92`, `GuardrailResult` stores `similarity_score = nan` rather than handling calculation error cleanly. |
| **SEC-03** | Preservation rules use keyword presence matching; vulnerable to clause swapping and polarity inversion. | **MEDIUM** | Permutations of clauses with identical keywords pass preservation validation. |
| **SEC-04** | Tokenizer sequence length is hard-coded to 128 tokens by `tokenizer.json` configuration. | **MEDIUM** | Prompts longer than 128 tokens have tail tokens truncated from the embedding representation. |
| **SEC-05** | Standalone `evaluate()` without `retry_callback` cannot perform adaptive relaxation. | **MEDIUM** | Calling Stage 4 outside the pipeline orchestrator causes immediate rollback on first failure. |
| **SEC-06** | Parity against official `sentence-transformers` library unverified due to missing package in host Python. | **LOW** | Minor numerical discrepancies in 6th decimal place may exist vs official library. |
| **SEC-07** | JSON keys extraction limited to explicit `"keys ..."` phrasing. | **LOW** | Alternative phrasing (`"fields:"`, `"attributes:"`) not extracted as explicit key checks. |

---

## 4. Verified vs. Unverified Components

### Verified Components (Confirmed by Direct Inspection & Tests):
1. Native PyTorch MiniLM forward pass math: 6 layers, 12 heads, 384 hidden size, LayerNorm, GELU, and mean pooling with attention mask.
2. Unit L2 vector normalization.
3. Cosine similarity dimension and zero-vector guards.
4. Active threshold gating ($0.96, 0.92, 0.86$).
5. Preservation checks for negations, numbers, units, ranges, URLs, file paths, and code blocks.
6. Real-model CPU execution latency $< 60\text{ ms}$ (comfortably below 100 ms thesis ceiling).
7. Regression suite integrity: **115 / 115 tests passing** across all modules.
8. Core verification suite integrity: **10 / 10 prompts passing (100.0%)**.

### Unverified Components (Explicitly Documented):
1. Exact float32 parity against official Hugging Face `sentence_transformers` library (cannot be executed without installing external package).
2. Long prompt embeddings beyond 128 tokens (truncated by cached tokenizer profile).
3. Semantic scope preservation for complex compound sentences with multiple clauses.

---

## 5. Technical Validation & Git State

### Exact Test Suite Results:
- `python -m pytest -p no:langsmith -v tests/test_semantic_guard.py` $\rightarrow$ **30 / 30 PASSED in 2.89s (Exit Code: 0)**
- `python -m pytest -p no:langsmith -v` $\rightarrow$ **115 / 115 PASSED in 7.07s (Exit Code: 0)**
- `python verify_engine.py` $\rightarrow$ **10 / 10 PASSED in 6.22s (Exit Code: 0)**
- `git diff --check` $\rightarrow$ **0 whitespace errors / 0 conflicts (Exit Code: 0)**

### Working Tree & Repository Immutability:
- **Active Git Branch:** `version-2` (Tracking `origin/version-2`)
- **Main Branch:** Untouched at commit `e920e89`
- **ZIP Backup:** Untouched (`120,304 bytes`, modified `10-11-2026 23:16:43`)
- **Production Files Modified in this Audit:** **ZERO** (Audit is strictly read-only)
- **Commits / Pushes Executed:** **ZERO**
