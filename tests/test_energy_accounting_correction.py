"""
Targeted Unit & Integration Test Suite for Energy Accounting Correction (Phase 10).
Validates:
1. Scenario 1 (INPUT_ONLY): Exact input token measurements, 0 output savings assumed.
2. Scenario 2 (INPUT_PLUS_PREDICTED_OUTPUT): Modeled downstream output estimation with epistemic labeling.
3. Scenario 3 (INPUT_PLUS_MEASURED_OUTPUT): Empirical generation when provided; marked NOT AVAILABLE otherwise.
4. Zero-Diff Guard: When original_prompt == optimized_prompt (or rollback), output delta is strictly 0.0 and net energy reflects honest CPU overhead debt.
5. calculate_multi_scenario_impact container integrity and unit conversions.
"""

import math
import pytest
from promptgreen.engine.thermodynamics import (
    calculate_thermodynamic_impact,
    calculate_multi_scenario_impact,
    AccountingScenario,
    EnergyCarbonResult,
    MultiScenarioEnergyResult,
)
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.engine.model_profiles import DEFAULT_PROFILE_REGISTRY


def test_scenario_1_input_only_accounting():
    """Verify Scenario 1 computes gross savings strictly from input tokens and assumes 0 output delta."""
    tier = DEFAULT_PROFILE_REGISTRY.get_tier("mid_tier")  # alpha_prefill=0.24, alpha_decode=0.92
    res = calculate_thermodynamic_impact(
        tin_original=100,
        tout_original=200.0,
        tin_optimized=80,
        tout_optimized=150.0,
        model_tier=tier,
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=100.0,
        accounting_scenario=AccountingScenario.INPUT_ONLY.value,
    )

    assert res.accounting_scenario == "INPUT_ONLY"
    assert res.is_measured is True
    assert res.is_output_predicted is False

    # Gross energy saved must strictly reflect 20 input tokens:
    # 20 * 0.24 mWh * 1.15 PUE / 1000 = 0.00552 Wh
    expected_gross_wh = (20 * 0.24 * 1.15) / 1000.0
    assert pytest.approx(res.gross_energy_saved_wh, abs=1e-7) == expected_gross_wh

    # Overhead for 100 ms at 35W: 35.0 * 0.1 / 3600 = 0.0009722 Wh
    expected_overhead_wh = (35.0 * 0.1) / 3600.0
    assert pytest.approx(res.optimizer_overhead_wh, abs=1e-7) == expected_overhead_wh
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == expected_gross_wh - expected_overhead_wh
    assert res.is_net_carbon_debt is False


def test_scenario_2_input_plus_predicted_output():
    """Verify Scenario 2 incorporates modeled downstream output estimation with exploratory labeling."""
    tier = DEFAULT_PROFILE_REGISTRY.get_tier("mid_tier")
    res = calculate_thermodynamic_impact(
        tin_original=100,
        tout_original=200.0,
        tin_optimized=80,
        tout_optimized=150.0,
        model_tier=tier,
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=100.0,
        accounting_scenario=AccountingScenario.INPUT_PLUS_PREDICTED_OUTPUT.value,
        is_output_predicted=True,
    )

    assert res.accounting_scenario == "INPUT_PLUS_PREDICTED_OUTPUT"
    assert res.is_output_predicted is True
    assert res.is_measured is False

    # Gross energy includes 20 input tokens and 50 output tokens:
    # (20 * 0.24 + 50 * 0.92) * 1.15 / 1000 = (4.8 + 46.0) * 1.15 / 1000 = 0.05842 Wh
    expected_gross_wh = ((20 * 0.24) + (50 * 0.92)) * 1.15 / 1000.0
    assert pytest.approx(res.gross_energy_saved_wh, abs=1e-7) == expected_gross_wh


def test_zero_diff_guard_on_identical_prompts():
    """Verify that when prompts are identical, output delta is 0 and honest carbon debt is reported."""
    predictor = HybridPredictor()
    pred_res = predictor.predict("Hello world, test prompt.", "Hello world, test prompt.")

    # Rule and ML layers must report 0 delta for identical prompt
    assert pred_res.predicted_output_token_delta == 0.0
    assert pred_res.rule_output_delta == 0.0
    assert pred_res.ml_output_delta == 0.0
    assert pred_res.direction == "UNCHANGED"

    # In thermodynamic engine, is_prompt_identical=True enforces 0 gross savings and honest CPU debt
    tier = DEFAULT_PROFILE_REGISTRY.get_tier("mid_tier")
    res = calculate_thermodynamic_impact(
        tin_original=10,
        tout_original=100.0,
        tin_optimized=10,
        tout_optimized=100.0,
        model_tier=tier,
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=250.0,
        accounting_scenario=AccountingScenario.INPUT_PLUS_PREDICTED_OUTPUT.value,
        is_prompt_identical=True,
    )

    assert res.gross_energy_saved_wh == 0.0
    expected_overhead = 35.0 * (250.0 / 1000.0) / 3600.0
    assert pytest.approx(res.optimizer_overhead_wh, abs=1e-7) == expected_overhead
    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == -expected_overhead
    assert res.is_net_carbon_debt is True
    assert res.net_carbon_abated_gco2 < 0.0
    assert res.net_water_saved_ml < 0.0


def test_multi_scenario_impact_container_without_measured_output():
    """Verify calculate_multi_scenario_impact returns structured container with Scenario 3 marked NOT AVAILABLE."""
    multi = calculate_multi_scenario_impact(
        tin_original=50,
        tin_optimized=40,
        optimizer_latency_ms=120.0,
        model_tier="mid_tier",
        grid_scenario="ILLUSTRATIVE_385",
        predicted_tout_original=200.0,
        predicted_tout_optimized=160.0,
        measured_tout_original=None,
        measured_tout_optimized=None,
        is_prompt_identical=False,
    )

    assert isinstance(multi, MultiScenarioEnergyResult)

    # Scenario 1 check
    assert multi.input_only.accounting_scenario == "INPUT_ONLY"
    assert multi.input_only.gross_energy_saved_wh > 0.0

    # Scenario 2 check
    assert multi.input_plus_predicted_output.accounting_scenario == "INPUT_PLUS_PREDICTED_OUTPUT"
    assert multi.input_plus_predicted_output.gross_energy_saved_wh > multi.input_only.gross_energy_saved_wh

    # Scenario 3 check (unavailable)
    assert multi.measured_output_available is False
    assert multi.input_plus_measured_output is None


def test_multi_scenario_impact_container_with_measured_output():
    """Verify calculate_multi_scenario_impact populates Scenario 3 when empirical token counts supplied."""
    multi = calculate_multi_scenario_impact(
        tin_original=50,
        tin_optimized=40,
        optimizer_latency_ms=120.0,
        model_tier="mid_tier",
        grid_scenario="ILLUSTRATIVE_385",
        predicted_tout_original=200.0,
        predicted_tout_optimized=160.0,
        measured_tout_original=210,
        measured_tout_optimized=175,
        measured_model_name="meta-llama/Llama-3-8B-Instruct",
        is_prompt_identical=False,
    )

    assert multi.measured_output_available is True
    assert multi.input_plus_measured_output is not None
    assert multi.input_plus_measured_output.accounting_scenario == "INPUT_PLUS_MEASURED_OUTPUT"
    assert multi.input_plus_measured_output.is_measured is True

    # Gross energy includes 10 input tokens and 35 measured output tokens:
    # (10 * 0.24 + 35 * 0.92) * 1.15 / 1000 = (2.4 + 32.2) * 1.15 / 1000 = 0.03979 Wh
    expected_gross = ((10 * 0.24) + (35 * 0.92)) * 1.15 / 1000.0
    assert pytest.approx(multi.input_plus_measured_output.gross_energy_saved_wh, abs=1e-7) == expected_gross


def test_thermodynamic_unit_conversions_carbon_and_water():
    """Verify mathematical conversions from canonical Wh to gCO2e and mL cooling water."""
    net_wh = 1.250  # 1.25 Watt-hours
    grid_gco2_kwh = 385.0
    wue_ml_per_wh = 1.8

    expected_carbon_g = (net_wh / 1000.0) * grid_gco2_kwh  # 0.48125 gCO2e
    expected_water_ml = net_wh * wue_ml_per_wh             # 2.25 mL

    res = calculate_thermodynamic_impact(
        tin_original=1000,
        tout_original=1000.0,
        tin_optimized=900,
        tout_optimized=900.0,
        model_tier="frontier_dense",
        grid_scenario=grid_gco2_kwh,
        optimizer_latency_ms=0.0,
        wue_ml_per_wh=wue_ml_per_wh,
        accounting_scenario=AccountingScenario.INPUT_ONLY.value,
    )

    # Ratio check
    carbon_ratio = res.net_carbon_abated_gco2 / res.net_energy_saved_wh
    assert pytest.approx(carbon_ratio, abs=1e-7) == grid_gco2_kwh / 1000.0

    water_ratio = res.net_water_saved_ml / res.net_energy_saved_wh
    assert pytest.approx(water_ratio, abs=1e-7) == wue_ml_per_wh
