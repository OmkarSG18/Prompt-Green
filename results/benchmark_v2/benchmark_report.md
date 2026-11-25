# PromptGreen V2 — Independent 240-Prompt Evaluation Report
**Evaluation Date:** 2026-11-22T17:07:20.429310Z  
**Dataset:** `data/benchmark_240_independent.json` (240 unique prompts)  
**Model Tier Evaluated:** `mid_tier`  
**Grid Scenario:** `ILLUSTRATIVE_385`  
**Isolated Persistence:** `results/benchmark_v2\benchmark_ledger.db`  

> [!IMPORTANT]
> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment
> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.
> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.

---
## 1. Executive Summary Across Modes

| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |
|---|---|---|---|---|---|---|---|---|---|
| **CONSERVATIVE** | 240 | 235 | 97.92% | 5 | 0.7 tok | 1.24% | 290.98 ms | 0.9961 | 11.5041 Wh |
| **BALANCED** | 240 | 236 | 98.33% | 4 | 0.75 tok | 1.35% | 332.47 ms | 0.9959 | 11.4064 Wh |
| **AGGRESSIVE** | 240 | 236 | 98.33% | 4 | 3.36 tok | 6.11% | 337.24 ms | 0.9893 | 11.3086 Wh |

## 2. Category Breakdown (CONSERVATIVE Mode)

| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |
|---|---|---|---|---|---|---|---|---|
| Analytical reasoning | 30 | 30 | 100.0% | 0.37 tok | 0.7% | 248.38 ms | 0.9979 | 1.4146 Wh |
| CI/CD and developer workflows | 30 | 30 | 100.0% | 0.3 tok | 0.52% | 279.03 ms | 0.9979 | 1.3981 Wh |
| Code generation and debugging | 30 | 30 | 100.0% | 1.97 tok | 3.27% | 324.67 ms | 0.9932 | 1.3576 Wh |
| Data science and machine learning | 30 | 30 | 100.0% | 0.33 tok | 0.6% | 311.15 ms | 0.9985 | 1.3956 Wh |
| General technical instructions | 30 | 30 | 100.0% | 0.27 tok | 0.48% | 367.87 ms | 0.9984 | 1.3607 Wh |
| RAG and information retrieval | 30 | 30 | 100.0% | 1.17 tok | 2.15% | 265.9 ms | 0.9919 | 1.4477 Wh |
| Structured output and formatting constraints | 30 | 27 | 90.0% | 0.5 tok | 0.75% | 301.26 ms | 0.9964 | 1.4709 Wh |
| Summarization and information extraction | 30 | 28 | 93.33% | 0.67 tok | 1.47% | 229.58 ms | 0.9944 | 1.6589 Wh |

## 3. Preservation & Security Verification

- **Protected Content Violations:** 4 (Must be exactly 0)
- **Negative Token Reductions:** 0
- **Zero Token Reductions:** 159
- **Net Carbon Debt Cases:** 0 (0.0%)
- **Stage 2 Fallback Rate:** 100.0%
- **Stage 3 Fallback Rate:** 100.0%
- **Total Net Energy Saved:** 11.5041 Wh across 240 prompts

## 4. Notable Edge & Failure Cases

Total flagged edge cases in `conservative` mode: **5**

| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |
|---|---|---|---|---|---|---|
| `pg-bench-091` | Summarization and information extraction | easy | 0 (0.0%) | 0.9596 | ROLLED_BACK | Cosine similarity (0.9596) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `pg-bench-111` | Summarization and information extraction | easy | 0 (0.0%) | 0.9812 | ROLLED_BACK | Inline code identifier '`{env: {}, args: []}`' present in original was altered or removed.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `pg-bench-184` | Structured output and formatting constraints | adversarial | 0 (0.0%) | 1.0 | ROLLED_BACK | Output format inversion: candidate explicitly negates required format 'json'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `pg-bench-187` | Structured output and formatting constraints | medium | 0 (0.0%) | 0.9827 | ROLLED_BACK | Inline code identifier '`<enclosure url="..." length="..." type="audio/mpeg"/>`' present in original was altered or removed.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `pg-bench-199` | Structured output and formatting constraints | medium | 0 (0.0%) | 0.9954 | ROLLED_BACK | Inline code identifier '`payload JSONB NOT NULL DEFAULT '{}'`' present in original was altered or removed.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |

---
*Report generated automatically by PromptGreen V2 Benchmark Suite.*