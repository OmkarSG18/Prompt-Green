# Stage 6 Phase 2 Implementation Report: Conservative Green Model Router

**Document ID:** `PG-V2-ST6-P2-REPORT-001`  
**Date:** 2026-11-22  
**Branch:** `version-2`  
**Base Commit HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Implemented Modules:** `promptgreen/engine/model_router.py`, `tests/test_model_router.py`  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  

---

## 1. Executive Summary

PromptGreen V2 Stage 6 Phase 2 introduces the **Conservative Green Model Router** (`GreenModelRouter`). The router evaluates whether an incoming LLM inference task is demonstrably suitable for execution by a lower-energy model tier (such as `compact_green`) and provides transparent, like-for-like physical energy and carbon comparisons using the foundational thermodynamic engine implemented in Phase 1.

### Core Architectural Contracts
1. **Advisory Recommendation Engine Only:** The router **never** automatically switches a user's model or mutates runtime model selection. It outputs structured advisory recommendations with explicit disclaimers.
2. **Zero External API Calls:** No external LLM providers, network endpoints, or remote inference gateways are invoked during routing decisions.
3. **No Quality Equivalence Claims:** Lower-energy models are explicitly **not** claimed to be semantically or qualitatively equivalent to frontier models.
4. **Conservative Safety Policy:** Tasks with unclear requirements, complex multi-step reasoning, mathematical/numerical precision demands, code generation/debugging, safety-critical implications, strict formatting constraints, or user model preferences are strictly barred from downgrading.
5. **Thermodynamic Unit Consistency:** Energy differences are computed in canonical Watt-hours ($\text{Wh}$) using prefill vs. decode coefficients ($\text{mWh/token}$), and carbon differences are computed in grams $\text{CO}_2\text{e}$ only when an explicit grid intensity scenario is provided.

---

## 2. Architecture & Public API

The router is implemented in `promptgreen/engine/model_router.py` and exported via `promptgreen/engine/__init__.py`.

```
┌────────────────────────────────────────────────────────────────────────┐
│                              TaskContext                               │
│  (Category, Complexity, Reasoning, Code, Math, Safety, Format, Pref)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                           GreenModelRouter                             │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │              Conservative Safety Evaluation Engine             │   │
│   │   - Rule 1: Explicit User Model Preference                    │   │
│   │   - Rule 2: Safety-Critical / High-Consequence Guards          │   │
│   │   - Rule 3: Complex Multi-Step Reasoning Protection            │   │
│   │   - Rule 4: Code Generation & Debugging Protection             │   │
│   │   - Rule 5: Numerical & Mathematical Precision Protection      │   │
│   │   - Rule 6: Strict Output Formatting Protection                │   │
│   │   - Rule 7: Adversarial / High-Rigor Phrase Detection          │   │
│   │   - Rule 8: Insufficient Information Safeguard                 │   │
│   │   - Rule 9: Candidate Capability & Energy Ranking              │   │
│   │   - Rule 10: Simple / Low-Complexity Down-Routing              │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │                                    │
│                                   ▼                                    │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │             Like-for-Like Thermodynamic Comparison             │   │
│   │   - Inference Energy: E = PUE * (Tin*alpha_in + Tout*alpha_out)│   │
│   │   - Carbon Abatement: DeltaC = DeltaE * I_grid                 │   │
│   │   - Optimizer Overhead Cancels Out (Downstream Like-for-Like)  │   │
│   └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      ModelRoutingRecommendation                        │
│   (Outcome, Recommended Tier, Suitability, Confidence, Rejections,     │
│    Assumptions, TierEnergyComparison, TierCarbonComparison, Disclaimer)│
└────────────────────────────────────────────────────────────────────────┘
```

### Public API Dataclasses and Enums

```python
class RoutingOutcome(str, Enum):
    KEEP_CURRENT_MODEL = "KEEP_CURRENT_MODEL"
    RECOMMEND_LOWER_ENERGY_TIER = "RECOMMEND_LOWER_ENERGY_TIER"
    NO_SAFE_DOWNGRADE = "NO_SAFE_DOWNGRADE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"

class TaskCategory(str, Enum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    SIMPLE_SUMMARIZATION = "simple_summarization"
    GENERAL_SUMMARIZATION = "general_summarization"
    TRANSLATION = "translation"
    COMPLEX_REASONING = "complex_reasoning"
    CODE_GENERATION = "code_generation"
    MATHEMATICAL = "mathematical"
    SAFETY_CRITICAL = "safety_critical"
    UNKNOWN = "unknown"

class TaskComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"

class RoutingConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNCERTAIN = "UNCERTAIN"
```

### Core Router Methods

1. `recommend(current_model_tier, task_context=None, input_tokens=100, expected_output_tokens=100, pue=1.15, grid_scenario=None, ...)`:
   Evaluates task context and candidate tiers to generate a comprehensive `ModelRoutingRecommendation`.
2. `compare_tiers(current_tier, candidate_tier, input_tokens, expected_output_tokens, pue=1.15, grid_scenario=None, custom_grid_provenance=None)`:
   Executes direct pairwise physical thermodynamic comparison between any two tiers.

---

## 3. Conservative Suitability Logic & Rules

The routing engine enforces ten hierarchical decision rules to protect output quality and reliability:

| Rule | Trigger Condition | Decision Outcome | Rationale |
|---|---|---|---|
| **Rule 1** | User specified `user_model_preference` matching current tier | `KEEP_CURRENT_MODEL` | Explicit user preference takes absolute priority over automated optimization. |
| **Rule 2** | `is_safety_critical=True` or `task_category == SAFETY_CRITICAL` | `NO_SAFE_DOWNGRADE` | Safety-critical guidance requires verified high-capacity frontier models; downgrading is strictly prohibited. |
| **Rule 3** | `requires_deep_reasoning=True`, `COMPLEX_REASONING`, or `complexity == HIGH` | `NO_SAFE_DOWNGRADE` | Deductive reasoning depth drops non-linearly in compact models; severe risk of logical fallacies. |
| **Rule 4** | `requires_code_generation=True` or `task_category == CODE_GENERATION` | `NO_SAFE_DOWNGRADE` | Code generation and debugging require extensive programming language syntax representation. |
| **Rule 5** | `requires_math_precision=True` or `task_category == MATHEMATICAL` | `NO_SAFE_DOWNGRADE` | Smaller models hallucinate arithmetic intermediate steps and symbolic proofs. |
| **Rule 6** | `requires_strict_format=True` | `NO_SAFE_DOWNGRADE` | Adherence to strict JSON schemas or formal grammars cannot be guaranteed on compact models. |
| **Rule 7** | Adversarial high-rigor phrasing detected (`"think deeply"`, `"be extremely accurate"`, etc.) | `NO_SAFE_DOWNGRADE` | Deliberation and extreme precision demands cannot be guaranteed on compact models. |
| **Rule 8** | `task_category == UNKNOWN` or `task_complexity == UNKNOWN` | `INSUFFICIENT_INFORMATION` | Ambiguous or missing task information produces a conservative halt rather than an optimistic downgrade. |
| **Rule 9** | Current tier is already the lowest available energy tier (`compact_green`) | `KEEP_CURRENT_MODEL` | No candidate tier offers lower physical energy consumption. |
| **Rule 10** | Eligible simple task (`CLASSIFICATION`, `EXTRACTION`, `SIMPLE_SUMMARIZATION`) | `RECOMMEND_LOWER_ENERGY_TIER` | Demonstrably low-complexity tasks can be serviced by `compact_green`, achieving major energy savings. |

---

## 4. Energy & Carbon Comparison Methodology

The router reuses the Phase 1 thermodynamic engine (`calculate_inference_energy_wh` and `calculate_net_carbon_g`) rather than duplicating equations.

### 1. Like-for-Like Physical Comparison
Comparisons hold all non-model variables constant:
- **Input Tokens ($T_{\text{in}}$):** Identical for both tiers.
- **Expected Output Tokens ($T_{\text{out}}$):** Modeled under identical length assumptions.
- **Datacenter PUE:** Identical datacenter facility overhead applied equally.
- **Optimizer Overhead ($E_{\text{local\_opt}}$):** The same prompt optimization is applied before inference regardless of the downstream tier chosen; therefore, optimizer energy cancels out in downstream model comparison ($\Delta E = E_{\text{curr}} - E_{\text{cand}}$).

### 2. Equations
$$\Delta E_{\text{saved\_Wh}} = \text{PUE} \times \left[ \frac{T_{\text{in}} \cdot (\alpha_{\text{prefill\_curr}} - \alpha_{\text{prefill\_cand}}) + T_{\text{out}} \cdot (\alpha_{\text{decode\_curr}} - \alpha_{\text{decode\_cand}})}{1000} \right]$$

$$\Delta C_{\text{saved\_gCO2e}} = \frac{\Delta E_{\text{saved\_Wh}}}{1000} \times I_{\text{grid\_gCO2e/kWh}}$$

### 3. Missing Grid Scenario Guard
If `grid_scenario` is omitted (`None`), `carbon_comparison` is explicitly set to `None`. PromptGreen strictly refuses to invent carbon figures or substitute an unverified grid intensity.

---

## 5. Confidence & Uncertainty Epistemic Framework

Rather than using pseudo-precise numerical confidence scores (e.g. "87.4% confidence"), the router provides qualitative uncertainty classifications with documented limitations:

- **`HIGH`:** Complete, verified task specification for demonstrably simple tasks (e.g., low-complexity classification or structured key-value extraction) where compact models have strong empirical track records.
- **`MEDIUM`:** Standard tasks with minor ambiguity or general summarization where lower tiers are viable under normal conditions.
- **`LOW`:** Borderline tasks with mixed attributes.
- **`UNCERTAIN`:** Missing task attributes, unknown categories, or adversarial descriptions.

*Limitation Notice:* Qualitative confidence ratings reflect task specification clarity and conservative heuristics; they do **not** represent empirical benchmark accuracy or quality guarantees on user-specific datasets.

---

## 6. Why Automatic Model Switching is Excluded

Automatic model switching is intentionally excluded by design:
1. **Semantic Risk:** A compact model cannot be assumed to possess the nuanced alignment, safety filters, or domain knowledge of a frontier model.
2. **Deterministic Control:** Developers and enterprise systems require deterministic execution targets; transparent recommendations allow informed human decision-making.
3. **No External Network Dependency:** Automatic switching would necessitate provider SDK dependencies and live API key management. PromptGreen remains completely local, sandboxed, and lightweight.

---

## 7. Verification and Test Results

### 1. Full Pytest Regression Suite
```bash
python -m pytest -p no:langsmith
```
**Results:** **230 / 230 PASSED (100.0%)** in 24.15 seconds.
- `tests/test_all.py`: 8 passed (Legacy V1 end-to-end regression).
- `tests/test_carbon_engine.py`: 27 passed (Phase 1 thermodynamic engine & profiles).
- `tests/test_model_router.py`: 28 passed (Phase 2 conservative routing, edge cases, error handling).
- `tests/test_compressor.py`: 25 passed (Stage 2 compressor).
- `tests/test_output_shaper.py`: 30 passed (Stage 3 directive shaper).
- `tests/test_pipeline.py`: 20 passed (Stage 5 unified pipeline).
- `tests/test_rule_pruner.py`: 22 passed (Stage 1 rule pruner).
- `tests/test_semantic_guard.py`: 70 passed (Stage 4 semantic guardrail).

### 2. Standalone Engine Verification Suite
```bash
python verify_engine.py
```
**Results:** **10 / 10 Prompts Verified Successful (100.0%)**.

---

## 8. Summary of Active Repository State & Safeguards

- **Active Branch:** `version-2` (tracked to `origin/version-2`).
- **Current HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455` (uncommitted work held in working tree).
- **V1 Production Branch:** `main` remains untouched at `e920e8927c40dc508e1a93dace3fac3dbfac8200`.
- **Physical Backup:** `..\PromptGreen.zip` remains untouched at `120,304 bytes`.
- **Git State:** 2 modified tracked files, 9 untracked files. Zero files staged into index (`git diff --cached` is empty).

### Complete Phase 1 & 2 File Inventory

| Relative File Path | Git Tracking Status | Phase & Description |
|---|---|---|
| `promptgreen/engine/__init__.py` | **Modified (tracked)** | Exported V2 profiles, thermodynamics, and green model router API. |
| `promptgreen/engine/carbon_engine.py` | **Modified (tracked)** | Wrapped `calculate_thermodynamic()` wrapper while preserving legacy V1 engine. |
| `docs/DAY1_STAGE6_CARBON_ENGINE_AUDIT.md` | **Untracked** | Initial Stage 6 audit document (preserved). |
| `docs/DAY1_STAGE6_CORRECTIVE_AUDIT.md` | **Untracked** | Corrective audit with reconciled numerical cases (preserved). |
| `docs/DAY1_STAGE6_PHASE1_REPORT.md` | **Untracked** | Initial Phase 1 thermodynamic implementation report (preserved). |
| `docs/DAY1_STAGE6_PHASE1_PROFILE_AUDIT.md` | **Untracked** | Comprehensive profile audit and refinement report (preserved). |
| `docs/DAY1_STAGE6_PHASE2_REPORT.md` | **Untracked** | This Phase 2 model router implementation report. |
| `promptgreen/engine/model_profiles.py` | **Untracked** | V2 model profiles, hardware specs, and scenario registry. |
| `promptgreen/engine/thermodynamics.py` | **Untracked** | Canonical Watt-hour thermodynamic calculation engine. |
| `promptgreen/engine/model_router.py` | **Untracked** | Conservative Green Model Router implementation. |
| `tests/test_carbon_engine.py` | **Untracked** | 27 unit tests validating thermodynamic calculations and profile rules. |
| `tests/test_model_router.py` | **Untracked** | 28 unit tests validating model router rules, comparisons, and errors. |
