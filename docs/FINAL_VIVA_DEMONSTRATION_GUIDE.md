# PromptGreen V2 — Final Viva & Capstone Demonstration Guide
**Academic Evaluation & External Viva Interviewer Runbook (5–7 Minutes)**

- **Project:** PromptGreen (Version 2.0)
- **Thesis Title:** *PromptGreen: Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable Large Language Model Inference*
- **Target Audience:** Academic Evaluators, Major Project Faculty Panel, External Examiner
- **Demonstration Timing:** 5 to 7 Minutes
- **Execution Mode:** 100% Offline, Local Windows Execution via `http://localhost:8000`

---

## 1. Quick Demonstration Overview & Timeline

| Step | Duration | Stage & Focus | Core Concept Demonstrated |
| :---: | :---: | :--- | :--- |
| **1** | 0:30 | **1-Click Launch & Startup** | `start_promptgreen.bat`, self-contained offline startup, server readiness. |
| **2** | 0:45 | **The Core Problem Statement** | LLM compute explosion: prefill vs decode quadratic costs, hidden carbon footprint of prompt fluff. |
| **3** | 1:30 | **Scenario 1: Verbose Prompt & 4-Stage Pipeline** | Fluff pruning, lexical compression, directive shaping, and MiniLM semantic validation. |
| **4** | 1:00 | **Scenario 2: First-Principles Environmental Accounting** | Canonical Watt-hours (Wh), PUE (1.15), gCO2e conversion, water cooling (1.8 mL/Wh). |
| **5** | 1:00 | **Scenario 3: Negative-Savings & Honest Accounting** | Micro-prompt `"Hi!"`, local CPU overhead exceeding gross inference savings, net carbon debt. |
| **6** | 1:00 | **Scenario 4: Green Model Router & Safety Invariants** | Task classification, Frontier-to-Compact energy comparison, medical `NO_SAFE_DOWNGRADE`. |
| **7** | 0:45 | **Scenario 5: Audit Ledger & Defensibility** | SQLite compliance log (`prompt_ledger.db`), architectural scope boundaries, research limitations. |

---

## 2. Step-by-Step Demonstration Script

### Step 1: Launching PromptGreen (0:00 – 0:30)
1. Open Windows Explorer at `D:\EDU\DSU\Major project\PromptGreen`.
2. **Action:** Double-click `start_promptgreen.bat`.
3. **What Evaluators See:**
   - Console displays Python environment verification and local port allocation: `http://localhost:8000`.
   - Web browser opens automatically to the **Green Prompt Studio** at `http://localhost:8000`.
   - Top-right badge shows a green pulsing indicator: `Backend Ready` and `v2.0 Active Telemetry`.
4. **Talking Point:**
   > *"PromptGreen V2 is completely self-contained. It requires zero cloud connectivity or external CDNs during evaluation. All frontend assets, SVG graphics, CSS styling, and REST endpoints run locally as a unified service on port 8000."*

---

### Step 2: Explaining the Problem Statement (0:30 – 1:15)
1. **Talking Point:**
   > *"Modern LLMs consume massive amounts of datacenter energy during inference. While most green computing focuses on model training, over 80% of real-world lifecycle emissions come from recurring inference. Prompts sent to LLMs frequently suffer from conversational fluff, bloated multi-shot examples, and redundant adjectives. Furthermore, in autoregressive transformers, every output token generated requires sequential KV-cache passes, making decoding significantly more energy-intensive than prefill. PromptGreen addresses this by actively pruning prompts, shaping output directives to curb token inflation, and routing requests away from power-hungry frontier clusters to green compact models."*

---

### Step 3: Primary Optimization Workflow (1:15 – 2:45)
1. **Action:** Click the preset button **"Climate Query"** (or paste the prompt below):
   ```text
   Hello! Could you please be so kind as to explain in extensive detail with multiple comprehensive real-world examples how climate change impacts coastal biodiversity? Think step-by-step and write an in-depth analysis.
   ```
2. **Configuration:**
   - Optimization Mode: **Balanced** (4-Stage Active Pipeline).
   - Target Serving Model Tier: **Frontier Dense (0.42 / 1.60 mWh)**.
   - Grid Intensity Scenario: **Illustrative Scenario (385.0 gCO2e/kWh)**.
3. **Action:** Click **"Optimize Prompt (v2.0 Pipeline)"**.
4. **What Evaluators See:**
   - Spinner activates with `Optimizing Across 4 Stages...`.
   - In seconds, the **4-Stage Execution Strip** populates:
     * **Stage 1 (Rule Pruner):** Fluff trimmed (e.g. `Hello! Could you please be so kind as to` removed).
     * **Stage 2 (Compressor):** Redundant modifiers pruned via deterministic lexical heuristics.
     * **Stage 3 (Directive Shaper):** Conciseness directives injected (Ollama neural pass or graceful fallback).
     * **Stage 4 (Semantic Guard):** Cosine embedding similarity calculated via `all-MiniLM-L6-v2` ($\ge 0.92$ threshold).
   - **Side-by-Side View:**
     * Original: 38 words (~49 tokens).
     * Optimized: 24 words (~32 tokens).
     * Reduction: ~25%–35% input token reduction with preserved technical meaning.
5. **Talking Point:**
   > *"Notice how Stage 1 strips linguistic noise deterministically in under 10ms, while Stage 4 guarantees semantic fidelity using a local sentence-transformer. If semantic similarity ever drops below threshold, PromptGreen automatically rolls back the prompt to preserve safety."*

---

### Step 4: First-Principles Environmental Telemetry (2:45 – 3:45)
1. **Point to the Thermodynamic Footprint Card:**
   - **Baseline Inference Energy:** $\sim 0.20$ Wh.
   - **Optimized Inference Energy:** $\sim 0.10$ Wh.
   - **Gross Savings:** $\sim 0.10$ Wh.
   - **Optimizer CPU Overhead:** $\sim 0.03$ Wh ($35\text{W} \times \frac{t_{\text{ms}}}{3,600,000}$).
   - **Net Energy Saved:** $+0.07$ Wh (reported in canonical Watt-hours, not unscaled heuristics).
   - **Carbon Abatement:** Reported in grams CO2e per query and per 1,000 queries.
   - **Water Conservation:** $1.8\text{ mL/Wh}$ datacenter cooling water saved.
2. **Talking Point:**
   > *"Unlike naive token counters, PromptGreen accounts for the physical asymmetry between prefill and decode phases using our thesis formula: $E = \text{PUE} \times (T_{\text{in}} \alpha_p + T_{\text{out}} \alpha_d) / 1000$. Crucially, we deduct local optimizer compute overhead, ensuring honest net accounting."*

---

### Step 5: Honest Accounting & Negative-Savings Scenario (3:45 – 4:45)
1. **Action:** Clear the prompt input and type:
   ```text
   Hi!
   ```
2. **Configuration:** Mode: **Balanced**, Model: **Compact Green**.
3. **Action:** Click **"Optimize Prompt"**.
4. **What Evaluators See:**
   - Prompt remains `"Hi!"` (0 tokens saved).
   - **Amber Warning Badge Appears:**  
     `⚠️ Net Carbon Debt: Local optimizer energy exceeded gross inference savings`
   - Net Energy Saved: **Negative** ($\approx -0.0006$ Wh).
   - Net Carbon Abated: **Negative** (Carbon Debt).
5. **Talking Point:**
   > *"This demonstrates the scientific integrity of PromptGreen. If an optimization achieves zero or trivial token savings, running the local CPU optimizer consumes more energy than is saved at the inference cluster. PromptGreen does not greenwash: it explicitly flags carbon debt."*

---

### Step 6: Green Model Router & Safety Invariants (4:45 – 5:45)
1. **Scenario A (Downgrade Recommendation):**
   - Click preset **"Sentiment Classification"**:
     ```text
     Classify the sentiment of the following customer support ticket into positive, neutral, or negative: 'The shipment arrived two days late and the outer box was damaged, but the contents were fine.'
     ```
   - Target Tier: **Frontier Dense**.
   - Result: Router recommends **`RECOMMEND_DOWNGRADE`** to **`compact_green`**.
   - Point out the like-for-like physical energy comparison: $0.091\text{ Wh} \rightarrow 0.007\text{ Wh}$ ($>90\%$ energy reduction).
2. **Scenario B (Safety-Critical Invariant):**
   - Click preset **"Medical Guidance"**:
     ```text
     Provide dosage guidance for pediatric acetaminophen. WARNING: Must strictly adhere to official weight-based safety guidelines (10-15 mg/kg every 4 to 6 hours). Do not exceed 5 doses in 24 hours.
     ```
   - Mode: **Aggressive**, Model: **Frontier Dense**.
   - Result:
     * Semantic Guard score: 1.0000 (dosage and negations `Do not exceed` preserved byte-for-byte).
     * Router Outcome: **`NO_SAFE_DOWNGRADE`**.
3. **Talking Point:**
   > *"The Green Model Router enforces conservative safety boundaries. High-risk domains like medical dosages and complex mathematical proofs are strictly locked against downgrading. Furthermore, the router is advisory: it never silently switches models without operator approval."*

---

### Step 7: Audit Ledger & Closing (5:45 – 6:30)
1. **Scroll down to Prompt Carbon Audit Ledger:**
   - Point to the live table showing all runs persisted in `prompt_ledger.db`.
   - Point to top KPI summary counters: Total Runs, Cumulative Wh Saved, and Cumulative gCO2e Abated.
2. **Conclusion & Defensibility Summary:**
   > *"In summary, PromptGreen V2 delivers a production-grade, unit-consistent prompt optimization and carbon telemetry engine. It bridges software engineering with environmental thermodynamics, providing verifiable carbon transparency for sustainable enterprise AI."*

---

## 3. Evaluator Q&A Defense Sheet

### Q1: "Are these energy numbers physically measured from GPU sensors during this run?"
- **Answer:** *"No. They are modeled thermodynamic approximations calculated from our thesis profile coefficients ($\alpha_{\text{prefill}}$ and $\alpha_{\text{decode}}$ in mWh/token), scaled by datacenter PUE ($1.15$). We explicitly label hardware TDPs and grid numbers as illustrative or thesis-provided references, not real-time physical power meter readings."*

### Q2: "How do you guarantee that pruning doesn't change the LLM's answer?"
- **Answer:** *"Through our Stage 4 Semantic Fidelity Guard. We compute sentence-transformer embeddings (`all-MiniLM-L6-v2`) and measure cosine similarity against the original prompt. If the score drops below threshold (0.92 in Conservative mode, 0.85 in Balanced), the pipeline triggers an automatic rollback to the original prompt, logging a warning in the audit ledger."*

### Q3: "Why did you use 385 gCO2e/kWh and 367 gCO2e/kWh?"
- **Answer:** *"367 gCO2e/kWh is the thesis-provided global benchmark scenario from Chapter 5. 385 gCO2e/kWh is an illustrative US national baseline scenario. Following our Stage 6 audit, we do not present either number as a universal empirical truth; users can also supply custom verified grid intensities from their local electricity provider via the Custom Grid UI."*

### Q4: "What happens if Ollama or the local LLM is offline?"
- **Answer:** *"The pipeline is designed with fault-tolerant fallbacks. If Ollama is offline or times out, Stage 3 completes gracefully as a deterministic no-op without crashing or hanging the user request."*
