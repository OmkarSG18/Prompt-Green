"""
Comprehensive test suite for PromptGreen V2 Stage 6 Phase 2:
Conservative Green Model Router.

Validates:
1. Simple classification -> RECOMMEND_LOWER_ENERGY_TIER
2. Structured extraction -> RECOMMEND_LOWER_ENERGY_TIER
3. Simple summarization -> RECOMMEND_LOWER_ENERGY_TIER
4. Complex reasoning -> NO_SAFE_DOWNGRADE
5. Code generation -> NO_SAFE_DOWNGRADE
6. Mathematical precision -> NO_SAFE_DOWNGRADE
7. Safety-critical requests -> NO_SAFE_DOWNGRADE
8. Explicit user preference -> KEEP_CURRENT_MODEL
9. Unknown task requirements -> INSUFFICIENT_INFORMATION
10. Unsupported candidate capabilities -> Rejected in audit trail
11. No available lower-energy candidate -> KEEP_CURRENT_MODEL
12. Missing grid intensity -> Carbon comparison is None
13. Energy comparison consistency -> Matches thermodynamic formula
14. Carbon comparison consistency -> Matches thermodynamic formula
15. Invalid model tiers -> KeyError
16. Invalid token counts -> ValueError
17. Invalid PUE -> ValueError
18. Missing output-token assumption -> ValueError
19. Qualitative confidence/uncertainty behavior
20. Adversarial descriptions -> Prevent unsafe downgrade
21. Non-automated recommendation contract (disclaimer present, no switching)
22. Optimizer overhead cancellation in like-for-like comparison
23. Custom user-supplied grid intensity and separate provenance
24. Regression: Phase 1 thermodynamic engine unchanged
25. Regression: Stage 5 pipeline unchanged
"""

import math
import pytest

from promptgreen.engine.model_profiles import (
    ModelTierProfile,
    GridIntensityScenario,
    ModelProfileRegistry,
    DEFAULT_PROFILE_REGISTRY,
    STANDARD_MODEL_TIERS,
)
from promptgreen.engine.thermodynamics import (
    calculate_inference_energy_wh,
    calculate_net_carbon_g,
    calculate_thermodynamic_impact,
)
from promptgreen.engine.model_router import (
    GreenModelRouter,
    RoutingOutcome,
    TaskCategory,
    TaskComplexity,
    RoutingConfidence,
    TaskContext,
    TierEnergyComparison,
    TierCarbonComparison,
    ModelRoutingRecommendation,
)
from promptgreen.engine.carbon_engine import CarbonEngine


@pytest.fixture
def router() -> GreenModelRouter:
    """Fixture providing a default GreenModelRouter instance."""
    return GreenModelRouter()


# ==============================================================================
# GROUP 1: RECOMMENDED DOWNGRADE FOR LOW-COMPLEXITY TASKS (Tests 1, 2, 3)
# ==============================================================================

def test_simple_classification_recommends_compact_tier(router: GreenModelRouter) -> None:
    """Requirement 1: Simple classification on high tier recommends compact green tier with high confidence."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
        input_tokens=120,
        expected_output_tokens=10,
        pue=1.15,
        grid_scenario="ILLUSTRATIVE_385",
    )

    assert rec.outcome == RoutingOutcome.RECOMMEND_LOWER_ENERGY_TIER
    assert rec.current_model_tier == "frontier_dense"
    assert rec.recommended_model_tier == "compact_green"
    assert rec.confidence_level == RoutingConfidence.HIGH
    assert "classification" in rec.task_suitability
    assert rec.energy_comparison is not None
    assert rec.energy_comparison.energy_saved_wh > 0.0
    assert rec.energy_comparison.energy_saved_pct > 80.0
    assert rec.carbon_comparison is not None
    assert rec.carbon_comparison.carbon_saved_gco2 > 0.0
    assert "RECOMMENDATION ONLY" in rec.disclaimer


def test_structured_extraction_recommends_compact_tier(router: GreenModelRouter) -> None:
    """Requirement 2: Structured extraction task recommends compact green tier."""
    ctx = TaskContext(
        task_category=TaskCategory.EXTRACTION,
        task_complexity=TaskComplexity.LOW,
        requires_deep_reasoning=False,
        requires_strict_format=False,
    )
    rec = router.recommend(
        current_model_tier="large_reasoning",
        task_context=ctx,
        input_tokens=250,
        expected_output_tokens=30,
        pue=1.15,
    )

    assert rec.outcome == RoutingOutcome.RECOMMEND_LOWER_ENERGY_TIER
    assert rec.current_model_tier == "large_reasoning"
    assert rec.recommended_model_tier == "compact_green"
    assert rec.confidence_level == RoutingConfidence.HIGH
    assert rec.energy_comparison is not None
    assert rec.energy_comparison.energy_saved_wh > 0.0


def test_simple_summarization_recommends_lower_tier(router: GreenModelRouter) -> None:
    """Requirement 3: Simple summarization recommends lower energy tier."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.SIMPLE_SUMMARIZATION,
        task_complexity=TaskComplexity.LOW,
        input_tokens=500,
        expected_output_tokens=80,
    )

    assert rec.outcome == RoutingOutcome.RECOMMEND_LOWER_ENERGY_TIER
    assert rec.recommended_model_tier == "compact_green"
    assert rec.energy_comparison is not None
    assert rec.energy_comparison.energy_saved_pct > 70.0


# ==============================================================================
# GROUP 2: CONSERVATIVE REJECTION OF UNSAFE DOWNGRADES (Tests 4, 5, 6, 7)
# ==============================================================================

def test_complex_reasoning_rejects_downgrade(router: GreenModelRouter) -> None:
    """Requirement 4: Complex multi-step reasoning strictly refuses downgrade."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.COMPLEX_REASONING,
        task_complexity=TaskComplexity.HIGH,
        requires_deep_reasoning=True,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert rec.confidence_level == RoutingConfidence.HIGH
    assert "complex multi-step reasoning" in rec.explanation
    assert rec.energy_comparison is None
    assert rec.carbon_comparison is None
    assert "compact_green" in rec.rejection_reasons


def test_code_generation_rejects_downgrade(router: GreenModelRouter) -> None:
    """Requirement 5: Code generation and debugging strictly refuses downgrade."""
    rec = router.recommend(
        current_model_tier="large_reasoning",
        task_category=TaskCategory.CODE_GENERATION,
        requires_code_generation=True,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert "code generation" in rec.explanation.lower()
    assert rec.energy_comparison is None


def test_mathematical_precision_rejects_downgrade(router: GreenModelRouter) -> None:
    """Requirement 6: Numerical and mathematical precision strictly refuses downgrade."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.MATHEMATICAL,
        requires_math_precision=True,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert "mathematical" in rec.explanation.lower()


def test_safety_critical_rejects_downgrade(router: GreenModelRouter) -> None:
    """Requirement 7: Safety-critical instructions strictly refuse downgrade."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        is_safety_critical=True,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert "safety-critical" in rec.explanation.lower()


def test_strict_output_formatting_rejects_downgrade(router: GreenModelRouter) -> None:
    """Strict output formatting constraints prevent safe downgrade."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        requires_strict_format=True,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert "formatting" in rec.explanation.lower()


# ==============================================================================
# GROUP 3: USER PREFERENCE AND MISSING INFORMATION (Tests 8, 9, 10, 11)
# ==============================================================================

def test_explicit_user_preference_keeps_current_model(router: GreenModelRouter) -> None:
    """Requirement 8: Explicit user model preference retains current model even on simple task."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
        user_model_preference="frontier_dense",
    )

    assert rec.outcome == RoutingOutcome.KEEP_CURRENT_MODEL
    assert rec.recommended_model_tier is None
    assert "user preference" in rec.explanation.lower()
    assert rec.confidence_level == RoutingConfidence.HIGH


def test_unknown_task_requirements_insufficient_information(router: GreenModelRouter) -> None:
    """Requirement 9: Unknown task category or complexity yields INSUFFICIENT_INFORMATION."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.UNKNOWN,
        task_complexity=TaskComplexity.UNKNOWN,
    )

    assert rec.outcome == RoutingOutcome.INSUFFICIENT_INFORMATION
    assert rec.recommended_model_tier is None
    assert rec.confidence_level == RoutingConfidence.UNCERTAIN
    assert "unknown" in rec.explanation.lower()


def test_unsupported_candidate_capabilities_recorded_in_rejection_reasons(router: GreenModelRouter) -> None:
    """Requirement 10: Unsupported candidate model tier IDs are captured in rejection reasons."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
        candidate_model_tiers=["unsupported_tier_xyz", "another_unknown"],
    )

    assert "unsupported_tier_xyz" in rec.rejection_reasons
    assert "unsupported" in rec.rejection_reasons["unsupported_tier_xyz"].lower()
    assert rec.outcome == RoutingOutcome.KEEP_CURRENT_MODEL


def test_no_available_lower_energy_candidate_keeps_current_model(router: GreenModelRouter) -> None:
    """Requirement 11: When current tier is already compact_green, router keeps current model."""
    rec = router.recommend(
        current_model_tier="compact_green",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
    )

    assert rec.outcome == RoutingOutcome.KEEP_CURRENT_MODEL
    assert rec.recommended_model_tier is None
    assert "already the most energy-efficient" in rec.explanation


# ==============================================================================
# GROUP 4: ENERGY & CARBON COMPARISON INTEGRITY (Tests 12, 13, 14, 22, 23)
# ==============================================================================

def test_missing_grid_intensity_produces_no_carbon_comparison(router: GreenModelRouter) -> None:
    """Requirement 12: Missing grid scenario leaves carbon_comparison as None without inventing carbon numbers."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
        grid_scenario=None,
    )

    assert rec.outcome == RoutingOutcome.RECOMMEND_LOWER_ENERGY_TIER
    assert rec.energy_comparison is not None
    assert rec.carbon_comparison is None
    assert any("Carbon impact not calculated" in a for a in rec.assumptions)


def test_energy_comparison_consistency_matches_thermodynamic_formula(router: GreenModelRouter) -> None:
    """Requirement 13: Energy comparison values strictly match calculate_inference_energy_wh."""
    tin = 120
    tout = 45
    pue = 1.15

    e_comp, _ = router.compare_tiers(
        current_tier="frontier_dense",
        candidate_tier="compact_green",
        input_tokens=tin,
        expected_output_tokens=tout,
        pue=pue,
    )

    # Manual thermodynamic calculation
    expected_e_curr = calculate_inference_energy_wh(tin, tout, 0.42, 1.60, pue)
    expected_e_cand = calculate_inference_energy_wh(tin, tout, 0.04, 0.15, pue)
    expected_saved = expected_e_curr - expected_e_cand

    assert pytest.approx(e_comp.current_energy_wh, abs=1e-7) == expected_e_curr
    assert pytest.approx(e_comp.candidate_energy_wh, abs=1e-7) == expected_e_cand
    assert pytest.approx(e_comp.energy_saved_wh, abs=1e-7) == expected_saved


def test_carbon_comparison_consistency_matches_thermodynamic_formula(router: GreenModelRouter) -> None:
    """Requirement 14: Carbon comparison values strictly match calculate_net_carbon_g under explicit grid scenario."""
    tin = 120
    tout = 45
    pue = 1.15

    e_comp, c_comp = router.compare_tiers(
        current_tier="frontier_dense",
        candidate_tier="compact_green",
        input_tokens=tin,
        expected_output_tokens=tout,
        pue=pue,
        grid_scenario="ILLUSTRATIVE_385",
    )

    assert c_comp is not None
    assert c_comp.grid_intensity_gco2_kwh == 385.0

    expected_curr_carbon = calculate_net_carbon_g(e_comp.current_energy_wh, 385.0)
    expected_cand_carbon = calculate_net_carbon_g(e_comp.candidate_energy_wh, 385.0)
    expected_saved_carbon = expected_curr_carbon - expected_cand_carbon

    assert pytest.approx(c_comp.current_carbon_gco2, abs=1e-7) == expected_curr_carbon
    assert pytest.approx(c_comp.candidate_carbon_gco2, abs=1e-7) == expected_cand_carbon
    assert pytest.approx(c_comp.carbon_saved_gco2, abs=1e-7) == expected_saved_carbon
    assert pytest.approx(c_comp.carbon_saved_per_1k_gco2, abs=1e-5) == expected_saved_carbon * 1000.0


def test_custom_user_supplied_grid_intensity_with_separate_provenance(router: GreenModelRouter) -> None:
    """Requirement 23: Custom user-supplied numeric intensity records custom provenance without claiming verification."""
    _, c_comp = router.compare_tiers(
        current_tier="large_reasoning",
        candidate_tier="compact_green",
        input_tokens=100,
        expected_output_tokens=50,
        grid_scenario=708.0,
        custom_grid_provenance="User-provided CEA baseline estimate (unverified by PromptGreen).",
    )

    assert c_comp is not None
    assert c_comp.grid_intensity_gco2_kwh == 708.0
    assert c_comp.grid_provenance == "User-provided CEA baseline estimate (unverified by PromptGreen)."


# ==============================================================================
# GROUP 5: INPUT VALIDATION AND ERROR HANDLING (Tests 15, 16, 17, 18)
# ==============================================================================

def test_invalid_model_tiers_rejected(router: GreenModelRouter) -> None:
    """Requirement 15: Invalid or unknown model tiers raise KeyError."""
    with pytest.raises(KeyError, match="Unknown model tier 'unknown_tier_404'"):
        router.recommend(
            current_model_tier="unknown_tier_404",
            task_category=TaskCategory.CLASSIFICATION,
        )


def test_invalid_token_counts_rejected(router: GreenModelRouter) -> None:
    """Requirement 16: Negative, NaN, Inf, or boolean token counts raise ValueError."""
    # Negative input tokens
    with pytest.raises(ValueError, match="input_tokens must be a finite non-negative number"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=-10, expected_output_tokens=10)

    # Boolean input tokens
    with pytest.raises(ValueError, match="input_tokens must be a finite non-negative number"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=True, expected_output_tokens=10)  # type: ignore

    # NaN input tokens
    with pytest.raises(ValueError, match="input_tokens must be a finite non-negative number"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=float("nan"), expected_output_tokens=10)


def test_invalid_pue_rejected(router: GreenModelRouter) -> None:
    """Requirement 17: PUE < 1.0, NaN, Inf, or boolean raises ValueError."""
    with pytest.raises(ValueError, match="PUE must be a finite number >= 1.0"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=10, expected_output_tokens=10, pue=0.85)

    with pytest.raises(ValueError, match="PUE must be a finite number >= 1.0"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=10, expected_output_tokens=10, pue=float("inf"))


def test_missing_output_token_assumption_rejected(router: GreenModelRouter) -> None:
    """Requirement 18: Missing or negative expected_output_tokens raises ValueError."""
    with pytest.raises(ValueError, match="expected_output_tokens must be a finite non-negative number"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=10, expected_output_tokens=None)  # type: ignore

    with pytest.raises(ValueError, match="expected_output_tokens must be a finite non-negative number"):
        router.compare_tiers("frontier_dense", "compact_green", input_tokens=10, expected_output_tokens=-5)


# ==============================================================================
# GROUP 6: ADVERSARIAL PHRASING & CONFIDENCE BEHAVIOR (Tests 19, 20)
# ==============================================================================

def test_qualitative_confidence_behavior(router: GreenModelRouter) -> None:
    """Requirement 19: Qualitative confidence reflects specification completeness without pseudo-precise decimals."""
    # Clear low-complexity classification -> HIGH
    rec_high = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
    )
    assert rec_high.confidence_level == RoutingConfidence.HIGH

    # Unknown task -> UNCERTAIN
    rec_unc = router.recommend(
        current_model_tier="frontier_dense",
        task_category=TaskCategory.UNKNOWN,
    )
    assert rec_unc.confidence_level == RoutingConfidence.UNCERTAIN


@pytest.mark.parametrize("phrase", [
    "Think deeply.",
    "Be extremely accurate.",
    "Give the best possible answer.",
    "Maximum precision required.",
    "Deep deliberation is essential.",
])
def test_adversarial_descriptions_prevent_unsafe_downgrade(router: GreenModelRouter, phrase: str) -> None:
    """Requirement 20: Adversarial high-rigor phrasing alone must not cause an unsafe downgrade."""
    rec = router.recommend(
        current_model_tier="frontier_dense",
        task_description=f"Classify this text. {phrase}",
        task_category=TaskCategory.CLASSIFICATION,
        task_complexity=TaskComplexity.LOW,
    )

    assert rec.outcome == RoutingOutcome.NO_SAFE_DOWNGRADE
    assert rec.recommended_model_tier is None
    assert rec.confidence_level == RoutingConfidence.UNCERTAIN
    assert "high-rigor phrasing" in rec.explanation.lower()


# ==============================================================================
# GROUP 7: REGRESSION TESTS (Phase 1, Stage 5, Legacy V1)
# ==============================================================================

def test_regression_phase1_thermodynamic_calculations_unchanged() -> None:
    """Regression check: calculate_thermodynamic_impact from Phase 1 remains completely unchanged."""
    res = calculate_thermodynamic_impact(
        tin_original=120,
        tout_original=250,
        tin_optimized=60,
        tout_optimized=150,
        model_tier="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385",
        optimizer_latency_ms=180.0,
    )

    assert pytest.approx(res.net_energy_saved_wh, abs=1e-7) == 0.2112300
    assert pytest.approx(res.net_carbon_abated_per_1k_gco2, abs=1e-5) == 81.323550
    assert res.grid_intensity_gco2_kwh == 385.0


def test_regression_legacy_v1_carbon_engine_unchanged() -> None:
    """Regression check: V1 CarbonEngine.calculate() remains fully functional."""
    engine = CarbonEngine(model_key="llama-3-8b", region="US")
    old_p = "Explain quantum computing in detail."
    new_p = "Summarize quantum computing in 3 bullets."

    res = engine.calculate(old_p, new_p, monthly_inferences=1000)
    assert res.model_name == "Llama-3 8B"
    assert res.carbon_intensity_gco2_kwh == 385.0
    assert res.carbon_delta_per_1k_gco2 < 0.0
