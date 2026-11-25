# Stage 6 Phase 1: Model, Hardware, and Regional Grid Profile Audit & Refinement Report

**Document ID:** `PG-V2-ST6-P1-AUDIT-002`  
**Date:** 2026-11-22  
**Branch:** `version-2`  
**Starting Commit HEAD:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Audited Component:** `promptgreen/engine/model_profiles.py`, `thermodynamics.py`, & Carbon Engine Integration  
**Status:** COMPLETE & INDEPENDENTLY VERIFIED  

---

## 1. Executive Summary & Four Corrective Resolutions

This report provides the finalized technical audit and source-code refinement for the model profiles, hardware configurations, and grid-intensity scenarios introduced in Stage 6 Phase 1 of PromptGreen V2.

Four specific issues identified in the prior review have been resolved:

1. **Correction of the 708.0 Custom-Intensity Example:**
   - The value 708.0 $\text{gCO}_2\text{e/kWh}$ is **never** described as verified.
   - All custom grid-intensity inputs are strictly classified as **user-supplied values**.
   - PromptGreen cleanly decouples the numeric intensity from independent verification of its source.
   - Custom provenance can now be supplied independently via the `custom_grid_provenance` parameter. When omitted, the default provenance explicitly records: `"User-supplied custom grid intensity: <val> gCO2e/kWh (unverified user input; independent source verification not performed)."`.
2. **Renaming of Misleading Grid Scenario Identifiers:**
   - `US` is renamed to **`ILLUSTRATIVE_385`**.
   - `THESIS_GLOBAL` is renamed to **`THESIS_367`**.
   - Descriptions are codified to prevent geographic misattribution:
     - `ILLUSTRATIVE_385`: `"385 gCO2e/kWh, illustrative scenario, source and reference year unverified."`
     - `THESIS_367`: `"367 gCO2e/kWh, thesis-provided scenario, not independently calibrated and not a verified global average."`
   - Neither scenario is silently treated as a regional or universal default.
3. **Reconsideration of Custom Model Profile Validation:**
   - The rigid rule rejecting profiles where $\alpha_{\text{decode}} < \alpha_{\text{prefill}}$ has been removed.
   - Custom profiles with unusual ratios (e.g. specialized speculative draft or non-autoregressive models) are accepted without raising an exception.
   - Instead, the engine flags `is_ratio_unusual = True` and populates the `ratio_note` metadata field.
   - Robust validation remains strictly enforced for numeric types (`int` or `float`), finite numbers (`math.isfinite`, rejecting `NaN`, `+Inf`, `-Inf`), boolean rejection, strictly positive values ($> 0$), and non-empty string identifiers.
   - The four thesis-provided profiles and their exact coefficients are preserved.
4. **Reconciliation of Git Working-Tree Status:**
   - The inaccurate phrasing in the earlier report ("clean working tree with no staged or committed changes") has been rectified.
   - The working tree is **not** clean: it contains 2 modified tracked files and 7 untracked implementation/audit files.
   - A complete inventory of every Phase 1 file and its Git status is documented below. No files were discarded, reset, staged, or committed.

---

## 2. Final Grid Scenario Identifiers & Audit

PromptGreen eliminates all unverified regional presets and retains strictly two illustrative/thesis benchmark scenarios.

### Summary Table of Audited Scenarios & Renamed Identifiers

| Previous Identifier | Final Scenario Identifier | Intensity ($\text{gCO}_2\text{e/kWh}$) | Exact Codified Description | Independently Verified? | Codebase Status |
|---|---|---|---|---|---|
| `US` | **`ILLUSTRATIVE_385`** | `385.0` | `385 gCO2e/kWh, illustrative scenario, source and reference year unverified.` | **NO** | Selectable preset |
| `THESIS_GLOBAL` | **`THESIS_367`** | `367.0` | `367 gCO2e/kWh, thesis-provided scenario, not independently calibrated and not a verified global average.` | **NO** (Thesis scenario) | Selectable preset |
| `IN` | *None* | `708.0` | *N/A (Unverified Indian regional value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `IN-WE` | *None* | `740.0` | *N/A (Unverified Western India value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `IN-SO` | *None* | `680.0` | *N/A (Unverified Southern India value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `EU` | *None* | `255.0` | *N/A (Unverified European Union value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `UK` | *None* | `210.0` | *N/A (Unverified United Kingdom value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `DE` | *None* | `380.0` | *N/A (Unverified Germany value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `FR` | *None* | `55.0` | *N/A (Unverified France value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |
| `GLOBAL` | *None* | `475.0` | *N/A (Unverified Global average value removed)* | **NO** | Placeholder in `UNAVAILABLE_REGIONAL_PLACEHOLDERS` |

### Guardrail Implementation
1. If a caller requests any removed regional identifier (`IN`, `EU`, `UK`, `DE`, `FR`, `GLOBAL`, etc.) or deprecated geographic code (`US`, `THESIS_GLOBAL`), `ModelProfileRegistry.get_grid_scenario()` raises `KeyError`:
   ```text
   KeyError: "Grid intensity for region 'IN' is unavailable without user specification: India national grid carbon intensity lacks an independently verified reference year and source in the thesis. PromptGreen will not silently substitute ILLUSTRATIVE_385 or THESIS_367. Please provide an explicit user-supplied numeric gCO2e/kWh value and specify its provenance separately."
   ```
2. If `grid_scenario` is omitted (`None`), the calculation engine raises `ValueError`:
   ```text
   ValueError: "grid_scenario must be explicitly provided (e.g. 'ILLUSTRATIVE_385', 'THESIS_367', or a user-supplied float); cannot silently invent a universal grid intensity."
   ```
3. PromptGreen refuses to silently substitute `ILLUSTRATIVE_385` or `THESIS_367` for any user prompt.

---

## 3. User-Supplied Numeric Intensity & Provenance Separation

The engine distinguishes the ingestion of a numeric intensity from independent verification of its source:

1. **User-Supplied Float Ingestion:**
   When a user supplies a numeric float (e.g. `grid_scenario=708.0`), it is treated strictly as an uncalibrated user input.
2. **Separate Provenance Tracking:**
   The `calculate_thermodynamic_impact()` function accepts `custom_grid_provenance: Optional[str] = None`.
   - If provided, the exact user-specified provenance string is attached to `EnergyCarbonResult.grid_intensity_provenance`.
   - If omitted, the default provenance string is automatically assigned:
     ```text
     "User-supplied custom grid intensity: 708.0 gCO2e/kWh (unverified user input; independent source verification not performed)."
     ```
3. **Finite & Positive Validation:**
   Numeric values must be finite numbers (`not math.isnan(x)` and `not math.isinf(x)`), cannot be booleans (`isinstance(x, bool)` is rejected), and must be strictly positive ($> 0$).

---

## 4. Custom Model Profile Validation Behavior

The model tier validation logic in `ModelTierProfile.__post_init__` was revised to accommodate non-standard model architectures without sacrificing physical or typing rigor.

### Preserved Thesis Profiles

All four thesis-provided baseline model tiers are preserved with their exact coefficients in milliWatt-hours per token ($\text{mWh/token}$):

| Tier ID | Display Name | $\alpha_{\text{prefill}}$ ($\text{mWh/tok}$) | $\alpha_{\text{decode}}$ ($\text{mWh/tok}$) | Asymmetric Ratio | Hardware ID | Provenance |
|---|---|---|---|---|---|---|
| `frontier_dense` | Frontier Dense (GPT-4o / Claude 3.5 Sonnet Class) | `0.42` | `1.60` | $3.81\times$ | `h100_pcie` | `THESIS_PROVENANCE_WARNING` |
| `large_reasoning` | Large Reasoning (Llama-3 70B / Qwen-2.5 72B Class) | `0.35` | `1.35` | $3.86\times$ | `a100_sxm4` | `THESIS_PROVENANCE_WARNING` |
| `mid_tier` | Mid-Tier MoE/Dense (Mixtral 8x7B / Command-R Class) | `0.24` | `0.92` | $3.83\times$ | `a100_sxm4` | `THESIS_PROVENANCE_WARNING` |
| `compact_green` | Compact Green (Llama-3.2 3B / Phi-3.5 3.8B Class) | `0.04` | `0.15` | $3.75\times$ | `l4_pcie` | `THESIS_PROVENANCE_WARNING` |

### Validation Rules for Custom Profiles

1. **Non-Empty String Identifiers:** `tier_id` and `hardware_id` must be non-empty strings.
2. **Strict Type Checking:** `alpha_prefill_mwh` and `alpha_decode_mwh` must be `float` or `int`. Booleans (`True`, `False`) are explicitly rejected with `TypeError`.
3. **Finite Positive Values:** Coefficients must be finite (`math.isfinite(val) == True`) and strictly positive ($> 0$). Values such as `float('nan')`, `float('inf')`, `0.0`, or `-1.5` raise `ValueError`.
4. **Non-Rejecting Ratio Inspection:**
   When a profile defines $\alpha_{\text{decode}} < \alpha_{\text{prefill}}$:
   - The profile is **not** rejected.
   - The dataclass attribute `is_ratio_unusual` is set to `True`.
   - The `ratio_note` attribute records:
     `"Unusual coefficient ratio: alpha_decode_mwh (<val>) is lower than alpha_prefill_mwh (<val>). Valid for specialized or non-autoregressive architectures."`
   - The profile functions normally throughout thermodynamic calculations.

---

## 5. GPU Hardware Profiles & Decoupling

The reference hardware profiles (`h100_pcie`, `a100_sxm4`, `l4_pcie`) provide datacenter hardware specifications:

- `h100_pcie`: TDP 700.0 W (SXM5 node thermal envelope limit; PCIe card nominal is 350W), 480.0 W heuristic operating power, 80 GB memory.
- `a100_sxm4`: TDP 400.0 W, 280.0 W heuristic operating power, 80 GB memory.
- `l4_pcie`: TDP 72.0 W, 60.0 W heuristic operating power, 24 GB memory.

### Methodological Safeguards:
1. **Manufacturer Envelope vs. Measured Energy:** TDP and operating power represent manufacturer maximum electrical/thermal limits and heuristic duty-cycle estimates. They do **not** represent measured inference energy per token.
2. **Decoupled from Core Engine:** The thermodynamic calculation engine does not query hardware power to derive energy. Energy per token is derived strictly from `ModelTierProfile` coefficients.
3. **Validation:** Hardware profiles validate that TDP, operating power, and memory are finite positive numbers and reject booleans.

---

## 6. Complete Phase 1 File Inventory & Git Working-Tree Reconciliation

The earlier profile-audit report contained an ambiguous statement: *"Git State: Clean working tree with no staged or committed changes."* While no changes were staged into the Git index or committed to history, the working tree is **not clean**; it holds active Stage 6 Phase 1 development files.

### Exact Status of All Phase 1 Files

| Relative File Path | Git Tracking Status | Description & Purpose |
|---|---|---|
| `promptgreen/engine/__init__.py` | **Modified (tracked)** | Exported V2 profiles (`ILLUSTRATIVE_385`, `THESIS_367`), hardware profiles, thermodynamic functions, and placeholders. |
| `promptgreen/engine/carbon_engine.py` | **Modified (tracked)** | Wrapped `calculate_thermodynamic()` with fallback mapping while strictly preserving legacy V1 `calculate()` and `CACHED_REGIONAL_CI`. |
| `docs/DAY1_STAGE6_CARBON_ENGINE_AUDIT.md` | **Untracked** | Initial Stage 6 audit document (preserved for historical traceability). |
| `docs/DAY1_STAGE6_CORRECTIVE_AUDIT.md` | **Untracked** | Corrective audit document with mathematically reconciled cases (preserved). |
| `docs/DAY1_STAGE6_PHASE1_REPORT.md` | **Untracked** | Initial Phase 1 implementation report (preserved). |
| `docs/DAY1_STAGE6_PHASE1_PROFILE_AUDIT.md` | **Untracked** | This comprehensive profile audit and refinement report. |
| `promptgreen/engine/model_profiles.py` | **Untracked** | V2 model profiles, hardware configurations, and scenario registry. |
| `promptgreen/engine/thermodynamics.py` | **Untracked** | Canonical Watt-hour thermodynamic calculation engine with PUE, asymmetry, and CPU deduction. |
| `tests/test_carbon_engine.py` | **Untracked** | Comprehensive test suite containing 27 unit tests for Stage 6 Phase 1. |

### Confirmation of Preservations
- **No Destructive Commands:** No `git clean`, `git reset`, `git restore`, or checkout operations were executed.
- **No Staged Files:** Zero files are staged (`git diff --cached` is empty).
- **No Commits or Pushes:** The commit history remains untouched.
- **Main Branch Preservation:** `main` remains at `e920e8927c40dc508e1a93dace3fac3dbfac8200`.
- **Physical Backup:** `..\PromptGreen.zip` remains intact at `120,304 bytes`.
- **Stage 6 Phase 2:** Green Model Routing has not been started.

---

## 7. Full Test Suite & Verification Results

### 1. Pytest Test Suite
Full repository test suite execution:
```bash
python -m pytest -p no:langsmith
```
**Results:** **202 / 202 PASSED (100.0%)** in 24.42 seconds.
- `tests/test_all.py`: 8 passed (Legacy V1 end-to-end regression).
- `tests/test_carbon_engine.py`: 27 passed (Phase 1 thermodynamic engine, Cases 1A–3, custom profile ratio tests, NaN/Inf rejection, and scenario lookups).
- `tests/test_compressor.py`: 25 passed.
- `tests/test_output_shaper.py`: 30 passed.
- `tests/test_pipeline.py`: 20 passed.
- `tests/test_rule_pruner.py`: 22 passed.
- `tests/test_semantic_guard.py`: 70 passed.

### 2. Standalone Engine Verification Suite
Execution of `verify_engine.py`:
```bash
python verify_engine.py
```
**Results:** **10 / 10 Prompts Verified Successful (100.0%)**.

---

## 8. Summary of Active Repository State

```text
On branch version-2
Your branch is up to date with 'origin/version-2'.

Changes not staged for commit:
  modified:   promptgreen/engine/__init__.py
  modified:   promptgreen/engine/carbon_engine.py

Untracked files:
  docs/DAY1_STAGE6_CARBON_ENGINE_AUDIT.md
  docs/DAY1_STAGE6_CORRECTIVE_AUDIT.md
  docs/DAY1_STAGE6_PHASE1_PROFILE_AUDIT.md
  docs/DAY1_STAGE6_PHASE1_REPORT.md
  promptgreen/engine/model_profiles.py
  promptgreen/engine/thermodynamics.py
  tests/test_carbon_engine.py

no changes added to commit (use "git add" and/or "git commit -a")
```
- **HEAD Commit:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`
- **Remote:** In sync with `origin/version-2`
