# PromptGreen V2 — Independent 1,200-Prompt Evaluation Report
**Evaluation Date:** 2026-11-23T11:36:43.907291Z  
**Dataset:** `data/benchmark_1200_independent.json` (1200 unique prompts)  
**Model Tier Evaluated:** `mid_tier`  
**Grid Scenario:** `ILLUSTRATIVE_385`  
**Isolated Persistence:** `results/benchmark_1200\benchmark_ledger.db`  

> [!IMPORTANT]
> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment
> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.
> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.

---
## 1. Executive Summary Across Modes

| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |
|---|---|---|---|---|---|---|---|---|---|
| **CONSERVATIVE** | 1200 | 1188 | 99.0% | 12 | 0.18 tok | 0.31% | 478.44 ms | 0.9987 | 3.4472 Wh |
| **BALANCED** | 1200 | 1192 | 99.33% | 8 | 0.25 tok | 0.42% | 485.56 ms | 0.9985 | 6.5002 Wh |
| **AGGRESSIVE** | 1200 | 1193 | 99.42% | 7 | 3.59 tok | 5.74% | 479.29 ms | 0.9895 | 51.0287 Wh |

## 2. Category Breakdown (CONSERVATIVE Mode)

| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |
|---|---|---|---|---|---|---|---|---|
| Analytical reasoning | 100 | 100 | 100.0% | 0.15 tok | 0.28% | 288.41 ms | 0.9993 | 0.4889 Wh |
| CI/CD and developer workflows | 100 | 99 | 99.0% | 0.09 tok | 0.16% | 244.69 ms | 0.9994 | 0.2887 Wh |
| Code generation and debugging | 100 | 99 | 99.0% | 0.63 tok | 1.05% | 299.11 ms | 0.9974 | 1.0035 Wh |
| Conversational and multilingual assistance | 100 | 99 | 99.0% | 0.28 tok | 0.37% | 676.21 ms | 0.9993 | 0.5702 Wh |
| Creative writing and content generation | 100 | 98 | 98.0% | 0.12 tok | 0.14% | 756.05 ms | 0.9983 | 0.0061 Wh |
| Data science and machine learning | 100 | 100 | 100.0% | 0.1 tok | 0.18% | 264.42 ms | 0.9995 | 0.1705 Wh |
| General technical instructions | 100 | 100 | 100.0% | 0.09 tok | 0.16% | 276.67 ms | 0.9995 | 0.2565 Wh |
| RAG and information retrieval | 100 | 100 | 100.0% | 0.35 tok | 0.65% | 269.05 ms | 0.9976 | 0.7974 Wh |
| Safety-sensitive and professional applications | 100 | 100 | 100.0% | 0.03 tok | 0.04% | 1080.09 ms | 0.9997 | -0.4461 Wh |
| Structured output and formatting constraints | 100 | 95 | 95.0% | 0.15 tok | 0.22% | 247.06 ms | 0.9963 | 0.5021 Wh |
| Summarization and information extraction | 100 | 98 | 98.0% | 0.21 tok | 0.46% | 237.63 ms | 0.9982 | 0.4626 Wh |
| Tool-use and agentic workflows | 100 | 100 | 100.0% | 0.01 tok | 0.01% | 1101.91 ms | 1.0 | -0.6531 Wh |

## 3. Preservation & Security Verification

- **Protected Content Violations:** 7 (Must be exactly 0)
- **Negative Token Reductions:** 6
- **Zero Token Reductions:** 1068
- **Net Carbon Debt Cases:** 1016 (84.67%)
- **Stage 2 Fallback Rate:** 100.0%
- **Stage 3 Fallback Rate:** 100.0%
- **Total Net Energy Saved:** 3.4472 Wh across 1200 prompts

## 4. Notable Edge & Failure Cases

Total flagged edge cases in `conservative` mode: **1022**

| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |
|---|---|---|---|---|---|---|
| `pg-bench-008` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-014` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-018` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-020` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-021` | Code generation and debugging | hard | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-023` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-025` | Code generation and debugging | adversarial | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-029` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-032` | RAG and information retrieval | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-035` | RAG and information retrieval | adversarial | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-042` | RAG and information retrieval | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-044` | RAG and information retrieval | adversarial | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-045` | RAG and information retrieval | hard | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-050` | RAG and information retrieval | easy | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `pg-bench-052` | RAG and information retrieval | adversarial | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |

*(And 1007 additional cases detailed in `failure_cases.json`)*

---
*Report generated automatically by PromptGreen V2 Benchmark Suite.*