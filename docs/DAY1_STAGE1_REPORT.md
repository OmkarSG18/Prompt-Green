# PROMPTGREEN v2.0 — DAY 1, STAGE 1 & 1.1 REPORT
## Structural and Rule-Based Prompt Pruner

**Execution Date:** November 21, 2026  
**Component:** `promptgreen/optimizer/rule_pruner.py`  
**Test Suite:** `tests/test_rule_pruner.py`  
**Status:** **FINAL ACCEPTANCE — PASS (30/30 Tests Passing)**  

---

## 1. Executive Summary

PromptGreen v2.0 introduces an active multi-stage prompt optimization pipeline (`promptgreen/optimizer/`). **Stage 1 & 1.1** implement the **Structural and Rule-Based Prompt Pruner**, providing a robust pre-processing foundation for subsequent neural token pruning (LLMLingua-2) and SLM output shaping.

The primary mission of Stage 1 is **deterministic zero-loss structural protection**: identifying, isolating, and masking all syntactically fragile elements (fenced code blocks, JSON objects, YAML configurations, XML/HTML tags, inline code, file paths, programming identifiers, URLs, and numerical constraints) before any conversational pruning occurs, conservatively removing polite fluff and greetings, and deterministically restoring protected regions **byte-for-byte**.

Following an independent quality audit, **Stage 1.1** applied corrective patches addressing mid-sentence subordinate clause clipping and Unicode normalization sequencing, validated against an expanded 30-test regression suite.

---

## 2. Independent Audit Findings & Stage 1.1 Corrective Patches

An independent review identified two subtle semantic preservation issues:

### Issue 1: Mid-Sentence Subordinate Clause Over-Pruning
- **Audit Finding:** The pattern `(?i)\bif\s+you\s+(?:can|could)\s*[,]?\s*` matched conditional clauses mid-sentence. For example, `"Check if you can reproduce the error."` was incorrectly pruned to `"Check reproduce the error."`.
- **Stage 1.1 Correction:**
  1. Completely removed the un-anchored `if you can` pattern from the polite prefix list. Conditional clauses like `"Check if you can reproduce the error."` or `"If you can, validate the output."` are now preserved 100%.
  2. Anchored all polite opening patterns to sentence/clause starts using `(?:^|(?<=[.!?\n]))\s*`.
  3. Meaningful occurrences of `"please"` (such as `"Please say please before entering."`) now cleanly prune only the sentence-opening request while preserving the direct object: `"Say please before entering."`.

### Issue 2: Unicode Normalization Sequencing on Protected Blocks
- **Audit Finding:** Applying `unicodedata.normalize("NFC", prompt)` *before* masking meant that deliberately decomposed Unicode sequences (e.g., NFD strings `Caf\u0065\u0301` inside code or JSON payloads) were normalized prior to being protected.
- **Stage 1.1 Correction:** Restructured the execution sequence:
  1. Preserve the raw, un-normalized `raw_prompt`.
  2. Execute structural masking directly on `raw_prompt`, storing exact raw substrings in `placeholder_map`.
  3. Apply NFC normalization *only* to the masked string (`norm_masked_text = unicodedata.normalize("NFC", masked_text)`), which normalizes natural language while leaving ASCII placeholders (`__CODE_BLOCK_0__`) unaffected.
  4. Prune conversational boilerplate on the normalized text.
  5. Restore protected regions from `placeholder_map`, guaranteeing byte-for-byte preservation of decomposed code points inside code blocks and JSON strings.
  6. Verify restoration integrity; if any placeholder remains un-restored, execute an atomic rollback to `raw_prompt`.

### Issue 3: Unclosed Fenced Code Blocks
- **Audit Finding:** Prompts terminating with an opening code fence without a closing delimiter (```` ```python\nx = 1 ````) bypassed closed-block regexes.
- **Stage 1.1 Correction:** Added secondary unclosed-block detection: any trailing unclosed code block from an opening fence to the end of the string is safely masked as a protected `fenced_code` region, preventing corruption during whitespace normalization.

---

## 3. Files Created and Modified

### Files Created
1. **`promptgreen/optimizer/__init__.py`**
   - Package initializer exposing `RuleBasedPruner`, `PruningResult`, and `ProtectedRegion`.
2. **`promptgreen/optimizer/rule_pruner.py`** (720 lines)
   - Core implementation of Stage 1 & 1.1 structural protection and rule-based pruning.
3. **`tests/test_rule_pruner.py`** (315 lines)
   - Comprehensive test suite covering 22 test functions (13 original scenarios + 9 corrective regression suites).
4. **`docs/DAY1_STAGE1_REPORT.md`**
   - Detailed architectural documentation and empirical verification report.

### Files Modified
- *None.* All existing v1.0 baseline modules (`diff_parser.py`, `carbon_engine.py`, `hybrid_predictor.py`, `database.py`, `server.py`, etc.) remain completely untouched and backward-compatible.
- `PromptGreen.zip` backup in the parent directory remains untouched (120,304 bytes; LastWriteTime: 10-11-2026 23:16:43).

---

## 4. Architecture & Pipeline Sequence

```
                                    Raw User Prompt
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Raw Prompt Ingestion & Safety Check                                                 │
│    • Preserve raw original prompt (`raw_prompt = prompt`)                              │
│    • Empty / whitespace input handling (returns empty PruningResult)                   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Raw Text (Un-normalized)
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 2. Multi-Pass Structural Protection (`mask_protected_regions`)                         │
│    • Pass 1: Closed & Unclosed Fenced Code Blocks (```...```, ~~~...~~~)              │
│    • Pass 2: XML & HTML Element Blocks (<tag>...</tag>, <tag />)                      │
│    • Pass 3: YAML Configuration Blocks (---, multiline indented key-values)            │
│    • Pass 4: JSON Objects, Arrays & Schemas ({...} balanced parser)                    │
│    • Pass 5: Inline Backtick Code (`...`)                                              │
│    • Pass 6: Explicit User Requirement Headers (MUST:, REQUIRED:, DO NOT:)             │
│    • Pass 7: Web & API URLs (http://, https://, ftp://)                                │
│    • Pass 8: File Paths (POSIX /path/to/file, Windows C:\path\to\file)                 │
│    • Pass 9: Strict Numerical Constraints (30s, 500ms, 100MB, <= 0.05, 3 retries)     │
│    • Pass 10: Programming Identifiers (snake_case, camelCase, UPPER_CASE, obj.method)  │
│    • Collision Detection: Incremental salting (__TAG_0_1__) if collision in user text │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Masked Natural-Language Text
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 3. Natural-Language NFC Normalization (`unicodedata.normalize('NFC')`)                 │
│    • Normalizes only natural-language segments; protected blocks remain raw in map     │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Normalized Masked Text
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 4. Conservative Conversational Pruning (`prune_boilerplate`)                           │
│    • Anchored polite opening preambles ("Could you please kindly...", etc.)            │
│    • Anchored greetings ("Hello!", "Good morning AI,")                                 │
│    • Conversational closures ("Thank you in advance!", "Have a wonderful day!")        │
│    • Collapse redundant spaces & blank lines while preserving newline semantics        │
│    • Sentence recasing (capitalize first letter after opening prefix removal)          │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ Pruned Masked Text
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 5. Deterministic Content Restoration (`restore_protected_regions`)                     │
│    • Substitute all placeholders (__CODE_BLOCK_0__, etc.) with raw byte-content       │
│    • Integrity Check: Verify zero un-restored placeholders remain                      │
│    • Fallback Rollback: If integrity check fails, revert cleanly to raw_prompt         │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │
                                           ▼
                                     PruningResult
```

---

## 5. Token Counting Behavior & Transparency

- **Primary Tokenizer:** `tiktoken` with `cl100k_base` encoding.
- **Offline / Sandbox Fallback:** If `tiktoken` cannot reach external network endpoints to download un-cached vocabularies, `count_tokens` automatically falls back to:
  $$\text{Token Count} \approx \max(1, \lfloor \text{Words} \times 1.3 \rfloor)$$
- **Transparency Guarantee:**
  - `is_exact_token_count = False` when fallback is active.
  - `tokenizer_name = "fallback_word_ratio_1.3x"` clearly recorded in `PruningResult`.
  - A descriptive warning is appended to `warnings`.
  - Word-ratio estimates are **never claimed as exact tokenizer outputs**.

---

## 6. Test Suite & Empirical Verification Results

### Regression Commands Executed
```bash
python -m pytest -p no:langsmith -v
python verify_engine.py
```

### Pytest Execution Evidence (30 / 30 Tests Passing)

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Renuk\AppData\Local\Programs\Python\Python311\python.exe
cachedir: .pytest_cache
rootdir: D:\EDU\DSU\Major project\PromptGreen
plugins: anyio-4.13.0, langsmith-0.14.11, asyncio-1.4.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 30 items

tests/test_all.py::test_diff_analyzer_semantic_extraction PASSED         [  3%]
tests/test_all.py::test_few_shot_counting PASSED                         [  6%]
tests/test_all.py::test_cot_detection PASSED                             [ 10%]
tests/test_all.py::test_hybrid_predictor_blending PASSED                 [ 13%]
tests/test_all.py::test_carbon_engine_calculation PASSED                 [ 16%]
tests/test_all.py::test_prompt_gate_evaluation PASSED                    [ 20%]
tests/test_all.py::test_prompt_ledger_sqlite PASSED                      [ 23%]
tests/test_all.py::test_benchmark_validation_suite PASSED                [ 26%]
tests/test_rule_pruner.py::test_1_ordinary_conversational_prompt PASSED  [ 30%]
tests/test_rule_pruner.py::test_2_prompt_containing_python_code PASSED   [ 33%]
tests/test_rule_pruner.py::test_3_prompt_containing_json PASSED          [ 36%]
tests/test_rule_pruner.py::test_4_prompt_containing_yaml PASSED          [ 40%]
tests/test_rule_pruner.py::test_5_prompt_containing_inline_code PASSED   [ 43%]
tests/test_rule_pruner.py::test_6_prompt_containing_file_paths_and_identifiers PASSED [ 46%]
tests/test_rule_pruner.py::test_7_prompt_containing_urls PASSED          [ 50%]
tests/test_rule_pruner.py::test_8_prompt_containing_numerical_constraints PASSED [ 53%]
tests/test_rule_pruner.py::test_9_prompt_containing_mixed_blocks PASSED  [ 56%]
tests/test_rule_pruner.py::test_10_empty_and_whitespace_input PASSED     [ 60%]
tests/test_rule_pruner.py::test_11_unicode_text_handling PASSED          [ 63%]
tests/test_rule_pruner.py::test_12_restoration_failure_handling PASSED   [ 66%]
tests/test_rule_pruner.py::test_immutability_of_original_input PASSED    [ 70%]
tests/test_rule_pruner.py::test_a_subordinate_conditional_clause_preservation PASSED [ 73%]
tests/test_rule_pruner.py::test_b_meaningful_uses_of_please PASSED       [ 76%]
tests/test_rule_pruner.py::test_c_explicit_placeholder_collision PASSED  [ 80%]
tests/test_rule_pruner.py::test_d_multiple_adjacent_fenced_code_blocks PASSED [ 83%]
tests/test_rule_pruner.py::test_e_unclosed_fenced_code_block PASSED      [ 86%]
tests/test_rule_pruner.py::test_f_decomposed_unicode_inside_fenced_code PASSED [ 90%]
tests/test_rule_pruner.py::test_g_decomposed_unicode_inside_json_strings PASSED [ 93%]
tests/test_rule_pruner.py::test_h_negative_instructions_and_exceptions PASSED [ 96%]
tests/test_rule_pruner.py::test_i_mixed_natural_language_and_multiple_protected_regions PASSED [100%]

============================= 30 passed in 3.37s ==============================
```

### Core Verification Suite
`python verify_engine.py` was executed:
```
FINAL VERIFICATION SUMMARY: 10 / 10 Prompts Verified Successful (100.0%)
```

---

## 7. Remaining Known Limitations

1. **Non-Standard Bare Code:** Code written without Markdown fences (```` ``` ````) or inline backticks (`` ` ``) is protected via individual identifier and path heuristics, but cannot be guaranteed as a single atomic block unless fenced.
2. **Grammatically Ambiguous Conditionals:** Highly colloquial phrases combining politeness and conditions (e.g., *"If you could just please somehow make it work"*) are conservatively preserved rather than aggressively pruned to avoid altering user intent.
3. **Lexical Scope Boundary:** Rule-based pruning alone cannot compress verbose prose (e.g., transforming a 3-paragraph context into 1 paragraph). That capability is designed for **Stage 2 (LLMLingua-2 Extractive Token Compressor)** and **Stage 3 (SLM Output Shaping)**.

---

## 8. Final Acceptance Criteria Verification

| Acceptance Criterion | Result | Evidence |
| :--- | :--- | :--- |
| 1. Meaningful conditional clauses retained | **PASS** | Verified in `test_a_subordinate_conditional_clause_preservation` across 6 test prompts. |
| 2. Negative instructions & exceptions preserved | **PASS** | Verified in `test_h_negative_instructions_and_exceptions` (Do not, Never, Only proceed if). |
| 3. Protected regions remain byte-for-byte identical | **PASS** | Verified in `test_2`, `test_3`, `test_4`, `test_5`, `test_6`, `test_7`, `test_9`. |
| 4. Unicode normalization does not alter protected regions | **PASS** | Verified in `test_f_decomposed_unicode_inside_fenced_code` and `test_g_decomposed_unicode_inside_json_strings`. |
| 5. Placeholder collision immunity | **PASS** | Verified in `test_c_explicit_placeholder_collision` (`__CODE_BLOCK_0_1__` salting). |
| 6. Adjacent and unclosed code blocks pass safely | **PASS** | Verified in `test_d_multiple_adjacent_fenced_code_blocks` and `test_e_unclosed_fenced_code_block`. |
| 7. All previous Stage 1 tests pass | **PASS** | All 13 original tests passing. |
| 8. All existing v1 regression tests pass | **PASS** | All 8 original v1 tests passing in `tests/test_all.py`. |
| 9. Token counting transparently labeled | **PASS** | Verified exact vs. fallback flags in `PruningResult`. |

**Stage 1 & 1.1 are accepted as COMPLETE and fully qualified to serve as the foundation for Day 1, Stage 2 (LLMLingua-2 Extractive Compressor).**
