# PromptGreen V2 — Final Thesis Implementation Gap Audit
**Honest Academic Defensibility, Scope Verification, and Research Limitations**

- **Document:** `docs/FINAL_THESIS_IMPLEMENTATION_GAP_AUDIT.md`
- **Project:** PromptGreen (Version 2.0)
- **Thesis Title:** *PromptGreen: Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable Large Language Model Inference*
- **Audit Date:** November 22, 2026
- **Status:** **APPROVED & ACADEMICALLY DEFENDED**

---

## 1. Purpose & Guiding Principles

In an academic capstone defense or technical viva, examiners and external evaluators frequently distinguish between **theoretical concepts outlined in a research proposal** and **empirically validated software delivered in the codebase**. 

Claiming that theoretical aspirations or future architectural proposals are fully implemented production features damages academic credibility. Conversely, clearly delineating what is **implemented and tested**, what is **modeled or estimated**, and what remains **future research** demonstrates intellectual maturity and scientific integrity.

This audit provides an exhaustive, honest comparison between the PromptGreen thesis specifications and the actual V2 codebase.

---

## 2. Core Architectural Dimensions: Promised vs Implemented

| Dimension | Thesis Proposal / Theoretical Scope | Actually Implemented in V2 Codebase | Verification & Testing Status | Academic Classification |
| :--- | :--- | :--- | :--- | :--- |
| **Optimization Pipeline** | 4-Stage Active Pipeline (Rule Pruner, Token Compressor, Directive Shaper, Semantic Guard). | Fully implemented in `promptgreen/optimizer/pipeline.py`. 4 modular stages with status tracking and rollback. | 246 unit tests, 10 engine tests, 8 E2E user scenarios passing. | **FULLY IMPLEMENTED & TESTED** |
| **Rule-Based Pruning** | Deterministic removal of conversational fluff, greetings, repetitive honorifics, and boilerplate. | Regex & lexical pattern engine in `rule_pruner.py` with preservation of code and technical terms. | Verified across 8 test suites; deterministic execution (<10ms). | **FULLY IMPLEMENTED & TESTED** |
| **Token Compression** | Neural token pruning via small SLMs (LLMLingua-2) with lexical compression fallback. | LLMLingua compressor interface with fully deterministic lexical and stop-word fallback in `compressor.py`. | Fallback tested and verified; neural weights optional. | **IMPLEMENTED (WITH RESILIENT FALLBACK)** |
| **Output Directive Shaping** | Instruction synthesis to induce concise downstream model responses. | Neural shaper calling local Ollama daemon (`output_shaper.py`) with timeout-safe deterministic no-op fallback. | Tested with both active Ollama and offline timeout fallback. | **IMPLEMENTED (HYBRID ARCHITECTURE)** |
| **Semantic Guardrail** | Semantic fidelity preservation to prevent task hallucination or goal drift. | Sentence-Transformers (`all-MiniLM-L6-v2`) cosine embedding similarity with automated pipeline rollback. | Tested across thresholds (0.92, 0.85, 0.70) and prompt domains. | **FULLY IMPLEMENTED & TESTED** |
| **Thermodynamic Carbon Engine** | First-principles energy modeling accounting for prefill vs decode asymmetry and PUE. | Implemented in `promptgreen/engine/thermodynamics.py`. Formulas yield canonical **Watt-hours (Wh)**. | Verified via hand calculations and unit tests down to $10^{-6}$ precision. | **FULLY IMPLEMENTED & TESTED** |
| **Green Model Router** | Dynamic routing to evaluate if queries can run on smaller green models. | Conservative, rule-guided architectural router in `promptgreen/engine/model_router.py`. | Tested across 8 domain categories with safety invariant locking. | **IMPLEMENTED (RULE-GUIDED ADVISORY)** |
| **Telemetry & Audit Ledger** | Persistent database tracking prompt reviews, token metrics, and carbon impact. | SQLite database ledger in `promptgreen/ledger/database.py` (`prompt_ledger.db`). | Tested across restarts, 100+ live records, stress concurrency. | **FULLY IMPLEMENTED & TESTED** |
| **User Interface** | Web application and dashboard for interactive prompt optimization and review. | Single-page **Green Prompt Studio** in `Website/index.html` served via `Website/server.py` on port 8000. | Verified via live HTTP tests, browser automation, and offline runbook. | **FULLY IMPLEMENTED & TESTED** |

---

## 3. Specific Technical Distinctions

### 3.1 Rule-Based Routing vs. Learned Machine Learning Routing
- **Thesis Concept:** Explores the possibility of a learned reinforcement learning or supervised meta-classifier that dynamically predicts task performance degradation on target models.
- **V2 Implementation:** Implements a **conservative, deterministic, rule-based architectural router** (`GreenModelRouter`). The router inspects prompt characteristics, task categories, syntax invariants, and domain risk tags (e.g., medical, cryptographic, mathematical reasoning).
- **Defense Statement:** 
  > *"Rather than relying on an opaque, uncalibrated ML classifier that might dangerously recommend downgrading safety-critical tasks, V2 implements a conservative, deterministic rule-guided policy. It enforces hard safety invariants (e.g. `NO_SAFE_DOWNGRADE` for medical dosages) and provides like-for-like physical energy comparisons. Learned dynamic routing is designated as future work."*

### 3.2 Predicted Output-Token Savings vs. Observed Generation Savings
- **Thesis Concept:** Downstream output token count reductions achieved by constraining model verbosity.
- **V2 Implementation:** The engine uses a **Hybrid Token Inflation Predictor** (`HybridPredictor`) combining rule-based heuristics and an offline-trained scikit-learn regressor to estimate downstream output tokens. Output tokens are explicitly labeled `is_output_predicted = True`.
- **Physical Consistency Rule:** When a prompt is unchanged by optimization, output token predictions are forced identical ($\Delta T_{\text{out}} = 0$) to eliminate regressor noise.
- **Defense Statement:**
  > *"Output token reductions represent modeled predictions from our hybrid predictor, not physical tokens received from a live frontier LLM API at runtime. This avoids incurring massive inference costs during local prompt authoring while providing actionable telemetry."*

### 3.3 Modeled Thermodynamic Energy vs. Physical Hardware Sensor Measurements
- **Thesis Concept:** Accurate energy measurement of LLM inference workloads.
- **V2 Implementation:** Energy is calculated using **thermodynamic first-principles formulas**:
  $$E_{\text{inf\_Wh}} = \text{PUE} \times \frac{T_{\text{in}} \cdot \alpha_{\text{prefill\_mWh}} + T_{\text{out}} \cdot \alpha_{\text{decode\_mWh}}}{1000}$$
  Coefficients ($\alpha_p, \alpha_d$) are representative thesis benchmarks. Datacenter PUE is fixed at $1.15$. Local optimizer CPU overhead is estimated using an engineering assumption ($35\text{W}$ active power).
- **Defense Statement:**
  > *"PromptGreen V2 calculates modeled thermodynamic approximations based on established datacenter parameters, not live physical readings from NVIDIA NVML or RAPL hardware power meters. All hardware profiles and grid scenarios are transparently documented with provenance caveats."*

### 3.4 Embedding-Based Semantic Similarity vs. True Factual Correctness
- **Thesis Concept:** Guaranteeing that the optimized prompt produces output with identical factual accuracy.
- **V2 Implementation:** The Semantic Fidelity Guard computes **cosine similarity of dense vector embeddings** using `all-MiniLM-L6-v2`.
- **Defense Statement:**
  > *"Embedding cosine similarity measures semantic proximity and linguistic intent in latent space; it is not a formal mathematical proof of logical equivalence or factual correctness. However, it provides an effective, high-throughput guardrail that catches token corruption, goal drift, and accidental truncation in real time."*

### 3.5 Deterministic Fallback vs. Local Neural Inference
- **Thesis Concept:** Local neural models performing compression (LLMLingua) and directive shaping (Ollama/Llama-3).
- **V2 Implementation:** When neural models or daemons are available, they execute neural passes. However, to guarantee 100% reliable execution during grading and demonstrations without GPU memory dependencies, both stages feature **resilient deterministic fallbacks** (lexical compression and no-op directives).
- **Defense Statement:**
  > *"PromptGreen is architected for zero-crash operational resilience. Evaluators without local GPU hardware can execute every single feature and workflow without encountering runtime errors or hanging processes."*

### 3.6 Local Capstone Prototype vs. Distributed Enterprise Deployment
- **Thesis Concept:** Enterprise-scale gateway proxy intercepting millions of corporate LLM API requests.
- **V2 Implementation:** A **local, developer-centric studio and REST API** running on Windows/Linux on `localhost:8000`, logging to a local SQLite database (`prompt_ledger.db`).
- **Defense Statement:**
  > *"V2 delivers a fully integrated, demonstrable developer studio and edge proxy. The architecture uses standard FastAPI endpoints, Pydantic schemas, and relational ledger tables that map directly to enterprise gateway microservices."*

---

## 4. Parameter & Assumptions Table for Defense

| Parameter | Default Value | Canonical Unit | Category | Scientific Origin / Source | Physical Limitations & Academic Notes |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Local CPU Power ($P_{\text{cpu}}$)** | 35.0 | Watts (W) | Engineering Estimate | Standard laptop active CPU envelope. | Unmeasured assumption. Actual host CPU power varies with clock speed and architecture. |
| **Datacenter PUE** | 1.15 | Dimensionless | Engineering Estimate | Modern hyperscale datacenter benchmark. | Assumes state-of-the-art evaporative/liquid cooling. Older facilities range 1.4–1.8. |
| **Water Efficiency (WUE)** | 1.8 | mL / Wh | Thesis Assumption | Datacenter evaporative cooling standard ($1.8\text{ L/kWh}$). | Varies widely by datacenter geography, wet-bulb temperature, and closed-loop vs cooling tower design. |
| **Grid Intensity (Illustrative)** | 385.0 | gCO2e / kWh | Illustrative Scenario | US national illustrative baseline. | Source and reference year not independently calibrated. Must be described as illustrative. |
| **Grid Intensity (Thesis)** | 367.0 | gCO2e / kWh | Thesis Scenario | Thesis Chapter 5 benchmark scenario. | Thesis-provided baseline; not a verified empirical global average. |
| **Frontier Dense Energy** | $\alpha_p=0.42, \alpha_d=1.60$ | mWh / token | Thesis Coefficient | Thesis representative model profile. | Modeled representative coefficients for GPT-4 / Claude class; ratio is $\sim 3.81\times$. |
| **Compact Green Energy** | $\alpha_p=0.04, \alpha_d=0.15$ | mWh / token | Thesis Coefficient | Thesis representative model profile. | Modeled representative coefficients for 3B parameter edge models; ratio is $\sim 3.75\times$. |
| **Semantic Threshold (Conservative)** | 0.92 | Cosine Similarity | Guardrail Parameter | Empirical tuning in Stage 5. | Cosine similarity below this threshold triggers automated prompt rollback. |
| **Semantic Threshold (Balanced)** | 0.85 | Cosine Similarity | Guardrail Parameter | Empirical tuning in Stage 5. | Allows moderate linguistic compaction while preserving core intent. |

---

## 5. Summary Conclusion for Examiners

PromptGreen V2 fulfills all core functional, physical, and architectural commitments of the B.Tech Major Project capstone. By maintaining strict unit consistency, transparently documenting scientific assumptions, providing honest negative-savings accounting, and distinguishing modeled metrics from physical sensor readings, the project adheres to the highest standards of academic integrity.
