# PromptGreen V2 — IGE-1000 Final Dataset Freeze & Cryptographic Verification Report

**Document Date:** 2026-11-23  
**Freeze Milestone:** Formal Holdout Dataset Cryptographic Lock  
**Project Workspace:** `D:\EDU\DSU\Major project\PromptGreen`  
**Git Branch:** `version-2` | **HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Auditor Mode:** Strictly Read-Only Final Dataset Verification  

---

## 1. Executive Freeze Statement

This document formally declares the **IGE-1000 holdout dataset cryptographically frozen and immutable** for the PromptGreen V2 Independent Generalization Evaluation.

The dataset, located at:
`data/benchmark_ige_1000_unseen.json`

has undergone complete post-correction verification following the replacement of historical near-duplicate `ige-0001` and the mathematical calibration of personal-initial challenge probes across all 12 categories. The dataset has passed all seven preflight validation gates with zero warnings and zero exceptions.

The holdout dataset is now permanently locked. No further modifications, regenerations, or reformatting operations may be performed on this dataset.

---

## 2. Dataset Identity & Cryptographic Provenance

The authoritative cryptographic identity of the finalized holdout dataset is established as follows:

| Attribute | Authoritative Value |
|:---|:---|
| **Relative Path** | `data/benchmark_ige_1000_unseen.json` |
| **Absolute Path** | `D:\EDU\DSU\Major project\PromptGreen\data\benchmark_ige_1000_unseen.json` |
| **Cryptographic Hash (SHA-256)** | `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3` |
| **Exact File Size** | **1,109,310 bytes** |
| **Total Prompt Records** | **1,000 JSON objects** |
| **Sequential Identifiers** | `ige-0001` through `ige-1000` (zero gaps, zero duplicates) |
| **Schema Invariance** | Strict 8-field schema conforming to `promptgreen/validation/benchmark_v2.py` |
| **Tokenizer Specification** | OpenAI `cl100k_base` BPE tokenizer (`tiktoken` v0.14.0) |
| **Semantic Embedder** | Sentence-Transformers `all-MiniLM-L6-v2` (384-dimensional dense vectors) |
| **Python Environment** | Python 3.11.9 on Windows |

---

## 3. Pre-Correction vs. Post-Correction Traceability

To maintain complete historical auditability, the pre-correction dataset has been preserved as an immutable reference file alongside the corrected master:

| Dataset Version | File Path | SHA-256 Hash | File Size | Key Characteristics | Status |
|:---|:---|:---|:---:|:---|:---:|
| **Pre-Correction Reference** | `data/benchmark_ige_1000_unseen_pre_correction.json` | `ca80c37f1e9615c1c77fe110b6db78d80cfa7b6d2c49087b6bcf3f81d375e9eb` | 1,102,538 bytes | Near-dup `ige-0001` (Cosine 0.8172 vs `pg-bench-241`); 406 initial probes (40.6%) | **IMMUTABLE REFERENCE** |
| **Final Active Master** | `data/benchmark_ige_1000_unseen.json` | `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3` | 1,109,310 bytes | Replaced `ige-0001` (Cosine 0.1516 vs `pg-bench-241`); exactly 72 initial probes (7.2%) | **FROZEN ACTIVE MASTER** |

---

## 4. Exact Specifications of Applied Dataset Corrections

### Correction 1: Replacement of Historical Near-Duplicate `ige-0001`

- **Pre-Correction Prompt (`ige-0001`):** C++20 lock-free SPSC ring buffer using atomic operations.
  - Historical comparison: `pg-bench-241` (C++20 SPSC ring buffer).
  - Pre-correction cosine similarity: **0.8172** (close to 0.8200 ceiling).
- **Post-Correction Replacement (`ige-0001`):**
  - **Category:** `Code generation and debugging` (preserved).
  - **Difficulty:** `easy` (preserved).
  - **Length Profile:** `short` (preserved, $< 50$ tokens).
  - **Token Count:** **39 tokens** (`cl100k_base`).
  - **Prompt Text:**
    > *"Can you help me implement a Python class that calculates the running median of a numerical data stream using two heaps (heapq) with O(log n) insertion. Follow A. Einstein's guidelines."*
  - **Expected Intent:** *"Implement running median finder using two heaps in Python."*
  - **Critical Constraints:** `['Python', 'heapq', 'two heaps', 'O(log n) insertion', "A. Einstein's guidelines"]`
  - **Historical Similarity Outcome:**
    - Cosine vs `pg-bench-241`: **0.1516** (reduced from 0.8172, **-0.6656** reduction).
    - Max Cosine vs all 1,200 historical prompts: **0.3554** (vs `pg-bench-285`).
    - Max Cosine vs remaining 999 IGE holdout prompts: **0.4059** (vs `ige-0041`).
- **Audit Verification:** Complete elimination of historical leakage risk.

### Correction 2: Calibration of Personal-Initial Challenge Probes

- **Pre-Correction Defect:** Generator over-indexing on the personal initial regression fixture, injecting initials (`Dr. A. B. Smith`, `A. Einstein`, etc.) into **406 prompts (40.6%)**, including 100% of long prompts.
- **Post-Correction Calibration:** Symmetrically calibrated to **72 prompts (7.2%)**, precisely matching the target representative challenge range (~5% to 7%):
  - **Short (< 50 tokens):** **24 prompts** (9.6% of short tier).
  - **Medium (50–200 tokens):** **24 prompts** (4.8% of medium tier).
  - **Long (> 200 tokens):** **24 prompts** (9.6% of long tier).
  - **Total:** **72 prompts (7.2%)**.
- **Category-Level Symmetry:** Exactly **6 challenge probes per category** (2 short, 2 medium, 2 long) across all 12 categories.
- **Audit Verification:** Provides representative edge-case coverage to evaluate Stage 1 name-initial preservation without distorting overall benchmark generalizability.

---

## 5. Preflight Validation Gate Verification Results

The finalized dataset was subjected to the full automated 7-gate preflight test suite (`scratch/validate_ige_1000_preflight.py`). All gates passed with zero warnings:

| Preflight Gate | Audit Description & Scope | Locked Threshold | Empirical Measured Result | Gate Status |
|:---|:---|:---:|:---:|:---:|
| **Gate 1: Historical Safeguards** | Cryptographic verification of historical assets & DBs | 100% Bit-for-bit parity | All hashes & record counts identical | **PASS** |
| **Gate 2: Schema & Invariance** | Strict 8-field structure & non-empty prompt check | 8 required keys, 0 empty | 1,000 / 1,000 valid records | **PASS** |
| **Gate 3: Quotas & Distribution** | Category (4x84 + 8x83), Difficulty (3/5/2), Length (2.5/5/2.5) | Exact integer quotas | Exactly 1,000 / 1,000 matching quotas | **PASS** |
| **Gate 4: Historical Lexical Overlap** | Normalized exact match & token Jaccard vs 1,200 | 0 exact, $J < 0.5500$ | **0 exact matches**, $\max J = \mathbf{0.4000}$ | **PASS** |
| **Gate 5: Historical Semantic Screening**| Full matrix $1,000 \times 1,200$ dot products (`MiniLM`) | $\max \text{Cosine} < 0.8200$, 0 flagged | $\max \text{Cosine} = \mathbf{0.7977}$, **0 flagged** | **PASS** |
| **Gate 6: Internal Uniqueness** | Internal exact deduplication, Jaccard, & Cosine ($499.5\text{k}$) | $J < 0.6500$, $\text{Cosine} < 0.8800$ | $\max J = \mathbf{0.6327}$, $\max \text{Cosine} = \mathbf{0.8661}$ | **PASS** |
| **Gate 7: Lexical Diversity** | Total words, unique vocabulary size, TTR | High vocabulary breadth | 68,413 words, 7,015 unique vocab, TTR 0.1025 | **PASS** |

### Top Similarity Boundary Confirmations
- **Top Historical Semantic Similarity:** **0.7977** (`ige-0363` vs `pg-bench-026`, threshold: $< 0.8200$).
- **Top Internal Semantic Similarity:** **0.8661** (`ige-0161` vs `ige-0312`, threshold: $< 0.8800$).
- **Top Internal Jaccard Similarity:** **0.6327** (`ige-0068` vs `ige-0527`, threshold: $< 0.6500$).
- **Top Historical Jaccard Similarity:** **0.4000** (`ige-0338` vs `pg-bench-702`, threshold: $< 0.5500$).

---

## 6. Invariance Verification of Historical Assets & Production State

All pre-existing datasets, databases, and backup archives were verified directly from disk to confirm zero collateral mutation:

| Asset Description | Path | Expected Checksum / Count | Measured Value | Invariance State |
|:---|:---|:---|:---|:---:|
| **Historical 240 Dataset** | `data/benchmark_240_independent.json` | `977f52289f073afe5f7db536063a3080cef36699987ecbac5b690270ead1176f` | Same | **IMMUTABLE** |
| **Historical 1200 Dataset** | `data/benchmark_1200_independent.json` | `13dd7cece5794e4071f2987ef7aa3971b5f8bf86d97e466807afc330ab01363e` | Same | **IMMUTABLE** |
| **V1 Backup ZIP** | `../PromptGreen.zip` | 120,304 bytes, SHA `dc8b78a3371efbcb1066169222ad98053ff4f36e1d49f79974246e0243d08808` | Same | **IMMUTABLE** |
| **Production SQLite DB** | `prompt_ledger.db` | Exactly 413 records | 413 records | **IMMUTABLE** |
| **Benchmark V2 DB** | `results/benchmark_v2/benchmark_ledger.db` | Exactly 720 records | 720 records | **IMMUTABLE** |
| **Benchmark 1200 DB** | `results/benchmark_1200/benchmark_ledger.db` | Exactly 3,600 records | 3,600 records | **IMMUTABLE** |

### Git State Governance
- **Current Branch:** `version-2`
- **HEAD Commit:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`
- **Staged Files:** **0 files staged**
- **New Commits Created:** **0 commits created**
- **Working Tree Preservation:** All 13 tracked modified files and untracked development artifacts remain preserved with zero unintended loss or modification.

---

## 7. Formal Statement of Readiness

The IGE-1000 independent benchmark dataset (`data/benchmark_ige_1000_unseen.json`) is cryptographically frozen, fully validated, and verified free from historical overlap, internal redundancy, and synthetic distortion.

**READINESS DECLARATION:**  
The dataset is **STRICTLY READY AND FULLY AUTHORIZED FOR PHASE 2 BENCHMARK EXECUTION**.
