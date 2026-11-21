# PROMPTGREEN v2.0 — STAGE 5 IMPLEMENTATION REPORT
## Unified 4-Stage Active Pipeline Orchestrator & Multi-Chunk Safety Integration

**Date:** November 21, 2026
**Target Milestone:** PromptGreen v2.0 — Day 1, Stage 5
**Host Environment:** Windows 11, Intel Core i7-10610U CPU (4 Cores / 8 Threads @ 1.80GHz–4.90GHz), 32 GB RAM, Non-CUDA / CPU-first execution
**Active Git Branch:** `version-2` (Tracking `origin/version-2`)
**Base Checkpoint:** `e63f879` — `feat(v2): implement semantic fidelity guardrail with chunked MiniLM validation`

---

## 1. Executive Summary

Stage 5 delivers the **unified, four-stage active prompt optimization pipeline orchestrator** for PromptGreen Version 2.0. Rather than replacing the existing Stage 1–4 components, Stage 5 integrates them into an end-to-end executable engine housed in `promptgreen/optimizer/pipeline.py`.

### Primary Objectives Delivered:
1. **Unified Pipeline Architecture:** Integrates `RuleBasedPruner` (Stage 1), `LLMLinguaCompressor` (Stage 2), `OutputDirectiveShaper` (Stage 3), and `SemanticFidelityGuard` (Stage 4) in strict execution order.
2. **Intermediate Output Retention:** Retains and exposes outputs from all intermediate stages (`stage_1_output`, `stage_2_output`, `stage_3_output`), per-stage token deltas, stage latencies, execution statuses, and fallback flags.
3. **Multi-Chunk Semantic Safety (CHUNK-01 Resolution):** Addresses the critical audit finding from the Stage 4 final acceptance audit (`docs/DAY1_STAGE4_FINAL_ACCEPTANCE_AUDIT.md`) where localized tail divergence in long prompts could be diluted by large unchanged prefixes. Stage 4 now evaluates windowed chunk coverage ($\text{cov}_i \ge \theta_{\text{chunk}}$) and candidate relevance ($\text{rel}_j \ge \theta_{\text{chunk}}$), actively gating acceptance.
4. **Adaptive Relaxation & Recovery:** Connects the Stage 4 validation gate directly back to Stage 2 extractive compression. If an aggressive candidate fails validation, the orchestrator triggers bounded relaxation (`aggressive` $\rightarrow$ `balanced` $\rightarrow$ `conservative`). If retries fail or are exhausted, the pipeline executes an atomic, lossless rollback to the original prompt.
5. **Honest Token Accounting:** Distinguishes original tokens, stage-level tokens, final accepted tokens, and net token reductions using a single consistent tokenizer (`cl100k_base` via `tiktoken`). Stage 3 directive additions are strictly accounted for and never mischaracterized as input-token compression savings.
6. **Internal Placeholder Protection:** Guarantees that internal structural placeholders (`__CODE_BLOCK_i__`, `__JSON_BLOCK_i__`, etc.) never leak to user-facing outputs.

---

## 2. Pipeline Execution Sequence & Topology

```
                                Raw User Prompt
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Structural & Rule-Based Pruner (`RuleBasedPruner`)                 │
│ • AST parsing of fenced code blocks, JSON schemas, URLs, paths, constraints │
│ • Conservative pruning of conversational greetings and sign-offs            │
│ • Byte-for-byte structural restoration into `stage_1_output`                │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Extractive Token Compression (`LLMLinguaCompressor`)               │
│ • Microsoft LLMLingua-2 token classifier / CPU information-density fallback │
│ • Retention rates: Conservative (0.75), Balanced (0.55), Aggressive (0.40)  │
│ • Strict protection of immune words, negations, conditionals, and numbers   │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Abstractive Output Directive Shaper (`OutputDirectiveShaper`)      │
│ • Clarifies output formatting bounds (tables, JSON keys, numbered lists)    │
│ • Local Ollama SLM (qwen2.5:0.5b) or deterministic rule template fallback   │
│ • Instruction preservation validation (never drops negative constraints)    │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: Semantic Fidelity Guardrail (`SemanticFidelityGuard`)              │
│ • Dense vector embeddings via `all-MiniLM-L6-v2` (PyTorch CPU forward pass) │
│ • Cosine similarity gate: Conservative (0.96), Balanced (0.92), Aggr (0.86) │
│ • Multi-Chunk localized safety gate: coverage & relevance >= theta_chunk    │
│ • Strict preservation of negations, operators, numbers, and JSON fields     │
└──────────────────┬──────────────────────────────────────┬───────────────────┘
                   │ PASSED                               │ FAILED
                   ▼                                      ▼
        Accept Optimized Prompt                 Adaptive Relaxation Loop
                                                (Retry Stage 2 at relaxed mode)
                                                          │
                                             Exhausted / Unrecoverable
                                                          ▼
                                                Atomic Rollback to
                                                Original User Prompt
```

---

## 3. Public API & Interfaces

### 1. `PipelineConfig`
```python
@dataclass
class PipelineConfig:
    mode: str = "balanced"  # "conservative", "balanced", "aggressive"
    enable_stage_1: bool = True
    enable_stage_2: bool = True
    enable_stage_3: bool = True
    enable_stage_4: bool = True
    pruner_tokenizer_name: str = "cl100k_base"
    compressor_config: Optional[CompressorConfig] = None
    shaper_config: Optional[ShaperConfig] = None
    guardrail_config: Optional[GuardrailConfig] = None
    max_retries: int = 2
    pass_intermediate_stages: bool = True
    enforce_placeholder_cleanup: bool = True
```

### 2. `PipelineResult` (Alias: `OptimizationResult`)
```python
@dataclass
class PipelineResult:
    original_prompt: str
    final_prompt: str
    stage_1_output: Optional[str] = None
    stage_2_output: Optional[str] = None
    stage_3_output: Optional[str] = None
    success: bool = True
    accepted: bool = True
    rollback_occurred: bool = False
    rollback_stage: Optional[str] = None  # "none", "original", "stage_1", "stage_2"
    rollback_reason: Optional[str] = None
    initial_mode: str = "balanced"
    final_mode: str = "balanced"
    original_token_count: int = 0
    final_token_count: int = 0
    net_token_reduction: int = 0
    net_token_reduction_pct: float = 0.0
    is_exact_token_count: bool = True
    tokenizer_name: str = "cl100k_base"
    stage_1_token_count: Optional[int] = None
    stage_2_token_count: Optional[int] = None
    stage_3_token_count: Optional[int] = None
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    semantic_similarity: Optional[float] = None
    chunk_similarities: List[float] = field(default_factory=list)
    chunk_coverage: List[float] = field(default_factory=list)
    guardrail_passed: bool = True
    preservation_violations: List[str] = field(default_factory=list)
    retry_count: int = 0
    retry_history: List[Dict[str, Any]] = field(default_factory=list)
    stage_executions: Dict[str, StageExecution] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    failure_reasons: List[str] = field(default_factory=list)
```

### 3. `optimize_prompt()` Functional Entrypoint
```python
def optimize_prompt(
    prompt: str,
    mode: str = "balanced",
    enable_stage_1: bool = True,
    enable_stage_2: bool = True,
    enable_stage_3: bool = True,
    enable_stage_4: bool = True,
    max_retries: int = 2,
    pipeline: Optional[PromptGreenPipeline] = None,
) -> PipelineResult:
    """Public functional helper for active prompt optimization."""
```

---

## 4. Multi-Chunk Semantic Guardrail Integration (CHUNK-01 & CHUNK-02)

### The Defect (Discovered in Stage 4 Final Audit):
In long prompts (> 150 words), global mean-pooled cosine similarity averages token representations across all chunks. When 85%–90% of a prompt's prefix was identical, an altered natural-language final chunk ($S_{\text{chunk}} = 0.0548$) yielded an aggregate cosine similarity of $0.9908 \ge 0.92$, causing accidental acceptance because chunk similarities were purely diagnostic telemetry.

### The Stage 5 Resolution:
1. **Windowed Chunk Coverage Evaluation:**
   For multi-chunk prompts (`len(orig_chunks) > 1` or `len(cand_chunks) > 1`), candidate chunks are assembled into single chunks and adjacent pairs ($C_j + " " + C_{j+1}$) to absorb boundary shifts from compression.
2. **Bidirectional Semantic Gating:**
   - **Original Chunk Coverage:** Each original chunk $O_i$ must achieve $\text{cov}_i = \max_W S(O_i, W) \ge \theta_{\text{chunk}}$.
   - **Candidate Chunk Relevance:** Each non-directive candidate chunk $C_j$ must achieve $\text{rel}_j = \max_W S(C_j, W) \ge \theta_{\text{chunk}}$.
3. **Empirically bounded heuristic thresholds, evaluated on a limited technical and adversarial sample (`MODE_CHUNK_THRESHOLDS`):**
   - Conservative: $\theta_{\text{chunk}} = 0.82$ (Global $\theta = 0.96$)
   - Balanced: $\theta_{\text{chunk}} = 0.75$ (Global $\theta = 0.92$)
   - Aggressive: $\theta_{\text{chunk}} = 0.65$ (Global $\theta = 0.86$)
   - Explicitly configurable via `GuardrailConfig(chunk_threshold=...)`.
   - **Methodological Disclosure:** These values represent empirically bounded heuristic thresholds evaluated on a limited technical and adversarial sample (~10 technical prompts and ~5 adversarial variants from the repository test suite). This is not a statistically calibrated decision boundary. The thresholds require evaluation on a larger, representative external benchmark across diverse domain distributions.
   - **Heuristic Nature:** Cosine similarity thresholding is an empirical heuristic check for topical and semantic proximity; it does not constitute mathematical proof of semantic equivalence or logical interchangeability.
4. **Token Clamping Guard (CHUNK-02):**
   `chunk_text()` enforces a character limit (`max_chars_per_chunk = 360`) in addition to word counts, ensuring dense compound technical identifiers do not expand beyond the MiniLM 128-token input window.

---

## 5. Test Suite Verification Results

The complete test suite was executed on the local developer machine:

| Test Module | Total Tests | Passed | Failed | Skipped | Execution Time |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `tests/test_rule_pruner.py` (Stage 1) | 22 | 22 | 0 | 0 | 0.45s |
| `tests/test_compressor.py` (Stage 2) | 25 | 25 | 0 | 0 | 0.52s |
| `tests/test_output_shaper.py` (Stage 3) | 30 | 30 | 0 | 0 | 0.61s |
| `tests/test_semantic_guard.py` (Stage 4) | 58 | 58 | 0 | 0 | 4.14s |
| `tests/test_all.py` (v1 Baseline Regression) | 8 | 8 | 0 | 0 | 0.42s |
| `tests/test_pipeline.py` (Stage 5 Orchestrator) | 20 | 20 | 0 | 0 | 6.66s |
| **Full Pytest Suite Total** | **163** | **163** | **0** | **0** | **12.66s** |
| `verify_engine.py` (Core Engine Verification) | 10 | 10 | 0 | 0 | 5.21s |

---

## 6. End-to-End Empirical Benchmark Results

Measured using `tests/benchmark_pipeline.py` on the local developer machine:
- **Processor:** Intel Core i7-10610U CPU (4 Cores / 8 Threads @ 1.80GHz–4.90GHz)
- **RAM:** 32 GB DDR4
- **Operating System:** Windows 11
- **PyTorch Device:** `cpu` (Direct PyTorch safetensors forward pass, zero CUDA)
- **Pre-Warm Initialization Latency:** 2397.90 ms (Cold safetensors load into memory)

### Measured Performance Summary Table:

| Benchmark Prompt | Input Category | Original Tokens | Final Tokens | Net Reduction | Net Reduction % | Stage Latency Breakdown (ms) | Total Latency (ms) | Cosine Sim | Acceptance Verdict |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :--- |
| **Run 1: Connection Pooling** | Short | 20 | 10 | +10 | +50.00% | S1: 6.04 \| S2: 1.61 \| S3: 26.98 \| S4: 118.37 | 165.29 ms | 0.9692 | **ACCEPTED** |
| **Run 2: Microservices ID** | Medium | 67 | 47 | +20 | +29.85% | S1: 0.52 \| S2: 1.69 \| S3: 35.39 \| S4: 104.95 | 142.77 ms | 0.9277 | **ACCEPTED** |
| **Run 3: Telemetry Schema** | Long | 141 | 132 | +9 | +6.38% | S1: 0.86 \| S2: 2.47 \| S3: 17.01 \| S4: 556.80 | 577.52 ms | 0.9956 | **ACCEPTED** |
| **Run 4: Software Arch** | Multi-Chunk | 159 | 158 | +1 | +0.63% | S1: 1.15 \| S2: 2.99 \| S3: 22.00 \| S4: 760.20 | 786.92 ms | 0.9997 | **ACCEPTED** |
| **Run 5: Adversarial Corrupt** | Adversarial | 37 | 37 | +0 | +0.00% | S1: 0.41 \| S2: 0.01 \| S3: 29.23 \| S4: 171.42 | 201.27 ms | 0.4149 | **ROLLED_BACK (original)** |

### Analytical Observations from Benchmark:
1. **Short & Medium Prompts:** High input-token savings (29.8% to 50.0%) achieved through conversational boilerplate pruning and discourse filler compression, completing in under 185 ms total latency.
2. **Long & Multi-Chunk Prompts:** Preservation rules protect JSON schemas, code blocks, URLs, and architectural constraints. Multi-chunk evaluation achieves high chunk coverage ($[1.0, 1.0, 0.9984, 1.0]$) and completes in $\approx 780\text{ ms}$ on CPU.
3. **Adversarial Candidate Gating:** When an adversarial candidate alters critical negations or drops coverage below the chunk threshold, the guardrail identifies the violation ($S_{\text{cos}} = 0.4149$), triggers relaxation, exhausts retries, and safely rolls back to the original prompt without token corruption.

---

## 7. Known Architectural Limitations

1. **CPU Forward-Pass Scaling with Chunk Count:**
   Because `all-MiniLM-L6-v2` runs on CPU without GPU batching, each chunk forward pass requires $\approx 20\text{–}30\text{ ms}$. For prompts exceeding 10 chunks (> 700 words), Stage 4 embedding latency scales to $\approx 1.5\text{–}2.5\text{ seconds}$. This is acceptable for pre-deploy CI/CD gates and background optimization, but interactive streaming studio usage will benefit from ONNX Runtime CPU quantization in Day 2.
2. **Local Ollama Daemon Dependency for Abstractive Shaping:**
   Stage 3 utilizes deterministic rule-template bounding when the local Ollama daemon is offline or model generation fails validation. Full SLM abstractive rephrasing requires a running Ollama daemon (`qwen2.5:0.5b`).
3. **Empirically Bounded Heuristic Thresholds:**
   The chunk thresholds (`conservative: 0.82`, `balanced: 0.75`, `aggressive: 0.65`) and sentence thresholds are empirically bounded heuristic thresholds evaluated on a limited technical and adversarial sample (~10 technical prompts and ~5 adversarial variants from the local test suite). This is not a statistically calibrated decision boundary and requires future validation against large-scale academic benchmarks.
4. **Intra-Chunk Sentence Boundaries and Clause-Level Invariance:**
   While the localized sentence preservation safeguard detects substantial instruction sentence replacement or deletion, subtle intra-sentence clause modifications (e.g. changing an adverb or rearranging subordinate clauses inside a long compound sentence without altering core vocabulary) can produce minor similarity drops that remain above heuristic rejection thresholds. Cosine similarity thresholding is an empirical proximity check, not a formal mathematical proof of semantic equivalence.

---

## 8. Git Review & Changes Summary

- **Modified Files:**
  - `promptgreen/optimizer/semantic_guard.py` (Added `MODE_CHUNK_THRESHOLDS`, chunk character limits, windowed chunk coverage, and relevance gating).
  - `promptgreen/optimizer/__init__.py` (Exported pipeline classes and entrypoint).
- **Newly Created Files:**
  - `promptgreen/optimizer/pipeline.py` (Core Stage 5 pipeline orchestrator, 442 lines).
  - `tests/test_pipeline.py` (20 dedicated unit and integration tests, 395 lines).
  - `tests/benchmark_pipeline.py` (CPU performance benchmark runner, 206 lines).
  - `docs/DAY1_STAGE5_REPORT.md` (Stage 5 technical report).
- **Working Tree Status:** Clean, ready for technical review.
