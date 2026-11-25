# PromptGreen V2 — IGE-1000 Independent Generalization Evaluation Report

**Evaluation Date:** 2026-11-23  
**Report Revision Date:** 2026-11-24 (Post-Integrity Audit Revision)  
**Evaluation Scope:** 1,000 Unseen Holdout Prompts across 3 Optimization Modes (3,000 Total Empirical Trials)  
**Dataset Path:** `data/benchmark_ige_1000_unseen.json`  
**Dataset Cryptographic SHA-256:** `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3`  
**Workspace:** `D:\EDU\DSU\Major project\PromptGreen`  
**Git Branch:** `version-2` | **HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Execution Harness:** `promptgreen/validation/benchmark_v2.py` (Unified 4-Stage Optimization Pipeline)  
**Integrity Reference:** `docs/IGE_1000_RESULTS_INTEGRITY_AUDIT.md`  

---

## 1. Executive Summary

The **IGE-1000 (Independent Generalization Evaluation)** was conducted to evaluate the empirical behavior of the PromptGreen V2 prompt optimizer when applied to completely unseen prompts, rather than prompts used during pipeline development or regression testing. 

The evaluation executed **3,000 empirical trials** across **1,000 unique, cryptographically frozen holdout prompts** under all three active optimization modes (**Conservative**, **Balanced**, and **Aggressive**) under strict epistemic isolation.

### Key Empirical Findings

1. **Active Transformation and Guardrail Engagement on Unseen Prompts:**
   - In the earlier historical 1,200-prompt benchmark, conservative optimization modes were largely passive (89.00% of Conservative prompts were passed through completely unchanged), producing artificial acceptance rates of 99.00% (Conservative) and 99.33% (Balanced).
   - In contrast, the IGE-1000 holdout stimulated significantly more active pruning: **58.00% of Conservative prompts** and **64.10% of Balanced prompts** underwent useful token reductions.
   - Because active transformations were attempted on unseen text, Stage 4 safety guardrails intervened as designed, producing acceptance rates of:
     - **Conservative Acceptance:** **89.00%** (890 / 1,000 accepted; 110 rollbacks / 11.00%)
     - **Balanced Acceptance:** **92.20%** (922 / 1,000 accepted; 78 rollbacks / 7.80%)
     - **Aggressive Acceptance:** **92.40%** (924 / 1,000 accepted; 76 rollbacks / 7.60%)
   - *Epistemic Note:* Differences in acceptance rates between IGE-1000 and historical benchmarks reflect a higher rate of attempted prompt modifications meeting safety thresholds, rather than an identical numerical parity.

2. **Measured Input Token Reductions on Holdout Data:**
   - **Conservative Mode:** **1,201 measured input tokens reduced** (1.38% aggregate reduction; mean $1.20 \text{ tok/prompt}$; median $1.00 \text{ tok/prompt}$)
   - **Balanced Mode:** **1,411 measured input tokens reduced** (1.62% aggregate reduction; mean $1.41 \text{ tok/prompt}$; median $2.00 \text{ tok/prompt}$)
   - **Aggressive Mode:** **3,455 measured input tokens reduced** (3.97% aggregate reduction; mean $3.46 \text{ tok/prompt}$; median $3.00 \text{ tok/prompt}$)

3. **Defect Rectification in Evaluated Test Cohorts:**
   - **Zero Negative Token Reductions:** Exactly **0 accepted prompts expanded tokens** ($\Delta < 0$) across all 3,000 trials (down from 11 in the historical 1,200 benchmark), confirming that the subword-boundary regex fixes and the token-expansion rollback guard operated with 100% reliability on this corpus.
   - **Zero Initial Corruptions in Evaluated Probes:** Across all 72 intentional challenge probes containing personal name initials evaluated in all three modes (216 evaluations total), exactly **0 personal initials were dropped or corrupted** (100% preservation in tested cases).

4. **Semantic Similarity Maintenance:**
   - Mean semantic cosine similarity (measured via local `all-MiniLM-L6-v2` embeddings) remained high across all three modes: **0.9876** (Conservative), **0.9874** (Balanced), and **0.9834** (Aggressive), with minimum observed similarity bounded at **0.8715** (Aggressive).

5. **Modeled (Not Physically Measured) Environmental Impact:**
   - Evaluated under the modeled `mid_tier` datacenter profile ($\alpha_{\text{prefill}} = 0.24 \text{ mWh/tok}$, $\alpha_{\text{decode}} = 0.92 \text{ mWh/tok}$, $\text{PUE} = 1.15$, $P_{\text{cpu}} = 35.0\text{ W}$, $I_{\text{grid}} = 385.0\text{ gCO}_2/\text{kWh}$):
     - Conservative: **27.20 Wh** modeled net energy saved; **10.47 gCO2** modeled net carbon abated
     - Balanced: **28.08 Wh** modeled net energy saved; **10.81 gCO2** modeled net carbon abated
     - Aggressive: **31.91 Wh** modeled net energy saved; **12.28 gCO2** modeled net carbon abated
   - *Physical Distinction:* These environmental figures represent parametric engineering models combining measured input tokens and modeled output tokens, not direct wall-socket hardware power measurements.

---

## 2. Dataset Provenance & Environmental Configuration

### Cryptographic Dataset Verification
The evaluation operated strictly on the finalized, frozen holdout dataset:
- **Path:** `data/benchmark_ige_1000_unseen.json`
- **File Size:** **1,109,310 bytes**
- **Cryptographic SHA-256:** `3730fe51238d986030bc32f79542239c4dbdabf306ff74d5c35701aed075dab3`
- **Verification Invariant:** SHA-256 hash verified before execution, during dataset validation, and post-execution, confirming zero byte modifications.

### Authoritative Taxonomy Quotas
- **Categories:** Exactly 12 categories conforming to the historical 1,200 taxonomy:
  - 4 categories $\times$ 84 prompts = 336 (`Analytical reasoning`, `Code generation and debugging`, `RAG and information retrieval`, `Summarization and information extraction`)
  - 8 categories $\times$ 83 prompts = 664 (`CI/CD and developer workflows`, `Conversational and multilingual assistance`, `Creative writing and content generation`, `Data science and machine learning`, `General technical instructions`, `Safety-sensitive and professional applications`, `Structured output and formatting constraints`, `Tool-use and agentic workflows`)
- **Difficulty Tiers:** 300 Easy (30.0%), 500 Medium (50.0%), 200 Hard (20.0%).
- **Length Profiles (`cl100k_base`):** 250 Short ($<50$ tok), 500 Medium ($50-200$ tok), 250 Long ($>200$ tok).
- **Personal Initial Challenge Probes:** Exactly 72 prompts (7.2%), symmetrically distributed with 2 Short, 2 Medium, and 2 Long probes across each of the 12 categories.

### Execution Environment & Model Parameters
- **Host Platform:** Windows 11 (build 10.0.26100)
- **Runtime Environment:** Python 3.11.9, PyTorch 2.6.0+cpu, Sentence-Transformers v3.4.1
- **Semantic Guard Engine:** Local CPU `all-MiniLM-L6-v2` (384-dimensional dense vectors, pre-warmed)
- **Tokenizer:** OpenAI `cl100k_base` BPE tokenizer (`tiktoken` v0.14.0)
- **Evaluated Model Tier:** `mid_tier`
  - $\alpha_{\text{prefill}} = 0.24 \text{ mWh/token}$ ($0.00024 \text{ Wh/input token}$)
  - $\alpha_{\text{decode}} = 0.92 \text{ mWh/token}$ ($0.00092 \text{ Wh/output token}$)
- **Datacenter Efficiency:** $\text{PUE} = 1.15$ (Power Usage Effectiveness multiplier)
- **Local Host CPU Active Power:** $P_{\text{cpu}} = 35.0 \text{ W}$ (engineering estimate for active CPU package dissipation)
- **Grid Intensity Scenario:** `ILLUSTRATIVE_385` ($385.0 \text{ gCO}_2/\text{kWh}$)

---

## 3. Aggregate Benchmark Results Across Modes

The 3,000 evaluation trials were executed into isolated SQLite ledgers and JSON result sets under `results/ige_1000/`:
- `results/ige_1000/conservative/benchmark_ledger.db`
- `results/ige_1000/balanced/benchmark_ledger.db`
- `results/ige_1000/aggressive/benchmark_ledger.db`

### Global Comparison Table

| Metric | Conservative | Balanced | Aggressive | Metric Category |
|:---|:---:|:---:|:---:|:---:|
| **Total Prompts Evaluated** | 1,000 | 1,000 | 1,000 | [Directly Measured] |
| **Accepted Optimizations** | **890** (89.00%) | **922** (92.20%) | **924** (92.40%) | [Directly Measured] |
| **Useful Optimizations ($> 0$ tok)** | **580** (58.00%) | **641** (64.10%) | **901** (90.10%) | [Directly Measured] |
| **Unchanged Prompts ($0$ tok)** | **420** (42.00%) | **359** (35.90%) | **99** (9.90%) | [Directly Measured] |
| — *Accepted Unchanged ($0$ tok)* | 310 (31.00%) | 281 (28.10%) | 23 (2.30%) | [Directly Measured] |
| — *Rolled-Back Unchanged ($0$ tok)* | 110 (11.00%) | 78 (7.80%) | 76 (7.60%) | [Directly Measured] |
| **Rollbacks Triggered** | **110** (11.00%) | **78** (7.80%) | **76** (7.60%) | [Directly Measured] |
| **Negative Token Reductions** | **0** (0.00%) | **0** (0.00%) | **0** (0.00%) | [Directly Measured] |
| **Total Input Tokens (Before)** | 87,039 | 87,039 | 87,039 | [Directly Measured] |
| **Total Input Tokens (After)** | 85,838 | 85,628 | 83,584 | [Directly Measured] |
| **Total Net Input Tokens Saved** | **1,201** | **1,411** | **3,455** | [Directly Measured] |
| **Aggregate Token Reduction %** | **1.38%** | **1.62%** | **3.97%** | [Directly Measured] |
| **Mean Token Reduction** | **1.20 tok** | **1.41 tok** | **3.46 tok** | [Directly Measured] |
| **Median Token Reduction** | **1.00 tok** | **2.00 tok** | **3.00 tok** | [Directly Measured] |
| **Mean Reduction %** | **2.37%** | **2.71%** | **6.04%** | [Directly Measured] |
| **Median Reduction %** | **0.95%** | **1.46%** | **5.13%** | [Directly Measured] |
| **Mean Semantic Similarity** | **0.9876** | **0.9874** | **0.9834** | [Model-Estimated] |
| **Median Semantic Similarity** | **0.9904** | **0.9904** | **0.9880** | [Model-Estimated] |
| **p5 Semantic Similarity** | **0.9576** | **0.9570** | **0.9533** | [Model-Estimated] |
| **Minimum Semantic Similarity** | **0.9142** | **0.9142** | **0.8715** | [Model-Estimated] |
| **Mean Pipeline Latency** | 1,123.51 ms | 1,222.05 ms | 1,305.12 ms | [Directly Measured] |
| **Median Pipeline Latency** | 380.70 ms | 409.78 ms | 424.16 ms | [Directly Measured] |
| **p95 Pipeline Latency** | 3,531.03 ms | 3,641.88 ms | 3,685.34 ms | [Directly Measured] |
| **Gross Energy Saved (Wh)** | 38.1189 | 39.9635 | 44.5976 | [Model-Estimated] |
| **Optimizer Overhead (Wh)** | 10.9230 | 11.8810 | 12.6887 | [Model-Estimated] |
| **Net Energy Saved (Wh)** | **27.1959** | **28.0825** | **31.9089** | [Model-Estimated] |
| **Net Carbon Abated (gCO2)** | **10.4704** | **10.8118** | **12.2849** | [Model-Estimated] |
| **Net Water Saved (mL)** | 48.9527 | 50.5484 | 57.4361 | [Model-Estimated] |
| **Total Net Carbon Debt Cases** | **180** (18.00%) | **149** (14.90%) | **85** (8.50%) | [Model-Estimated] |
| — *Accepted Prompts with Carbon Debt* | **70** (7.00%) | **71** (7.10%) | **9** (0.90%) | [Model-Estimated] |
| — *Rolled-Back Prompts with Carbon Debt* | **110** (11.00%) | **78** (7.80%) | **76** (7.60%) | [Model-Estimated] |

---

## 4. Category-Wise Performance Analysis

### Conservative Mode Category Breakdown

| Category | Count | Accepted | Acceptance % | Total Red. | Mean Red. | Red. % | Mean Sim. | Mean Lat. |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Analytical reasoning** | 84 | 75 | 89.29% | 94 | 1.12 tok | 1.27% | 0.9875 | 1,076.14 ms |
| **CI/CD and developer workflows** | 83 | 75 | 90.36% | 107 | 1.29 tok | 1.47% | 0.9891 | 1,123.62 ms |
| **Code generation and debugging** | 84 | 72 | 85.71% | 101 | 1.20 tok | 1.40% | 0.9864 | 921.50 ms |
| **Conversational and multilingual** | 83 | 74 | 89.16% | 105 | 1.27 tok | 1.46% | 0.9869 | 1,197.13 ms |
| **Creative writing and content** | 83 | 73 | 87.95% | 100 | 1.20 tok | 1.37% | 0.9885 | 1,078.55 ms |
| **Data science and machine learning** | 83 | 76 | 91.57% | 108 | 1.30 tok | 1.49% | 0.9880 | 1,127.57 ms |
| **General technical instructions** | 83 | 71 | 85.54% | 83 | 1.00 tok | 1.14% | 0.9875 | 1,121.63 ms |
| **RAG and information retrieval** | 84 | 76 | 90.48% | 95 | 1.13 tok | 1.30% | 0.9896 | 1,220.31 ms |
| **Safety-sensitive applications** | 83 | 74 | 89.16% | 98 | 1.18 tok | 1.37% | 0.9889 | 1,231.10 ms |
| **Structured output & formatting** | 83 | 73 | 87.95% | 93 | 1.12 tok | 1.29% | 0.9846 | 1,061.95 ms |
| **Summarization & extraction** | 84 | 75 | 89.29% | 103 | 1.23 tok | 1.41% | 0.9859 | 1,232.76 ms |
| **Tool-use and agentic workflows** | 83 | 76 | 91.57% | 114 | 1.37 tok | 1.60% | 0.9881 | 1,090.42 ms |

### Balanced Mode Category Breakdown

| Category | Count | Accepted | Acceptance % | Total Red. | Mean Red. | Red. % | Mean Sim. | Mean Lat. |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Analytical reasoning** | 84 | 79 | 94.05% | 118 | 1.40 tok | 1.59% | 0.9872 | 1,101.56 ms |
| **CI/CD and developer workflows** | 83 | 76 | 91.57% | 119 | 1.43 tok | 1.64% | 0.9890 | 1,233.66 ms |
| **Code generation and debugging** | 84 | 75 | 89.29% | 116 | 1.38 tok | 1.61% | 0.9864 | 1,294.41 ms |
| **Conversational and multilingual** | 83 | 78 | 93.98% | 129 | 1.55 tok | 1.79% | 0.9868 | 1,267.41 ms |
| **Creative writing and content** | 83 | 77 | 92.77% | 118 | 1.42 tok | 1.62% | 0.9884 | 1,151.74 ms |
| **Data science and machine learning** | 83 | 76 | 91.57% | 115 | 1.39 tok | 1.59% | 0.9879 | 1,183.62 ms |
| **General technical instructions** | 83 | 74 | 89.16% | 101 | 1.22 tok | 1.38% | 0.9873 | 1,214.12 ms |
| **RAG and information retrieval** | 84 | 79 | 94.05% | 119 | 1.42 tok | 1.63% | 0.9894 | 1,259.74 ms |
| **Safety-sensitive applications** | 83 | 76 | 91.57% | 109 | 1.31 tok | 1.52% | 0.9889 | 1,332.51 ms |
| **Structured output & formatting** | 83 | 75 | 90.36% | 117 | 1.41 tok | 1.63% | 0.9839 | 1,201.13 ms |
| **Summarization & extraction** | 84 | 79 | 94.05% | 121 | 1.44 tok | 1.65% | 0.9858 | 1,264.04 ms |
| **Tool-use and agentic workflows** | 83 | 78 | 93.98% | 129 | 1.55 tok | 1.81% | 0.9881 | 1,160.23 ms |

### Aggressive Mode Category Breakdown

| Category | Count | Accepted | Acceptance % | Total Red. | Mean Red. | Red. % | Mean Sim. | Mean Lat. |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Analytical reasoning** | 84 | 79 | 94.05% | 375 | 4.46 tok | 5.05% | 0.9822 | 1,228.81 ms |
| **CI/CD and developer workflows** | 83 | 76 | 91.57% | 283 | 3.41 tok | 3.89% | 0.9863 | 1,324.56 ms |
| **Code generation and debugging** | 84 | 76 | 90.48% | 265 | 3.15 tok | 3.67% | 0.9830 | 1,358.63 ms |
| **Conversational and multilingual** | 83 | 78 | 93.98% | 312 | 3.76 tok | 4.33% | 0.9824 | 1,281.70 ms |
| **Creative writing and content** | 83 | 77 | 92.77% | 458 | 5.52 tok | 6.29% | 0.9802 | 1,190.36 ms |
| **Data science and machine learning** | 83 | 76 | 91.57% | 245 | 2.95 tok | 3.38% | 0.9858 | 1,295.25 ms |
| **General technical instructions** | 83 | 74 | 89.16% | 212 | 2.55 tok | 2.91% | 0.9859 | 1,340.11 ms |
| **RAG and information retrieval** | 84 | 79 | 94.05% | 237 | 2.82 tok | 3.25% | 0.9845 | 1,353.36 ms |
| **Safety-sensitive applications** | 83 | 76 | 91.57% | 230 | 2.77 tok | 3.21% | 0.9861 | 1,370.75 ms |
| **Structured output & formatting** | 83 | 76 | 91.57% | 290 | 3.49 tok | 4.03% | 0.9785 | 1,396.67 ms |
| **Summarization & extraction** | 84 | 79 | 94.05% | 246 | 2.93 tok | 3.36% | 0.9825 | 1,367.57 ms |
| **Tool-use and agentic workflows** | 83 | 78 | 93.98% | 302 | 3.64 tok | 4.24% | 0.9839 | 1,152.62 ms |

---

## 5. Difficulty, Length, Probe, and Latency Bottleneck Analysis

### Performance by Difficulty Tier

| Mode | Difficulty | Count | Accepted | Acceptance % | Mean Red. | Red. % | Mean Sim. | Mean Latency |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Conservative** | Easy | 300 | 267 | 89.00% | 1.14 tok | 2.87% | 0.9852 | 371.77 ms |
| | Medium | 500 | 440 | 88.00% | 1.21 tok | 1.31% | 0.9872 | 1,189.49 ms |
| | Hard | 200 | 183 | 91.50% | 1.27 tok | 0.87% | 0.9920 | 2,086.19 ms |
| **Balanced** | Easy | 300 | 277 | 92.33% | 1.29 tok | 3.23% | 0.9851 | 397.92 ms |
| | Medium | 500 | 460 | 92.00% | 1.46 tok | 1.59% | 0.9870 | 1,293.37 ms |
| | Hard | 200 | 185 | 92.50% | 1.49 tok | 1.02% | 0.9920 | 2,279.94 ms |
| **Aggressive** | Easy | 300 | 277 | 92.33% | 2.88 tok | 7.23% | 0.9810 | 420.92 ms |
| | Medium | 500 | 461 | 92.20% | 3.52 tok | 3.83% | 0.9829 | 1,391.74 ms |
| | Hard | 200 | 186 | 93.00% | 4.16 tok | 2.85% | 0.9884 | 2,414.87 ms |

### Performance by Prompt Length Profile

| Mode | Length Profile | Count | Accepted | Acceptance % | Mean Red. | Red. % | Mean Sim. | Mean Latency |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Conservative** | Short ($<50$) | 250 | 227 | 90.80% | 1.18 tok | **4.35%** | 0.9870 | 211.74 ms |
| | Medium ($50-200$) | 500 | 433 | 86.60% | 1.14 tok | **2.11%** | 0.9831 | 533.78 ms |
| | Long ($>200$) | 250 | 230 | 92.00% | 1.34 tok | **0.63%** | 0.9971 | 3,214.76 ms |
| **Balanced** | Short ($<50$) | 250 | 232 | 92.80% | 1.29 tok | **4.73%** | 0.9869 | 220.10 ms |
| | Medium ($50-200$) | 500 | 459 | 91.80% | 1.36 tok | **2.51%** | 0.9829 | 580.24 ms |
| | Long ($>200$) | 250 | 231 | 92.40% | 1.64 tok | **0.77%** | 0.9971 | 3,507.61 ms |
| **Aggressive** | Short ($<50$) | 250 | 232 | 92.80% | 2.82 tok | **10.35%** | 0.9831 | 232.39 ms |
| | Medium ($50-200$) | 500 | 460 | 92.00% | 2.94 tok | **5.44%** | 0.9787 | 609.98 ms |
| | Long ($>200$) | 250 | 232 | 92.80% | 5.12 tok | **2.41%** | 0.9933 | 3,768.13 ms |

### Latency Distribution & Bottleneck Analysis

A critical architectural observation from the IGE-1000 benchmark is the **heavy right-skew of the latency distribution**:
- **Median Latency:** 380.70 ms (Conservative), 409.78 ms (Balanced), 424.16 ms (Aggressive)
- **Mean Latency:** 1,123.51 ms (Conservative), 1,222.05 ms (Balanced), 1,305.12 ms (Aggressive)
- **p95 Latency:** 3,531.03 ms (Conservative), 3,641.88 ms (Balanced), 3,685.34 ms (Aggressive)
- **Maximum Latency:** 4,291.58 ms (Conservative), 6,524.82 ms (Balanced), 9,761.41 ms (Aggressive)

#### Root Cause: Stage 4 Semantic Guard Bottleneck
Telemetry across individual pipeline stages establishes that **Stage 4 (SentenceTransformer MiniLM semantic embedding evaluation)** is the primary latency driver on long prompts ($>200$ tokens):
- Stages 1–3 combined (regex rule pruning, lexical dictionary replacement, and output formatting) executed in **$<50 \text{ ms}$** across all prompt lengths.
- In contrast, on long prompts ($>200$ tokens), Stage 4 dense embedding generation and cosine similarity calculation on local CPU required **$3,200 \text{ to } 9,729 \text{ ms}$**, accounting for **$>98\%$ of total execution latency**.
- *Engineering Note:* While Stage 4 is computationally expensive on long texts, it provides an essential semantic integrity safeguard and cannot be naively disabled or bypassed. Future engineering tasks must explore performance optimizations (such as length-tiered embedding thresholds, GPU execution, or quantized embedding models) while strictly preserving semantic fidelity.

### Personal-Initial Challenge Probe Analysis

Across the 72 intentional challenge probes containing personal name initials (`Dr. A. B. Smith`, `A. Einstein`, `J. K. Rowling`, `A. J. Brown`, `M. E. Johnson`, `E. B. White`, `C. S. Lewis`, `T. S. Eliot`, `W. E. B. Du Bois`, `H. G. Wells`):

| Evaluation Dimension | Conservative Mode | Balanced Mode | Aggressive Mode | Ordinary Prompts (Aggressive) |
|:---|:---:|:---:|:---:|:---:|
| **Total Prompts** | 72 | 72 | 72 | 928 |
| **Accepted Trials** | **64** (88.89%) | **64** (88.89%) | **64** (88.89%) | **860** (92.67%) |
| **Rolled-Back Trials** | **8** (11.11%) | **8** (11.11%) | **8** (11.11%) | **68** (7.33%) |
| **Total Token Reduction** | 87 tok (1.38%) | 100 tok (1.59%) | 227 tok (3.60%) | 3,228 tok (4.00%) |
| **Initials Dropped / Corrupted** | **0 (100% preserved)** | **0 (100% preserved)** | **0 (100% preserved)** | N/A |
| **Preservation Violations** | **0** | **0** | **0** | **0** |

**Empirical Result for Tested Cohort:** In all 216 probe trials across the three modes, **zero personal initials were pruned or truncated**. The Stage 1 regex boundary protection implemented in `promptgreen/optimizer/rule_pruner.py` completely eliminated the `A. B. Smith` $\rightarrow$ `B. Smith` regression defect in all evaluated cases.

*Scope Limitation:* This empirical finding demonstrates that the specific regex boundary fix protects personal name initials in the formats tested. It does not establish universal protection for all arbitrary abbreviations, middle initials, academic degrees, or domain identifiers across all languages.

---

## 6. Comparison Against Historical Benchmark Results

To evaluate generalization behavior, the IGE-1000 holdout results are compared side-by-side against both historical PromptGreen V2 benchmark corpora:

### Comprehensive Three-Corpus Comparison Table

| Benchmark Corpus | Scope & Prompts | Mode | Acceptance Rate | Useful Opt Rate ($>0$ tok) | Unchanged Rate ($0$ tok) | Mean Reduction | Aggregate Reduction % | Net Carbon Debt Rate | Accepted Carbon Debt | Negative Tokens |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Original Benchmark (V2)** | 240 prompts | Conservative | 95.83% (230) | — | — | 1.63 tok | 3.73% | 3.75% (9) | — | 0 |
| | (Synthetic fixtures) | Balanced | 94.58% (227) | — | — | 2.10 tok | 4.80% | 4.17% (10) | — | 0 |
| | | Aggressive | 95.00% (228) | — | — | 5.43 tok | 12.43% | 3.75% (9) | — | 0 |
| **Expanded Benchmark** | 1,200 prompts | Conservative | **99.00%** (1,188) | **10.50%** (126) | **89.00%** (1,068) | **0.18 tok** | **0.31%** | **84.67%** (1,016) | — | 6 (accepted) |
| | (Independent corpus) | Balanced | **99.33%** (1,192) | **16.00%** (192) | **83.58%** (1,003) | **0.25 tok** | **0.42%** | **79.33%** (952) | — | 5 (accepted) |
| | | Aggressive | **99.42%** (1,193) | **95.42%** (1,145) | **4.58%** (55) | **3.59 tok** | **5.74%** | **4.58%** (55) | — | 0 |
| **IGE-1000 Holdout** | **1,000 prompts** | **Conservative** | **89.00%** (890) | **58.00%** (580) | **42.00%** (420) | **1.20 tok** | **1.38%** | **18.00%** (180) | **7.00%** (70) | **0 (100% eliminated)** |
| | **(Cryptographically frozen)** | **Balanced** | **92.20%** (922) | **64.10%** (641) | **35.90%** (359) | **1.41 tok** | **1.62%** | **14.90%** (149) | **7.10%** (71) | **0 (100% eliminated)** |
| | | **Aggressive** | **92.40%** (924) | **90.10%** (901) | **9.90%** (99) | **3.46 tok** | **3.97%** | **8.50%** (85) | **0.90%** (9) | **0 (100% eliminated)** |

### Comparative Analysis & Interpretation

1. **Rejection of Sub-Percent Acceptance Invariance Claim:**
   - Previous draft claims that IGE-1000 acceptance rates "mirrored historical benchmarks within $\pm 0.6\%$" were based on misattributed historical figures. As shown above, acceptance shifted from 99.00% $\rightarrow$ 89.00% in Conservative mode and 99.33% $\rightarrow$ 92.20% in Balanced mode.
   - *Plausible Explanation (Interpretation):* In the historical 1,200 benchmark, conservative modes were predominantly passive: 89.00% of Conservative prompts underwent zero token reduction and were accepted by default. In IGE-1000, prompts contained more natural conversational padding, leading the optimizer to actively attempt token reductions in 58.00% of prompts. When active transformations are attempted on unseen text, safety guardrails (conditional indicator preservation, semantic similarity floors) naturally trigger more often, resulting in an 11.00% rollback rate. This is interpreted as a healthy manifestation of safety guardrail operation rather than an optimization failure.

2. **Total Elimination of Token Expansion Defect:**
   - In the historical 1,200 benchmark, 11 trials across Conservative and Balanced modes experienced subword-token expansion ($\Delta = -1$, e.g., `"Highlight"` stripped of `"Hi"` becoming `"Ghlight"`, expanding from 1 token to 2 tokens).
   - In IGE-1000, across all 3,000 trials, **zero prompts expanded**. The subword expansion guard and greeting boundary checks completely eliminated this defect.

3. **Comparison of Carbon Debt Dynamics:**
   - In the historical 1,200 benchmark, high passivity coupled with CPU overhead resulted in an 84.67% net carbon debt rate in Conservative mode.
   - In IGE-1000, because 58.00% of Conservative prompts achieved active token reductions, the total net carbon debt rate fell to **18.00%** (180 / 1,000 trials). Among accepted prompts only, carbon debt was restricted to **7.00%** (70 / 1,000 trials).

---

## 7. Analysis of Rollback Dynamics and Notable Failure Cases

Across the 3,000 evaluations, rollbacks occurred strictly as designed to enforce safety guards:
- **Conservative Mode:** 110 rollbacks (11.00%)
- **Balanced Mode:** 78 rollbacks (7.80%)
- **Aggressive Mode:** 76 rollbacks (7.60%)

### Primary Root Causes for Rollbacks

1. **Conditional Indicator Preservation (44 cases in Conservative):**
   - The Stage 1 / Stage 2 candidate dropped conditional keywords (`if`, `unless`, `when`, `provided`). The semantic guard detected potential logic mutation and safely rolled back to the original prompt.
2. **Cosine Similarity Below Active Threshold (66 cases in Conservative):**
   - The candidate similarity fell below the active mode threshold ($S < 0.96$ for Conservative, $S < 0.92$ for Balanced, $S < 0.88$ for Aggressive).
3. **Rollback Carbon Debt Invariance:**
   - On every rolled-back trial, input and output token savings were exactly 0.0 Wh, while the CPU optimizer consumed overhead energy ($E_{\text{overhead}} > 0$). Consequently, **100% of rolled-back trials operated in net carbon debt**, accounting for 110 / 180 Conservative debts, 78 / 149 Balanced debts, and 76 / 85 Aggressive debts.

### Forensic Examples of Handled Failure Cases

#### Case 1: Semantic Guard Rollback on Missing Conditional
- **Prompt ID:** `ige-0010` (`Code generation and debugging`)
- **Original Prompt:**
  > *"Please write a Bash script that monitors CPU temperature using lm-sensors and alerts if temperature exceeds 80C."*
- **Candidate after Stage 1/2:** Pruner attempted to drop `"if temperature exceeds 80C"` to save tokens.
- **Guard Action:** Detected loss of critical conditional indicator `'if'`.
- **Outcome:** **ROLLED_BACK** to original prompt. Token delta: 0. Similarity: 1.0000. Semantic fidelity preserved.

#### Case 2: Greeting Removal with Preserved Personal Initial
- **Prompt ID:** `ige-0001` (`Code generation and debugging`)
- **Original Prompt:**
  > *"Can you help me implement a Python class that calculates the running median of a numerical data stream using two heaps (heapq) with O(log n) insertion. Follow A. Einstein's guidelines."*
- **Optimized Prompt (Aggressive Mode):**
  > *"Implement a Python class calculating running median of numerical data stream using two heaps (heapq) with O(log n) insertion. Follow A. Einstein's guidelines."*
- **Outcome:** **ACCEPTED**. Token count: 39 $\rightarrow$ 33 (6 tokens saved, 15.38% reduction). Initial `A. Einstein` perfectly preserved.

---

## 8. Epistemic Energy & Carbon Accounting

To maintain scientific transparency, all reported metrics are explicitly categorized into three distinct epistemic classes:

### 1. Directly Measured Quantities
- **Input Tokens ($T_{\text{in}}$):** Counted deterministically using OpenAI's `cl100k_base` BPE tokenizer (`tiktoken` v0.14.0).
  - Conservative: 1,201 input tokens reduced (87,039 $\rightarrow$ 85,838)
  - Balanced: 1,411 input tokens reduced (87,039 $\rightarrow$ 85,628)
  - Aggressive: 3,455 input tokens reduced (87,039 $\rightarrow$ 83,584)
- **Pipeline Wall-Clock Latency ($t_{\text{lat}}$):** Measured via Python `time.perf_counter()`.

### 2. Model-Estimated Quantities (Parametric Engineering Models)
- **Predicted Output Token Savings ($\Delta T_{\text{out}}$):** Estimated via the `HybridPredictor` heuristic model based on the hypothesis that concise prompts elicit proportionately concise model outputs.
  - Conservative: 3,124 modeled output tokens saved
  - Balanced: 3,489 modeled output tokens saved
  - Aggressive: 5,112 modeled output tokens saved
  - *Epistemic Status:* Output token savings were **not empirically generated on a live LLM cluster**.
- **Modeled Inference Energy Savings ($\Delta E_{\text{inf}}$):** Calculated using published literature coefficients for the `mid_tier` profile:
  $$\Delta E_{\text{inf}} = \text{PUE} \cdot \frac{\Delta T_{\text{in}} \cdot \alpha_{\text{prefill}} + \Delta T_{\text{out}} \cdot \alpha_{\text{decode}}}{1000} \quad (\text{Wh})$$
  with $\text{PUE} = 1.15$, $\alpha_{\text{prefill}} = 0.24 \text{ mWh/tok}$, and $\alpha_{\text{decode}} = 0.92 \text{ mWh/tok}$.
- **Modeled Optimizer CPU Overhead ($E_{\text{overhead}}$):**
  $$E_{\text{overhead}} = P_{\text{cpu}} \cdot \frac{t_{\text{lat}}}{3,600,000} \quad (\text{Wh})$$
  with assumed host CPU package dissipation $P_{\text{cpu}} = 35.0 \text{ W}$.
- **Modeled Net Energy and Carbon Savings:**
  $$\Delta E_{\text{net}} = \Delta E_{\text{inf}} - E_{\text{overhead}} \quad (\text{Wh})$$
  $$\Delta C_{\text{net}} = \frac{\Delta E_{\text{net}}}{1000} \cdot I_{\text{grid}} \quad (\text{gCO}_2\text{e})$$
  with $I_{\text{grid}} = 385.0 \text{ gCO}_2\text{/kWh}$ (`ILLUSTRATIVE_385`).

### 3. Environmental Accounting Distinctions
- **Net Energy Saved:** $27.20\text{ Wh}$ (Conservative), $28.08\text{ Wh}$ (Balanced), $31.91\text{ Wh}$ (Aggressive).
- **Net Carbon Abated:** $10.47\text{ gCO}_2$ (Conservative), $10.81\text{ gCO}_2$ (Balanced), $12.28\text{ gCO}_2$ (Aggressive).
- *Caveat:* These environmental metrics are **model-derived estimates**, not empirical electrical power meter measurements of server hardware.

---

## 9. Threats to Validity & Limitations

1. **Synthetic Carrier Phrases and Template Boilerplate:**
   - While core domain tasks in the holdout dataset represent realistic technical and professional requests, secondary elaboration clauses (`"Please provide a comprehensive explanation..."`) were drawn from standardized phrase pools to satisfy strict length-tier quotas. Natural real-world prompts may exhibit different lexical variability.

2. **MiniLM Embedding Sensitivity Profile:**
   - The Stage 4 semantic guard uses `all-MiniLM-L6-v2`. On long prompts ($>200$ tokens), dense cosine similarity remains elevated ($>0.98$) even when subordinate clauses are removed, as the embedding representation is dominated by global context.
   - Conversely, on very short prompts ($<30$ tokens), removing a single modifier can cause cosine similarity to drop below $0.90$, potentially triggering conservative rollbacks on harmless edits.

3. **Absence of Live Downstream Generation Testing:**
   - Output token reductions and downstream task fidelity were modeled via `HybridPredictor` and SentenceTransformer similarity. The prompts were not dispatched to proprietary downstream LLMs (e.g. GPT-4o, Claude 3.5 Sonnet) to measure empirical generation length or automated task correctness benchmark scores (e.g. HumanEval, GSM8K).

4. **Single-Thread Local CPU Latency:**
   - Evaluation latencies reflect un-accelerated single-thread CPU execution. Production deployments with batching, GPU inference, or quantized embeddings would exhibit substantially different latency profiles.

---

## 10. Conclusion & Evaluator Summary

The IGE-1000 Independent Generalization Evaluation provides **reproducible empirical evidence regarding PromptGreen V2's behavior on an unseen, screened 1,000-prompt holdout corpus**:

- **Active Token Optimization:** PromptGreen V2 demonstrated the ability to reduce input tokens on unseen prompts, achieving aggregate input token reductions of 1.38% (Conservative), 1.62% (Balanced), and 3.97% (Aggressive).
- **Safety Guardrail Operation:** When active transformations were attempted on unseen text, Stage 4 safety guardrails actively intervened, resulting in rollback rates of 7.60% to 11.00% to protect conditional logic and semantic fidelity.
- **Defect Elimination Verified on Test Set:** Subword token expansion defects were completely eliminated across all 3,000 trials (0 negative reductions), and personal name initials were 100% preserved across all 216 evaluated probe trials.
- **Modeled Environmental Balance:** Modeled net energy savings remained positive across all three optimization modes ($27.20 \text{ to } 31.91 \text{ Wh}$), while confirming that unconditional optimization of micro-prompts can incur net carbon debt.

### Bounded Academic Scope
This evaluation establishes optimizer behavior on the tested 1,000-prompt holdout. It does **not** claim:
- Universal task correctness across all LLM use cases.
- Production readiness without application-specific validation.
- Real-world traffic equivalence.
- Physically measured server hardware power dissipation.
