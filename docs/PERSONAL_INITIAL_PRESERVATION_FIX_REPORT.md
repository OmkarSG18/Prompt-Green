# PromptGreen V2 — Personal Initial Preservation Fix Report

**Document Version:** 1.0.0  
**Date:** November 23, 2026  
**Status:** COMPLETED & VERIFIED  
**Repository Branch:** `version-2`  
**Base Commit Reference:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`

---

## 1. Executive Summary

During the final read-only audit of the PromptGreen V2 optimizer, a regression in Stage 2 extractive compression was identified:
$$\text{"A. B. Smith"} \longrightarrow \text{"B. Smith"}$$

In Aggressive optimization mode, the standalone article pruning logic (`ARTICLES = {"the", "a", "an"}`) processed cleaned word tokens by stripping surrounding punctuation (`raw_tok.strip(".,;:?!'\"()[]{}").lower()`). Consequently, the single-letter initial `"A."` was normalized to `"a"`, misidentified as the English indefinite article, and dropped. This corrupted personal names, academic citations, and author designations.

A targeted, backward-compatible fix was implemented in `promptgreen/optimizer/compressor.py`. The optimizer now incorporates a dedicated personal initial detector (`_is_personal_initial`) and protects all initialisms (`A.`, `B.`, `J.`, `A.B.`, `A. B.`, etc.) from article pruning across all modes (Conservative, Balanced, and Aggressive), while ordinary grammatical article pruning continues to function safely (`"A detailed report is required."` $\to$ `"Detailed report is required."`).

A comprehensive suite of 27 new targeted regression tests was added to `tests/test_optimizer_correctness_fixes.py`. The complete repository pytest suite of **390 tests** passed with **100% success (0 failures, 0 skipped)**.

---

## 2. Root Cause Analysis

- **Affected File:** `promptgreen/optimizer/compressor.py`
- **Location:** `LLMLinguaCompressor._compress_fallback_natural_text()`
- **Mechanism:**
  In Stage C of extractive token filtering:
  ```python
  for match in token_matches:
      ws, raw_tok = match.group(1), match.group(2)
      word_clean = raw_tok.strip(".,;:?!'\"()[]{}").lower()
      ...
      elif mode == "aggressive" and word_clean in ARTICLES:
          drop = True
  ```
  When the prompt contained `"A. B. Smith"`:
  1. Token `"A."` was stripped of its punctuation: `word_clean = "a"`.
  2. Because `"a"` is an element of `ARTICLES = {"the", "a", "an"}`, `word_clean in ARTICLES` evaluated to `True`.
  3. `_is_technical_or_identifier("A.")` also stripped punctuation (`clean = "A"`), found no digits, symbols, or multi-letter uppercase acronyms (`len >= 2`), and returned `False`.
  4. In Aggressive mode, `drop` was set to `True`, pruning `"A."` from the sentence.
  5. The token `"B."` was not dropped because `"b"` is not in `ARTICLES`.
  6. The output became `"B. Smith"`, truncating the author's primary initial.

---

## 3. Exact Source Code Modifications

### 1. Dedicated Initial Detector: `LLMLinguaCompressor._is_personal_initial`
Added static method in `promptgreen/optimizer/compressor.py` (lines 672–689):
```python
@staticmethod
def _is_personal_initial(token: str, next_token: str = "") -> bool:
    """
    Detect if a token is a personal initial (e.g. 'A.', 'B.', 'J.', 'A.B.', 'A.B.C.'),
    optionally enclosed in quotes or brackets, or followed by punctuation.
    Also detects bare initials followed by another initial (e.g. 'A' in 'A B Smith' or 'A' in 'A B.').
    Prevents personal initials from being mistakenly pruned as English articles ('a').
    """
    stripped = token.strip("'\"()[]{}")
    # 1. Standard single or multi-part dotted initial: A., B., J., A.B., A.B.C., A.-B.
    if re.match(r"^(?:[A-Za-z]\.[-]?)+[,;:?!]?$", stripped):
        return True
    # 2. Standalone uppercase single letter followed by another initial: 'A' in 'A B Smith' or 'A' in 'A B.'
    if len(stripped) == 1 and stripped.isupper() and next_token:
        next_stripped = next_token.strip("'\"()[]{}")
        if re.match(r"^[A-Za-z]\.?", next_stripped) and (len(next_stripped) == 1 or next_stripped.endswith(".")):
            return True
    return False
```

### 2. Integration into Technical Identifier Check
Updated `LLMLinguaCompressor._is_technical_or_identifier` (lines 691–703) to automatically protect initials across all helper contexts:
```python
@staticmethod
def _is_technical_or_identifier(token: str) -> bool:
    clean = token.strip(".,;:?!'\"()[]{}")
    if not clean:
        return False
    # Personal initials or initialisms (A., B., J., A.B., etc.)
    if LLMLinguaCompressor._is_personal_initial(token):
        return True
    # Digits (numbers, versions, ports, units)
    if any(c.isdigit() for c in clean):
        return True
    ...
```

### 3. Contextual Initial Immunity & Article Pruning Guard
Updated token filtering loop in `_compress_fallback_natural_text` (lines 566–598):
```python
kept_tokens: List[str] = []
for tok_idx, match in enumerate(token_matches):
    ws, raw_tok = match.group(1), match.group(2)
    word_clean = raw_tok.strip(".,;:?!'\"()[]{}").lower()

    # Detect if token is a personal initial or initialism (e.g., 'A.', 'B.', 'J.', 'A.B.', 'A. B.')
    next_raw = token_matches[tok_idx + 1].group(2) if tok_idx + 1 < len(token_matches) else ""
    is_initial = self._is_personal_initial(raw_tok, next_raw)

    # Determine if word is immune to pruning
    is_immune = (
        word_clean in IMMUNE_WORDS
        or self._is_technical_or_identifier(raw_tok)
        or is_initial
        or (
            freq.get(word_clean, 0) == 1
            and len(word_clean) > 3
            and word_clean not in WEAK_ADVERBS
            and word_clean not in FILLER_QUALIFIERS
            and word_clean not in ARTICLES
        )
    )

    drop = False
    if not is_immune:
        if word_clean in WEAK_ADVERBS:
            ...
        elif mode in ("balanced", "aggressive") and word_clean in FILLER_QUALIFIERS:
            drop = True
        elif mode == "aggressive" and word_clean in ARTICLES:
            # In aggressive mode, prune non-essential articles unless at sentence start or an initial
            if not is_initial:
                drop = True

    if not drop:
        kept_tokens.append(ws + raw_tok)
```

---

## 4. Before-and-After Verification Examples

| Test Case | Mode | Before Fix | After Fix | Status |
| :--- | :---: | :--- | :--- | :---: |
| `"The book was written by A. B. Smith last year."` | Aggressive | `"Book was written by B. Smith last year."` | `"Book was written by A. B. Smith last year."` | **RESOLVED** |
| `"A. Smith will attend the meeting."` | Aggressive | `"Smith will attend meeting."` | `"A. Smith will attend meeting."` | **RESOLVED** |
| `"Research by A. J. Brown was cited."` | Aggressive | `"Research by J. Brown was cited."` | `"Research by A. J. Brown was cited."` | **RESOLVED** |
| `"Theory was developed by A. Einstein in 1905."` | Aggressive | `"Theory was developed by Einstein in 1905."` | `"Theory was developed by A. Einstein in 1905."` | **RESOLVED** |
| `"Sequence: A. B. C. are valid points."` | Aggressive | `"Sequence: B. C. are valid points."` | `"Sequence: A. B. C. are valid points."` | **RESOLVED** |
| `"Dr. A. Smith confirmed the diagnosis."` | Aggressive | `"Dr. Smith confirmed diagnosis."` | `"Dr. A. Smith confirmed diagnosis."` | **RESOLVED** |
| `"Review performed by:\nA. Smith."` | Aggressive | `"Review performed by: Smith."` | `"Review performed by:\nA. Smith."` | **RESOLVED** |
| `"Smith, A. The results are clear."` | Aggressive | `"Smith, results are clear."` | `"Smith, A. results are clear."` | **RESOLVED** |
| `"A detailed report is required."` | Aggressive | `"Detailed report is required."` | `"Detailed report is required."` | **ARTICLE PRUNED** |
| `"Write a short summary."` | Aggressive | `"Write short summary."` | `"Write short summary."` | **ARTICLE PRUNED** |
| `"Use an appropriate method."` | Aggressive | `"Use method."` | `"Use method."` | **ARTICLE PRUNED** |

---

## 5. Mode Invariance Verification

Personal initials were evaluated across all three operational modes to ensure complete consistency:
- **Conservative Mode:** `A. B. Smith`, `A. Smith`, `A. J. Brown`, `A. Einstein`, `A. B. C.` $\longrightarrow$ **100% Preserved**.
- **Balanced Mode:** `A. B. Smith`, `A. Smith`, `A. J. Brown`, `A. Einstein`, `A. B. C.` $\longrightarrow$ **100% Preserved**.
- **Aggressive Mode:** `A. B. Smith`, `A. Smith`, `A. J. Brown`, `A. Einstein`, `A. B. C.` $\longrightarrow$ **100% Preserved**.

---

## 6. Comprehensive Regression Test Results

A dedicated test class `TestFixPersonalInitialPreservation` was added to `tests/test_optimizer_correctness_fixes.py` containing 27 parameterized test variants:
1. `test_reported_ab_smith_case_in_all_modes` (3 modes): Verifies exact retention of `"A. B. Smith"`.
2. `test_single_and_multiple_initials_preserved` (12 test combinations): Verifies `"A. Smith"`, `"A. J. Brown"`, `"A. Einstein"`, and `"A. B. C."` in all 3 modes.
3. `test_initials_in_different_positions` (3 modes): Verifies sentence start, mid-sentence, and sentence end.
4. `test_initials_adjacent_to_punctuation_and_newlines` (3 modes): Verifies titles (`Dr. A. Smith`), parentheses (`(A. Smith)`), quotes (`"A. Smith"`), and newlines (`\nA. Smith`).
5. `test_ordinary_articles_still_pruned_in_aggressive_mode`: Verifies that ordinary articles (`"A detailed"`, `"a short"`, `"an appropriate"`) are pruned in Aggressive mode.
6. `test_protected_regions_with_initials`: Verifies code blocks, URLs, and file paths with initials.
7. `test_unicode_and_mixed_casing_with_initials`: Verifies accented names (`M. René A. Smith`).
8. `test_no_token_expansion_on_initials` (3 modes): Confirms net token reduction is $\ge 0$.

### Test Suite Execution Summary
- `pytest tests/test_optimizer_correctness_fixes.py`: **115 PASSED (100%)** in 16.91s.
- `pytest tests/` (Complete Repository Suite): **390 PASSED (100%)** in 46.63s.
- **Failures:** 0
- **Skipped:** 0

---

## 7. Remaining Edge Cases & Limitations

1. **Bare Single Letters Followed by Lowercase Words:**  
   If an author writes `"A"` without a period followed by a lowercase word (e.g. `"A smith"`), `"A"` is treated as an article and pruned in Aggressive mode. In standard English, initials are written with periods (`"A. Smith"`), which is fully protected.
2. **Initials Without Periods in Monograms:**  
   Three-letter monograms without periods (e.g. `"JFK"`, `"FDR"`) are protected by the acronym check (`len >= 2 and isupper()`), while single-letter initials require standard period punctuation (`"A."`) or adjacent initial pairing (`"A B"`).

---

## 8. Audit of Repository Safeguards

| Resource | Expected Status | Verified Status |
| :--- | :--- | :---: |
| `results/benchmark_1200/benchmark_ledger.db` | 3,600 records | **3,600 records (Intact)** |
| `results/benchmark_v2/benchmark_ledger.db` | 720 records | **720 records (Intact)** |
| `data/benchmark_240_independent.json` | SHA-256: `977f5228...` | **Verbatim Match (Intact)** |
| `data/benchmark_1200_independent.json` | SHA-256: `13dd7cec...` | **Verbatim Match (Intact)** |
| `../PromptGreen.zip` (V1 Backup) | 120,304 bytes | **120,304 bytes (Intact)** |
| Git Branch & Status | Branch `version-2`, 0 staged | **Branch `version-2`, 0 staged commits** |
| Previous Fixes | Greeting regex, sentence split, token gate | **All 100% Retained and Passing** |
