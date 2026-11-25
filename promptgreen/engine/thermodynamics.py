"""
Foundational Thermodynamic Energy, Carbon, and Water Estimation Engine for PromptGreen V2.

Standardizes on canonical internal energy units of Watt-hours (Wh).
Implements prefill vs. decode asymmetric energy modeling, datacenter PUE overhead,
dynamic CPU optimizer overhead deduction, and net carbon/water balance tracking.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union, Dict, Any

from promptgreen.engine.model_profiles import (
    ModelTierProfile,
    GridIntensityScenario,
    DEFAULT_PROFILE_REGISTRY,
    THESIS_PROVENANCE_WARNING,
    WATER_COEFFICIENT_WARNING,
    CPU_POWER_ESTIMATE_WARNING,
)


class AccountingScenario(str, Enum):
    """Explicit thermodynamic accounting scenarios to prevent unverified predictions from being blended with measured data."""
    INPUT_ONLY = "INPUT_ONLY"
    INPUT_PLUS_PREDICTED_OUTPUT = "INPUT_PLUS_PREDICTED_OUTPUT"
    INPUT_PLUS_MEASURED_OUTPUT = "INPUT_PLUS_MEASURED_OUTPUT"


@dataclass(frozen=True)
class EnergyCarbonResult:
    """
    Structured thermodynamic and environmental impact result.
    Internal energy is strictly in Watt-hours (Wh).
    Differentiates gross inference savings from net savings after optimizer overhead deduction.
    """
    # Token Counts
    tin_original: int
    tout_original: float
    tin_optimized: int
    tout_optimized: float

    # Energy Balances (in Watt-hours)
    energy_orig_wh: float
    energy_opt_wh: float
    gross_energy_saved_wh: float
    optimizer_overhead_wh: float
    net_energy_saved_wh: float

    # Carbon Balances (in gCO2e)
    grid_intensity_gco2_kwh: float
    grid_intensity_provenance: str
    net_carbon_abated_gco2: float
    net_carbon_abated_per_1k_gco2: float

    # Datacenter Water Footprint (in mL)
    net_water_saved_ml: float
    net_water_saved_per_1k_ml: float

    # Environmental Classification
    is_net_carbon_debt: bool

    # Model & Scenario Parameters
    model_tier_id: str
    model_tier_provenance: str
    pue_used: float
    wue_used_ml_per_wh: float
    cpu_power_w_used: float
    optimizer_latency_ms: float

    # Epistemic Transparency Flags
    is_output_predicted: bool = True
    is_measured: bool = False  # Explicitly documents that values are algorithmic models, not physical sensor measurements

    # Explicit Accounting Scenario Separation
    accounting_scenario: str = "INPUT_PLUS_PREDICTED_OUTPUT"
    accounting_notes: str = ""

    # Energy Component Decompositions (Canonical Wh & Modeled Joules)
    prefill_energy_opt_wh: Optional[float] = None
    decode_energy_opt_wh: Optional[float] = None
    modeled_prefill_energy_j: Optional[float] = None
    modeled_decode_energy_j: Optional[float] = None
    modeled_total_energy_j: Optional[float] = None


@dataclass(frozen=True)
class MultiScenarioEnergyResult:
    """
    Standardized multi-scenario thermodynamic result explicitly separating:
    1. input_only: Verifiable input token measurements with zero downstream output savings.
    2. input_plus_predicted_output: Exploratory modeled output estimation via HybridPredictor.
    3. input_plus_measured_output: Measured downstream generation if empirical evaluation performed.
    """
    input_only: EnergyCarbonResult
    input_plus_predicted_output: EnergyCarbonResult
    input_plus_measured_output: Optional[EnergyCarbonResult] = None
    measured_output_available: bool = False
    measured_output_metadata: Dict[str, Any] = field(default_factory=dict)


def calculate_inference_energy_wh(
    tin: Union[int, float],
    tout: Union[int, float],
    alpha_prefill_mwh: float,
    alpha_decode_mwh: float,
    pue: float = 1.15,
) -> float:
    """
    Calculate single-request LLM inference energy in Watt-hours (Wh).

    Formula:
      E_inf_Wh = PUE * (Tin * alpha_prefill_mWh + Tout * alpha_decode_mWh) / 1000

    Args:
        tin: Number of ingested input (prefill) tokens. Must be non-negative.
        tout: Number of generated output (decode) tokens. Must be non-negative.
        alpha_prefill_mwh: Energy consumed per prefill token in mWh/token. Must be > 0.
        alpha_decode_mwh: Energy consumed per decode token in mWh/token. Must be > 0.
        pue: Datacenter Power Usage Effectiveness multiplier. Must be >= 1.0 (default: 1.15).

    Returns:
        Inference energy in Watt-hours (Wh).
    """
    if isinstance(tin, bool) or not isinstance(tin, (int, float)) or not math.isfinite(tin) or tin < 0:
        raise ValueError(f"Input tokens (tin) must be a finite non-negative number, got {tin}")
    if isinstance(tout, bool) or not isinstance(tout, (int, float)) or not math.isfinite(tout) or tout < 0:
        raise ValueError(f"Output tokens (tout) must be a finite non-negative number, got {tout}")
    if isinstance(alpha_prefill_mwh, bool) or not isinstance(alpha_prefill_mwh, (int, float)) or not math.isfinite(alpha_prefill_mwh) or alpha_prefill_mwh <= 0:
        raise ValueError(f"alpha_prefill_mwh must be a finite positive number, got {alpha_prefill_mwh}")
    if isinstance(alpha_decode_mwh, bool) or not isinstance(alpha_decode_mwh, (int, float)) or not math.isfinite(alpha_decode_mwh) or alpha_decode_mwh <= 0:
        raise ValueError(f"alpha_decode_mwh must be a finite positive number, got {alpha_decode_mwh}")
    if isinstance(pue, bool) or not isinstance(pue, (int, float)) or not math.isfinite(pue) or pue < 1.0:
        raise ValueError(f"PUE must be a finite number >= 1.0 (physical efficiency lower bound), got {pue}")

    # Zero-token boundary case
    if tin == 0 and tout == 0:
        return 0.0

    # Numerator is in mWh; dividing by 1000 scales directly to canonical Wh
    energy_mwh = (float(tin) * float(alpha_prefill_mwh)) + (float(tout) * float(alpha_decode_mwh))
    energy_wh = float(pue) * (energy_mwh / 1000.0)
    return energy_wh


def estimate_optimizer_overhead_wh(
    latency_ms: Union[int, float],
    p_cpu_w: float = 35.0,
) -> float:
    """
    Estimate local optimizer CPU energy overhead in Watt-hours (Wh).

    Formula:
      E_local_opt_Wh = P_cpu_est_W * (t_opt_ms / 3_600_000)

    Note on Methodology:
      Wall-clock latency is used as a conservative proxy for CPU execution time.
      The default 35.0W CPU package power is an unmeasured engineering estimate,
      not an empirical physical measurement of the user's host laptop.

    Args:
        latency_ms: Total optimizer execution latency in milliseconds. Must be non-negative.
        p_cpu_w: Configurable CPU active power estimate in Watts (default: 35.0W). Must be > 0.

    Returns:
        Estimated optimizer compute energy in Watt-hours (Wh).
    """
    if isinstance(latency_ms, bool) or not isinstance(latency_ms, (int, float)) or not math.isfinite(latency_ms) or latency_ms < 0:
        raise ValueError(f"Optimizer latency must be a finite non-negative number, got {latency_ms}")
    if isinstance(p_cpu_w, bool) or not isinstance(p_cpu_w, (int, float)) or not math.isfinite(p_cpu_w) or p_cpu_w <= 0:
        raise ValueError(f"CPU power estimate must be a finite positive number, got {p_cpu_w}")

    if latency_ms == 0:
        return 0.0

    # 3_600_000 ms per hour (1000 ms/s * 3600 s/h)
    hours = float(latency_ms) / 3_600_000.0
    return float(p_cpu_w) * hours


def calculate_net_energy_wh(
    e_orig_wh: float,
    e_opt_wh: float,
    e_overhead_wh: float,
) -> tuple[float, float]:
    """
    Compute gross inference energy savings and net energy savings after optimizer overhead deduction.

    Formulas:
      DeltaE_gross_Wh = E_orig_Wh - E_opt_Wh
      DeltaE_net_Wh = DeltaE_gross_Wh - E_local_opt_Wh

    Returns:
        (gross_energy_saved_wh, net_energy_saved_wh)
    """
    gross_saved = float(e_orig_wh) - float(e_opt_wh)
    net_saved = gross_saved - float(e_overhead_wh)
    return gross_saved, net_saved


def calculate_net_carbon_g(
    net_energy_wh: float,
    grid_intensity_gco2_kwh: float,
) -> float:
    """
    Compute net carbon impact in grams of CO2 equivalent (gCO2e).

    Formula:
      DeltaC_net_g = (DeltaE_net_Wh / 1000) * I_grid_g_per_kWh

    Preserves negative values to explicitly represent carbon debt.

    Args:
        net_energy_wh: Net energy saved in Watt-hours (can be negative).
        grid_intensity_gco2_kwh: Regional grid emissions factor in gCO2e/kWh. Must be > 0.

    Returns:
        Net carbon abated in gCO2e (positive = savings, negative = carbon debt).
    """
    if grid_intensity_gco2_kwh is None or isinstance(grid_intensity_gco2_kwh, bool) or not isinstance(grid_intensity_gco2_kwh, (int, float)) or not math.isfinite(grid_intensity_gco2_kwh) or grid_intensity_gco2_kwh <= 0:
        raise ValueError(
            f"grid_intensity_gco2_kwh must be a finite positive number; cannot invent grid value. Got {grid_intensity_gco2_kwh}"
        )

    kwh = float(net_energy_wh) / 1000.0
    return kwh * float(grid_intensity_gco2_kwh)


def calculate_water_impact_ml(
    net_energy_wh: float,
    wue_ml_per_wh: float = 1.8,
) -> float:
    """
    Compute datacenter cooling water footprint impact in milliliters (mL).

    Formula:
      W_saved_mL = DeltaE_net_Wh * WUE_mL_per_Wh

    Preserves negative values to represent additional water consumption (water deficit).

    Args:
        net_energy_wh: Net energy saved in Watt-hours (can be negative).
        wue_ml_per_wh: Datacenter Water Usage Effectiveness in mL/Wh (default: 1.8 mL/Wh = 1.8 L/kWh).

    Returns:
        Net water saved in milliliters (positive = savings, negative = additional water footprint).
    """
    if isinstance(wue_ml_per_wh, bool) or not isinstance(wue_ml_per_wh, (int, float)) or not math.isfinite(wue_ml_per_wh) or wue_ml_per_wh < 0:
        raise ValueError(f"WUE must be a finite non-negative number, got {wue_ml_per_wh}")

    return float(net_energy_wh) * float(wue_ml_per_wh)


def calculate_thermodynamic_impact(
    tin_original: int,
    tout_original: float,
    tin_optimized: int,
    tout_optimized: float,
    model_tier: Union[str, ModelTierProfile] = "frontier_dense",
    grid_scenario: Optional[Union[str, GridIntensityScenario, float]] = None,
    custom_grid_provenance: Optional[str] = None,
    optimizer_latency_ms: float = 0.0,
    p_cpu_w: float = 35.0,
    pue: float = 1.15,
    wue_ml_per_wh: float = 1.8,
    is_output_predicted: bool = True,
    accounting_scenario: str = "INPUT_PLUS_PREDICTED_OUTPUT",
    accounting_notes: str = "",
    is_prompt_identical: bool = False,
) -> EnergyCarbonResult:
    """
    Orchestrate full thermodynamic energy, carbon, and water footprint impact evaluation.

    Args:
        tin_original: Original prompt input tokens.
        tout_original: Original prompt output tokens (predicted or observed).
        tin_optimized: Optimized prompt input tokens.
        tout_optimized: Optimized prompt output tokens (predicted or observed).
        model_tier: Model tier ID string (e.g. 'frontier_dense') or a ModelTierProfile object.
        grid_scenario: Grid scenario code string (e.g. 'ILLUSTRATIVE_385', 'THESIS_367'),
                       a GridIntensityScenario object, or an explicit float intensity in gCO2e/kWh.
                       MUST NOT BE NONE.
        custom_grid_provenance: Optional user-supplied provenance string for custom numeric float intensities.
        optimizer_latency_ms: Local optimizer execution wall-clock time in ms.
        p_cpu_w: Configurable CPU power estimate in Watts (default: 35.0W).
        pue: Datacenter PUE efficiency factor (default: 1.15).
        wue_ml_per_wh: Datacenter WUE water coefficient in mL/Wh (default: 1.8).
        is_output_predicted: Whether output token values are modeled predictions (True) or measured (False).
        accounting_scenario: Explicit accounting scenario: INPUT_ONLY, INPUT_PLUS_PREDICTED_OUTPUT, or INPUT_PLUS_MEASURED_OUTPUT.
        accounting_notes: Contextual notes on methodology and epistemic status.
        is_prompt_identical: When True (or on rollback), enforces 0 gross input and output token savings.

    Returns:
        EnergyCarbonResult with complete physical breakdown in canonical Wh.
    """
    # Resolve Model Tier Profile
    if isinstance(model_tier, str):
        tier_profile = DEFAULT_PROFILE_REGISTRY.get_tier(model_tier)
    elif isinstance(model_tier, ModelTierProfile):
        tier_profile = model_tier
    else:
        raise TypeError(f"model_tier must be a str or ModelTierProfile, got {type(model_tier).__name__}")

    # Resolve Grid Intensity
    if grid_scenario is None:
        raise ValueError(
            "grid_scenario must be explicitly provided (e.g. 'ILLUSTRATIVE_385', 'THESIS_367', or a user-supplied float); "
            "cannot silently invent a universal grid intensity."
        )

    if isinstance(grid_scenario, str):
        scenario_obj = DEFAULT_PROFILE_REGISTRY.get_grid_scenario(grid_scenario)
        ci_val = scenario_obj.carbon_intensity_gco2_kwh
        ci_prov = scenario_obj.provenance
    elif isinstance(grid_scenario, GridIntensityScenario):
        ci_val = grid_scenario.carbon_intensity_gco2_kwh
        ci_prov = grid_scenario.provenance
    elif isinstance(grid_scenario, (int, float)):
        if isinstance(grid_scenario, bool) or not math.isfinite(grid_scenario) or grid_scenario <= 0:
            raise ValueError(f"Custom grid intensity must be a finite positive number, got {grid_scenario}")
        ci_val = float(grid_scenario)
        if custom_grid_provenance and custom_grid_provenance.strip():
            ci_prov = custom_grid_provenance.strip()
        else:
            ci_prov = (
                f"User-supplied custom grid intensity: {ci_val:.1f} gCO2e/kWh "
                f"(unverified user input; independent source verification not performed)."
            )
    else:
        raise TypeError(f"Invalid grid_scenario type: {type(grid_scenario).__name__}")

    # Determine effective tokens and epistemic flags based on scenario and identical-text guard
    scenario_str = str(accounting_scenario).upper()
    if scenario_str in (AccountingScenario.INPUT_ONLY.value, "INPUT_ONLY"):
        eff_tin_orig = int(tin_original)
        eff_tin_opt = int(tin_original) if is_prompt_identical else int(tin_optimized)
        eff_tout_orig = 0.0
        eff_tout_opt = 0.0
        flag_pred = False
        flag_meas = True
        note_str = accounting_notes or "Conservative verified accounting based strictly on measured input tokens. Downstream decode energy is unmodeled and must not be interpreted as complete inference energy."
    elif scenario_str in (AccountingScenario.INPUT_PLUS_MEASURED_OUTPUT.value, "INPUT_PLUS_MEASURED_OUTPUT"):
        eff_tin_orig = int(tin_original)
        eff_tin_opt = int(tin_original) if is_prompt_identical else int(tin_optimized)
        eff_tout_orig = float(tout_original)
        eff_tout_opt = float(tout_original) if is_prompt_identical else float(tout_optimized)
        flag_pred = False
        flag_meas = True
        note_str = accounting_notes or "Empirically measured downstream generation on target LLM."
    else:  # Default: INPUT_PLUS_PREDICTED_OUTPUT
        eff_tin_orig = int(tin_original)
        eff_tin_opt = int(tin_original) if is_prompt_identical else int(tin_optimized)
        eff_tout_orig = float(tout_original)
        eff_tout_opt = float(tout_original) if is_prompt_identical else float(tout_optimized)
        flag_pred = is_output_predicted
        flag_meas = not is_output_predicted
        note_str = accounting_notes or "Exploratory modeled estimate combining measured input tokens with HybridPredictor downstream output estimates. Not physically measured."

    # Step 1: Compute Original and Optimized Inference Energy (Wh)
    e_orig = calculate_inference_energy_wh(
        tin=eff_tin_orig,
        tout=eff_tout_orig,
        alpha_prefill_mwh=tier_profile.alpha_prefill_mwh,
        alpha_decode_mwh=tier_profile.alpha_decode_mwh,
        pue=pue,
    )

    e_opt = calculate_inference_energy_wh(
        tin=eff_tin_opt,
        tout=eff_tout_opt,
        alpha_prefill_mwh=tier_profile.alpha_prefill_mwh,
        alpha_decode_mwh=tier_profile.alpha_decode_mwh,
        pue=pue,
    )

    # Step 2: Compute Optimizer Compute Overhead (Wh)
    e_overhead = estimate_optimizer_overhead_wh(
        latency_ms=optimizer_latency_ms,
        p_cpu_w=p_cpu_w,
    )

    # Step 3: Compute Gross and Net Energy Balances (Wh)
    gross_saved, net_saved = calculate_net_energy_wh(
        e_orig_wh=e_orig,
        e_opt_wh=e_opt,
        e_overhead_wh=e_overhead,
    )

    # Step 4: Compute Carbon Abatement (gCO2e)
    net_carbon = calculate_net_carbon_g(
        net_energy_wh=net_saved,
        grid_intensity_gco2_kwh=ci_val,
    )
    net_carbon_1k = net_carbon * 1000.0

    # Step 5: Compute Water Impact (mL)
    net_water = calculate_water_impact_ml(
        net_energy_wh=net_saved,
        wue_ml_per_wh=wue_ml_per_wh,
    )
    net_water_1k = net_water * 1000.0

    # Step 6: Flag Environmental Balance Status
    is_carbon_debt = net_saved < 0.0

    # Step 7: Compute Genuine Prefill and Decode Energy Components (Wh & Joules)
    prefill_opt_wh = float(pue) * (float(eff_tin_opt) * float(tier_profile.alpha_prefill_mwh) / 1000.0)
    prefill_opt_j = round(prefill_opt_wh * 3600.0, 6)

    if scenario_str in (AccountingScenario.INPUT_ONLY.value, "INPUT_ONLY") or eff_tout_opt == 0.0:
        decode_opt_wh = None
        decode_opt_j = None
    else:
        decode_opt_wh = float(pue) * (float(eff_tout_opt) * float(tier_profile.alpha_decode_mwh) / 1000.0)
        decode_opt_j = round(decode_opt_wh * 3600.0, 6)

    total_opt_j = round(e_opt * 3600.0, 6)

    return EnergyCarbonResult(
        tin_original=int(eff_tin_orig),
        tout_original=float(eff_tout_orig),
        tin_optimized=int(eff_tin_opt),
        tout_optimized=float(eff_tout_opt),
        energy_orig_wh=e_orig,
        energy_opt_wh=e_opt,
        gross_energy_saved_wh=gross_saved,
        optimizer_overhead_wh=e_overhead,
        net_energy_saved_wh=net_saved,
        grid_intensity_gco2_kwh=ci_val,
        grid_intensity_provenance=ci_prov,
        net_carbon_abated_gco2=net_carbon,
        net_carbon_abated_per_1k_gco2=net_carbon_1k,
        net_water_saved_ml=net_water,
        net_water_saved_per_1k_ml=net_water_1k,
        is_net_carbon_debt=is_carbon_debt,
        model_tier_id=tier_profile.tier_id,
        model_tier_provenance=tier_profile.provenance,
        pue_used=float(pue),
        wue_used_ml_per_wh=float(wue_ml_per_wh),
        cpu_power_w_used=float(p_cpu_w),
        optimizer_latency_ms=float(optimizer_latency_ms),
        is_output_predicted=flag_pred,
        is_measured=flag_meas,
        accounting_scenario=scenario_str,
        accounting_notes=note_str,
        prefill_energy_opt_wh=prefill_opt_wh,
        decode_energy_opt_wh=decode_opt_wh,
        modeled_prefill_energy_j=prefill_opt_j,
        modeled_decode_energy_j=decode_opt_j,
        modeled_total_energy_j=total_opt_j,
    )


def calculate_multi_scenario_impact(
    tin_original: int,
    tin_optimized: int,
    optimizer_latency_ms: float = 0.0,
    model_tier: Union[str, ModelTierProfile] = "mid_tier",
    grid_scenario: Union[str, GridIntensityScenario, float] = "ILLUSTRATIVE_385",
    custom_grid_provenance: Optional[str] = None,
    p_cpu_w: float = 35.0,
    pue: float = 1.15,
    wue_ml_per_wh: float = 1.8,
    predicted_tout_original: Optional[float] = None,
    predicted_tout_optimized: Optional[float] = None,
    measured_tout_original: Optional[int] = None,
    measured_tout_optimized: Optional[int] = None,
    measured_model_name: Optional[str] = None,
    measured_metadata: Optional[Dict[str, Any]] = None,
    is_prompt_identical: bool = False,
) -> MultiScenarioEnergyResult:
    """
    Computes all three standardized thermodynamic accounting scenarios simultaneously:
    1. INPUT_ONLY: Exact measured input tokens, zero output delta assumed.
    2. INPUT_PLUS_PREDICTED_OUTPUT: Measured input tokens + HybridPredictor output estimate (guarded against identical prompt bias).
    3. INPUT_PLUS_MEASURED_OUTPUT: Empirical downstream generation if provided, else None with 'NOT AVAILABLE' metadata.
    """
    # 1. INPUT_ONLY Scenario
    res_input_only = calculate_thermodynamic_impact(
        tin_original=tin_original,
        tout_original=0.0,
        tin_optimized=tin_optimized if not is_prompt_identical else tin_original,
        tout_optimized=0.0,
        model_tier=model_tier,
        grid_scenario=grid_scenario,
        custom_grid_provenance=custom_grid_provenance,
        optimizer_latency_ms=optimizer_latency_ms,
        p_cpu_w=p_cpu_w,
        pue=pue,
        wue_ml_per_wh=wue_ml_per_wh,
        is_output_predicted=False,
        accounting_scenario=AccountingScenario.INPUT_ONLY.value,
        accounting_notes="Conservative verified accounting based strictly on measured input tokens. Downstream decode energy is unmodeled and must not be interpreted as complete inference energy.",
        is_prompt_identical=is_prompt_identical,
    )

    # 2. INPUT_PLUS_PREDICTED_OUTPUT Scenario
    pred_orig = float(predicted_tout_original if predicted_tout_original is not None else 0.0)
    pred_opt = float(predicted_tout_optimized if predicted_tout_optimized is not None else pred_orig)
    if is_prompt_identical:
        pred_opt = pred_orig  # Guard against identical prompt ML prediction bias

    res_pred = calculate_thermodynamic_impact(
        tin_original=tin_original,
        tout_original=pred_orig,
        tin_optimized=tin_optimized if not is_prompt_identical else tin_original,
        tout_optimized=pred_opt,
        model_tier=model_tier,
        grid_scenario=grid_scenario,
        custom_grid_provenance=custom_grid_provenance,
        optimizer_latency_ms=optimizer_latency_ms,
        p_cpu_w=p_cpu_w,
        pue=pue,
        wue_ml_per_wh=wue_ml_per_wh,
        is_output_predicted=True,
        accounting_scenario=AccountingScenario.INPUT_PLUS_PREDICTED_OUTPUT.value,
        accounting_notes="Exploratory modeled estimate combining measured input tokens with HybridPredictor downstream output estimates. Not physically measured.",
        is_prompt_identical=is_prompt_identical,
    )

    # 3. INPUT_PLUS_MEASURED_OUTPUT Scenario
    res_meas = None
    has_meas = (measured_tout_original is not None and measured_tout_optimized is not None)
    meas_meta: Dict[str, Any] = {}
    if has_meas:
        meas_orig = float(measured_tout_original)
        meas_opt = float(measured_tout_optimized)
        if is_prompt_identical:
            meas_opt = meas_orig
        res_meas = calculate_thermodynamic_impact(
            tin_original=tin_original,
            tout_original=meas_orig,
            tin_optimized=tin_optimized if not is_prompt_identical else tin_original,
            tout_optimized=meas_opt,
            model_tier=model_tier,
            grid_scenario=grid_scenario,
            custom_grid_provenance=custom_grid_provenance,
            optimizer_latency_ms=optimizer_latency_ms,
            p_cpu_w=p_cpu_w,
            pue=pue,
            wue_ml_per_wh=wue_ml_per_wh,
            is_output_predicted=False,
            accounting_scenario=AccountingScenario.INPUT_PLUS_MEASURED_OUTPUT.value,
            accounting_notes=f"Empirically measured downstream generation on model '{measured_model_name or 'unspecified'}'.",
            is_prompt_identical=is_prompt_identical,
        )
        meas_meta = {
            "status": "AVAILABLE",
            "model_name": measured_model_name or "unspecified",
            "measured_tout_original": measured_tout_original,
            "measured_tout_optimized": measured_tout_optimized,
            "metadata": measured_metadata or {},
        }
    else:
        meas_meta = {
            "status": "NOT AVAILABLE",
            "reason": "No empirical downstream LLM generation was performed for this request.",
        }

    return MultiScenarioEnergyResult(
        input_only=res_input_only,
        input_plus_predicted_output=res_pred,
        input_plus_measured_output=res_meas,
        measured_output_available=has_meas,
        measured_output_metadata=meas_meta,
    )

