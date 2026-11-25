# PROMPTGREEN v2.0 — STAGE 6 CORRECTIVE TECHNICAL AUDIT
## Mathematical Formalization, Sourced Coefficients & Architectural Guardrails

**Date:** November 21, 2026  
**Document:** `docs/DAY1_STAGE6_CORRECTIVE_AUDIT.md`  
**Milestone:** Day 1 — Stage 6 Pre-Implementation Corrective Review (Revision 2)  
**Author:** Independent Technical Auditor (Antigravity AI on behalf of DSU Capstone Team)  
**Host Environment:** Windows 11, Intel Core i7-10610U CPU, 32 GB RAM, CPU-first / Non-CUDA execution  
**Active Git Branch:** `version-2`  
**Base Commit Checkpoint:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`  
**Audit Nature:** STRICTLY READ-ONLY CORRECTIVE REVIEW & MATHEMATICAL FORMALIZATION  

---

## 1. Executive Summary

This corrective technical audit updates and formalizes the initial Stage 6 carbon engine audit (`docs/DAY1_STAGE6_CARBON_ENGINE_AUDIT.md`). It incorporates a line-by-line review of the PromptGreen Capstone Project Thesis (*Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable Large Language Model Inference*, DSU 2026, particularly Chapter 1: Objectives & Scope, Chapter 2: Literature Survey, Chapter 5: Carbon Engine Methodology, pages 17–18, and Chapter 9: Conclusion).

### Core Audit Mandates Established
1. **Canonical Energy Standard:** Adopt **Watt-hours ($\text{Wh}$)** as the unified internal energy currency.
2. **Dimensional & Equation Reconciliation:** Formally document and correct unit ambiguities in the thesis formula when per-token coefficients are expressed in $\text{mWh}$ versus $\text{Wh}$ versus legacy $\text{mJ}$.
3. **Reproducible Numerical Scenarios:** Document exact, independently verified arithmetic for all test scenarios, explicitly distinguishing between different regional grid intensity baselines (Illustrative US grid-intensity scenario: $385.0\text{ gCO}_2\text{e/kWh}$, source and reference year not independently verified, versus $367.0\text{ gCO}_2\text{e/kWh}$ thesis pp. 17–18 baseline scenario).
4. **Distinction of Two Zero-Token Cases:** Rigorously differentiate a **Mathematical No-Op** (zero energy, zero impact) from an **Empty Prompt Processed by the Optimizer** (zero inference savings, non-zero CPU overhead, resulting in net carbon debt).
5. **Configurable Optimizer Power Modeling:** Clarify that a fixed $35\text{W}$ CPU figure is an unmeasured, configurable engineering estimate, not a measured property of the user's laptop.
6. **Transparent Coefficient Provenance:** Explicitly designate the thesis model tier coefficients as *"Thesis-provided representative coefficients; external provenance and independent calibration not yet verified."*
7. **Water Footprint Attribution:** Formalize $\text{WUE} = 1.8\text{ mL/Wh}$ ($1.8\text{ L/kWh}$) as an illustrative assumed water-use coefficient rather than universal data-center water consumption.

---

## 2. Mathematical Unit Validation & Inconsistency Resolution

### 2.1 Dimensional Definitions

PromptGreen V2 strictly defines and enforces the following physical dimensions across all modules:

| Metric / Symbol | Dimension | Unit Name | Equivalence / Definition |
| :--- | :--- | :--- | :--- |
| **Power ($P$)** | Power | Watt ($\text{W}$) | $1\text{ W} = 1\text{ J/s}$ |
| **Energy ($E$)** | Energy | Watt-hour ($\text{Wh}$) | **Canonical Internal Currency**: $1\text{ Wh} = 3,600\text{ J} = 3.6 \times 10^6\text{ mJ}$ |
| **Token Energy ($\alpha$)** | Specific Energy | milliWatt-hour / token ($\text{mWh/tok}$) | $1\text{ mWh} = 10^{-3}\text{ Wh} = 3.6\text{ J} = 3,600\text{ mJ}$ |
| **Legacy V1 Energy** | Specific Energy | milliJoule / token ($\text{mJ/tok}$) | $1\text{ mJ} = 10^{-3}\text{ J} = 2.778 \times 10^{-7}\text{ Wh} \approx 0.0002778\text{ mWh}$ |
| **Grid Intensity ($I_{\text{grid}}$)** | Carbon Factor | $\text{gCO}_2\text{e / kWh}$ | Grams of $\text{CO}_2$ equivalent per kiloWatt-hour ($1\text{ kWh} = 1,000\text{ Wh}$) |
| **Water Usage ($\text{WUE}$)** | Water Factor | $\text{mL / Wh}$ | $1.8\text{ L / kWh} \equiv 1.8\text{ mL / Wh} \equiv 1.8 \times 10^{-3}\text{ L / Wh}$ |

---

### 2.2 Thesis Equation Inconsistency & Mathematical Reconciliation

The proposed thesis formula (Thesis Chapter 5, page 17) states:
$$E_{\text{inf}} = \text{PUE} \times \frac{T_{\text{in}} \cdot \alpha_{\text{prefill}} + T_{\text{out}} \cdot \alpha_{\text{decode}}}{1000}$$

#### Mathematical Analysis of the Divisor `/ 1000`
1. **If $\alpha$ is expressed in $\text{mWh / token}$:**
   - The numerator $(T_{\text{in}} \cdot \alpha_{\text{prefill}} + T_{\text{out}} \cdot \alpha_{\text{decode}})$ is in **$\text{mWh}$**.
   - Dividing by $1,000$ scales $\text{mWh} \to \text{Wh}$.
   - The resulting $E_{\text{inf}}$ is dimensionally in **Watt-hours ($\text{Wh}$)**:
     $$E_{\text{inf, Wh}} = \text{PUE} \times \left( \frac{T_{\text{in}} \cdot \alpha_{\text{prefill, mWh}} + T_{\text{out}} \cdot \alpha_{\text{decode, mWh}}}{1000} \right)$$
2. **If $\alpha$ is expressed in $\text{Wh / token}$:**
   - The numerator is already in **$\text{Wh}$**.
   - Dividing by $1,000$ in this case is a dimensional error that produces an answer in **kiloWatt-hours ($\text{kWh}$)** or scales the result $1,000\times$ too small if labeled $\text{Wh}$.
   - When $\alpha$ is in $\text{Wh/tok}$, the division must be omitted:
     $$E_{\text{inf, Wh}} = \text{PUE} \times \left( T_{\text{in}} \cdot \alpha_{\text{prefill, Wh}} + T_{\text{out}} \cdot \alpha_{\text{decode, Wh}} \right)$$
3. **If $\alpha$ is expressed in legacy $\text{mJ / token}$:**
   - The numerator is in $\text{mJ}$.
   - Converting $\text{mJ} \to \text{Wh}$ requires dividing by $3.6 \times 10^6$ ($3,600\text{ s/h} \times 1,000\text{ mJ/J}$):
     $$E_{\text{inf, Wh}} = \frac{T_{\text{in}} \cdot \alpha_{\text{mJ}} + T_{\text{out}} \cdot \alpha_{\text{mJ}}}{3.6 \times 10^6}$$

#### Formal Architectural Decision
To eliminate unit ambiguity, PromptGreen V2 explicitly defines dataclass fields with their exact units in the variable name:
- Stored tier coefficients: `alpha_prefill_mwh`, `alpha_decode_mwh` (in $\text{mWh/token}$).
- Calculated inference energy: `energy_inf_wh` (in $\text{Wh}$, via `/ 1000`).
- Conversion to carbon: Energy in $\text{Wh}$ is divided by $1,000$ to obtain $\text{kWh}$ before multiplying by $I_{\text{grid}}$:
  $$C_{\text{inf, gCO}_2\text{e}} = \left( \frac{E_{\text{inf, Wh}}}{1000} \right) \times I_{\text{grid}} = E_{\text{inf, Wh}} \times \left( \frac{I_{\text{grid}}}{1000} \right)$$

---

## 3. Independent Numerical Verification Matrix

All scenarios below have been independently calculated and verified using Python floating-point arithmetic. Intermediate values and explicit units are presented.

### 3.1 Overview of Numerical Test Scenarios

```
Scenario 1A: Mathematical No-Op (Zero tokens, zero execution)
Scenario 1B: Empty Prompt Processed by Optimizer (Zero tokens, active CPU overhead)
Scenario 2A: Normal Inference (Illustrative US Grid Scenario: 385.0 gCO2e/kWh; source/year unverified)
Scenario 2B: Normal Inference (Thesis pp. 17-18 Baseline Scenario: 367.0 gCO2e/kWh)
Scenario 3:  Marginal Compression with Carbon Debt (Compact Green)
```

---

### 3.2 Complete Scenario Parameters & Calculation Walkthroughs

```
====================================================================================================
PARAMETER                       CASE 1A          CASE 1B          CASE 2A          CASE 2B          CASE 3
====================================================================================================
Original Input Tokens (Tin,orig) 0 tok           0 tok            120 tok          120 tok          18 tok
Optimized Input Tokens (Tin,opt) 0 tok           0 tok            60 tok           60 tok           17 tok
Original Output Tokens (Tout,orig) 0 tok         0 tok            250 tok          250 tok          10 tok
Optimized Output Tokens (Tout,opt) 0 tok         0 tok            150 tok          150 tok          10 tok
Model Tier                      Frontier Dense   Frontier Dense   Frontier Dense   Frontier Dense   Compact Green
Prefill Coeff (alpha_pref)      0.42 mWh/tok     0.42 mWh/tok     0.42 mWh/tok     0.42 mWh/tok     0.04 mWh/tok
Decode Coeff (alpha_dec)        1.60 mWh/tok     1.60 mWh/tok     1.60 mWh/tok     1.60 mWh/tok     0.15 mWh/tok
Datacenter PUE                  1.15             1.15             1.15             1.15             1.15
Optimizer Latency (t_opt)       0.0 ms           5.0 ms           180.0 ms         180.0 ms         220.0 ms
CPU Power Est (P_cpu)           0.0 W            35.0 W           35.0 W           35.0 W           35.0 W
Grid Carbon Intensity (I_grid)  385.0 gCO2e/kWh* 385.0 gCO2e/kWh* 385.0 gCO2e/kWh* 367.0 gCO2e/kWh† 385.0 gCO2e/kWh*
Water Coeff (WUE)               1.8 mL/Wh        1.8 mL/Wh        1.8 mL/Wh        1.8 mL/Wh        1.8 mL/Wh
----------------------------------------------------------------------------------------------------
Original Energy (E_orig)        0.0000000 Wh     0.0000000 Wh     0.5179600 Wh     0.5179600 Wh     0.0025530 Wh
Optimized Energy (E_opt)        0.0000000 Wh     0.0000000 Wh     0.3049800 Wh     0.3049800 Wh     0.0025070 Wh
Gross Energy Savings (dE_gross) 0.0000000 Wh     0.0000000 Wh     0.2129800 Wh     0.2129800 Wh     0.0000460 Wh
Optimizer Overhead (E_local_opt) 0.0000000 Wh    0.0000486 Wh     0.0017500 Wh     0.0017500 Wh     0.0021389 Wh
Net Energy Savings (dE_net)     0.0000000 Wh    -0.0000486 Wh     0.2112300 Wh     0.2112300 Wh    -0.0020929 Wh
----------------------------------------------------------------------------------------------------
Net Carbon per Request          0.00000000 gCO2e -0.00001872 gCO2e 0.08132355 gCO2e 0.07752141 gCO2e -0.00080576 gCO2e
Net Carbon per 1,000 Requests   0.000000 gCO2e  -0.018715 gCO2e  +81.323550 gCO2e +77.521410 gCO2e -0.805762 gCO2e
Net Water per Request           0.0000000 mL    -0.0000875 mL    0.3802140 mL     0.3802140 mL    -0.0037672 mL
Net Water per 1,000 Requests    0.00000 mL      -0.08750 mL      +380.21400 mL    +380.21400 mL    -3.76720 mL
----------------------------------------------------------------------------------------------------
Outcome Classification          Mathematical     Empty Pipeline   Substantial Net  Substantial Net  Net Carbon Debt
                                No-Op            Carbon Debt      Abatement        Abatement (p.17) (Overhead Exceeded)
====================================================================================================
* Illustrative US grid-intensity scenario: 385 gCO2e/kWh. Source and reference year not independently verified.
† Thesis pp. 17–18 baseline scenario: 367 gCO2e/kWh.
Neither value represents a universal grid intensity.
```

---

### 3.3 Detailed Step-by-Step Scenario Walkthroughs

#### Case 1A: Mathematical No-Op
- **Condition:** Pipeline is never invoked (or bypasses execution entirely).
- **Inference Energy:**
  $$E_{\text{inf, orig}} = 1.15 \times \frac{(0 \times 0.42) + (0 \times 1.60)}{1000} = 0.0000000\text{ Wh}$$
  $$E_{\text{inf, opt}} = 0.0000000\text{ Wh} \implies \Delta E_{\text{gross}} = 0.0000000\text{ Wh}$$
- **Optimizer Overhead:** $E_{\text{local\_opt}} = 0.0000000\text{ Wh}$.
- **Net Balances:**
  $$\Delta E_{\text{net}} = 0.0000000\text{ Wh}, \quad \Delta C_{\text{net}} = 0.000000\text{ gCO}_2\text{e}, \quad W_{\text{saved}} = 0.00000\text{ mL}$$
- **Outcome:** Clean boundary zero without division-by-zero or numerical artifacts.

#### Case 1B: Empty Prompt Processed by Optimizer
- **Condition:** User passes an empty string `""` into `PromptGreenPipeline.optimize_prompt()`. The pipeline runs Stage 1–4 checks, taking $t_{\text{opt}} = 5.0\text{ ms}$ on CPU, producing 0 tokens input and 0 tokens output.
- **Inference Energy:**
  $$E_{\text{inf, orig}} = 0.0000000\text{ Wh}, \quad E_{\text{inf, opt}} = 0.0000000\text{ Wh} \implies \Delta E_{\text{gross}} = 0.0000000\text{ Wh}$$
- **Optimizer Overhead:**
  $$E_{\text{local\_opt}} = 35.0\text{ W} \times \left( \frac{5.0 \times 10^{-3}\text{ s}}{3600\text{ s/h}} \right) = 35 \times 1.38889 \times 10^{-6} = 0.00004861\text{ Wh}$$
- **Net Balances:**
  $$\Delta E_{\text{net}} = 0.0000000 - 0.00004861 = -0.00004861\text{ Wh}$$
  $$\Delta C_{\text{net, 1k}} = \left( \frac{-0.00004861\text{ Wh} \times 1000}{1000\text{ Wh/kWh}} \right) \times 385.0\text{ gCO}_2\text{e/kWh} = -0.018715\text{ gCO}_2\text{e}$$
  $$W_{\text{saved, 1k}} = -0.00004861\text{ Wh} \times 1.8\text{ mL/Wh} \times 1000 = -0.08750\text{ mL}$$
- **Outcome:** Correctly identifies that processing an empty prompt consumes local CPU energy while generating zero inference savings, resulting in a **Net Carbon Debt**.

#### Case 2A: Normal Inference — Illustrative US Grid-Intensity Scenario ($I_{\text{grid}} = 385.0\text{ gCO}_2\text{e/kWh}$)
- **Grid Intensity Note:** Illustrative US grid-intensity scenario: 385 gCO2e/kWh. Source and reference year not independently verified. Does not represent a universal grid intensity.
- **Inputs:** $T_{\text{in}}: 120 \to 60\text{ tok}$, $T_{\text{out}}: 250 \to 150\text{ tok}$, Frontier Dense ($0.42 / 1.60\text{ mWh}$), $\text{PUE} = 1.15$, $t_{\text{opt}} = 180.0\text{ ms}$ ($35\text{W}$).
- **Step 1: Original Inference Energy:**
  $$E_{\text{inf, orig}} = 1.15 \times \frac{(120 \times 0.42) + (250 \times 1.60)}{1000} = 1.15 \times \frac{50.4 + 400.0}{1000} = 1.15 \times 0.4504 = 0.51796\text{ Wh}$$
- **Step 2: Optimized Inference Energy:**
  $$E_{\text{inf, opt}} = 1.15 \times \frac{(60 \times 0.42) + (150 \times 1.60)}{1000} = 1.15 \times \frac{25.2 + 240.0}{1000} = 1.15 \times 0.2652 = 0.30498\text{ Wh}$$
- **Step 3: Gross Energy Savings:**
  $$\Delta E_{\text{gross}} = 0.51796 - 0.30498 = 0.21298\text{ Wh}$$
- **Step 4: Optimizer Energy Overhead:**
  $$E_{\text{local\_opt}} = 35.0\text{ W} \times \left( \frac{180.0 \times 10^{-3}\text{ s}}{3600\text{ s/h}} \right) = 35 \times 0.00005 = 0.00175\text{ Wh}$$
- **Step 5: Net Energy Savings:**
  $$\Delta E_{\text{net}} = 0.21298 - 0.00175 = 0.21123\text{ Wh}$$
- **Step 6: Net Carbon Abatement ($I_{\text{grid}} = 385.0\text{ gCO}_2\text{e/kWh}$):**
  $$\Delta C_{\text{net, per inf}} = \left( \frac{0.21123}{1000} \right) \times 385.0 = 0.08132355\text{ gCO}_2\text{e}$$
  $$\Delta C_{\text{net, 1k}} = 0.08132355 \times 1000 = \mathbf{+81.32355\text{ gCO}_2\text{e}}$$
- **Step 7: Datacenter Water Savings ($\text{WUE} = 1.8\text{ mL/Wh}$):**
  $$W_{\text{saved, per inf}} = 0.21123 \times 1.8 = 0.380214\text{ mL} \implies W_{\text{saved, 1k}} = \mathbf{+380.214\text{ mL}}$$

#### Case 2B: Normal Inference — Thesis pp. 17–18 Baseline Scenario ($I_{\text{grid}} = 367.0\text{ gCO}_2\text{e/kWh}$)
- **Context:** Pages 17–18 of the thesis specify an alternative illustrative carbon intensity factor of $367.0\text{ gCO}_2\text{e/kWh}$.
- **Net Energy Savings:** Exactly identical to Case 2A: $\Delta E_{\text{net}} = 0.21123\text{ Wh}$.
- **Step 6: Net Carbon Abatement ($I_{\text{grid}} = 367.0\text{ gCO}_2\text{e/kWh}$):**
  $$\Delta C_{\text{net, per inf}} = \left( \frac{0.21123}{1000} \right) \times 367.0 = 0.07752141\text{ gCO}_2\text{e}$$
  $$\Delta C_{\text{net, 1k}} = 0.07752141 \times 1000 = \mathbf{+77.52141\text{ gCO}_2\text{e}}$$
- **Reconciliation Note:**
  $$\frac{81.32355\text{ gCO}_2\text{e}}{0.21123\text{ Wh}} \times 1000 = 385.0\text{ gCO}_2\text{e/kWh} \quad (\text{Illustrative US scenario; source/year unverified})$$
  $$\frac{77.52141\text{ gCO}_2\text{e}}{0.21123\text{ Wh}} \times 1000 = 367.0\text{ gCO}_2\text{e/kWh} \quad (\text{Thesis pp. 17–18 baseline scenario})$$
  Both values are mathematically exact for their respective grid intensities and must not be mixed silently. Neither represents a universal grid intensity.

#### Case 3: Marginal Compression with Carbon Debt (Compact Green)
- **Inputs:** $T_{\text{in}}: 18 \to 17\text{ tok}$, $T_{\text{out}}: 10 \to 10\text{ tok}$, Compact Green ($0.04 / 0.15\text{ mWh}$), $\text{PUE} = 1.15$, $t_{\text{opt}} = 220.0\text{ ms}$ ($35\text{W}$), $I_{\text{grid}} = 385.0\text{ gCO}_2\text{e/kWh}$.
- **Step 1: Original Inference Energy:**
  $$E_{\text{inf, orig}} = 1.15 \times \frac{(18 \times 0.04) + (10 \times 0.15)}{1000} = 1.15 \times \frac{0.72 + 1.50}{1000} = 1.15 \times 0.00222 = 0.0025530\text{ Wh}$$
- **Step 2: Optimized Inference Energy:**
  $$E_{\text{inf, opt}} = 1.15 \times \frac{(17 \times 0.04) + (10 \times 0.15)}{1000} = 1.15 \times \frac{0.68 + 1.50}{1000} = 1.15 \times 0.00218 = 0.0025070\text{ Wh}$$
- **Step 3: Gross Energy Savings:**
  $$\Delta E_{\text{gross}} = 0.0025530 - 0.0025070 = 0.0000460\text{ Wh} \quad (0.046\text{ mWh})$$
- **Step 4: Optimizer Energy Overhead:**
  $$E_{\text{local\_opt}} = 35.0\text{ W} \times \left( \frac{220.0 \times 10^{-3}\text{ s}}{3600\text{ s/h}} \right) = 35 \times 0.00006111 = 0.00213889\text{ Wh}$$
- **Step 5: Net Energy Savings:**
  $$\Delta E_{\text{net}} = 0.0000460 - 0.00213889 = \mathbf{-0.00209289\text{ Wh}} \quad (\text{Net Energy Deficit})$$
- **Step 6: Net Carbon Impact ($I_{\text{grid}} = 385.0\text{ gCO}_2\text{e/kWh}$):**
  $$\Delta C_{\text{net, per inf}} = \left( \frac{-0.00209289}{1000} \right) \times 385.0 = -0.00080576\text{ gCO}_2\text{e}$$
  $$\Delta C_{\text{net, 1k}} = \mathbf{-0.80576\text{ gCO}_2\text{e}} \quad (\text{Carbon Debt})$$
- **Step 7: Datacenter Water Impact ($\text{WUE} = 1.8\text{ mL/Wh}$):**
  $$W_{\text{saved, per inf}} = -0.00209289 \times 1.8 = -0.0037672\text{ mL} \implies W_{\text{saved, 1k}} = \mathbf{-3.7672\text{ mL}}$$
- **Critical Verification:** The optimizer consumed $46.5\times$ more energy ($0.002139\text{ Wh}$) than was saved by the single compressed token ($0.000046\text{ Wh}$). The engine strictly preserves the negative sign and flags a **Net Carbon Debt**.

---

## 4. Optimizer Energy Overhead ($E_{\text{local\_opt}}$) Reality & Limitations

### 4.1 Evaluation of Fixed 35W Power Assumption
The formula used in the audit:
$$E_{\text{local\_opt}} = P_{\text{cpu\_est}} \times \left( \frac{t_{\text{total\_latency\_ms}}}{1000 \times 3600} \right)$$
applies a default package power assumption of $P_{\text{cpu\_est}} = 35.0\text{ W}$.

#### Scientific Limitations to Document
1. **Configurable Estimate vs. Measurement:** A fixed $35\text{W}$ value is an engineering assumption based on the TDP rating of typical Intel Core i7 mobile processors under AVX-2 / PyTorch tensor execution. It is **NOT an empirical physical measurement** of the user's specific laptop hardware.
2. **Total System vs. Incremental Active Power:**
   - Total system power includes display backlight, DRAM, SSD, and Wi-Fi ($~15\text{W}$ base).
   - If idle power is $12\text{W}$ and active optimization peaks at $35\text{W}$, the *incremental* power attributable strictly to PromptGreen is $23\text{W}$.
   - Using full $35\text{W}$ is an intentionally conservative bound that avoids understating optimizer overhead.
3. **Wall-Clock Latency vs. Active CPU Time:**
   - $t_{\text{total\_latency\_ms}}$ measures elapsed wall-clock time.
   - If the process is descheduled or waits for file I/O, the CPU is not drawing peak load continuously.
4. **Implementation Contract:**
   The parameter `p_cpu_watts` must be exposed in configuration (default: $35.0\text{W}$, configurable from $5.0\text{W}$ to $125.0\text{W}$), and outputs must state:
   `"Estimated CPU optimization energy modeled at 35.0W active package power."`

---

## 5. Model Tier Energy Coefficient Provenance

### 5.1 Formal Provenance Classification
For the four model tiers specified in the thesis:
- **Tier 1 (Frontier Dense):** $\alpha_{\text{pref}} = 0.42\text{ mWh}$, $\alpha_{\text{dec}} = 1.60\text{ mWh}$
- **Tier 2 (Large Reasoning):** $\alpha_{\text{pref}} = 0.35\text{ mWh}$, $\alpha_{\text{dec}} = 1.35\text{ mWh}$
- **Tier 3 (Mid-Tier MoE/Dense):** $\alpha_{\text{pref}} = 0.24\text{ mWh}$, $\alpha_{\text{dec}} = 0.92\text{ mWh}$
- **Tier 4 (Compact Green):** $\alpha_{\text{pref}} = 0.04\text{ mWh}$, $\alpha_{\text{dec}} = 0.15\text{ mWh}$

PromptGreen V2 will formally classify and display these values with the following exact designation:

> **"Thesis-provided representative coefficients; external provenance and independent calibration not yet verified."**

### 5.2 Rationale
1. While literature (Samsi et al. 2023; Luccioni et al. 2023) establishes that decode energy is $3\times$ to $5\times$ prefill energy, the specific decimal values ($0.42, 1.60$, etc.) are architectural modeling baselines introduced in the thesis, not published empirical tables from Meta, OpenAI, or NVIDIA.
2. Real-world inference power fluctuates significantly based on tensor parallelism ($1\times, 2\times, 4\times, 8\times\text{ GPUs}$), quantization (INT4, FP8, FP16), and batch concurrency.
3. The engine will provide a `CustomModelProfile` registration hook allowing users to inject verified RAPL or NVML measurements.

---

## 6. Hardware Profile Validation & TDP Limits

### 6.1 Why TDP Alone Is Insufficient
Dividing Thermal Design Power by token throughput yields inaccurate energy figures:
- **TDP (Thermal Design Power):** Maximum thermal dissipation limit (H100: 700W, A100: 400W, L4: 72W).
- **Actual Operating Power:** During memory-bound autoregressive decoding, tensor cores sit idle waiting for memory transfers, drawing only $40\%$ to $65\%$ of TDP.
- **Batching Amortization:** In production, requests are batched ($B=8, 16, 32$). The static energy of loading model weights is shared across all tokens in the batch.
- **Formulation:**
  $$\alpha = \frac{P_{\text{active}}(\text{Watts})}{\text{Throughput}(\text{tok/s}) \times B} \quad [\text{Joules/token}] \implies \frac{\alpha_{\text{Joules}}}{3.6} \quad [\text{mWh/token}]$$

---

## 7. Output Token Estimation vs. Observation Integrity

### 7.1 Separation of Fact vs. Prediction
The carbon engine will maintain strict epistemic hygiene:
- **Tokenizer-Specific Input Measurement:** Input-token counts are deterministically measured using the `cl100k_base` BPE tokenizer when available. However, because target downstream models (e.g. Llama-3, Mistral, Claude, Gemini) employ different vocabularies and BPE/SentencePiece tokenizers, the token count measured by `cl100k_base` is tokenizer-specific and may differ from the actual tokenization of the target inference model. Furthermore, if `tiktoken` is unavailable and the offline word-count fallback ($1.3\times$ words) is engaged, the resulting token count must be explicitly labeled an **estimate**, not a deterministic measurement.
- **Predicted Output Token Reduction:** Modeled via `HybridPredictor` and Stage 3 (`output_shaper.py`) directives.
- **Rule of Disclosure:** The UI, CLI, and API must explicitly label output token savings and downstream carbon delta as **Modeled Estimates** unless an actual post-generation response token count is supplied.

---

## 8. Conservative Green Model Down-Routing

### 8.1 Safety Filters Against Inappropriate Down-Routing
The router will enforce five consecutive safety checks:
1. **User Pinning Override:** If `allow_downgrade == False`, return `NO_DOWNGRADE (User Pinned)`.
2. **Cognitive Complexity Filter:** Scans for mathematical, logical, and formal reasoning directives (`"prove"`, `"theorem"`, `"regulatory compliance"`, `"differential equation"`). If found, return `NO_DOWNGRADE (High Cognitive Complexity)`.
3. **Length Safety Gate:** Optimized input tokens must satisfy $T_{\text{in, opt}} \le 250$.
4. **Code Syntax Density:** Code token fraction must be $< 0.15$.
5. **Chain-of-Thought Marker:** Prompt must not contain CoT triggers (`"think step-by-step"`).

---

## 9. Regional Carbon Intensity & Water Usage Modeling

### 9.1 Grid Intensity Representation
- Illustrative static reference values:
  - `US`: $385.0\text{ gCO}_2\text{e / kWh}$ (Illustrative US grid-intensity scenario; source and reference year not independently verified).
  - `THESIS_GLOBAL`: $367.0\text{ gCO}_2\text{e / kWh}$ (Thesis pp. 17–18 baseline scenario).
  - `IN`: $708.0\text{ gCO}_2\text{e / kWh}$ (India national average reference).
  - `IN-WE`: $740.0\text{ gCO}_2\text{e / kWh}$ (India Western Grid reference).
  - `IN-SO`: $680.0\text{ gCO}_2\text{e / kWh}$ (India Southern Grid reference).
  - `EU`: $255.0\text{ gCO}_2\text{e / kWh}$ (European Union average reference).
  - `UK`: $210.0\text{ gCO}_2\text{e / kWh}$ (United Kingdom reference).
  - `DE`: $380.0\text{ gCO}_2\text{e / kWh}$ (Germany reference).
  - `FR`: $55.0\text{ gCO}_2\text{e / kWh}$ (France nuclear-base reference).
  - `GLOBAL`: $475.0\text{ gCO}_2\text{e / kWh}$ (Global fallback reference).
- **Universal Grid Warning:** Neither 385 nor 367 gCO2e/kWh represents a universal grid intensity. Both are illustrative scenario baselines and must not be treated as empirical measurements of any specific datacenter's real-time electricity feed.

### 9.2 Water Footprint Attribution
- $\text{WUE} = 1.8\text{ mL / Wh}$ ($1.8\text{ L / kWh}$) is defined as an **illustrative assumed water-use coefficient**.
- Outputs will explicitly differentiate:
  - Positive estimated water savings.
  - Negative estimated water savings / additional water footprint (when carbon debt occurs).
  - Unknown water footprint when facility cooling data is unavailable.
- **Universal Water Warning:** $1.8\text{ mL/Wh}$ does not apply universally to every data center (e.g. closed-loop dry chillers consume near zero direct water, whereas evaporative cooling towers in hot climates consume $> 3.0\text{ mL/Wh}$).

---

## 10. Final Stage 6 Acceptance Checklist

Before Stage 6 implementation begins, the engineering specifications must meet these eight verifiable conditions:

- [x] **Dimensional Consistency:** Internal calculations run in $\text{Wh}$, token coefficients in $\text{mWh/tok}$, carbon in $\text{gCO}_2\text{e}$.
- [x] **Reproducibility:** Every numerical example in Section 3 is independently reproducible from stated parameters.
- [x] **Grid Intensity Pairing:** Carbon savings explicitly identify their exact grid intensity (Illustrative US scenario: $385.0\text{ gCO}_2\text{e/kWh}$ with source/year unverified, vs. Thesis pp. 17–18 baseline scenario: $367.0\text{ gCO}_2\text{e/kWh}$). Neither is treated as universal.
- [x] **Single Overhead Deduction:** $E_{\text{local\_opt}}$ is deducted exactly once in the net energy balance equation.
- [x] **Preservation of Negative Savings:** Carbon debt resulting from optimizer overhead is preserved as negative savings.
- [x] **No Unverified Claims:** 35W CPU power and tier coefficients are formally labeled as estimates and representative baselines.
- [x] **Epistemic Separation:** Measured input tokens (via `cl100k_base` when available) are distinguished from target model tokenization and word-count estimates, and strictly separated from modeled output tokens.
- [x] **Thesis Unit Correction Documented:** The `/ 1000` scaling divisor is formally documented as a dimensional necessity for $\text{mWh} \to \text{Wh}$.

---

## 11. Git Status & Safeguard Statement

- **Active Branch:** `version-2` (Tracking `origin/version-2`)
- **HEAD Commit:** `0a4097172c6cd1f75cc20abe8dc591f17092a455`
- **Main Branch:** `e920e8927c40dc508e1a93dace3fac3dbfac8200` (Untouched)
- **Physical Backup:** `PromptGreen.zip` (120,304 bytes, Untouched)
- **Zero changes staged or committed.**
- **Zero application code or tests modified.**

```text
On branch version-2
Your branch is up to date with 'origin/version-2'.

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	docs/DAY1_STAGE6_CARBON_ENGINE_AUDIT.md
	docs/DAY1_STAGE6_CORRECTIVE_AUDIT.md

nothing added to commit but untracked files present (use "git add" to track)
```
