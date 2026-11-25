# PromptGreen V2 — Expanded Independent Benchmark Dataset Design (1,200 Prompts)

**Document Reference:** `docs/EXPANDED_BENCHMARK_DATASET_DESIGN.md`  
**Dataset Artifact:** `data/benchmark_1200_independent.json`  
**Baseline Artifact:** `data/benchmark_240_independent.json` (Immutable Baseline)  
**Creation Date:** November 23, 2026  
**Status:** Completed & Validated — Phase 1 (Dataset Design & Integrity)  

---

## 1. Executive Summary & Objective

This document defines the architecture, design taxonomy, schema specifications, and distribution metrics for the expanded PromptGreen V2 independent evaluation benchmark dataset.

The independent benchmark dataset has been expanded from its original baseline of **240 prompts** (8 categories $\times$ 30 prompts) to exactly **1,200 unique prompts** (12 categories $\times$ 100 prompts).

### Primary Objectives:
1. **Holistic Real-World Evaluation:** Expand domain coverage beyond software engineering and core tech into creative writing, cross-lingual localization, multi-agent tool execution, and high-consequence safety-sensitive domains.
2. **Stress-Testing Prompt Optimization Invariants:** Test whether PromptGreen's multi-stage optimization pipeline (lexical cleaning, rule-based pruning, semantic guard verification, and LLM-assisted refinement) preserves critical constraints, numerical parameters, regulatory citations, negative constraints, and safety disclaimers while reducing redundant conversational tokens.
3. **Multi-Mode Execution Scaling:** Establish a representative, balanced corpus for future evaluation across all three optimization modes:
   - **Conservative:** High-preservation, safety-first optimization.
   - **Balanced:** Production default balancing compression and structural fidelity.
   - **Aggressive:** Maximum token reduction and conciseness pruning.
   - **Target Execution Volume:** $1,200 \text{ prompts} \times 3 \text{ modes} = 3,600 \text{ independent benchmark executions}$.

---

## 2. Dataset Architecture & Strict Preservation Principles

The expansion was engineered under strict data-preservation principles to ensure complete scientific continuity with all prior benchmark runs:

1. **Verbatim Baseline Preservation:**
   - The original dataset `data/benchmark_240_independent.json` (190,426 bytes, SHA-256: `977f52289f073afe5f7db536063a3080cef36699987ecbac5b690270ead1176f`) was left completely untouched.
   - All 240 original records (`pg-bench-001` through `pg-bench-240`) are preserved verbatim as the first 240 records of `data/benchmark_1200_independent.json` (`data_1200[:240] == data_240` evaluates strictly to `True`).
2. **Non-Colliding Sequential Identifier Allocation:**
   - Original records: `pg-bench-001` to `pg-bench-240`.
   - Expanded records (Categories 1–8): `pg-bench-241` to `pg-bench-800` (70 additional prompts per original category, bringing each to exactly 100).
   - New domain records (Categories 9–12): `pg-bench-801` to `pg-bench-1200` (100 prompts per new category).
3. **Modular Generator Infrastructure:**
   - Prompts were generated using isolated, domain-specific modular generator modules located in `scratch/data_generators/`:
     - `cat1_code.py` (70 prompts)
     - `cat2_rag.py` (70 prompts)
     - `cat3_analytical.py` (70 prompts)
     - `cat4_summarization.py` (70 prompts)
     - `cat5_cicd.py` (70 prompts)
     - `cat6_datascience.py` (70 prompts)
     - `cat7_structured.py` (70 prompts)
     - `cat8_general_tech.py` (70 prompts)
     - `cat9_creative.py` (100 prompts)
     - `cat10_conversational.py` (100 prompts)
     - `cat11_tooluse.py` (100 prompts)
     - `cat12_safetysensitive.py` (100 prompts)
4. **Zero Production Contamination:**
   - Dataset generation and validation were conducted in strict read-only isolation with respect to the production database (`prompt_ledger.db`) and historical benchmark databases (`results/benchmark_v2/benchmark_ledger.db`). Zero optimization benchmarks were executed during dataset creation.

---

## 3. Category Taxonomy & Domain Breakdown (12 Categories, 100 Prompts Each)

The expanded dataset spans 12 balanced, non-overlapping functional categories. Each category contains exactly 100 prompts:

| Category ID | Category Name | Original Prompts | New Prompts | Total Prompts | Primary Focus & Domain Scope |
| :---: | :--- | :---: | :---: | :---: | :--- |
| **01** | `Code generation and debugging` | 30 | 70 | 100 | Algorithms, distributed systems, concurrency, async I/O, memory management, refactoring, compiler optimizations, kernel modules. |
| **02** | `RAG and information retrieval` | 30 | 70 | 100 | Vector search, semantic retrieval, chunking policies, hybrid BM25/dense search, query expansion, citation grounding, knowledge graph retrieval. |
| **03** | `Analytical reasoning` | 30 | 70 | 100 | Quantitative finance, algorithmic game theory, probability, root cause analysis, capacity planning, distributed consensus proofs, optimization models. |
| **04** | `Summarization and information extraction` | 30 | 70 | 100 | Technical whitepapers, architectural RFCs, incident post-mortems, earnings transcripts, multi-document synthesis, executive briefing abstracts. |
| **05** | `CI/CD and developer workflows` | 30 | 70 | 100 | Containerization, Kubernetes manifests, GitHub Actions workflows, blue/green deployments, canary testing, Terraform IaC, artifact signing. |
| **06** | `Data science and machine learning` | 30 | 70 | 100 | MLOps pipelines, feature engineering, distributed training, hyperparameter sweeps, model drift detection, model quantization (GGUF/AWQ), metrics evaluation. |
| **07** | `Structured output and formatting constraints` | 30 | 70 | 100 | Strict JSON/YAML schemas, OpenAPI specifications, Protobuf definitions, regex extraction, CSV/TSV table formatting, XML serialization, nested ASTs. |
| **08** | `General technical instructions` | 30 | 70 | 100 | Linux systems administration, TCP/IP networking, storage systems, web protocols, shell scripting, database indexing, infrastructure security. |
| **09** | `Creative writing and content generation` | 0 | 100 | 100 | Worldbuilding, narrative fiction, marketing copy decks, screenplays/dialogue, oratory speeches, formal metered poetry, author tone imitation, micro-fiction. |
| **10** | `Conversational and multilingual assistance` | 0 | 100 | 100 | Multi-turn clarification, persona/register adaptation, cross-lingual localization (12+ languages), idiomatic nuance, conflict de-escalation, dialect code-switching. |
| **11** | `Tool-use and agentic workflows` | 0 | 100 | 100 | Multi-step tool orchestration, strict JSON API argument extraction, safe filesystem management, SQL operations, error recovery/retries, human-in-the-loop gating, agent swarms. |
| **12** | `Safety-sensitive and professional applications` | 0 | 100 | 100 | Health literacy & medical triage boundaries, legal referrals & statutory deadlines, financial risk disclosures, defensive cybersecurity, industrial safety, emergency broadcasts, data privacy. |
| **Total** | **12 Categories** | **240** | **960** | **1,200** | **Comprehensive Evaluation Corpus** |

---

## 4. Metadata Schema & Invariant Specifications

The dataset uses a unified schema compatible with both the legacy 240-prompt benchmark runner and the expanded V2 analysis tools.

### Core Schema Keys:
Every prompt record contains the following mandatory keys:

```json
{
  "id": "pg-bench-1102",
  "category": "Safety-sensitive and professional applications",
  "subcategory": "Healthcare Communication & Boundaries",
  "original_prompt": "Draft an outpatient discharge instruction sheet for an adult patient following arthroscopic knee surgery...",
  "expected_task_intent": "Clear, precise post-surgical discharge instructions emphasizing safety thresholds and red-flag symptoms.",
  "critical_constraints": [
    "strict non-weight-bearing for 48 hours",
    "ice 20 min on / 40 min off with cloth barrier",
    "keep dressing dry",
    "exact contact thresholds: fever > 101.4°F, calf pain, shortness of breath"
  ],
  "expected_output_characteristics": "Structured, accessible patient instructions with urgent warning signs prominently highlighted.",
  "difficulty": "medium",
  "length_profile": "medium",
  "special_preservation_requirements": "Exact 48-hour limit, 20/40 icing cadence, fever threshold 101.4°F, calf pain and shortness of breath red flags."
}
```

### Key Descriptions & Behavioral Invariants:
1. **`id` (string):** Unique, immutable test identifier (`pg-bench-001` through `pg-bench-1200`).
2. **`category` (string):** Top-level functional taxonomy string. Uses sentence-style capitalization matching the benchmark runner's grouping logic.
3. **`subcategory` (string):** Granular functional subcategory (e.g., `Multi-Step Tool Calling & Orchestration`, `Healthcare Communication & Boundaries`).
4. **`original_prompt` (string):** Realistic, non-template, domain-authentic prompt text containing natural user preamble, context, and explicit constraints.
5. **`expected_task_intent` (string):** Canonical task intent statement used by the Semantic Guard to verify that optimization has not caused semantic drift.
6. **`critical_constraints` (list of strings):** Explicit list of technical, operational, or legal parameters that must survive prompt optimization intact (e.g., exact flags, numerical thresholds, statutory citations).
7. **`expected_output_characteristics` (string):** Target structural and stylistic profile of the expected LLM generation.
8. **`difficulty` (string):** Categorical grading: `easy` (straightforward constraints), `medium` (multi-step or mixed constraints), `hard` (complex dependencies or strict negative constraints), or `adversarial` (intentionally conversational or convoluted phrasing testing noise-pruning limits).
9. **`length_profile` (string):** Categorical input length: `short` (<30 words), `medium` (30–60 words), `long` (>60 words), or `multi-paragraph`.
10. **`special_preservation_requirements` (string):** Explicit instructions highlighting the core invariant terms, disclaimers, or tokens that must be preserved.

---

## 5. Statistical Distributions & Diversity Analysis

### A. Difficulty Distribution
The dataset is balanced across varying operational complexities, with an emphasis on realistic medium and hard engineering challenges:

| Difficulty Tier | Count | Percentage | Primary Characteristics |
| :--- | :---: | :---: | :--- |
| **Medium** | 612 | 51.0% | Standard multi-parameter instructions, composite constraints, and structured output requests. |
| **Hard** | 309 | 25.8% | High-dimensional specifications, multi-system orchestration, formal algorithmic or regulatory compliance. |
| **Easy** | 220 | 18.3% | Clear, direct technical requests with 1–2 explicit parameter constraints. |
| **Adversarial** | 59 | 4.9% | Extreme verbosity, conversational tangents, emotional rhetoric, or conflicting constraints testing safety guards. |
| **Total** | **1,200** | **100.0%** | **Balanced across all difficulty levels** |

### B. Length Profile Distribution
Prompts range from concise single-sentence commands to multi-paragraph scenario briefs:

| Length Profile | Count | Percentage | Word Count Range | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Medium** | 689 | 57.4% | 30 – 60 words | Standard production user prompts containing task description, context, and 2–4 constraints. |
| **Short** | 436 | 36.3% | 15 – 30 words | Crisp, direct instructions testing whether the optimizer avoids unnecessary bloating or over-compression. |
| **Long** | 67 | 5.6% | 60 – 95 words | Dense specifications containing detailed schemas, multiple error conditions, or statutory legal boilerplate. |
| **Multi-Paragraph** | 8 | 0.7% | 70 – 110 words | Structured multi-block prompts testing section preservation and layout awareness. |
| **Total** | **1,200** | **100.0%** | **16 – 91 words (Avg: 42.2)** | **Broad real-world distribution** |

### C. Text Length Summary Statistics:
- **Minimum Word Count:** 16 words (`pg-bench-1033` - Targeted YAML config edit)
- **Maximum Word Count:** 91 words (`pg-bench-895` - Epistolary flash fiction through found receipts and voicemail)
- **Mean Word Count:** 42.2 words
- **Minimum Character Count:** 141 characters
- **Maximum Character Count:** 650 characters
- **Mean Character Count:** 297.9 characters

---

## 6. Benchmark Runner Compatibility

The expanded dataset maintains 100% backward compatibility with `promptgreen/validation/benchmark_v2.py`.

### Verification Evidence:
- **Dynamic Grouping:** `benchmark_v2.py` groups benchmark executions dynamically via `p.get("category")`. The 12 exact category strings are recognized and group into 100 prompts each without requiring code changes to the runner.
- **Key Access:** The runner accesses `id`, `category`, `original_prompt`, `difficulty`, and `length_profile`. All 1,200 records contain these fields with valid types.
- **Execution Target:** When benchmark execution is triggered, the runner will execute 3,600 trials ($1,200 \times 3$), recording latency, original token count, optimized token count, token reduction percentage, semantic guard cosine similarity, and ledger entry status to the isolated database `results/benchmark_v2/benchmark_ledger.db`.

---

## 7. Integrity Checklist

- [x] All 240 original prompts preserved verbatim at indices 0–239.
- [x] Original dataset SHA-256 hash verified unchanged (`977f52289f073afe5f7db536063a3080cef36699987ecbac5b690270ead1176f`).
- [x] Exactly 1,200 unique prompts created with zero duplicate IDs.
- [x] Exactly 12 categories with 100 prompts per category.
- [x] Zero exact duplicate prompt texts.
- [x] Near-duplicate Jaccard similarity analysis confirmed 0 pairs exceeding 0.70 threshold.
- [x] Zero benchmark executions conducted; zero database mutations.
