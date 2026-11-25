# PromptGreen V2 — Corrected Independent 240-Prompt Evaluation Report
**Evaluation Methodology:** Post-Audit Re-Analysis with Explicit Dual-Scenario Energy Accounting  
**Source Dataset:** `data/benchmark_240_independent.json` (240 unique prompts, 8 categories, 3 difficulty tiers)  
**Original Raw Results:** `results/benchmark_v2/raw_results.json` (720 total executions)  
**Target Model Tier:** `mid_tier` (alpha_prefill = 0.24 mWh, alpha_decode = 0.92 mWh, PUE = 1.15)  
**Grid Scenario:** `ILLUSTRATIVE_385` (385.0 gCO2e/kWh)  

> [!IMPORTANT]
> **Epistemic Isolation & Grounding:**
> This report resolves findings documented in `docs/BENCHMARK_V2_NUMERICAL_AUDIT.md`. It separates verified input token reductions
> from modeled downstream generation, and applies a strict zero-diff guard to identical and rolled-back prompts.

---
## 1. Executive Summary: Dual-Scenario Accounting Across Modes

### Scenario A: Verified Input-Only Accounting (Primary Baseline)
*Based strictly on physical input token reductions measured via exact tokenizer; zero downstream output delta assumed.*

| Mode | Evaluated | Accepted | Acceptance % | Rollbacks | Zero-Red. | Single Net Wh (N=1) | Amortized Net Wh (N=10k) | Amortized Carbon (gCO2e) | Water Saved (L) |
|---|---|---|---|---|---|---|---|---|---|
| **CONSERVATIVE** | 240 | 235 | 97.92% | 5 | 159 | -0.6329 Wh | +460.24 Wh | +177.2 g | +0.83 L |
| **BALANCED** | 240 | 236 | 98.33% | 4 | 149 | -0.7258 Wh | +498.78 Wh | +192.0 g | +0.90 L |
| **AGGRESSIVE** | 240 | 236 | 98.33% | 4 | 13 | -0.5642 Wh | +2226.53 Wh | +857.2 g | +4.01 L |

### Scenario B: Exploratory HybridPredictor Modeled Estimate (Secondary)
*Combines measured input savings with HybridPredictor downstream output estimates; zero-diff fix enforced on unchanged/rolled-back prompts.*

| Mode | Evaluated | Accepted | Acceptance % | Rollbacks | Zero-Diff Fixed | Net Saved (Wh) | Mean Net Wh | Net Debt Cases | Net Debt % | Carbon Abated (gCO2e) |
|---|---|---|---|---|---|---|---|---|---|---|
| **CONSERVATIVE** | 240 | 235 | 97.92% | 5 | 156 | +3.4815 Wh | +0.014506 Wh | 156 | 65.0% | +1.3404 g |
| **BALANCED** | 240 | 236 | 98.33% | 4 | 146 | +3.8731 Wh | +0.016138 Wh | 146 | 60.83% | +1.4911 g |
| **AGGRESSIVE** | 240 | 236 | 98.33% | 4 | 13 | +10.6202 Wh | +0.044251 Wh | 13 | 5.42% | +4.0888 g |

---
## 2. Category Breakdown (Balanced Mode — Corrected Reconciliation)

| Category | Prompts | Accepted | Rollbacks | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Scenario B Net Wh | Scenario B Debt Count |
|---|---|---|---|---|---|---|---|---|---|
| Code generation and debugging | 30 | 30 | 0 | 100.0% | 2 tok | 3.34% | 423.51 ms | +0.9766 Wh | 7/30 |
| RAG and information retrieval | 30 | 30 | 0 | 100.0% | 1.33 tok | 2.43% | 336.76 ms | +0.9120 Wh | 10/30 |
| Analytical reasoning | 30 | 30 | 0 | 100.0% | 0.4 tok | 0.77% | 301.52 ms | +0.2977 Wh | 22/30 |
| Summarization and information extraction | 30 | 29 | 1 | 96.67% | 0.73 tok | 1.64% | 290.6 ms | +0.5730 Wh | 18/30 |
| CI/CD and developer workflows | 30 | 30 | 0 | 100.0% | 0.3 tok | 0.52% | 302.21 ms | +0.1952 Wh | 24/30 |
| Data science and machine learning | 30 | 30 | 0 | 100.0% | 0.43 tok | 0.77% | 327.25 ms | +0.3314 Wh | 21/30 |
| Structured output and formatting constraints | 30 | 27 | 3 | 90.0% | 0.53 tok | 0.82% | 317.16 ms | +0.3611 Wh | 21/30 |
| General technical instructions | 30 | 30 | 0 | 100.0% | 0.3 tok | 0.53% | 360.77 ms | +0.2259 Wh | 23/30 |
| **TOTAL** | **240** | **236** | **4** | **98.33%** | — | — | — | **+3.8731 Wh** | **146/240** |

> [!NOTE]
> **Table Reconciled:** The sum of accepted category prompts in Balanced Mode is exactly **236** (30x6 + 27 + 29 = 236).
> Summarization and information extraction achieves 29 accepted prompts (1 rollback), correcting the earlier typographical error of 28.

---
## 3. Physical & Epistemic Audit Insights

1. **Elimination of Artificial Predictor Savings on Unchanged Prompts:**
   - In the initial benchmark execution, the unconstrained ML layer predicted -60.5 to -97.5 output tokens on unchanged prompts.
   - This masked local CPU overhead and generated a false reporting of 0 carbon debt cases across all modes.
   - With the zero-diff guard enforced, unchanged prompts have an output delta of strictly 0.0.

2. **Honest Accounting of Local CPU Overhead:**
   - In Conservative Mode, 156 prompts achieve zero token savings (due to safety preservation of technical terms).
   - For a single run (N=1), local CPU overhead (~0.0028 Wh) exceeds single-prompt input token savings (~0.0002 Wh).
   - When amortized over production volume (N=10,000 inferences), positive net savings reach **+460.2 Wh** in Conservative Mode and **+1,250.7 Wh** in Aggressive Mode.
   - In Aggressive Mode, deeper token pruning reduces tokens on 227 prompts, dropping single-run carbon debt cases to only 13 (5.4%) under modeled output.

3. **Representative Model Assumptions:**
   - Thermodynamic coefficients at runtime are 0.24 mWh prefill and 0.92 mWh decode for mid_tier (A100-SXM4-40GB equivalent).
   - These reflect published datacenter LLM serving benchmarks and PUE=1.15 datacenter overhead.

---
*Report generated automatically by PromptGreen V2 Re-Analysis Suite.*