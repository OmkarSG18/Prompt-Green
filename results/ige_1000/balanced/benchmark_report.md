# PromptGreen V2 — Independent 240-Prompt Evaluation Report
**Evaluation Date:** 2026-11-23T17:05:14.425974Z  
**Dataset:** `data/benchmark_ige_1000_unseen.json` (1000 unique prompts)  
**Model Tier Evaluated:** `mid_tier`  
**Grid Scenario:** `ILLUSTRATIVE_385`  
**Isolated Persistence:** `results/ige_1000/balanced\benchmark_ledger.db`  

> [!IMPORTANT]
> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment
> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.
> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.

---
## 1. Executive Summary Across Modes

| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |
|---|---|---|---|---|---|---|---|---|---|
| **BALANCED** | 1000 | 922 | 92.2% | 78 | 1.41 tok | 2.71% | 1222.05 ms | 0.9874 | 28.0825 Wh |

## 2. Category Breakdown (BALANCED Mode)

| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |
|---|---|---|---|---|---|---|---|---|
| Analytical reasoning | 84 | 79 | 94.05% | 1.4 tok | 2.8% | 1101.56 ms | 0.9872 | 2.3312 Wh |
| CI/CD and developer workflows | 83 | 76 | 91.57% | 1.43 tok | 2.75% | 1233.66 ms | 0.989 | 2.3349 Wh |
| Code generation and debugging | 84 | 75 | 89.29% | 1.38 tok | 2.96% | 1294.41 ms | 0.9864 | 2.341 Wh |
| Conversational and multilingual assistance | 83 | 78 | 93.98% | 1.55 tok | 2.94% | 1267.41 ms | 0.9868 | 2.3235 Wh |
| Creative writing and content generation | 83 | 77 | 92.77% | 1.42 tok | 2.8% | 1151.74 ms | 0.9884 | 2.2838 Wh |
| Data science and machine learning | 83 | 76 | 91.57% | 1.39 tok | 2.55% | 1183.62 ms | 0.9879 | 2.173 Wh |
| General technical instructions | 83 | 74 | 89.16% | 1.22 tok | 2.19% | 1214.12 ms | 0.9873 | 2.1754 Wh |
| RAG and information retrieval | 84 | 79 | 94.05% | 1.42 tok | 2.73% | 1259.74 ms | 0.9894 | 2.2766 Wh |
| Safety-sensitive and professional applications | 83 | 76 | 91.57% | 1.31 tok | 2.6% | 1332.51 ms | 0.9889 | 2.0872 Wh |
| Structured output and formatting constraints | 83 | 75 | 90.36% | 1.41 tok | 2.61% | 1201.13 ms | 0.9839 | 2.6658 Wh |
| Summarization and information extraction | 84 | 79 | 94.05% | 1.44 tok | 2.77% | 1264.04 ms | 0.9858 | 2.5895 Wh |
| Tool-use and agentic workflows | 83 | 78 | 93.98% | 1.55 tok | 2.85% | 1160.23 ms | 0.9881 | 2.5005 Wh |

## 3. Preservation & Security Verification

- **Protected Content Violations:** 74 (Must be exactly 0)
- **Negative Token Reductions:** 0
- **Zero Token Reductions:** 359
- **Net Carbon Debt Cases:** 149 (14.9%)
- **Stage 2 Fallback Rate:** 100.0%
- **Stage 3 Fallback Rate:** 100.0%
- **Total Net Energy Saved:** 28.0825 Wh across 1000 prompts

## 4. Notable Edge & Failure Cases

Total flagged edge cases in `balanced` mode: **149**

| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |
|---|---|---|---|---|---|---|
| `ige-0002` | Code generation and debugging | easy | 0 (0.0%) | 0.9843 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0005` | Code generation and debugging | easy | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0016` | Code generation and debugging | easy | 0 (0.0%) | 0.9481 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9481) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0019` | Code generation and debugging | easy | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0026` | Code generation and debugging | medium | 0 (0.0%) | 0.9781 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0029` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0036` | Code generation and debugging | medium | 0 (0.0%) | 0.9716 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0049` | Code generation and debugging | medium | 0 (0.0%) | 0.9505 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9505) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0058` | Code generation and debugging | medium | 0 (0.0%) | 0.9629 | ROLLED_BACK | Ungrounded candidate section: candidate section relevance (0.6986) below chunk threshold (0.75).; Missing conditional/exception indicator 'if'.; Ungrounded candidate section: candidate section relevance (0.6986) below chunk threshold (0.75).; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0061` | Code generation and debugging | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0073` | Code generation and debugging | hard | 0 (0.0%) | 0.9652 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0075` | Code generation and debugging | hard | 3 (1.42%) | 0.9952 | ACCEPTED | Net Carbon Debt |
| `ige-0076` | Code generation and debugging | hard | 1 (0.46%) | 0.9993 | ACCEPTED | Net Carbon Debt |
| `ige-0077` | Code generation and debugging | hard | 2 (0.94%) | 0.999 | ACCEPTED | Net Carbon Debt |
| `ige-0078` | Code generation and debugging | hard | 0 (0.0%) | 0.9717 | ROLLED_BACK | Ungrounded candidate section: candidate section relevance (0.7165) below chunk threshold (0.75).; Missing conditional/exception indicator 'if'.; Ungrounded candidate section: candidate section relevance (0.7165) below chunk threshold (0.75).; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |

*(And 134 additional cases detailed in `failure_cases.json`)*

---
*Report generated automatically by PromptGreen V2 Benchmark Suite.*