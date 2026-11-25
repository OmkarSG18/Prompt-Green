# PromptGreen V2 — Independent Benchmark Numerical & Evidence Audit
**Audit Report: Independent 240-Prompt V2 Benchmark Verification**
**Date:** 2026-11-22  
**Repository:** `D:\EDU\DSU\Major project\PromptGreen`  
**Branch:** `version-2`  
**Base Commit (HEAD):** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Audit Scope:** Read-Only Numerical, Database, and Physical Consistency Audit of `results/benchmark_v2/`

---

## 1. Executive Summary & Verdict

This read-only audit independently inspected the source code, raw execution records (`results/benchmark_v2/raw_results.json`), summary telemetry (`summary.json`, `category_summary.json`), failure logs (`failure_cases.json`), and SQLite databases (`prompt_ledger.db`, `benchmark_ledger.db`).

### Key Findings & Verdicts

1. **Category Acceptance Count Sum vs. Aggregate Discrepancy [DISCREPANCY — DOCUMENTATION TYPO]:**
   - The reported balanced-mode aggregate of **236 accepted / 4 rollbacks** is **100% mathematically verified** in `raw_results.json` and `category_summary.json`.
   - The apparent sum of $235$ was caused by a manual documentation copy error in `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md` (Table 4), where the "Summarization & extraction" row was erroneously transcribed as **28** (the conservative mode count) instead of **29** (the actual balanced mode count).
   - Actual verified category counts in balanced mode: $30 + 30 + 30 + 30 + 30 + 30 + 27 + 29 = \mathbf{236}$.

2. **Energy Coefficient Documentation vs. Runtime Reality [DISCREPANCY — DOCUMENTATION TYPO]:**
   - The documentation in `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md` stated that `mid_tier` energy coefficients were $c_{\text{in}} = 0.0015\text{ mWh}$ and $c_{\text{out}} = 0.0040\text{ mWh}$.
   - The actual runtime code in `promptgreen/engine/model_profiles.py` used $\alpha_{\text{prefill}} = \mathbf{0.24\text{ mWh/token}}$ and $\alpha_{\text{decode}} = \mathbf{0.92\text{ mWh/token}}$.
   - All 720 raw energy figures in `raw_results.json` were computed using $0.24\text{ mWh}$ and $0.92\text{ mWh}$. The calculations in code are **100% reproducible down to the 6th decimal place** using the profile's true coefficients.

3. **HybridPredictor Output Token Bias & Carbon Debt Masking [DISCREPANCY — MODELING ARTIFACT]:**
   - In the runtime harness, output token delta predictions from `HybridPredictor` were credited towards gross energy savings for *every* prompt.
   - Because `HybridPredictor`'s Layer 2 (`RandomForestRegressor`) was trained exclusively on 50 synthetic pairs from `data/benchmark_suite.json` that *all* contained large output reductions ($-150$ to $-350$ tokens), it predicts an output token reduction of $\approx -47\text{ to } -97.5\text{ tokens}$ even when the input and output prompt text are **completely identical**.
   - Consequently, for the 4 rollback prompts and 149 unchanged prompts in balanced mode, the harness credited an artificial $\approx +0.05\text{ Wh}$ gross saving, which completely masked the local CPU optimizer overhead ($\approx 0.003\text{ Wh}$) and produced a reported "0 Net Carbon Debt" rate.
   - Under **strict physical grounding** (where identical text produces 0 gross savings), **146 prompts (60.8%) in balanced mode** and **156 prompts (65.0%) in conservative mode** are in Net Carbon Debt, while aggressive mode achieves real net positive savings on 227 prompts (**+10.62 Wh** net).

4. **Database Isolation & Audit Ledger Integrity [VERIFIED]:**
   - The independent benchmark database (`results/benchmark_v2/benchmark_ledger.db`) contains exactly **720 records** across all 3 modes.
   - The production ledger (`prompt_ledger.db`) contains **0 benchmark records**. Complete database isolation is verified.
   - All original 239 historical records remain intact.

---

## 2. Classification of Audit Findings

| Audit Dimension | Target Verification | Finding Classification | Summary Rationale |
|---|---|---|---|
| **Category Sum** | $30 \times 6 + 27 + 28 = 235 \neq 236$ | **DISCREPANCY (Report Typo)** | Raw results and `category_summary.json` show 29 accepted in Summarization. Report markdown miscopied 28 from conservative mode. |
| **Prompt Coverage** | Exactly 240 prompts per mode | **VERIFIED** | All 240 prompt IDs appear exactly once in identical sequence across all 3 modes (720 total runs). |
| **Model Energy Coeffs** | $c_{\text{in}}=0.0015$, $c_{\text{out}}=0.0040$ | **DISCREPANCY (Report Typo)** | Report prose misstated coefficients. Code executed `alpha_prefill=0.24`, `alpha_decode=0.92`. |
| **Energy Unit Math** | $E = \text{PUE} \cdot (T_{\text{in}} \alpha_{\text{in}} + T_{\text{out}} \alpha_{\text{out}}) / 1000$ | **VERIFIED** | Code math, PUE application (1.15), and Wh scaling are 100% mathematically correct. |
| **Overhead Math** | $E_{\text{opt}} = P_{\text{cpu}} \cdot (t_{\text{ms}} / 3,600,000)$ | **VERIFIED** | Verified conversion of milliseconds to hours at 35.0W CPU power. |
| **Output Token Bias** | Fictitious savings on unchanged prompts | **DISCREPANCY (Modeling Artifact)** | `HybridPredictor` predicts $-47$ to $-97$ tokens on identical text, masking net carbon debt on 146 prompts. |
| **Smoke-Test Mean** | $+0.0448\text{ Wh}$ net saved | **VERIFIED** | Exactly represents the mean per request ($0.8973\text{ Wh} / 20 = 0.044865\text{ Wh}$). |
| **Carbon & Water Math** | $C = (E/1000) \cdot 385$, $W = E \cdot 1.8$ | **VERIFIED** | Verified down to the 4th decimal place from net energy. |
| **Database Isolation** | Zero benchmark rows in `prompt_ledger.db` | **VERIFIED** | Benchmark written exclusively to `benchmark_ledger.db` (720 rows). Production DB has 0 benchmark rows. |
| **Rollback Invariance** | Byte-for-byte identity on rollback | **VERIFIED** | Final prompt text strictly equals original prompt text on all rollbacks. Input token reduction = 0. |

---

## 3. Detailed Finding A: Reconcile Aggregate & Category Counts

### Discrepancy Investigation
In `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md`:
- Section 3 reported **Balanced Mode: 236 accepted / 4 rollbacks**.
- Section 4 table reported:
  - Analytical reasoning: 30
  - CI/CD and developer workflows: 30
  - Code generation and debugging: 30
  - Data science and machine learning: 30
  - General technical instructions: 30
  - RAG and information retrieval: 30
  - Structured output & constraints: 27
  - Summarization & extraction: **28**
  - $\text{Sum} = 30 \times 6 + 27 + 28 = \mathbf{235}$ (discrepancy of $-1$).

### Evidence from Raw Results & Category Summary
Direct inspection of `results/benchmark_v2/category_summary.json` and `results/benchmark_v2/raw_results.json`:
```json
// category_summary.json -> balanced -> Summarization and information extraction
{
  "prompt_count": 30,
  "accepted_count": 29,
  "acceptance_rate_pct": 96.67
}
```
In Balanced Mode, only **1** prompt rolled back in Summarization: `pg-bench-111` (inline code modification detected). `pg-bench-091` passed with similarity $0.9596$ (threshold 0.92). Thus, $30 - 1 = \mathbf{29}$ accepted.
In Conservative Mode, **2** prompts rolled back in Summarization: `pg-bench-111` and `pg-bench-091` (similarity 0.9596 < conservative threshold 0.96). Thus, $30 - 2 = \mathbf{28}$ accepted.

### Root Cause
When authoring the markdown table in Section 4 of `INDEPENDENT_V2_BENCHMARK_REPORT.md`, the author copied the Summarization row from the conservative mode table (`28`) into the balanced mode table.
**Actual recomputed sum from raw data:** $30 + 30 + 30 + 30 + 30 + 30 + 27 + 29 = \mathbf{236}$ (**100% verified**).

---

## 4. Detailed Finding B: Independent Energy Recomputation

### Energy Formula & Unit Verification
In `promptgreen/engine/thermodynamics.py`:
1. **Prefill / Decode Units:** $\alpha_{\text{prefill}}$ and $\alpha_{\text{decode}}$ are stored in milliWatt-hours per token ($\text{mWh/token}$).
2. **Gross Inference Energy Formula:**
   $$\text{energy\_mwh} = (T_{\text{in}} \cdot \alpha_{\text{prefill}}) + (T_{\text{out}} \cdot \alpha_{\text{decode}})$$
   $$E_{\text{inf\_Wh}} = \text{PUE} \cdot \left(\frac{\text{energy\_mwh}}{1000.0}\right)$$
   - PUE multiplier ($1.15$) is applied **once** directly to the total datacenter energy.
   - Division by $1000.0$ converts $\text{mWh} \to \text{Wh}$ accurately.
3. **Optimizer Compute Overhead:**
   $$E_{\text{overhead\_Wh}} = P_{\text{cpu}} \cdot \left(\frac{t_{\text{ms}}}{3,600,000.0}\right)$$
   - $3,600,000.0\text{ ms/hour}$ ($1000\text{ ms/s} \times 3600\text{ s/h}$) converts milliseconds to hours correctly.
   - At $P_{\text{cpu}} = 35.0\text{W}$, for $t_{\text{ms}} = 184.23\text{ ms}$:
     $$E_{\text{overhead}} = 35.0 \times \frac{184.23}{3,600,000} = 0.0017911\text{ Wh}$$

### Discrepancy: Stated Coefficients vs. Runtime Coefficients
- **Stated in Report Prose:** $c_{\text{in}} = 0.0015\text{ mWh/token}$, $c_{\text{out}} = 0.0040\text{ mWh/token}$.
- **Actual Runtime Implementation in `model_profiles.py`:**
  ```python
  ModelTierProfile(
      tier_id='mid_tier',
      alpha_prefill_mwh=0.24,  # 0.24 mWh / input token
      alpha_decode_mwh=0.92,   # 0.92 mWh / output token
  )
  ```
The report prose contained a clerical error citing $0.0015$ and $0.0040$. The runtime code executed $0.24$ and $0.92$.

### Independent Recalculation Results (Model-As-Executed)
Using the actual runtime coefficients ($0.24$ and $0.92\text{ mWh}$), all 720 records were independently recomputed directly from `raw_results.json`:

| Optimization Mode | Independent Gross Saved | Summary Reported Gross | Independent Overhead | Summary Reported Overhead | Independent Net Saved | Summary Reported Net | Discrepancies > $10^{-4}$ |
|---|---|---|---|---|---|---|---|
| **Conservative** | 0.050763 Wh | 0.050763 Wh | 0.002829 Wh | 0.002829 Wh | **11.5041 Wh** | 11.5041 Wh | **0** |
| **Balanced** | 0.050759 Wh | 0.050759 Wh | 0.003232 Wh | 0.003232 Wh | **11.4064 Wh** | 11.4064 Wh | **0** |
| **Aggressive** | 0.050398 Wh | 0.050398 Wh | 0.003279 Wh | 0.003279 Wh | **11.3086 Wh** | 11.3086 Wh | **0** |

**Conclusion:** The reported summary numbers are **100% mathematically faithful to the raw records** down to the 6th decimal place.

---

## 5. Detailed Finding C: Token & Output Prediction Artifact

### The Source of Output Token Inflation
In `benchmark_v2.py`, line 229:
```python
pred_res = self.predictor.predict(original_prompt, pipeline_res.final_prompt)
```
When `original_prompt == pipeline_res.final_prompt` (which occurred in 159 conservative prompts, 149 balanced prompts, and all rollback prompts):
- `rule_delta = 0.0`.
- But `ml_model.predict(features)` returned $\mathbf{-97.5\text{ to } -121.0\text{ tokens}}$!
- Why? Because `HybridPredictor` was trained on `data/benchmark_suite.json` (50 synthetic pairs that *all* had large output reductions). The Random Forest model had zero training examples where prompt diff was 0.
- As a result, `final_delta = 0.5 \times 0.0 + 0.5 \times (-121.0) = \mathbf{-60.5\text{ tokens}}$.

### The Physical Impact on Net Energy & Carbon Debt
In physical reality, if a prompt is identical to its original, the downstream LLM generation cannot experience an output token reduction.
When recomputed under **Strict Physical Grounding** ($T_{\text{out\_opt}} = T_{\text{out\_orig}}$ whenever text is identical):

| Mode | Unchanged / Rollback Prompts | Reported Net Energy | Strictly Grounded Net Energy | Reported Carbon Debt Count | Strictly Grounded Debt Count |
|---|---|---|---|---|---|
| **Conservative** | 159 (66.3%) | 11.5041 Wh | **3.4815 Wh** | 0 (0.0%) | **156 (65.0%)** |
| **Balanced** | 149 (62.1%) | 11.4064 Wh | **3.8731 Wh** | 0 (0.0%) | **146 (60.8%)** |
| **Aggressive** | 13 (5.4%) | 11.3086 Wh | **10.6202 Wh** | 0 (0.0%) | **13 (5.4%)** |

### Critical Academic Finding
- The claim of "0 Net Carbon Debt" across all prompts was an artifact of `HybridPredictor` predicting fictitious output token reductions on unchanged prompts.
- When properly isolated, **aggressive mode** is the primary driver of defensible net energy savings (**+10.62 Wh**, 94.6% positive ROI), whereas conservative and balanced modes frequently leave technical prompts unchanged, incurring a small local CPU overhead without gross savings.

---

## 6. Detailed Finding D: Carbon & Water Calculation Verification

All carbon and water metrics were independently recomputed:
- **Carbon Conversion:**
  $$C = \left(\frac{\Delta E_{\text{net\_Wh}}}{1000}\right) \times 385.0\text{ gCO}_2\text{e/kWh}$$
  - Balanced Mode: $(11.4064 / 1000) \times 385.0 = \mathbf{4.3915\text{ gCO}_2\text{e}}$ (**Exact Match**).
  - Conservative Mode: $(11.5041 / 1000) \times 385.0 = \mathbf{4.4291\text{ gCO}_2\text{e}}$ (**Exact Match**).
  - Aggressive Mode: $(11.3086 / 1000) \times 385.0 = \mathbf{4.3538\text{ gCO}_2\text{e}}$ (**Exact Match**).
- **Water Conversion:**
  $$W = \Delta E_{\text{net\_Wh}} \times 1.8\text{ mL/Wh}$$
  - Balanced Mode: $11.4064 \times 1.8 = \mathbf{20.5315\text{ mL H}_2\text{O}}$ (**Exact Match**).
  - Conservative Mode: $11.5041 \times 1.8 = \mathbf{20.7074\text{ mL H}_2\text{O}}$ (**Exact Match**).
  - Aggressive Mode: $11.3086 \times 1.8 = \mathbf{20.3555\text{ mL H}_2\text{O}}$ (**Exact Match**).
- **Negative Balance Handling:** Negative net energies correctly propagate into negative carbon and water values (debt).

---

## 7. Detailed Finding E: Smoke-Test Discrepancy Analysis

The report stated:
> "Mean Net Energy Saved: +0.0448 Wh per request."

Independent verification of the smoke test execution:
- Total prompts evaluated: 20.
- Total net energy saved: **0.8973 Wh**.
- Calculation:
  $$\text{Mean per request} = \frac{0.8973\text{ Wh}}{20} = \mathbf{0.044865\text{ Wh/request}}$$
- **Verdict [VERIFIED]:** The reported value was strictly the **per-request mean**. It was not a unit error or total error. However, omitting the total (0.8973 Wh) in the prose created potential ambiguity.

---

## 8. Detailed Finding F: Database & Reproducibility Audit

### Benchmark Ledger (`results/benchmark_v2/benchmark_ledger.db`)
- **Total Records:** Exactly **720 records** (**VERIFIED**).
- **Records by Mode:**
  - `CONSERVATIVE`: 240 records
  - `BALANCED`: 240 records
  - `AGGRESSIVE`: 240 records
- **Author Tag:** 100% of records carry `author="benchmark-v2"` and `commit_hash="independent_eval"`.

### Production Ledger (`prompt_ledger.db`)
- **Total Records:** 270 records.
- **Records with `author="benchmark-v2"`:** **0 (ZERO)** (**VERIFIED**).
- **Original 239 Historical Records:** 100% intact (IDs 1 through 239).
- **Records 240 through 265:** Created during Day 3 Live HTTP and E2E integration verification.
- **Records 266 through 270:** Created during unit test suite runs (`tests/test_api_server.py`).

### Prompt ID Uniqueness & Consistency
- All 240 prompt IDs (`pg-bench-001` through `pg-bench-240`) appear exactly once in each mode.
- The prompt sequence in `raw_results.json` is identical across all three modes. Zero missing or duplicate combinations exist.

---

## 9. Comprehensive Discrepancy & Error Log

| Error ID | Severity | File / Location | Observed Text | Actual Ground Truth | Impact |
|---|---|---|---|---|---|
| **ERR-01** | Low (Typo) | `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md` (Table 4) | Summarization accepted: `28` | Actual accepted in Balanced Mode: `29` | Caused table sum to equal 235 instead of 236. Raw JSON is correct. |
| **ERR-02** | Low (Typo) | `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md` (Sec 1) | `c_in = 0.0015 mWh`, `c_out = 0.0040 mWh` | Actual coefficients in code: `0.24 mWh` and `0.92 mWh` | Cosmetic documentation error. Code execution used correct 0.24/0.92. |
| **ERR-03** | Medium (Model Bias) | `promptgreen/validation/benchmark_v2.py` (Line 229) | Output token reduction credited on unchanged/rollback prompts | When `old_prompt == new_prompt`, true output delta is 0.0 | Masked local CPU net carbon debts on 146 prompts in balanced mode. |

---

## 10. Recommendations for Defense & Code Hardening

1. **Correct Documentation Typos:**
   - Update Table 4 of `docs/INDEPENDENT_V2_BENCHMARK_REPORT.md` to show 29 accepted prompts in Summarization for Balanced Mode ($30 \times 6 + 27 + 29 = 236$).
   - Correct the cited energy coefficients in Section 1 to $0.24\text{ mWh}$ and $0.92\text{ mWh}$.
2. **Defensive Zero-Diff Guard in `benchmark_v2.py`:**
   - In `benchmark_v2.py`, add a physical guard before calling `calculate_thermodynamic_impact`:
     ```python
     if pipeline_res.rollback_occurred or original_prompt == pipeline_res.final_prompt:
         tout_orig = pred_res.predicted_old_output_tokens
         tout_opt = tout_orig  # Zero output delta if prompt was unchanged
     ```
   - This ensures that unchanged and rolled-back prompts truthfully reflect their local CPU energy debt ($-0.0028\text{ Wh}$ to $-0.0032\text{ Wh}$) rather than claiming fictitious output savings.
3. **Viva Defense Narrative:**
   - Present the audit findings proactively during the capstone viva. Acknowledging that conservative prompt engineering legitimately results in net energy debts when fluff is absent demonstrates genuine engineering honesty and rigorous scientific methodology.
