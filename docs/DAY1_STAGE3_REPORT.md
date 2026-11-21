# PROMPTGREEN v2.0 — DAY 1, STAGE 3 REPORT
## Local SLM Output Directive Shaper & Deterministic Bounding Engine

**Date:** November 21, 2026
**Status:** COMPLETE & VERIFIED
**Author:** Antigravity AI (on behalf of Dayananda Sagar University Major Project Team)
**Host Environment:** Windows 11, Intel Core i7-10610U CPU (4 cores / 8 threads @ 1.80GHz–4.90GHz), 32 GB RAM, Intel UHD Graphics 620 (Non-CUDA / CPU-first)
**Active Git Branch:** `version-2` (Tracking `origin/version-2`)

---

## 1. Stage Objective

Stage 3 of the PromptGreen v2.0 optimization pipeline implements the **Output Directive Shaper** (`promptgreen/optimizer/output_shaper.py`).

Its primary purpose is to clarify, bound, and make explicit the expected response format, structure, and output constraints (e.g. Markdown tables, JSON schemas, bullet lists, numbered steps, code-only bounds) so that downstream LLMs generate appropriately bounded and predictable completions.

### Core Architecture & Implementation Mandates:
- **Primary vs. Optional Implementation:** **Deterministic directive shaping is the primary reliable implementation** of Stage 3. Ollama-assisted shaping is an optional path designed for environments where local model execution is enabled.
- **Model Assistance Is Not Guaranteed:** The model-assisted path is **not guaranteed to produce an accepted transformation**. Whenever a candidate model output fails preservation validation, is empty, times out, or encounters errors, **rejected model outputs must use deterministic fallback**.
- **Clarify, Not Compress:** Stage 3's objective is output constraint clarification. Adding explicit structural directives **may increase prompt input tokens** rather than shortening the input prompt.
- **Preserve Underlying Intent:** The user's core task, question, or request must never be altered or deflected.
- **Conservative Bounding:** Never invent unrequested word or sentence limits. Negations (`not`, `never`, `without`, `except`), conditionals (`if`, `unless`), numerical values, and protected structural regions must be safeguarded.
- **No Downstream Claims:** No downstream output-token reduction or energy savings have been experimentally established in this stage.

---

## 2. Files Created and Modified

| File | Status | Description |
| :--- | :--- | :--- |
| `promptgreen/optimizer/output_shaper.py` | **Created** | Stage 3 Output Directive Shaper implementing a dual-engine architecture: primary conservative deterministic rule bounding engine + optional local Ollama SLM client with two-tier semantic preservation validation. |
| `promptgreen/optimizer/__init__.py` | **Modified** | Exported `OutputDirectiveShaper`, `ShaperConfig`, and `ShapingResult` without altering existing Stage 1 & Stage 2 exports. |
| `tests/test_output_shaper.py` | **Created** | Comprehensive 30-test suite covering deterministic directives, semantic constraints, edge cases, mocked Ollama timeouts, errors, unsafe rewrite rejection, and rollbacks. |
| `tests/benchmark_output_shaper.py` | **Created** | Repeatable CPU latency and prompt-token difference benchmark across short, medium, and long representative prompts. |
| `docs/DAY1_STAGE3_REPORT.md` | **Updated** | Technical report detailing empirical measurements, real local Ollama inference smoke tests, safety validation results, and status classification. |
| `docs/DAY1_STAGE3_OLLAMA_MODEL_COMPARISON.md` | **Created** | Controlled comparative evaluation report across `qwen2.5:0.5b`, `gemma3:4b`, and `qwen3:8b`. |

---

## 3. Local Environment & Ollama Integration Status

### 3.1 Local Ollama Audit
An inspection of the local environment (`C:\Users\Renuk\.ollama\models`) and daemon on `localhost:11434` confirmed:
- **Ollama CLI Binary:** Installed at `C:\Users\Renuk\AppData\Local\Programs\Ollama\ollama.EXE`
- **Ollama Background Service:** **RUNNING** on `http://localhost:11434`.
- **Locally Available Models on Disk:**
  - `qwen2.5:0.5b` (0.5B parameters, 397 MB on disk)
  - `qwen2.5:3b` (3B parameters)
  - `gemma3:4b` (4B parameters)
  - `qwen3:8b` (8B parameters)
- **Zero-Download Guarantee:** No models were downloaded or pulled from remote registries. All tested models were already present on disk.

### 3.2 Dual-Engine Architecture
Because process sandboxes, network firewalls, and offline environments may restrict localhost socket access or CPU bandwidth, `OutputDirectiveShaper` employs a resilient dual-engine design:
1. **Deterministic Bounding Engine (Primary Reliable Implementation):** Operates 100% offline on CPU in **< 0.70 ms** with zero dependencies. Converts implicit expectations into structured directives without altering prompt intent.
2. **Model-Assisted Path (Optional):** Sends requests to `http://localhost:11434/api/generate` with a fast bounded timeout (default 2.0s). Outputs are strictly vetted through `_validate_preservation`; any detected loss of negations, conditionals, numbers, or placeholders immediately triggers a safe fallback to the deterministic engine.

---

## 4. Real Local Ollama Inference Smoke Test (`qwen2.5:0.5b`)

Based on the comparative evaluation of local models (`qwen2.5:0.5b`, `gemma3:4b`, `qwen3:8b`), **`qwen2.5:0.5b` is the recommended optional CPU model**.

To evaluate real local model behavior rather than relying exclusively on unit mocks, an empirical smoke test was executed against the local Ollama service using `qwen2.5:0.5b` on the Intel Core i7-10610U CPU:

| Test Prompt | Real Inference Latency | Validation Status | Engine Used | Final Output | Analysis & Fallback Reason |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Prompt 1:** `"Explain database normalization in simple terms."` | **6,084.8 ms** *(cold-start)* | **REJECTED** | Deterministic Fallback | `"Explain database normalization. Use clear, simple language. Organize the explanation into short sections."` | Model attempted to answer the prompt with 416 characters rather than shaping the directive. Length sanity validator detected $416 > 47 \times 3.0$ and rolled back to deterministic shaping. |
| **Prompt 2:** `"Compare SQL and NoSQL databases in a table. Do not delete production tables under any circumstances."` | **2,893.5 ms** *(warm)* | **ACCEPTED** | `qwen2.5:0.5b` | `"Compare SQL and NoSQL databases in a table. Do not delete production tables under any circumstances."` | Model preserved all negations, format requirements, and conditions in this test case. |
| **Prompt 3:** `"Return only valid JSON with keys name, age and city. Never expose credentials."` | **3,155.4 ms** *(warm)* | **REJECTED** | Deterministic Fallback | `"Return only valid JSON with keys name, age and city. Never expose credentials."` | Model rewrite omitted the negation `"never"`. The validator detected: `Negation 'never' present in original was removed` and rejected model output, engaging fallback. |
| **Prompt 4:** `"List 3 key steps to boil an egg perfectly. Do not crack the shell before boiling."` | **3,504.4 ms** *(warm)* | **REJECTED** | Deterministic Fallback | `"List 3 key steps to boil an egg perfectly. Do not crack the shell before boiling. Present them as a clear numbered list."` | Model rewrite dropped the negative instruction `"not"`. Validator rejected model output; deterministic fallback preserved `"Do not crack the shell before boiling."` |

### Key Findings from Real Local SLM Execution:
1. **CPU Latency Penalty:** Running a 0.5B model on CPU requires **2.8 to 3.5 seconds** per prompt (and ~6.0s on cold start), which is **~5,000x to 35,000x slower** than the deterministic engine (< 0.7 ms).
2. **Model-Assisted Output Is Not Guaranteed:** In 3 of the 4 tested smoke test prompts (and 6 of 13 in the broader benchmark), the SLM output was rejected because it attempted conversational answering or omitted negations.
3. **Validator Efficacy in Tested Cases:** The Stage 3 `_validate_preservation` validator successfully identified dropped negations and length bounds violations in tested cases, automatically routing rejected outputs to deterministic fallback.

---

## 5. Deterministic Shaping Capabilities & Behavioral Rules

The deterministic engine recognizes 10 distinct directive patterns:

1. **Simple Explanation / Accessible Language:**
   - Input: `"Explain database normalization in simple terms."`
   - Shaped: `"Explain database normalization. Use clear, simple language. Organize the explanation into short sections."`
2. **Table Comparison:**
   - Input: `"Compare SQL and NoSQL databases in a table."`
   - Shaped: `"Compare SQL and NoSQL databases. Present the comparison in a table. Include the relevant comparison criteria."`
3. **Structured JSON with Exact Keys:**
   - Input: `"Return only valid JSON with keys name, age and city."`
   - Shaped: `"Return only valid JSON. Include exactly the requested keys: name, age, city."`
4. **Detailed Explanation with Example:**
   - Input: `"Write a detailed explanation of gradient descent with an example."`
   - Shaped: `"Provide a detailed explanation of gradient descent and include a relevant example."`
   *(Preserves the detailed request — does not alter it into a concise response).*
5. **Numbered Steps:**
   - Input: `"List 3 key steps to boil an egg perfectly."`
   - Shaped: `"List 3 key steps to boil an egg perfectly. Present them as a clear numbered list."`
6. **Bullet Points:**
   - Input: `"Summarize the key benefits of Docker in bullet points."`
   - Shaped: `"Summarize the key benefits of Docker. Present the key points as concise bullet points."`
7. **Code-Only Bounding:**
   - Input: `"Write a python script to sort a dictionary. Return code only."`
   - Shaped: `"Write a python script to sort a dictionary. Return only the code implementation without additional conversational text."`
8. **Explicit Word / Length Limit Preservation:**
   - Input: `"Explain quantum computing in under 50 words."`
   - Shaped: `"Explain quantum computing. Keep the response under 50 words."`
   *(Preserves user-specified numerical length limits — does not invent arbitrary limits).*
9. **Concise / Brief Request:**
   - Input: `"Explain microservices architecture briefly."`
   - Shaped: `"Explain microservices architecture. Keep the explanation concise and focused on the core concept."`
10. **Pre-Bounded / Sufficiently Clear Prompts:**
    - Input: `"Write a python script to sort a list. Return code only without explanations."`
    - Shaped: Unchanged (`shaping_applied = False`, `shaping_method = "none"`).

---

## 6. Empirical Performance Measurements (CPU Benchmark)

Measured on the target laptop (**Intel Core i7-10610U CPU @ 1.80GHz, 32 GB RAM, Windows 11**) across 10 iterations per prompt using `tests/benchmark_output_shaper.py`:

| Benchmark Prompt | Input Prompt Tokens | Output Prompt Tokens | Measured Token Difference | Shaping Applied | Shaping Method | Mean Latency (ms) | Median Latency (ms) | Target (< 100 ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Short** (`"Explain database normalization in simple terms."`) | 7 | 16 | **+9 tokens (+128.6%)** | True | `deterministic` | **0.10 ms** | 0.10 ms | **ACHIEVED** (1000x faster) |
| **Medium** (Table + Negation + URL + 100ms) | 35 | 35 | **+0 tokens (0.0%)** | False | `none` (Already clear) | **0.25 ms** | 0.24 ms | **ACHIEVED** (400x faster) |
| **Long** (Prose + AST Python Code + 2.0GB) | 94 | 94 | **+0 tokens (0.0%)** | False | `none` (Already clear) | **0.64 ms** | 0.64 ms | **ACHIEVED** (150x faster) |

### Transparent Analysis of Token & Carbon Impact:
1. **Measured Input Prompt Tokens:**
   - For the short prompt, input tokens increased from 7 to 16 (+9 tokens / +128.6%) because explicit formatting and sectioning directives were added.
   - For medium and long prompts, token counts remained unchanged (+0 tokens / 0.0%) because output requirements were already clear.
2. **Downstream Generated Tokens (Not Established):**
   - Actual reduction in downstream generated tokens has **not been experimentally established**, as downstream LLM completions were not generated or compared in this stage.
   - Any projected reduction in decode tokens from bounding open-ended directives remains a qualitative hypothesis until end-to-end downstream generation benchmarks are conducted.
3. **Downstream Carbon Footprint (Not Measured):**
   - No carbon savings were claimed or measured in this stage. Quantitative energy and carbon calculations belong strictly to the thermodynamic carbon engine (Day 2).

---

## 7. Test Results & Verification

### 7.1 Stage 3 Test Suite (`tests/test_output_shaper.py`)
All 30 unit tests passed:
```
tests/test_output_shaper.py::test_1_empty_input PASSED                   [  3%]
tests/test_output_shaper.py::test_2_whitespace_only_input PASSED         [  6%]
tests/test_output_shaper.py::test_3_simple_explanatory_prompt PASSED     [ 10%]
tests/test_output_shaper.py::test_4_explicit_concise_response_request PASSED [ 13%]
tests/test_output_shaper.py::test_5_explicit_detailed_response_request PASSED [ 16%]
tests/test_output_shaper.py::test_6_bullet_point_requirement PASSED      [ 20%]
tests/test_output_shaper.py::test_7_numbered_list_requirement PASSED     [ 23%]
tests/test_output_shaper.py::test_8_table_requirement PASSED             [ 26%]
tests/test_output_shaper.py::test_9_json_only_requirement PASSED         [ 30%]
tests/test_output_shaper.py::test_10_explicit_word_or_length_limit PASSED [ 33%]
tests/test_output_shaper.py::test_11_code_only_instruction PASSED        [ 36%]
tests/test_output_shaper.py::test_12_negative_instructions PASSED        [ 40%]
tests/test_output_shaper.py::test_13_conditional_instructions PASSED     [ 43%]
tests/test_output_shaper.py::test_14_exceptions_and_qualifications PASSED [ 46%]
tests/test_output_shaper.py::test_15_numerical_constraints PASSED        [ 50%]
tests/test_output_shaper.py::test_16_named_entities_and_technical_identifiers PASSED [ 53%]
tests/test_output_shaper.py::test_17_urls_and_file_paths PASSED          [ 56%]
tests/test_output_shaper.py::test_18_protected_code_and_structured_content PASSED [ 60%]
tests/test_output_shaper.py::test_19_prompt_with_multiple_output_requirements PASSED [ 63%]
tests/test_output_shaper.py::test_20_prompt_with_clear_output_instructions PASSED [ 66%]
tests/test_output_shaper.py::test_21_deterministic_repeatability PASSED  [ 70%]
tests/test_output_shaper.py::test_22_ollama_unavailable PASSED           [ 73%]
tests/test_output_shaper.py::test_23_ollama_timeout PASSED               [ 76%]
tests/test_output_shaper.py::test_24_ollama_inference_error PASSED       [ 80%]
tests/test_output_shaper.py::test_25_unsafe_model_rewrite_rejected PASSED [ 83%]
tests/test_output_shaper.py::test_26_fallback_to_deterministic_shaping PASSED [ 86%]
tests/test_output_shaper.py::test_27_fallback_to_original_prompt_when_necessary PASSED [ 90%]
tests/test_output_shaper.py::test_28_stage1_and_stage2_compatibility PASSED [ 93%]
tests/test_output_shaper.py::test_29_token_count_metadata PASSED         [ 96%]
tests/test_output_shaper.py::test_30_no_network_or_model_download_during_init PASSED [100%]
============================= 30 passed in 0.22s ==============================
```

### 7.2 Full Project Regression Suite
Executed: `python -m pytest -p no:langsmith -v`
```
============================= 85 passed in 3.69s ==============================
- tests/test_all.py: 8 passed (v1 legacy baseline)
- tests/test_rule_pruner.py: 22 passed (Stage 1 & 1.1 structural pruner)
- tests/test_compressor.py: 25 passed (Stage 2 extractive compressor)
- tests/test_output_shaper.py: 30 passed (Stage 3 output directive shaper)
```

### 7.3 Standalone Engine Verification
Executed: `python verify_engine.py`
```
FINAL VERIFICATION SUMMARY: 10 / 10 Prompts Verified Successful (100.0%)
```

---

## 8. Status Classification of Features

### 8.1 Implemented & Fully Verified
- `promptgreen/optimizer/output_shaper.py`: Complete `OutputDirectiveShaper`, `ShaperConfig`, and `ShapingResult`.
- Conservative deterministic output-bounding engine covering tables, JSON, bullet points, numbered steps, code-only, simple language, and word limits.
- Two-tier preservation validation checking negations, conditions, numbers, and protected regions.
- Stage 1 and Stage 2 sequential pipeline compatibility (`RuleBasedPruner` $\rightarrow$ `LLMLinguaCompressor` $\rightarrow$ `OutputDirectiveShaper`).
- Real local Ollama daemon execution tested with `qwen2.5:0.5b`, demonstrating safety validation rejection on negation loss and automatic fallback.
- Mocked Ollama SLM client unit tests (connection failures, timeouts, inference errors, and unsafe rewrite rejection).

### 8.2 Clearly Distinguished Limitations
- Deterministic directive shaping is the primary reliable implementation.
- Real local Ollama inference on CPU introduces significant latency (2.8 to 8.7 seconds) and semantic risk (dropping negations or conversational answering), making the deterministic engine (< 0.7 ms) the recommended production default.
- Downstream response-token reduction has not been measured experimentally in this stage.

### 8.3 Ready for Stage 4 Integration
- Stage 3 is fully decoupled and ready to feed its candidate shaped prompt directly into Stage 4 (**Semantic Fidelity Cosine Guardrail** via `sentence-transformers/all-MiniLM-L6-v2`), followed by the unified pipeline orchestrator (`promptgreen/optimizer/pipeline.py`).

---

## 9. Repository & Backup Integrity

1. **Workspace:** `D:\EDU\DSU\Major project\PromptGreen`
2. **Git Status:** On branch `version-2` (Tracking `origin/version-2`, changes uncommitted awaiting review).
3. **Backup File:** `D:\EDU\DSU\Major project\PromptGreen.zip`
   - **Size:** 120,304 bytes
   - **Last Modified:** `10-11-2026 23:16:43` (Completely untouched)
4. **Version 1 Immutability:** `origin/main` and local `main` remain untouched at commit `e920e89`.
