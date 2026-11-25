# PromptGreen V2 — Independent 240-Prompt Evaluation Report
**Evaluation Date:** 2026-11-23T17:28:00.722178Z  
**Dataset:** `data/benchmark_ige_1000_unseen.json` (1000 unique prompts)  
**Model Tier Evaluated:** `mid_tier`  
**Grid Scenario:** `ILLUSTRATIVE_385`  
**Isolated Persistence:** `results/ige_1000/aggressive\benchmark_ledger.db`  

> [!IMPORTANT]
> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment
> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.
> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.

---
## 1. Executive Summary Across Modes

| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |
|---|---|---|---|---|---|---|---|---|---|
| **AGGRESSIVE** | 1000 | 924 | 92.4% | 76 | 3.46 tok | 6.04% | 1305.12 ms | 0.9834 | 31.9089 Wh |

## 2. Category Breakdown (AGGRESSIVE Mode)

| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |
|---|---|---|---|---|---|---|---|---|
| Analytical reasoning | 84 | 79 | 94.05% | 4.46 tok | 7.4% | 1228.81 ms | 0.9822 | 2.7795 Wh |
| CI/CD and developer workflows | 83 | 76 | 91.57% | 3.41 tok | 6.16% | 1324.56 ms | 0.9863 | 2.5759 Wh |
| Code generation and debugging | 84 | 76 | 90.48% | 3.15 tok | 6.12% | 1358.63 ms | 0.983 | 2.7007 Wh |
| Conversational and multilingual assistance | 83 | 78 | 93.98% | 3.76 tok | 6.48% | 1281.7 ms | 0.9824 | 2.697 Wh |
| Creative writing and content generation | 83 | 77 | 92.77% | 5.52 tok | 8.98% | 1190.36 ms | 0.9802 | 2.8973 Wh |
| Data science and machine learning | 83 | 76 | 91.57% | 2.95 tok | 5.13% | 1295.25 ms | 0.9858 | 2.491 Wh |
| General technical instructions | 83 | 74 | 89.16% | 2.55 tok | 4.4% | 1340.11 ms | 0.9859 | 2.28 Wh |
| RAG and information retrieval | 84 | 79 | 94.05% | 2.82 tok | 5.25% | 1353.36 ms | 0.9845 | 2.7134 Wh |
| Safety-sensitive and professional applications | 83 | 76 | 91.57% | 2.77 tok | 4.8% | 1370.75 ms | 0.9861 | 2.3211 Wh |
| Structured output and formatting constraints | 83 | 76 | 91.57% | 3.49 tok | 6.21% | 1396.67 ms | 0.9785 | 2.8529 Wh |
| Summarization and information extraction | 84 | 79 | 94.05% | 2.93 tok | 4.97% | 1367.57 ms | 0.9825 | 2.843 Wh |
| Tool-use and agentic workflows | 83 | 78 | 93.98% | 3.64 tok | 6.64% | 1152.62 ms | 0.9839 | 2.7572 Wh |

## 3. Preservation & Security Verification

- **Protected Content Violations:** 74 (Must be exactly 0)
- **Negative Token Reductions:** 0
- **Zero Token Reductions:** 99
- **Net Carbon Debt Cases:** 85 (8.5%)
- **Stage 2 Fallback Rate:** 100.0%
- **Stage 3 Fallback Rate:** 100.0%
- **Total Net Energy Saved:** 31.9089 Wh across 1000 prompts

## 4. Notable Edge & Failure Cases

Total flagged edge cases in `aggressive` mode: **85**

| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |
|---|---|---|---|---|---|---|
| `ige-0002` | Code generation and debugging | easy | 0 (0.0%) | 0.9843 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0016` | Code generation and debugging | easy | 0 (0.0%) | 0.9481 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9481) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0026` | Code generation and debugging | medium | 0 (0.0%) | 0.9781 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0036` | Code generation and debugging | medium | 0 (0.0%) | 0.9716 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0049` | Code generation and debugging | medium | 0 (0.0%) | 0.9505 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9505) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0058` | Code generation and debugging | medium | 0 (0.0%) | 0.9629 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0073` | Code generation and debugging | hard | 0 (0.0%) | 0.9652 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0078` | Code generation and debugging | hard | 0 (0.0%) | 0.9717 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0097` | RAG and information retrieval | easy | 0 (0.0%) | 0.9839 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0118` | RAG and information retrieval | medium | 0 (0.0%) | 0.9425 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9425) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0121` | RAG and information retrieval | medium | 0 (0.0%) | 1.0 | ACCEPTED | Net Carbon Debt |
| `ige-0131` | RAG and information retrieval | medium | 0 (0.0%) | 0.972 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0155` | RAG and information retrieval | hard | 0 (0.0%) | 0.9833 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0160` | RAG and information retrieval | hard | 0 (0.0%) | 0.996 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |
| `ige-0179` | Analytical reasoning | easy | 0 (0.0%) | 0.9422 | ROLLED_BACK | Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Missing conditional/exception indicator 'if'.; Cosine similarity (0.9422) below active threshold (0.96).; Semantic fidelity guard rejected candidate; safely rolled back to original prompt. |

*(And 70 additional cases detailed in `failure_cases.json`)*

---
*Report generated automatically by PromptGreen V2 Benchmark Suite.*