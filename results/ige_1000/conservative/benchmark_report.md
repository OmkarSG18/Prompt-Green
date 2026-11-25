# PromptGreen V2 — Independent 240-Prompt Evaluation Report
**Evaluation Date:** 2026-11-23T16:43:53.793243Z  
**Dataset:** `data/benchmark_ige_1000_unseen.json` (1000 unique prompts)  
**Model Tier Evaluated:** `mid_tier`  
**Grid Scenario:** `ILLUSTRATIVE_385`  
**Isolated Persistence:** `results/ige_1000/conservative\benchmark_ledger.db`  

> [!IMPORTANT]
> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment
> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.
> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.

---
## 1. Executive Summary Across Modes

| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |
|---|---|---|---|---|---|---|---|---|---|
| **CONSERVATIVE** | 1000 | 890 | 89.0% | 110 | 1.2 tok | 2.37% | 1123.51 ms | 0.9876 | 27.1959 Wh |

## 2. Category Breakdown (CONSERVATIVE Mode)

| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |
|---|---|---|---|---|---|---|---|---|
| Analytical reasoning | 84 | 75 | 89.29% | 1.12 tok | 2.22% | 1076.14 ms | 0.9875 | 2.0974 Wh |
| CI/CD and developer workflows | 83 | 75 | 90.36% | 1.29 tok | 2.59% | 1123.62 ms | 0.9891 | 2.3705 Wh |
| Code generation and debugging | 84 | 72 | 85.71% | 1.2 tok | 2.7% | 921.5 ms | 0.9864 | 2.5041 Wh |
| Conversational and multilingual assistance | 83 | 74 | 89.16% | 1.27 tok | 2.46% | 1197.13 ms | 0.9869 | 2.1679 Wh |
| Creative writing and content generation | 83 | 73 | 87.95% | 1.2 tok | 2.41% | 1078.55 ms | 0.9885 | 2.1704 Wh |
| Data science and machine learning | 83 | 76 | 91.57% | 1.3 tok | 2.48% | 1127.57 ms | 0.988 | 2.2197 Wh |
| General technical instructions | 83 | 71 | 85.54% | 1.0 tok | 1.86% | 1121.63 ms | 0.9875 | 2.0842 Wh |
| RAG and information retrieval | 84 | 76 | 90.48% | 1.13 tok | 2.23% | 1220.31 ms | 0.9896 | 2.1079 Wh |
| Safety-sensitive and professional applications | 83 | 74 | 89.16% | 1.18 tok | 2.43% | 1231.1 ms | 0.9889 | 2.0597 Wh |
| Structured output and formatting constraints | 83 | 73 | 87.95% | 1.12 tok | 2.14% | 1061.95 ms | 0.9846 | 2.5614 Wh |
| Summarization and information extraction | 84 | 75 | 89.29% | 1.23 tok | 2.36% | 1232.76 ms | 0.9859 | 2.4245 Wh |
| Tool-use and agentic workflows | 83 | 76 | 91.57% | 1.37 tok | 2.52% | 1090.42 ms | 0.9881 | 2.4282 Wh |

## 3. Preservation & Security Verification

- **Protected Content Violations:** 74 (Must be exactly 0)
- **Negative Token Reductions:** 0
- **Zero Token Reductions:** 420
- **Net Carbon Debt Cases:** 180 (18.0%)
- **Stage 2 Fallback Rate:** 100.0%
- **Stage 3 Fallback Rate:** 100.0%
- **Total Net Energy Saved:** 27.1959 Wh across 1000 prompts

## 4. Notable Edge & Failure Cases

Total flagged edge cases in `conservative` mode: **180**

| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |
|---|---|---|---|---|---|---|
| `ige-0002` | Code generation and debugging | easy | 0 (0.0%) | 0.9843 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0005` | Code generation and debugging | easy | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0016` | Code generation and debugging | easy | 0 (0.0%) | 0.9481 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Cosine similarity (0.9481) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0019` | Code generation and debugging | easy | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0025` | Code generation and debugging | easy | 0 (0.0%) | 0.9528 | ROLLED_BACK | Cosine similarity (0.9528) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0026` | Code generation and debugging | medium | 0 (0.0%) | 0.9781 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0029` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0036` | Code generation and debugging | medium | 0 (0.0%) | 0.9716 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0041` | Code generation and debugging | medium | 0 (0.0%) | 0.9597 | ROLLED_BACK | Cosine similarity (0.9597) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0045` | Code generation and debugging | medium | 0 (0.0%) | 0.9364 | ROLLED_BACK | Cosine similarity (0.9364) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0049` | Code generation and debugging | medium | 0 (0.0%) | 0.9505 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Cosine similarity (0.9505) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0058` | Code generation and debugging | medium | 0 (0.0%) | 0.9629 | ROLLED_BACK | Ungrounded candidate section: candidate section relevance (0.6986) below chunk threshold (0.82).; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0061` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0073` | Code generation and debugging | hard | 0 (0.0%) | 0.9652 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0078` | Code generation and debugging | hard | 0 (0.0%) | 0.9717 | ROLLED_BACK | Ungrounded candidate section: candidate section relevance (0.7165) below chunk threshold (0.82).; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |

*(And 165 additional cases detailed in `failure_cases.json`)*

---
*Report generated automatically by PromptGreen V2 Benchmark Suite.*