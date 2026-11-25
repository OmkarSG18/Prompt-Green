"""
Comprehensive test suite for PromptGreen V2 Stage 6 Phase 1:
Foundational Thermodynamic Energy, Carbon, and Water Estimation Engine.

Validates:
- Canonical Wh internal energy currency
- Correct mWh-to-Wh conversion
- PUE application (>= 1.0, applied exactly once)
- Prefill vs. decode asymmetry (3.8x ratio)
- Dynamic optimizer overhead deduction
- Net energy, carbon abatement, and datacenter cooling water
- Numerical reproduction of Corrective Audit Cases 1A, 1B, 2A, 2B, 3
- Boundary and error handling (negative tokens, latency, PUE < 1.0, missing grid)
- Custom model profiles and registry lookup
- Backward compatibility with legacy V1 CarbonEngine.calculate()
"""

import pytest

from promptgreen.engine.model_profiles import (
    ModelTierProfile,
    HardwareProfile,
    GridIntensityScenario,
    ModelProfileRegistry,
    DEFAULT_PROFILE_REGISTRY,
    STANDARD_MODEL_TIERS,
    STANDARD_GRID_SCENARIOS,
    THESIS_PROVENANCE_WARNING,
    GRID_PROVENANCE_ILLUSTRATIVE_385,
    GRID_PROVENANCE_THESIS_367,
    GRID_PROVENANCE_US_ILLUSTRATIVE,
    GRID_PROVENANCE_THESIS_GLOBAL,
)
from promptgreen.engine.thermodynamics import (
    EnergyCarbonResult,
    calculate_inference_energy_wh,
    estimate_optimizer_overhead_wh,
    calculate_net_energy_wh,
    calculate_net_carbon_g,
    calculate_water_impact_ml,
    calculate_thermodynamic_impact,
)
from promptgreen.engine.carbon_engine import CarbonEngine, CarbonImpactResult


# ==============================================================================
# GROUP A: NUMERICAL REPRODUCTION OF AUDIT CASES (Cases 1A, 1B, 2A, 2B, 3)
# ==============================================================================

def test_case_1a_mathematical_no_op() -> None:
    """Case 1A: Mathematical no-op produces exact zero energy, carbon, and water."""
    res = calculate_thermodynamic_impact(
        tin_original=0,
        tout_original=0,
        tin_optimized=0,
        tout_optimized=0,
        model_tier="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=0.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    assert res.energy_orig_wh == 0.0
    assert res.energy_opt_wh == 0.0
    assert res.gross_energy_saved_wh == 0.0
    assert res.optimizer_overhead_wh == 0.0
    assert res.net_energy_saved_wh == 0.0
    assert res.net_carbon_abated_gco2 == 0.0
    assert res.net_carbon_abated_per_1k_gco2 == 0.0
    assert res.net_water_saved_ml == 0.0
    assert res.net_water_saved_per_1k_ml == 0.0
    assert res.is_net_carbon_debt is False


def test_case_1b_empty_prompt_with_optimizer_overhead() -> None:
    """Case 1B: Empty prompt processed by optimizer consumes CPU overhead and results in Net Carbon Debt."""
    res = calculate_thermodynamic_impact(
        tin_original=0,
        tout_original=0,
        tin_optimized=0,
        tout_optimized=0,
        model_tier="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=5.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    # 35W * (5ms / 3_600_000) = 0.0000486111... Wh
    assert res.energy_orig_wh == 0.0
    assert res.energy_opt_wh == 0.0
    assert res.gross_energy_saved_wh == 0.0
    assert pytest.approx(res.optimizer_overhead_wh, abs=1e-7) == 0.0000486
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == -0.0000486
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == -0.018715
    assert pytest.approx(res.net_water_saved_per_1k_ml, abs=1e-4) == -0.08750
    assert res.is_net_carbon_debt is True


def test_case_2a_normal_inference_illustrative_us_grid() -> None:
    """Case 2A: Normal inference under Illustrative Scenario (385.0 gCO2e/kWh) produces verified reference values."""
    res = calculate_thermodynamic_impact(
        tin_original=120,
        tout_original=250,
        tin_optimized=60,
        tout_optimized=150,
        model_tier="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=180.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    # Reference values:
    # E_orig: 0.5179600 Wh
    # E_opt:  0.3049800 Wh
    # Gross:  0.2129800 Wh
    # E_opt_overhead: 0.0017500 Wh
    # Net:    0.2112300 Wh
    # Carbon / 1k: +81.323550 gCO2e
    # Water / 1k:  +380.21400 mL
    assert pytest.approx(res.energy_orig_wh, abs=1e-7) == 0.5179600
    assert pytest.approx(res.energy_opt_wh, abs=1e-7) == 0.3049800
    assert pytest.approx(res.gross_energy_saved_wh, abs=1e-7) == 0.2129800
    assert pytest.approx(res.optimizer_overhead_wh, abs=1e-7) == 0.0017500
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == 0.2112300
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == 81.323550
    assert pytest.approx(res.net_water_saved_per_1k_ml, abs=1e-4) == 380.21400
    assert res.is_net_carbon_debt is False
    assert res.grid_intensity_gco2_kwh == 385.0


def test_case_2b_normal_inference_thesis_global_grid() -> None:
    """Case 2B: Normal inference under Thesis pp. 17–18 Scenario (367.0 gCO2e/kWh) produces verified reference values."""
    res = calculate_thermodynamic_impact(
        tin_original=120,
        tout_original=250,
        tin_optimized=60,
        tout_optimized=150,
        model_tier="frontier_dense",
        grid_scenario="THESIS_367",
        optimizer_latency_ms=180.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    # Reference values:
    # Net:    0.2112300 Wh
    # Carbon / 1k: +77.521410 gCO2e
    # Water / 1k:  +380.21400 mL
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == 0.2112300
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == 77.521410
    assert pytest.approx(res.net_water_saved_per_1k_ml, abs=1e-4) == 380.21400
    assert res.is_net_carbon_debt is False
    assert res.grid_intensity_gco2_kwh == 367.0


def test_case_3_carbon_debt_when_overhead_exceeds_savings() -> None:
    """Case 3: Marginal token compression on Compact Green model produces Net Carbon Debt."""
    res = calculate_thermodynamic_impact(
        tin_original=18,
        tout_original=10,
        tin_optimized=17,
        tout_optimized=10,
        model_tier="compact_green",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=220.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    # Reference values:
    # E_orig: 0.0025530 Wh
    # E_opt:  0.0025070 Wh
    # Gross:  0.0000460 Wh
    # E_overhead: 0.00213889 Wh
    # Net:   -0.00209289 Wh
    # Carbon / 1k: -0.805762 gCO2e
    # Water / 1k:  -3.76720 mL
    assert pytest.approx(res.energy_orig_wh, abs=1e-7) == 0.0025530
    assert pytest.approx(res.energy_opt_wh, abs=1e-7) == 0.0025070
    assert pytest.approx(res.gross_energy_saved_wh, abs=1e-7) == 0.0000460
    assert pytest.approx(res.optimizer_overhead_wh, abs=1e-7) == 0.0021389
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == -0.0020929
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == -0.805762
    assert pytest.approx(res.net_water_saved_per_1k_ml, abs=1e-4) == -3.76720
    assert res.is_net_carbon_debt is True


# ==============================================================================
# GROUP B: UNIT CONVERSIONS, PUE, AND ASYMMETRY
# ==============================================================================

def test_mwh_to_wh_conversion_is_exact() -> None:
    """Verify that dividing sum of mWh by 1000 scales exactly to Wh."""
    # 1000 tokens * 1.0 mWh/tok = 1000 mWh = 1.0 Wh (at PUE=1.0)
    e_wh = calculate_inference_energy_wh(
        tin=1000,
        tout=0,
        alpha_prefill_mwh=1.0,
        alpha_decode_mwh=3.8,
        pue=1.0,
    )
    assert e_wh == 1.0


def test_pue_application_is_applied_exactly_once() -> None:
    """Verify that PUE scales total IT energy exactly once."""
    e_pue_10 = calculate_inference_energy_wh(
        tin=100,
        tout=100,
        alpha_prefill_mwh=0.42,
        alpha_decode_mwh=1.60,
        pue=1.0,
    )
    e_pue_115 = calculate_inference_energy_wh(
        tin=100,
        tout=100,
        alpha_prefill_mwh=0.42,
        alpha_decode_mwh=1.60,
        pue=1.15,
    )
    assert pytest.approx(e_pue_115, abs=1e-7) == e_pue_10 * 1.15


def test_prefill_vs_decode_asymmetry() -> None:
    """Verify that generating N decode tokens consumes significantly more energy than ingesting N prefill tokens."""
    tier = STANDARD_MODEL_TIERS["frontier_dense"]
    e_prefill_only = calculate_inference_energy_wh(tin=100, tout=0, alpha_prefill_mwh=tier.alpha_prefill_mwh, alpha_decode_mwh=tier.alpha_decode_mwh)
    e_decode_only = calculate_inference_energy_wh(tin=0, tout=100, alpha_prefill_mwh=tier.alpha_prefill_mwh, alpha_decode_mwh=tier.alpha_decode_mwh)

    ratio = e_decode_only / e_prefill_only
    assert pytest.approx(ratio, abs=1e-4) == tier.decode_to_prefill_ratio
    assert ratio > 3.5


def test_optimizer_overhead_deduction_exactly_once() -> None:
    """Verify that net savings equals gross savings minus overhead exactly once."""
    gross, net = calculate_net_energy_wh(e_orig_wh=1.0, e_opt_wh=0.6, e_overhead_wh=0.1)
    assert pytest.approx(gross, abs=1e-7) == 0.4
    assert pytest.approx(net, abs=1e-7) == 0.3


# ==============================================================================
# GROUP C: VALIDATION AND ERROR REJECTION
# ==============================================================================

def test_reject_negative_tokens() -> None:
    """Reject negative token counts."""
    with pytest.raises(ValueError, match=r"Input tokens \(tin\) must be a finite non-negative number"):
        calculate_inference_energy_wh(tin=-1, tout=10, alpha_prefill_mwh=0.42, alpha_decode_mwh=1.60)

    with pytest.raises(ValueError, match=r"Output tokens \(tout\) must be a finite non-negative number"):
        calculate_inference_energy_wh(tin=10, tout=-5, alpha_prefill_mwh=0.42, alpha_decode_mwh=1.60)


def test_reject_invalid_pue() -> None:
    """Reject PUE values less than physical lower bound 1.0."""
    with pytest.raises(ValueError, match=r"PUE must be a finite number >= 1.0"):
        calculate_inference_energy_wh(tin=10, tout=10, alpha_prefill_mwh=0.42, alpha_decode_mwh=1.60, pue=0.9)


def test_reject_negative_optimizer_latency() -> None:
    """Reject negative execution latency."""
    with pytest.raises(ValueError, match=r"Optimizer latency must be a finite non-negative number"):
        estimate_optimizer_overhead_wh(latency_ms=-10.0)


def test_reject_invalid_cpu_power() -> None:
    """Reject non-positive CPU power estimate."""
    with pytest.raises(ValueError, match=r"CPU power estimate must be a finite positive number"):
        estimate_optimizer_overhead_wh(latency_ms=100.0, p_cpu_w=0.0)


def test_reject_missing_grid_intensity() -> None:
    """Reject missing / None grid scenario without inventing a default."""
    with pytest.raises(ValueError, match="grid_scenario must be explicitly provided"):
        calculate_thermodynamic_impact(
            tin_original=100,
            tout_original=100,
            tin_optimized=50,
            tout_optimized=50,
            grid_scenario=None,
        )


def test_reject_negative_grid_intensity() -> None:
    """Reject non-positive custom grid intensity."""
    with pytest.raises(ValueError, match="grid_intensity_gco2_kwh must be a finite positive number"):
        calculate_net_carbon_g(net_energy_wh=1.0, grid_intensity_gco2_kwh=-50.0)


def test_valid_custom_profile_with_decode_lower_than_prefill() -> None:
    """Verify that custom profile with decode < prefill is accepted with metadata flag and calculates correctly."""
    profile = ModelTierProfile(
        tier_id="speculative_draft_model",
        display_name="Speculative Draft Architecture",
        alpha_prefill_mwh=0.50,
        alpha_decode_mwh=0.20,
        hardware_id="l4_pcie",
        provenance="Custom speculative drafting experiment.",
    )
    assert profile.is_ratio_unusual is True
    assert "Unusual coefficient ratio" in profile.ratio_note
    assert profile.alpha_decode_mwh == 0.20
    assert profile.alpha_prefill_mwh == 0.50
    assert profile.decode_to_prefill_ratio == 0.40

    # Verify it can be used in thermodynamic calculation without error
    res = calculate_thermodynamic_impact(
        tin_original=100,
        tout_original=50,
        tin_optimized=50,
        tout_optimized=25,
        model_tier=profile,
        grid_scenario="ILLUSTRATIVE_385",
    )
    assert res.model_tier_id == "speculative_draft_model"
    assert res.energy_orig_wh > 0.0
    assert res.gross_energy_saved_wh > 0.0


# ==============================================================================
# GROUP D: MODEL TIERS, HARDWARE PROFILES, AND REGISTRY
# ==============================================================================

def test_standard_four_thesis_tiers_exist() -> None:
    """Verify all four thesis model tiers are registered with exact coefficients."""
    registry = DEFAULT_PROFILE_REGISTRY
    tiers = registry.list_tiers()

    assert "frontier_dense" in tiers
    assert "large_reasoning" in tiers
    assert "mid_tier" in tiers
    assert "compact_green" in tiers

    fd = registry.get_tier("frontier_dense")
    assert fd.alpha_prefill_mwh == 0.42
    assert fd.alpha_decode_mwh == 1.60
    assert fd.provenance == THESIS_PROVENANCE_WARNING

    lr = registry.get_tier("large_reasoning")
    assert lr.alpha_prefill_mwh == 0.35
    assert lr.alpha_decode_mwh == 1.35

    mt = registry.get_tier("mid_tier")
    assert mt.alpha_prefill_mwh == 0.24
    assert mt.alpha_decode_mwh == 0.92

    cg = registry.get_tier("compact_green")
    assert cg.alpha_prefill_mwh == 0.04
    assert cg.alpha_decode_mwh == 0.15


def test_custom_model_profile_registration() -> None:
    """Verify custom model profile creation and calculation."""
    custom_profile = ModelTierProfile(
        tier_id="custom_h100_quantized",
        display_name="Custom H100 FP8 Optimized",
        alpha_prefill_mwh=0.20,
        alpha_decode_mwh=0.76,
        hardware_id="h100_pcie",
        provenance="Empirically measured via local GPU power sensor.",
    )

    res = calculate_thermodynamic_impact(
        tin_original=100,
        tout_original=100,
        tin_optimized=50,
        tout_optimized=50,
        model_tier=custom_profile,
        grid_scenario=300.0,
        optimizer_latency_ms=50.0,
    )

    assert res.model_tier_id == "custom_h100_quantized"
    assert res.model_tier_provenance == "Empirically measured via local GPU power sensor."
    assert res.gross_energy_saved_wh > 0.0


def test_grid_scenario_lookup_and_custom_float() -> None:
    """Verify grid scenario lookup for retained scenarios and user-supplied float intensity."""
    # Lookup via retained THESIS_367 code
    res_tg = calculate_thermodynamic_impact(
        tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
        grid_scenario="THESIS_367",
    )
    assert res_tg.grid_intensity_gco2_kwh == 367.0
    assert "thesis-provided scenario" in res_tg.grid_intensity_provenance

    # Lookup via retained ILLUSTRATIVE_385 code
    res_us = calculate_thermodynamic_impact(
        tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
        grid_scenario="ILLUSTRATIVE_385",
    )
    assert res_us.grid_intensity_gco2_kwh == 385.0
    assert "illustrative scenario" in res_us.grid_intensity_provenance

    # User-supplied numeric intensity (unverified user input; never described as verified)
    res_in_custom = calculate_thermodynamic_impact(
        tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
        grid_scenario=708.0,
    )
    assert res_in_custom.grid_intensity_gco2_kwh == 708.0
    assert "User-supplied custom grid intensity" in res_in_custom.grid_intensity_provenance
    assert "unverified user input" in res_in_custom.grid_intensity_provenance

    # User-supplied numeric intensity with separate provenance
    res_with_prov = calculate_thermodynamic_impact(
        tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
        grid_scenario=708.0,
        custom_grid_provenance="User-provided CEA baseline estimate (unverified by PromptGreen).",
    )
    assert res_with_prov.grid_intensity_gco2_kwh == 708.0
    assert res_with_prov.grid_intensity_provenance == "User-provided CEA baseline estimate (unverified by PromptGreen)."

    # Lookup via generic custom float
    res_float = calculate_thermodynamic_impact(
        tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
        grid_scenario=500.0,
    )
    assert res_float.grid_intensity_gco2_kwh == 500.0
    assert "User-supplied custom grid intensity" in res_float.grid_intensity_provenance


def test_unverified_regional_grid_codes_rejected_without_silent_defaults() -> None:
    """Verify that unverified or renamed regional codes are rejected with informative error and not silently substituted."""
    unverified_codes = ["IN", "IN-WE", "IN-SO", "EU", "UK", "DE", "FR", "GLOBAL", "US", "THESIS_GLOBAL"]
    for code in unverified_codes:
        with pytest.raises(KeyError, match=f"Grid intensity for region '{code}' is unavailable without user specification"):
            calculate_thermodynamic_impact(
                tin_original=100,
                tout_original=100,
                tin_optimized=50,
                tout_optimized=50,
                grid_scenario=code,
            )


def test_unknown_grid_code_lists_available_scenarios() -> None:
    """Verify that completely unknown grid codes list selectable scenarios and prompt for user-supplied float."""
    with pytest.raises(KeyError, match="Unknown grid region 'XYZ'. Selectable verified scenarios: ILLUSTRATIVE_385, THESIS_367"):
        calculate_thermodynamic_impact(
            tin_original=100,
            tout_original=100,
            tin_optimized=50,
            tout_optimized=50,
            grid_scenario="XYZ",
        )


def test_hardware_profile_validation() -> None:
    """Verify hardware profile validation rejects invalid parameters."""
    with pytest.raises(ValueError, match="tdp_watts must be a finite positive number"):
        HardwareProfile(hardware_id="h_bad", name="Bad", tdp_watts=-10.0, typical_operating_watts=100.0, memory_gb=80.0)

    with pytest.raises(ValueError, match="typical_operating_watts must be a finite positive number"):
        HardwareProfile(hardware_id="h_bad", name="Bad", tdp_watts=100.0, typical_operating_watts=0.0, memory_gb=80.0)

    with pytest.raises(ValueError, match="memory_gb must be a finite positive number"):
        HardwareProfile(hardware_id="h_bad", name="Bad", tdp_watts=100.0, typical_operating_watts=50.0, memory_gb=-4.0)

    with pytest.raises(ValueError, match="hardware_id must be a non-empty string"):
        HardwareProfile(hardware_id="", name="Bad", tdp_watts=100.0, typical_operating_watts=50.0, memory_gb=80.0)


def test_grid_intensity_scenario_validation() -> None:
    """Verify grid intensity scenario validation rejects invalid parameters."""
    with pytest.raises(ValueError, match="region_code must be a non-empty string"):
        GridIntensityScenario(region_code="  ", carbon_intensity_gco2_kwh=300.0, provenance="test")

    with pytest.raises(ValueError, match="carbon_intensity_gco2_kwh must be a finite positive number"):
        GridIntensityScenario(region_code="BAD", carbon_intensity_gco2_kwh=-10.0, provenance="test")


def test_model_tier_profile_validation_rejects_empty_ids_and_non_numbers() -> None:
    """Verify model tier profile rejects empty IDs, non-numeric coefficients, and negative values."""
    with pytest.raises(ValueError, match="tier_id must be a non-empty string"):
        ModelTierProfile(tier_id="", display_name="Bad", alpha_prefill_mwh=0.1, alpha_decode_mwh=0.4, hardware_id="h1")

    with pytest.raises(ValueError, match="hardware_id must be a non-empty string"):
        ModelTierProfile(tier_id="t1", display_name="Bad", alpha_prefill_mwh=0.1, alpha_decode_mwh=0.4, hardware_id="")

    with pytest.raises(TypeError, match="alpha_prefill_mwh must be a float or int"):
        ModelTierProfile(tier_id="t1", display_name="Bad", alpha_prefill_mwh="invalid", alpha_decode_mwh=0.4, hardware_id="h1")  # type: ignore

    with pytest.raises(ValueError, match="alpha_decode_mwh must be a finite positive number"):
        ModelTierProfile(tier_id="t1", display_name="Bad", alpha_prefill_mwh=0.1, alpha_decode_mwh=-0.4, hardware_id="h1")


def test_nan_inf_and_boolean_rejection() -> None:
    """Verify NaN, Inf, and booleans are strictly rejected across profile and calculation engines."""
    # ModelTierProfile
    with pytest.raises(ValueError, match="alpha_prefill_mwh must be a finite positive number"):
        ModelTierProfile(tier_id="t", display_name="T", alpha_prefill_mwh=float("nan"), alpha_decode_mwh=1.0, hardware_id="h")

    with pytest.raises(ValueError, match="alpha_decode_mwh must be a finite positive number"):
        ModelTierProfile(tier_id="t", display_name="T", alpha_prefill_mwh=1.0, alpha_decode_mwh=float("inf"), hardware_id="h")

    with pytest.raises(TypeError, match="alpha_prefill_mwh must be a float or int"):
        ModelTierProfile(tier_id="t", display_name="T", alpha_prefill_mwh=True, alpha_decode_mwh=1.0, hardware_id="h")  # type: ignore

    # HardwareProfile
    with pytest.raises(ValueError, match="tdp_watts must be a finite positive number"):
        HardwareProfile(hardware_id="h", name="H", tdp_watts=float("nan"), typical_operating_watts=100.0, memory_gb=80.0)

    # GridIntensityScenario
    with pytest.raises(ValueError, match="carbon_intensity_gco2_kwh must be a finite positive number"):
        GridIntensityScenario(region_code="BAD", carbon_intensity_gco2_kwh=float("inf"), provenance="prov")

    # calculate_thermodynamic_impact custom grid
    with pytest.raises(ValueError, match="Custom grid intensity must be a finite positive number"):
        calculate_thermodynamic_impact(
            tin_original=100, tout_original=100, tin_optimized=50, tout_optimized=50,
            grid_scenario=float("nan"),
        )


# ==============================================================================
# GROUP E: INTEGRATION & BACKWARD COMPATIBILITY
# ==============================================================================

def test_carbon_engine_calculate_thermodynamic_wrapper() -> None:
    """Verify CarbonEngine.calculate_thermodynamic produces identical results to calculate_thermodynamic_impact."""
    engine = CarbonEngine(model_key="llama-3-8b", region="US")
    res = engine.calculate_thermodynamic(
        tin_orig=120,
        tout_orig=250,
        tin_opt=60,
        tout_opt=150,
        model_tier="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=180.0,
        p_cpu_w=35.0,
        pue=1.15,
        wue_ml_per_wh=1.8,
    )

    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == 0.2112300
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == 81.323550
    assert res.is_measured is False


def test_legacy_v1_carbon_engine_calculate_backward_compatible() -> None:
    """Verify that existing V1 CarbonEngine.calculate() remains fully functional."""
    engine = CarbonEngine(model_key="llama-3-8b", region="US")
    old_p = "Explain in detail with extensive examples how quantum computing works."
    new_p = "Summarize quantum computing in 3 bullet points."

    res = engine.calculate(old_p, new_p, monthly_inferences=10000)
    assert isinstance(res, CarbonImpactResult)
    assert res.model_name == "Llama-3 8B"
    assert res.carbon_intensity_gco2_kwh == 385.0
    assert res.old_energy_per_inf_mj > 0.0
    assert res.new_energy_per_inf_mj > 0.0
    assert res.carbon_delta_per_1k_gco2 < 0.0
