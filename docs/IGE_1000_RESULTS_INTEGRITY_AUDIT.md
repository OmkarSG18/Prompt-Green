# PromptGreen V2 — IGE-1000 Independent Generalization Benchmark Results Integrity Audit

**Audit Date:** 2026-11-23T23:30:00Z  
**Auditor:** Independent Automated Quality Assurance & Verification Harness  
**Target Document Audited:** `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md`  
**Primary Databases Audited:**
- `results/ige_1000/conservative/benchmark_ledger.db` (1,000 records)
- `results/ige_1000/balanced/benchmark_ledger.db` (1,000 records)
- `results/ige_1000/aggressive/benchmark_ledger.db` (1,000 records)
- `results/benchmark_1200/benchmark_ledger.db` (Historical reference: 3,600 records)  
**Dataset Reference:** `data/benchmark_ige_1000_unseen.json` (SHA-256: `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3`)  
**Git Branch:** `version-2` | **Commit HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Epistemic Scope:** Strictly read-only numerical, statistical, forensic, and thermodynamic verification. Zero code or database modifications.

---

## 1. Executive Verdict

### Formal Verdict: VERDICT B (Empirical Execution Sound and Verified; Report Requires Corrections)

**Verdict Rationale:**
1. **Raw Empirical Soundness (Verified):** The execution of the 3,000 trials across Conservative, Balanced, and Aggressive modes in `results/ige_1000/` was executed cleanly with strict isolation. Exactly 1,000 unique prompt trials were evaluated per mode without database collision, pipeline crashes, data corruption, or negative token expansion defects.
2. **Personal Initial Defect Rectification (Verified):** All 72 intentional challenge probes containing personal initials (evaluated 3 times across modes = 216 total trials) preserved 100% of names and initials (`Dr. A. B. Smith`, `A. Einstein`, `J. K. Rowling`, `A. J. Brown`, `W. E. B. Du Bois`). Zero initials were dropped or corrupted.
3. **Discrepancy Requiring Report Revision (Material Finding):** `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md` contains significant reporting errors in its comparative analysis against historical benchmarks:
   - **Historical Acceptance Rate Misattribution:** The report claims historical 1,200 benchmark acceptance rates were **89.2%** (Conservative), **92.8%** (Balanced), and **92.5%** (Aggressive), asserting that IGE-1000 acceptance rates "mirror historical benchmarks within $\pm 0.6\%$". In fact, the audited historical 1,200 benchmark ledger (`results/benchmark_1200/benchmark_ledger.db`) recorded acceptance rates of **99.00%**, **99.33%**, and **99.42%**.
   - **Net Carbon Debt Cases Misreported:** The report summary table reports **70**, **55**, and **49** carbon debt cases across modes, whereas the actual raw database and export files record **180 (18.0%)**, **149 (14.9%)**, and **85 (8.5%)**. The report conflated accepted debt cases with total debt cases and historical figures.
   - **Historical 1,200 Reduction Metrics Misattributed:** In the comparative table, mean reductions for the 1,200 benchmark were reported as 1.25 tok (Conservative) and 1.48 tok (Balanced), whereas the actual measured reductions in `results/benchmark_1200/` were 0.18 tok and 0.25 tok.

Because the underlying raw execution data is fully intact and physically defensible, the evaluation does **not** need to be rerun (avoiding Verdict C). However, the report conclusions and comparison tables must be updated to reflect the true historical values before formal acceptance.

---

## 2. Raw Database and Ledger Verification

A forensic integrity inspection was conducted across all three IGE-1000 SQLite databases:
1. `results/ige_1000/conservative/benchmark_ledger.db`
2. `results/ige_1000/balanced/benchmark_ledger.db`
3. `results/ige_1000/aggressive/benchmark_ledger.db`

### Integrity Audit Results

| Audit Check | Verification Target | Audited Finding | Status |
|---|---|---|:---:|
| **Schema Uniformity** | 22 canonical columns matching V2 schema | All 3 databases instantiate identical 22-column tables | **PASS** |
| **Row Count (Conservative)** | Exactly 1,000 rows | 1,000 rows | **PASS** |
| **Row Count (Balanced)** | Exactly 1,000 rows | 1,000 rows | **PASS** |
| **Row Count (Aggressive)** | Exactly 1,000 rows | 1,000 rows | **PASS** |
| **Total Empirical Trials** | Exactly 3,000 rows | 3,000 rows across 3 databases | **PASS** |
| **Prompt ID Match** | Exact 1:1 match with `benchmark_ige_1000_unseen.json` | 1,000 unique prompt IDs (`ige-0001` through `ige-1000`) per mode | **PASS** |
| **Duplicate Check** | 0 duplicate prompt IDs per mode | Exactly 0 duplicate prompt IDs | **PASS** |
| **Status Vocabulary** | Strictly `ACCEPTED` or `ROLLED_BACK` | 100% compliant; no `FAILED`, `ERROR`, or `NULL` statuses | **PASS** |
| **Negative Token Check** | No accepted prompt with $T_{\text{opt}} > T_{\text{orig}}$ | Exactly 0 accepted prompts expanded tokens ($\Delta < 0$) | **PASS** |
| **Rollback Invariance** | Rolled back prompts must have $T_{\text{opt}} == T_{\text{orig}}$ | Exactly 0 token deltas on all 264 rollback trials | **PASS** |
| **Semantic Range** | $S \in [0.0, 1.0]$ | All scores bounded in $[0.8715, 1.0000]$ | **PASS** |
| **Latency Non-Negativity** | $t_{\text{lat}} > 0.0 \text{ ms}$ | Min latency: 108.16 ms, Max: 9,761.41 ms | **PASS** |

---

## 3. Independent Metric Recalculation

All metrics were independently recalculated directly from the raw records in the SQLite ledgers and cross-verified against `raw_results.json` and `summary.json`.

### Recalculation Summary Table

| Metric | Mode | Reported in IGE Report | Independently Recalculated | Discrepancy / Alignment |
|---|---|:---:|:---:|:---:|
| **Total Prompts** | Cons / Bal / Agg | 1,000 / 1,000 / 1,000 | 1,000 / 1,000 / 1,000 | **EXACT MATCH** |
| **Accepted Count** | Conservative | 890 (89.0%) | 890 (89.00%) | **EXACT MATCH** |
| | Balanced | 922 (92.2%) | 922 (92.20%) | **EXACT MATCH** |
| | Aggressive | 924 (92.4%) | 924 (92.40%) | **EXACT MATCH** |
| **Rollback Count** | Conservative | 110 (11.0%) | 110 (11.00%) | **EXACT MATCH** |
| | Balanced | 78 (7.8%) | 78 (7.80%) | **EXACT MATCH** |
| | Aggressive | 76 (7.6%) | 76 (7.60%) | **EXACT MATCH** |
| **Useful Opt (>0 tok)** | Conservative | 580 (58.0%) | 580 (58.00%) | **EXACT MATCH** |
| | Balanced | 641 (64.1%) | 641 (64.10%) | **EXACT MATCH** |
| | Aggressive | 901 (90.1%) | 901 (90.10%) | **EXACT MATCH** |
| **Unchanged (0 tok)** | Conservative | 420 (42.0%) | 420 (42.00%) | **EXACT MATCH** |
| | Balanced | 359 (35.9%) | 359 (35.90%) | **EXACT MATCH** |
| | Aggressive | 99 (9.9%) | 99 (9.90%) | **EXACT MATCH** |
| **Total Input Tokens** | Initial (All Modes) | 87,039 | 87,039 | **EXACT MATCH** |
| | Cons (After) | 85,838 | 85,838 | **EXACT MATCH** |
| | Bal (After) | 85,628 | 85,628 | **EXACT MATCH** |
| | Agg (After) | 83,584 | 83,584 | **EXACT MATCH** |
| **Total Tokens Saved** | Conservative | 1,201 (1.38%) | 1,201 (1.3798%) | **EXACT MATCH** |
| | Balanced | 1,411 (1.62%) | 1,411 (1.6211%) | **EXACT MATCH** |
| | Aggressive | 3,455 (3.97%) | 3,455 (3.9695%) | **EXACT MATCH** |
| **Mean Token Red.** | Conservative | 1.20 tok | 1.2010 tok | **EXACT MATCH** |
| | Balanced | 1.41 tok | 1.4110 tok | **EXACT MATCH** |
| | Aggressive | 3.46 tok | 3.4550 tok | **EXACT MATCH** |
| **Median Token Red.** | Conservative | 1.0 tok | 1.0 tok | **EXACT MATCH** |
| | Balanced | 2.0 tok | 2.0 tok | **EXACT MATCH** |
| | Aggressive | 3.0 tok | 3.0 tok | **EXACT MATCH** |
| **Mean Semantic Sim.** | Conservative | 0.9876 | 0.98757 | **EXACT MATCH** |
| | Balanced | 0.9874 | 0.98741 | **EXACT MATCH** |
| | Aggressive | 0.9834 | 0.98342 | **EXACT MATCH** |
| **Median Semantic** | Conservative | 0.9929 | 0.9904 (p50) / 0.9929* | Minor rounding/calc diff |
| | Balanced | 0.9904 | 0.9904 | **EXACT MATCH** |
| | Aggressive | 0.9880 | 0.9880 | **EXACT MATCH** |
| **Mean Latency** | Conservative | 1,123.51 ms | 1,123.51 ms | **EXACT MATCH** |
| | Balanced | 1,222.05 ms | 1,222.05 ms | **EXACT MATCH** |
| | Aggressive | 1,305.12 ms | 1,305.12 ms | **EXACT MATCH** |
| **Median Latency** | Conservative | 380.70 ms | 380.70 ms | **EXACT MATCH** |
| | Balanced | 409.78 ms | 409.78 ms | **EXACT MATCH** |
| | Aggressive | 424.16 ms | 424.16 ms | **EXACT MATCH** |
| **p95 Latency** | Conservative | 3,531.03 ms | 3,531.03 ms | **EXACT MATCH** |
| | Balanced | 3,641.88 ms | 3,641.88 ms | **EXACT MATCH** |
| | Aggressive | 3,685.34 ms | 3,685.34 ms | **EXACT MATCH** |
| **Net Energy Saved** | Conservative | 27.20 Wh | 27.1959 Wh | **EXACT MATCH** |
| | Balanced | 28.08 Wh | 28.0825 Wh | **EXACT MATCH** |
| | Aggressive | 31.91 Wh | 31.9089 Wh | **EXACT MATCH** |
| **Net Carbon Abated** | Conservative | 10.47 gCO2 | 10.4704 gCO2 | **EXACT MATCH** |
| | Balanced | 10.81 gCO2 | 10.8118 gCO2 | **EXACT MATCH** |
| | Aggressive | 12.28 gCO2 | 12.2849 gCO2 | **EXACT MATCH** |
| **Net Carbon Debt Cases** | Conservative | **70 (7.0%)** | **180 (18.00%)** | **MISREPORTED (Major)** |
| | Balanced | **55 (5.5%)** | **149 (14.90%)** | **MISREPORTED (Major)** |
| | Aggressive | **49 (4.9%)** | **85 (8.50%)** | **MISREPORTED (Major)** |

---

## 4. Forensic Investigation of Historical Benchmark Discrepancy

### 4.1 The Core Discrepancy
In `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md` (Lines 21–24 and Lines 218–220), the author asserts:
> *"Across all three modes, acceptance rates on the unseen 1,000-prompt holdout mirror the expanded 1,200-prompt benchmark within $\pm 0.6\%$:
> - Conservative Acceptance: 89.0% (IGE-1000) vs. 89.2% (Historical 1,200)
> - Balanced Acceptance: 92.2% (IGE-1000) vs. 92.8% (Historical 1,200)
> - Aggressive Acceptance: 92.4% (IGE-1000) vs. 92.5% (Historical 1,200)"*

An independent query of the actual historical benchmark ledger `results/benchmark_1200/benchmark_ledger.db` reveals this comparison is factually incorrect.

### 4.2 Comprehensive Three-Corpus Comparison Table

| Metric | Optimization Mode | Original 240 Benchmark | Historical 1,200 Benchmark (As Reported in IGE) | Historical 1,200 Benchmark (True Audited DB) | IGE-1000 Unseen Holdout (True Audited DB) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Corpus Prompts** | — | 240 | 1,200 | 1,200 | **1,000** |
| **Total Trials** | — | 720 | 3,600 | 3,600 | **3,000** |
| **Acceptance Rate** | Conservative | 95.83% (230) | **89.2%** *(Incorrect)* | **99.00%** (1,188) | **89.00%** (890) |
| | Balanced | 94.58% (227) | **92.8%** *(Incorrect)* | **99.33%** (1,192) | **92.20%** (922) |
| | Aggressive | 95.00% (228) | **92.5%** *(Incorrect)* | **99.42%** (1,193) | **92.40%** (924) |
| **Rollback Rate** | Conservative | 4.17% (10) | — | **1.00%** (12) | **11.00%** (110) |
| | Balanced | 5.42% (13) | — | **0.67%** (8) | **7.80%** (78) |
| | Aggressive | 5.00% (12) | — | **0.58%** (7) | **7.60%** (76) |
| **Useful Opt Rate** | Conservative | — | — | **10.50%** (126) | **58.00%** (580) |
| | Balanced | — | — | **16.00%** (192) | **64.10%** (641) |
| | Aggressive | — | — | **95.42%** (1,145) | **90.10%** (901) |
| **Unchanged Rate** | Conservative | — | — | **89.00%** (1,068) | **42.00%** (420) |
| | Balanced | — | — | **83.58%** (1,003) | **35.90%** (359) |
| | Aggressive | — | — | **4.58%** (55) | **9.90%** (99) |
| **Total Tokens Saved** | Conservative | 392 tok | — | **221 tok** | **1,201 tok** |
| | Balanced | 503 tok | — | **301 tok** | **1,411 tok** |
| | Aggressive | 1,304 tok | — | **4,311 tok** | **3,455 tok** |
| **Mean Reduction** | Conservative | 1.63 tok | **1.25 tok** *(Incorrect)* | **0.18 tok** | **1.20 tok** |
| | Balanced | 2.10 tok | **1.48 tok** *(Incorrect)* | **0.25 tok** | **1.41 tok** |
| | Aggressive | 5.43 tok | **3.86 tok** *(Incorrect)* | **3.59 tok** | **3.46 tok** |
| **Aggregate Red. %** | Conservative | 3.73% | **1.17%** *(Incorrect)* | **0.31%** | **1.38%** |
| | Balanced | 4.80% | **1.39%** *(Incorrect)* | **0.42%** | **1.62%** |
| | Aggressive | 12.43% | **3.61%** *(Incorrect)* | **5.74%** | **3.97%** |
| **Net Carbon Debt Rate**| Conservative | 3.75% | — | **84.67%** (1,016) | **18.00%** (180) |
| | Balanced | 4.17% | — | **79.33%** (952) | **14.90%** (149) |
| | Aggressive | 3.75% | — | **4.58%** (55) | **8.50%** (85) |
| **Negative Token Expansion**| Conservative | 0 | 6 (accepted) | **6 (accepted)** | **0 (100% eliminated)** |
| | Balanced | 0 | 5 (accepted) | **5 (accepted)** | **0 (100% eliminated)** |
| | Aggressive | 0 | 0 | **0** | **0** |

### 4.3 Why Did This Divergence Occur?

1. **The Nature of Prompt Transformation in IGE-1000 vs. 1,200 Benchmark:**
   - In the **Historical 1,200 Benchmark**, prompts were synthetic and concise. In Conservative mode, **89.00% of prompts were completely untouched** by Stage 1 and Stage 2. When a prompt is untouched, it passes Stage 4 with a similarity score of 1.0 and is marked `ACCEPTED`. Therefore, the 99.00% acceptance rate in the 1,200 benchmark was an artifact of passivity, not robust optimization.
   - In **IGE-1000**, prompts were deliberately crafted with conversational framing, natural fluff, multi-sentence constraints, and verbose preambles. Consequently, **58.00% of Conservative prompts and 64.10% of Balanced prompts were actively modified** (a 5.5x and 4.0x increase in active transformations).
2. **Safety Rollback Activation:**
   - Because the optimizer actively transformed the prompts, Stage 4 guardrails actively engaged to protect meaning.
   - In Conservative mode, 110 prompts (11.0%) triggered safety rollbacks (44 due to conditional preservation drops such as `if`, `unless`, `when`, and 66 due to cosine similarity below 0.96).
   - In Balanced mode, 78 prompts (7.8%) were rolled back; in Aggressive mode, 76 prompts (7.6%) were rolled back.
3. **Academic Significance:**
   - The increase in rollback rate from 1.0% to 11.0% is **not a generalization failure**; it is empirical proof that the PromptGreen safety guardrails actively protect prompts when pruners attempt aggressive transformations on unseen text.
   - However, claiming that IGE-1000 "mirrored" historical 1,200 acceptance within $\pm 0.6\%$ by inventing 89.2%, 92.8%, and 92.5% is a serious reporting defect that compromises the academic credibility of the report.

---

## 5. Thermodynamic and Energy Accounting Audit

### 5.1 Verification of Thermodynamic Engine
The thermodynamic calculation engine in `promptgreen/engine/thermodynamics.py` was audited:
- **Prefill/Decode Energy Formula:**
  $$\Delta E_{\text{inf}} = \text{PUE} \cdot \frac{\Delta T_{\text{in}} \cdot \alpha_{\text{prefill}} + \Delta T_{\text{out}} \cdot \alpha_{\text{decode}}}{1000} \quad (\text{Wh})$$
- **Optimizer Overhead Formula:**
  $$E_{\text{overhead}} = P_{\text{cpu}} \cdot \frac{t_{\text{latency}}}{3,600,000} \quad (\text{Wh})$$
- **Net Energy and Carbon Balances:**
  $$\Delta E_{\text{net}} = \Delta E_{\text{inf}} - E_{\text{overhead}} \quad (\text{Wh})$$
  $$\Delta C_{\text{net}} = \frac{\Delta E_{\text{net}}}{1000} \cdot I_{\text{grid}} \quad (\text{gCO}_2\text{e})$$

### 5.2 Environmental Parameters Checked
- **Model Tier:** `mid_tier` ($\alpha_{\text{prefill}} = 0.24 \text{ mWh/tok}$, $\alpha_{\text{decode}} = 0.92 \text{ mWh/tok}$)
- **Datacenter PUE:** $1.15$
- **Grid Scenario:** `ILLUSTRATIVE_385` ($385.0 \text{ gCO}_2\text{/kWh}$)
- **CPU Active Power Estimate:** $35.0 \text{ W}$

### 5.3 Forensic Reconciliation of Net Carbon Debt Cases
In `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md` (Table line 104), the report claims:
- Conservative: 70 cases (7.0%)
- Balanced: 55 cases (5.5%)
- Aggressive: 49 cases (4.9%)

The audited truth from `benchmark_ledger.db` and `summary.json`:
- Conservative: **180 cases (18.00%)**
- Balanced: **149 cases (14.90%)**
- Aggressive: **85 cases (8.50%)**

**Audit Discovery:**
- In Conservative mode: Total net carbon debts = 180. Of these, 110 were rolled back ($0 \text{ Wh saved} - E_{\text{overhead}} < 0$). Exactly **70** were accepted prompts operating in net carbon debt. The author of the report reported only the accepted subset (70) and omitted the 110 rollback debts.
- In Balanced mode: Total debts = 149 (78 rollbacks + 71 accepted debts). The report author wrote "55", which is an ungrounded hallucination or confusion with historical 1,200 Aggressive debt (55 cases).
- In Aggressive mode: Total debts = 85 (76 rollbacks + 9 accepted debts). The report author wrote "49".

The report must be corrected to state both **Total Net Carbon Debt** (180 / 149 / 85) and **Accepted Net Carbon Debt** (70 / 71 / 9) transparently.

---

## 6. Latency Distribution and Sensitivity Audit

### 6.1 Distribution Statistics Across Modes

| Latency Metric | Conservative | Balanced | Aggressive |
|---|:---:|:---:|:---:|
| **Minimum** | 108.16 ms | 153.12 ms | 153.19 ms |
| **25th Percentile (p25)** | 265.24 ms | 313.82 ms | 328.14 ms |
| **Median (p50)** | **380.70 ms** | **409.78 ms** | **424.16 ms** |
| **Mean** | **1,123.51 ms** | **1,222.05 ms** | **1,305.12 ms** |
| **75th Percentile (p75)** | 1,439.20 ms | 2,011.55 ms | 2,788.24 ms |
| **95th Percentile (p95)** | **3,531.03 ms** | **3,641.88 ms** | **3,685.34 ms** |
| **99th Percentile (p99)** | 3,718.00 ms | 5,679.05 ms | 8,459.75 ms |
| **Maximum** | 4,291.58 ms | 6,524.82 ms | 9,761.41 ms |

### 6.2 Latency Sensitivity by Length Profile

The latency distribution exhibits pronounced positive skew ($Mean \approx 3 \times Median$). Segmenting by length profile isolates the cause:

| Length Profile | Token Range | Mode | Count | Mean Latency | Median Latency | p95 Latency |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Short** | $< 50$ tokens | Conservative | 250 | 211.74 ms | 205.92 ms | 294.40 ms |
| | | Balanced | 250 | 220.10 ms | 204.04 ms | 306.00 ms |
| | | Aggressive | 250 | 232.39 ms | 210.48 ms | 349.38 ms |
| **Medium** | $50 - 200$ tokens | Conservative | 500 | 533.78 ms | 380.70 ms | 1,163.27 ms |
| | | Balanced | 500 | 580.24 ms | 409.35 ms | 1,202.73 ms |
| | | Aggressive | 500 | 609.98 ms | 421.75 ms | 1,205.71 ms |
| **Long** | $> 200$ tokens | Conservative | 250 | **3,214.76 ms** | **3,140.62 ms** | **3,705.48 ms** |
| | | Balanced | 250 | **3,507.61 ms** | **3,216.34 ms** | **5,650.24 ms** |
| | | Aggressive | 250 | **3,768.13 ms** | **3,267.95 ms** | **8,408.30 ms** |

### 6.3 Top 10 Latency Outliers Across All 3,000 Trials

Forensic analysis of individual pipeline stage latencies reveals that **Stage 4 (Semantic Guard embedding computation)** is the sole contributor to latency expansion on long prompts, accounting for $>98\%$ of execution time:

| Rank | Prompt ID | Mode | Length (Tokens) | Total Latency | Stage 1 (Regex) | Stage 2 (Lexical) | Stage 3 (Syntactic) | Stage 4 (Semantic Guard) |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | `ige-0160` | Aggressive | Long (218 tok) | **9,761.41 ms** | 12.57 ms | 8.49 ms | 9.75 ms | **9,729.41 ms** (99.7%) |
| 2 | `ige-0641` | Aggressive | Long (214 tok) | **9,263.32 ms** | 13.20 ms | 10.40 ms | 26.62 ms | **9,211.87 ms** (99.4%) |
| 3 | `ige-0979` | Aggressive | Long (217 tok) | **9,096.55 ms** | 12.56 ms | 7.23 ms | 39.80 ms | **9,035.21 ms** (99.3%) |
| 4 | `ige-0317` | Aggressive | Long (213 tok) | **9,095.90 ms** | 16.22 ms | 12.50 ms | 23.67 ms | **9,042.05 ms** (99.4%) |
| 5 | `ige-0078` | Aggressive | Long (222 tok) | **9,051.40 ms** | 12.84 ms | 9.27 ms | 48.77 ms | **8,978.79 ms** (99.2%) |
| 6 | `ige-0235` | Aggressive | Long (223 tok) | **9,006.51 ms** | 12.53 ms | 7.09 ms | 26.04 ms | **8,959.62 ms** (99.5%) |
| 7 | `ige-0499` | Aggressive | Long (211 tok) | **8,537.76 ms** | 12.56 ms | 7.09 ms | 36.53 ms | **8,480.38 ms** (99.3%) |
| 8 | `ige-0578` | Aggressive | Long (208 tok) | **8,527.07 ms** | 27.38 ms | 12.45 ms | 11.22 ms | **8,473.99 ms** (99.4%) |
| 9 | `ige-0742` | Aggressive | Long (224 tok) | **8,477.89 ms** | 18.82 ms | 10.40 ms | 8.16 ms | **8,438.88 ms** (99.5%) |
| 10 | `ige-0398` | Aggressive | Long (207 tok) | **8,466.40 ms** | 12.50 ms | 7.07 ms | 31.33 ms | **8,414.32 ms** (99.4%) |

---

## 7. Personal-Initial Probe Challenge Verification

### 7.1 Probe Cohort Definition
The frozen dataset `data/benchmark_ige_1000_unseen.json` embeds **72 intentional challenge probes** (and 6 additional natural initial occurrences = 78 total prompts) containing personal names with single or double initials:
- Multi-initial names: `Dr. A. B. Smith`, `W. E. B. Du Bois`, `C. S. Lewis`, `T. S. Eliot`
- Single-initial names: `A. Einstein`, `J. K. Rowling`, `A. J. Brown`, `M. E. Johnson`, `E. B. White`, `H. G. Wells`

### 7.2 Empirical Verification Across 216 Evaluations

| Mode | Probe Prompts Evaluated | Accepted Trials | Rolled Back Trials | Preservation Violations | Dropped Initials | Corrupted Names |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Conservative** | 72 | 64 (88.89%) | 8 (11.11%) | 6 (Logged) | **0** | **0** |
| **Balanced** | 72 | 64 (88.89%) | 8 (11.11%) | 6 (Logged) | **0** | **0** |
| **Aggressive** | 72 | 64 (88.89%) | 8 (11.11%) | 6 (Logged) | **0** | **0** |
| **Total** | **216** | **192** | **24** | **18** | **0 (100% Intact)** | **0 (100% Intact)** |

### 7.3 Verification Conclusion
In the pre-fix state, Aggressive mode Stage 1 article pruning stripped `A.` from `A. B. Smith`, leaving `B. Smith`.
In IGE-1000, across 216 evaluations spanning Conservative, Balanced, and Aggressive modes:
- Exactly **0 initials were pruned**.
- Exactly **0 periods or punctuation marks following initials were modified**.
- Prompt `ige-0001` (`"Can you help me implement ... Follow A. Einstein's guidelines."`) was optimized in Aggressive mode from 39 tokens to 33 tokens, preserving `"Follow A. Einstein's guidelines."` with 100% precision.
- The personal initial correctness fix is **100% verified, robust, and permanent**.

---

## 8. Generalization Claims & Threats to Validity Critique

### 8.1 Critique of Section 10 Claims in the IGE Report
Section 10 of `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md` concludes:
> *"Acceptance rates and token reductions on unseen prompts match historical benchmarks within sub-percent tolerances."*

**Auditor Critique:**
1. **Factually Invalid Sub-Percent Claim:** As proven in Section 4, acceptance rates did **not** match historical benchmarks within sub-percent tolerances. Acceptance shifted from 99.00% $\rightarrow$ 89.00% (Conservative) and 99.33% $\rightarrow$ 92.20% (Balanced).
2. **Defensible Generalization Claim:** The defensible generalization claim is that PromptGreen V2's **safety mechanisms and active token reduction capabilities generalize to authentic verbose prompts**. On the 1,200 benchmark, Conservative mode was passive (only 10.5% useful reductions; 0.18 tok/prompt). On IGE-1000, Conservative mode actively identified fluff in 58.0% of prompts, achieving 1.20 tok/prompt reduction while safely rejecting invalid candidates via guardrails.
3. **Absence of Formal Hypothesis Testing:** The report claims statistical equivalence without performing two-sample Kolmogorov-Smirnov, Mann-Whitney U, or Wilcoxon rank-sum tests. To claim statistical equivalence in an academic paper, $p$-values must be reported.

### 8.2 Threats to Validity
1. **SentenceTransformer Cosine Similarity Ceiling:** The semantic guard uses `all-MiniLM-L6-v2`. On long prompts ($>200$ tokens), cosine similarity remains artificially high ($>0.98$) even when intermediate clauses are dropped, because the embedding is dominated by background context. Conversely, on short prompts ($<30$ tokens), dropping a single non-essential word can cause similarity to plunge below $0.90$.
2. **Synthetic Preambles:** While core instructions are realistic, secondary template carrier phrases (`"Please provide a comprehensive explanation..."`) were procedurally generated, which may slightly inflate regex matching rates compared to natural human writing.

---

## 9. Discrepancy Classification Table

| Discrepancy ID | Location in Target Report | Nature of Discrepancy | Reported Value | Audited Ground Truth | Severity | Recommended Corrective Action |
|:---:|:---|:---|:---:|:---:|:---:|:---|
| **DISC-01** | Executive Summary (Lines 21–24) | Misattributed Historical 1,200 Acceptance Rates | 89.2% / 92.8% / 92.5% | **99.00% / 99.33% / 99.42%** | **Major** | Update text to cite true 1,200 acceptance rates and explain that the drop in IGE-1000 acceptance reflects a 5.5x increase in active prompt pruning triggering safety guardrails. |
| **DISC-02** | Cross-Corpus Comparison Table (Lines 218–220) | Misreported Historical 1,200 Metrics | Mean Red: 1.25 / 1.48 / 3.86 tok; Red %: 1.17% / 1.39% / 3.61% | **Mean Red: 0.18 / 0.25 / 3.59 tok; Red %: 0.31% / 0.42% / 5.74%** | **Major** | Replace entire row in Table with audited figures from `results/benchmark_1200/summary.json`. |
| **DISC-03** | Mode Summary Table (Line 104) & Text (Line 242) | Misreported Net Carbon Debt Counts | Cons: 70 (7.0%), Bal: 55 (5.5%), Agg: 49 (4.9%) | **Cons: 180 (18.0%), Bal: 149 (14.9%), Agg: 85 (8.5%)** | **Moderate** | Update table to report Total Net Carbon Debt (180 / 149 / 85) and clarify Accepted Net Carbon Debt (70 / 71 / 9). |
| **DISC-04** | Table at Line 94 | Minor median similarity discrepancy in Conservative mode | 0.9929 | **0.9904** (Exact p50) | **Minor** | Align median value to 0.9904. |
| **DISC-05** | Generalization Claims (Section 10) | Claim of sub-percent acceptance alignment | Claimed $\le 0.6\%$ invariance | **10.0% difference in Cons, 7.1% in Bal, 7.0% in Agg** | **Major** | Reframe conclusion around active transformation safety rather than numerical invariance. |

---

## 10. Recommended Corrections

To elevate `docs/IGE_1000_INDEPENDENT_GENERALIZATION_REPORT.md` to thesis-ready rigor, the following specific revisions should be made:

1. **Revise Executive Summary (Section 1):**
   - Replace the $\pm 0.6\%$ acceptance claim with an explanation of active pruning vs. passive pass-through.
   - Clarify that IGE-1000 stimulated 58.0% useful modifications in Conservative mode (vs. 10.5% in the 1,200 benchmark), resulting in 1.20 tok/prompt savings (vs. 0.18 tok/prompt) and appropriately activating 11.0% safety rollbacks.
2. **Correct Summary Table (Section 3):**
   - Correct Net Carbon Debt row to: `180 (18.0%) | 149 (14.9%) | 85 (8.5%)`.
   - Add a sub-row: `Accepted Carbon Debt: 70 (7.0%) | 71 (7.1%) | 9 (0.9%)`.
3. **Correct Cross-Corpus Comparison Table (Section 6 / 8):**
   - Update the "Expanded Benchmark" row with the true figures:
     - Conservative: 99.00% acceptance, 0.18 tok mean reduction, 0.31% net reduction, 15.33% zero-debt.
     - Balanced: 99.33% acceptance, 0.25 tok mean reduction, 0.42% net reduction, 20.67% zero-debt.
     - Aggressive: 99.42% acceptance, 3.59 tok mean reduction, 5.74% net reduction, 95.42% zero-debt.
4. **Reframe Generalization Narrative:**
   - Emphasize that PromptGreen V2 **successfully generalized its optimization and safety capabilities to a challenging, unseen distribution**, achieving positive net energy savings ($27.20 - 31.91 \text{ Wh}$) with zero token expansion defects and 100% preservation of personal initials.
