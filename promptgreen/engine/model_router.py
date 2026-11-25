"""
Conservative Green Model Router for PromptGreen V2.

Evaluates whether an incoming task may be safely serviced by a lower-energy model tier
and provides transparent energy and carbon comparisons using Phase 1 thermodynamic formulas.

RECOMMENDATION ENGINE ONLY:
- Does NOT automatically switch the user's model.
- Does NOT call external LLM APIs.
- Does NOT claim semantic or functional equivalence.
- Strictly adheres to conservative safety defaults.
"""

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

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
)


class RoutingOutcome(str, Enum):
    """Explicit decision outcome from the Green Model Router."""
    KEEP_CURRENT_MODEL = "KEEP_CURRENT_MODEL"
    RECOMMEND_LOWER_ENERGY_TIER = "RECOMMEND_LOWER_ENERGY_TIER"
    NO_SAFE_DOWNGRADE = "NO_SAFE_DOWNGRADE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class TaskCategory(str, Enum):
    """Functional category of the user prompt task."""
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
    """Qualitative complexity rating of the task."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class RoutingConfidence(str, Enum):
    """
    Qualitative uncertainty classification for model routing recommendations.

    NOTE ON METHODOLOGY:
      These represent heuristic certainty levels based on task specification completeness,
      NOT empirical probabilities, benchmark scores, or quality guarantees.
    """
    HIGH = "HIGH"          # High confidence in low-complexity task suitability for compact tier
    MEDIUM = "MEDIUM"      # Moderate confidence with standard low-risk assumptions
    LOW = "LOW"            # Low confidence due to borderline complexity or mixed attributes
    UNCERTAIN = "UNCERTAIN"# High uncertainty due to ambiguous, adversarial, or missing information


@dataclass(frozen=True)
class TierEnergyComparison:
    """Like-for-like inference energy comparison between current and candidate model tiers."""
    current_tier_id: str
    candidate_tier_id: str
    current_energy_wh: float
    candidate_energy_wh: float
    energy_saved_wh: float
    energy_saved_pct: float
    pue_used: float
    input_tokens: float
    expected_output_tokens: float
    is_output_assumed: bool = True


@dataclass(frozen=True)
class TierCarbonComparison:
    """Carbon emissions comparison between current and candidate tiers under explicit grid intensity."""
    current_tier_id: str
    candidate_tier_id: str
    grid_intensity_gco2_kwh: float
    grid_provenance: str
    current_carbon_gco2: float
    candidate_carbon_gco2: float
    carbon_saved_gco2: float
    carbon_saved_per_1k_gco2: float


@dataclass(frozen=True)
class TaskContext:
    """
    Structured context and requirements describing the task for routing evaluation.
    """
    task_category: Union[str, TaskCategory] = TaskCategory.UNKNOWN
    task_complexity: Union[str, TaskComplexity] = TaskComplexity.UNKNOWN
    requires_deep_reasoning: bool = False
    requires_code_generation: bool = False
    requires_math_precision: bool = False
    requires_strict_format: bool = False
    is_safety_critical: bool = False
    user_model_preference: Optional[str] = None
    task_description: str = ""

    def get_category_enum(self) -> TaskCategory:
        """Resolve task_category to TaskCategory enum."""
        if isinstance(self.task_category, TaskCategory):
            return self.task_category
        val = str(self.task_category).lower().strip()
        for member in TaskCategory:
            if member.value == val or member.name.lower() == val:
                return member
        return TaskCategory.UNKNOWN

    def get_complexity_enum(self) -> TaskComplexity:
        """Resolve task_complexity to TaskComplexity enum."""
        if isinstance(self.task_complexity, TaskComplexity):
            return self.task_complexity
        val = str(self.task_complexity).lower().strip()
        for member in TaskComplexity:
            if member.value == val or member.name.lower() == val:
                return member
        return TaskComplexity.UNKNOWN


@dataclass(frozen=True)
class ModelRoutingRecommendation:
    """
    Structured result produced by the Green Model Router.
    Contains explicit decision, explanation, rejection audit trail, assumptions, and physical comparisons.
    """
    current_model_tier: str
    recommended_model_tier: Optional[str]
    outcome: RoutingOutcome
    task_suitability: str
    confidence_level: RoutingConfidence
    explanation: str
    rejection_reasons: Dict[str, str]
    assumptions: List[str]
    energy_comparison: Optional[TierEnergyComparison] = None
    carbon_comparison: Optional[TierCarbonComparison] = None
    disclaimer: str = (
        "RECOMMENDATION ONLY: PromptGreen does not automatically switch your selected model. "
        "Lower-energy models are not guaranteed to be semantically or functionally equivalent. "
        "Review task requirements before manual migration."
    )


# Phrasings that indicate high reasoning, extreme precision, or deliberation requirements
# These phrases alone must NOT cause an unsafe downgrade.
ADVERSARIAL_HIGH_RIGOR_PHRASES: Set[str] = {
    "think deeply",
    "be extremely accurate",
    "give the best possible answer",
    "maximum precision",
    "deep deliberation",
    "step-by-step proof",
    "rigorous mathematical proof",
    "zero tolerance for error",
    "mission critical",
}


class GreenModelRouter:
    """
    Conservative Green Model Router.

    Recommends lower-energy model tiers for tasks that demonstrably do not require
    large or frontier parameter capacities, while strictly protecting tasks with
    reasoning, mathematical, coding, safety, or formatting requirements from degradation.
    """

    def __init__(self, registry: Optional[ModelProfileRegistry] = None):
        self.registry = registry or DEFAULT_PROFILE_REGISTRY

    def compare_tiers(
        self,
        current_tier: Union[str, ModelTierProfile],
        candidate_tier: Union[str, ModelTierProfile],
        input_tokens: Union[int, float],
        expected_output_tokens: Union[int, float],
        pue: float = 1.15,
        grid_scenario: Optional[Union[str, GridIntensityScenario, float]] = None,
        custom_grid_provenance: Optional[str] = None,
    ) -> Tuple[TierEnergyComparison, Optional[TierCarbonComparison]]:
        """
        Conduct a like-for-like physical energy and carbon comparison between two model tiers.

        Args:
            current_tier: Current ModelTierProfile or tier ID string.
            candidate_tier: Candidate ModelTierProfile or tier ID string.
            input_tokens: Ingested prompt tokens (must be finite non-negative number).
            expected_output_tokens: Predicted/assumed output tokens (must be finite non-negative number).
            pue: Datacenter Power Usage Effectiveness (must be >= 1.0).
            grid_scenario: Optional grid scenario identifier, GridIntensityScenario, or user-supplied float.
            custom_grid_provenance: Optional provenance description for user-supplied float intensity.

        Returns:
            Tuple of (TierEnergyComparison, Optional[TierCarbonComparison]).
        """
        # Validate input tokens
        if isinstance(input_tokens, bool) or not isinstance(input_tokens, (int, float)) or not math.isfinite(input_tokens) or input_tokens < 0:
            raise ValueError(f"input_tokens must be a finite non-negative number, got {input_tokens}")

        # Validate expected output tokens (must not be None or invalid)
        if expected_output_tokens is None or isinstance(expected_output_tokens, bool) or not isinstance(expected_output_tokens, (int, float)) or not math.isfinite(expected_output_tokens) or expected_output_tokens < 0:
            raise ValueError(
                f"expected_output_tokens must be a finite non-negative number; output assumption required. Got {expected_output_tokens}"
            )

        # Validate PUE
        if isinstance(pue, bool) or not isinstance(pue, (int, float)) or not math.isfinite(pue) or pue < 1.0:
            raise ValueError(f"PUE must be a finite number >= 1.0 (physical efficiency lower bound), got {pue}")

        # Resolve tier profiles
        curr_prof = current_tier if isinstance(current_tier, ModelTierProfile) else self.registry.get_tier(current_tier)
        cand_prof = candidate_tier if isinstance(candidate_tier, ModelTierProfile) else self.registry.get_tier(candidate_tier)

        # Calculate like-for-like inference energy (Wh)
        # Note: Local optimizer overhead is identical for both downstream tiers and cancels out.
        e_curr = calculate_inference_energy_wh(
            tin=input_tokens,
            tout=expected_output_tokens,
            alpha_prefill_mwh=curr_prof.alpha_prefill_mwh,
            alpha_decode_mwh=curr_prof.alpha_decode_mwh,
            pue=pue,
        )
        e_cand = calculate_inference_energy_wh(
            tin=input_tokens,
            tout=expected_output_tokens,
            alpha_prefill_mwh=cand_prof.alpha_prefill_mwh,
            alpha_decode_mwh=cand_prof.alpha_decode_mwh,
            pue=pue,
        )

        e_saved = e_curr - e_cand
        e_saved_pct = (e_saved / e_curr * 100.0) if e_curr > 0 else 0.0

        energy_comp = TierEnergyComparison(
            current_tier_id=curr_prof.tier_id,
            candidate_tier_id=cand_prof.tier_id,
            current_energy_wh=e_curr,
            candidate_energy_wh=e_cand,
            energy_saved_wh=e_saved,
            energy_saved_pct=e_saved_pct,
            pue_used=float(pue),
            input_tokens=float(input_tokens),
            expected_output_tokens=float(expected_output_tokens),
            is_output_assumed=True,
        )

        # Carbon comparison requires explicit grid intensity; missing scenario produces None
        carbon_comp: Optional[TierCarbonComparison] = None
        if grid_scenario is not None:
            if isinstance(grid_scenario, str):
                scen_obj = self.registry.get_grid_scenario(grid_scenario)
                ci_val = scen_obj.carbon_intensity_gco2_kwh
                ci_prov = scen_obj.provenance
            elif isinstance(grid_scenario, GridIntensityScenario):
                ci_val = grid_scenario.carbon_intensity_gco2_kwh
                ci_prov = grid_scenario.provenance
            elif isinstance(grid_scenario, (int, float)):
                if isinstance(grid_scenario, bool) or not math.isfinite(grid_scenario) or grid_scenario <= 0:
                    raise ValueError(f"Custom grid intensity must be a finite positive number, got {grid_scenario}")
                ci_val = float(grid_scenario)
                ci_prov = (
                    custom_grid_provenance.strip()
                    if custom_grid_provenance and custom_grid_provenance.strip()
                    else f"User-supplied custom grid intensity: {ci_val:.1f} gCO2e/kWh (unverified user input)."
                )
            else:
                raise TypeError(f"Invalid grid_scenario type: {type(grid_scenario).__name__}")

            c_curr = calculate_net_carbon_g(e_curr, ci_val)
            c_cand = calculate_net_carbon_g(e_cand, ci_val)
            c_saved = c_curr - c_cand
            c_saved_1k = c_saved * 1000.0

            carbon_comp = TierCarbonComparison(
                current_tier_id=curr_prof.tier_id,
                candidate_tier_id=cand_prof.tier_id,
                grid_intensity_gco2_kwh=ci_val,
                grid_provenance=ci_prov,
                current_carbon_gco2=c_curr,
                candidate_carbon_gco2=c_cand,
                carbon_saved_gco2=c_saved,
                carbon_saved_per_1k_gco2=c_saved_1k,
            )

        return energy_comp, carbon_comp

    def recommend(
        self,
        current_model_tier: Union[str, ModelTierProfile],
        task_context: Optional[TaskContext] = None,
        task_category: Optional[Union[str, TaskCategory]] = None,
        task_complexity: Optional[Union[str, TaskComplexity]] = None,
        requires_deep_reasoning: bool = False,
        requires_code_generation: bool = False,
        requires_math_precision: bool = False,
        requires_strict_format: bool = False,
        is_safety_critical: bool = False,
        user_model_preference: Optional[str] = None,
        task_description: str = "",
        candidate_model_tiers: Optional[List[Union[str, ModelTierProfile]]] = None,
        input_tokens: Union[int, float] = 100,
        expected_output_tokens: Union[int, float] = 100,
        pue: float = 1.15,
        grid_scenario: Optional[Union[str, GridIntensityScenario, float]] = None,
        custom_grid_provenance: Optional[str] = None,
    ) -> ModelRoutingRecommendation:
        """
        Evaluate task suitability and generate a conservative model routing recommendation.

        Accepts either a TaskContext object or individual task parameter keywords.
        """
        # Resolve TaskContext
        if task_context is None:
            ctx = TaskContext(
                task_category=task_category or TaskCategory.UNKNOWN,
                task_complexity=task_complexity or TaskComplexity.UNKNOWN,
                requires_deep_reasoning=requires_deep_reasoning,
                requires_code_generation=requires_code_generation,
                requires_math_precision=requires_math_precision,
                requires_strict_format=requires_strict_format,
                is_safety_critical=is_safety_critical,
                user_model_preference=user_model_preference,
                task_description=task_description,
            )
        else:
            ctx = task_context

        # Resolve current tier profile
        curr_prof = (
            current_model_tier
            if isinstance(current_model_tier, ModelTierProfile)
            else self.registry.get_tier(current_model_tier)
        )

        cat = ctx.get_category_enum()
        complexity = ctx.get_complexity_enum()

        # Build list of assumptions
        assumptions: List[str] = [
            "Inference energy modeled using PromptGreen V2 thermodynamic prefill vs. decode coefficients.",
            f"Output token count assumed at {expected_output_tokens} tokens (modeled assumption; actual generation may vary).",
            f"Datacenter PUE assumed at {pue:.2f}.",
            "Lower-energy model recommendation does NOT establish semantic equivalence or identical accuracy.",
            "Optimizer CPU overhead is assumed identical across tiers and cancels out in like-for-like comparison.",
        ]
        if grid_scenario is not None:
            assumptions.append(f"Grid intensity scenario specified: {grid_scenario}.")
        else:
            assumptions.append("Carbon impact not calculated: no explicit grid intensity scenario was provided.")

        rejection_reasons: Dict[str, str] = {}

        # Resolve candidate tiers
        if candidate_model_tiers is None:
            candidate_profiles = [self.registry.get_tier(t) for t in self.registry.list_tiers()]
        else:
            candidate_profiles = []
            for t in candidate_model_tiers:
                if isinstance(t, ModelTierProfile):
                    candidate_profiles.append(t)
                else:
                    try:
                        candidate_profiles.append(self.registry.get_tier(t))
                    except KeyError:
                        rejection_reasons[str(t)] = f"Candidate tier '{t}' is unsupported or not found in registry."

        # Check for adversarial high-rigor phrasing in task description
        desc_lower = ctx.task_description.lower().strip()
        detected_adversarial_phrases = [
            phrase for phrase in ADVERSARIAL_HIGH_RIGOR_PHRASES if phrase in desc_lower
        ]

        # ----------------------------------------------------------------------
        # RULE 1: User explicitly preferred the current model tier
        # ----------------------------------------------------------------------
        if ctx.user_model_preference and (
            ctx.user_model_preference.lower().strip() == curr_prof.tier_id.lower().strip()
            or ctx.user_model_preference.lower().strip() == "current"
        ):
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.KEEP_CURRENT_MODEL,
                task_suitability=f"User explicitly expressed preference to retain current tier '{curr_prof.tier_id}'.",
                confidence_level=RoutingConfidence.HIGH,
                explanation=f"Explicit user preference to retain current model tier '{curr_prof.tier_id}'. Router will not override user preference.",
                rejection_reasons={p.tier_id: "User preferred current model tier." for p in candidate_profiles if p.tier_id != curr_prof.tier_id},
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 2: Safety-Critical Instructions
        # ----------------------------------------------------------------------
        if ctx.is_safety_critical or cat == TaskCategory.SAFETY_CRITICAL:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier rejected: task is safety-critical or high-consequence."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="Safety-critical instructions require verified high-capacity model.",
                confidence_level=RoutingConfidence.HIGH,
                explanation="Task is classified as safety-critical or high-consequence. Model tier downgrading is strictly prohibited.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 3: Complex Multi-Step Reasoning
        # ----------------------------------------------------------------------
        if ctx.requires_deep_reasoning or cat == TaskCategory.COMPLEX_REASONING or complexity == TaskComplexity.HIGH:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier lacks multi-step deductive reasoning depth."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="Complex reasoning requires high-capacity or frontier reasoning models.",
                confidence_level=RoutingConfidence.HIGH,
                explanation="Task requires complex multi-step reasoning. Lower-energy model tiers pose a high risk of logical degradation or hallucination.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 4: Code Generation and Debugging
        # ----------------------------------------------------------------------
        if ctx.requires_code_generation or cat == TaskCategory.CODE_GENERATION:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier has insufficient programming language syntax and architectural modeling capacity."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="Code generation and debugging require high-capacity language models.",
                confidence_level=RoutingConfidence.HIGH,
                explanation="Task requires code generation or debugging. Lower-energy model tiers lack sufficient code syntax and semantic representation capacity.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 5: Mathematical and Numerical Precision
        # ----------------------------------------------------------------------
        if ctx.requires_math_precision or cat == TaskCategory.MATHEMATICAL:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier susceptible to arithmetic inaccuracies and calculation hallucinations."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="Mathematical precision requires high-capacity mathematical reasoning models.",
                confidence_level=RoutingConfidence.HIGH,
                explanation="Task requires numerical or mathematical precision. Lower-energy tiers are susceptible to arithmetic inaccuracies and calculation hallucinations.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 6: Strict Output Formatting Constraints
        # ----------------------------------------------------------------------
        if ctx.requires_strict_format:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier cannot reliably guarantee strict output formatting constraints."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="Strict formatting requirements cannot be guaranteed on lower-energy tiers.",
                confidence_level=RoutingConfidence.MEDIUM,
                explanation="Task mandates strict output formatting constraints that cannot be reliably guaranteed by lower-energy model tiers.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 7: Adversarial or High-Rigor Phrasing Detected
        # ----------------------------------------------------------------------
        if detected_adversarial_phrases:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Candidate tier rejected due to high-rigor or adversarial phrasing in task description."
            phrases_str = ", ".join(f"'{p}'" for p in detected_adversarial_phrases)
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability="High-rigor or deliberate reasoning demands preclude compact model downgrade.",
                confidence_level=RoutingConfidence.UNCERTAIN,
                explanation=f"Task description contains high-rigor phrasing ({phrases_str}). Conservative safety policy prevents downgrading to lower-energy tiers.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 8: Unknown Category or Complexity (Insufficient Information)
        # ----------------------------------------------------------------------
        if cat == TaskCategory.UNKNOWN or complexity == TaskComplexity.UNKNOWN:
            for p in candidate_profiles:
                if p.tier_id != curr_prof.tier_id:
                    rejection_reasons[p.tier_id] = "Task characteristics are unknown or unspecified."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.INSUFFICIENT_INFORMATION,
                task_suitability="Task category or complexity is unknown.",
                confidence_level=RoutingConfidence.UNCERTAIN,
                explanation="Task category or complexity is unknown or unverified. Conservative safety policy requires verified task characteristics before recommending a lower-energy tier.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 9: Check Candidate Capabilities & Identify Lower-Energy Tiers
        # ----------------------------------------------------------------------
        # Compute baseline energy of current tier to find strictly lower-energy tiers
        e_curr_ref = curr_prof.alpha_prefill_mwh + curr_prof.alpha_decode_mwh

        # Find candidates with strictly lower energy than current tier
        lower_candidates: List[ModelTierProfile] = []
        for cand in candidate_profiles:
            if cand.tier_id == curr_prof.tier_id:
                rejection_reasons[cand.tier_id] = "Current model tier."
                continue
            e_cand_ref = cand.alpha_prefill_mwh + cand.alpha_decode_mwh
            if e_cand_ref >= e_curr_ref:
                rejection_reasons[cand.tier_id] = f"Candidate tier '{cand.tier_id}' consumes equal or greater energy ({e_cand_ref:.2f} >= {e_curr_ref:.2f} mWh/tok)."
            else:
                lower_candidates.append(cand)

        # If no lower energy tier exists
        if not lower_candidates:
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.KEEP_CURRENT_MODEL,
                task_suitability=f"Current tier '{curr_prof.tier_id}' is already the lowest-energy candidate available.",
                confidence_level=RoutingConfidence.HIGH,
                explanation=f"Current model tier '{curr_prof.tier_id}' is already the most energy-efficient tier among available candidates.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # ----------------------------------------------------------------------
        # RULE 10: Evaluate Downgrade for Simple / Demonstrably Low-Complexity Tasks
        # ----------------------------------------------------------------------
        # Eligible low-complexity categories:
        is_simple_task = cat in (
            TaskCategory.CLASSIFICATION,
            TaskCategory.EXTRACTION,
            TaskCategory.SIMPLE_SUMMARIZATION,
        ) or (
            cat in (TaskCategory.TRANSLATION, TaskCategory.GENERAL_SUMMARIZATION)
            and complexity == TaskComplexity.LOW
        )

        if not is_simple_task:
            for cand in lower_candidates:
                rejection_reasons[cand.tier_id] = f"Task category '{cat.value}' with '{complexity.value}' complexity is not demonstrably safe for lower-energy tier."
            return ModelRoutingRecommendation(
                current_model_tier=curr_prof.tier_id,
                recommended_model_tier=None,
                outcome=RoutingOutcome.NO_SAFE_DOWNGRADE,
                task_suitability=f"Task category '{cat.value}' does not meet conservative low-complexity criteria.",
                confidence_level=RoutingConfidence.MEDIUM,
                explanation=f"Task category '{cat.value}' with '{complexity.value}' complexity does not qualify for safe downgrade. Retaining current tier '{curr_prof.tier_id}'.",
                rejection_reasons=rejection_reasons,
                assumptions=assumptions,
            )

        # Select the most efficient viable lower candidate (sorted by energy ascending)
        lower_candidates.sort(key=lambda p: (p.alpha_prefill_mwh + p.alpha_decode_mwh))
        recommended_tier = lower_candidates[0]

        # Record rejection reasons for other lower candidates that were not selected (if any)
        for other_cand in lower_candidates[1:]:
            rejection_reasons[other_cand.tier_id] = (
                f"Candidate '{other_cand.tier_id}' consumes more energy than optimal recommendation '{recommended_tier.tier_id}'."
            )

        # Determine qualitative confidence
        if cat in (TaskCategory.CLASSIFICATION, TaskCategory.EXTRACTION) and complexity == TaskComplexity.LOW:
            confidence = RoutingConfidence.HIGH
        else:
            confidence = RoutingConfidence.MEDIUM

        # Perform physical energy & carbon comparison
        e_comp, c_comp = self.compare_tiers(
            current_tier=curr_prof,
            candidate_tier=recommended_tier,
            input_tokens=input_tokens,
            expected_output_tokens=expected_output_tokens,
            pue=pue,
            grid_scenario=grid_scenario,
            custom_grid_provenance=custom_grid_provenance,
        )

        suitability_msg = (
            f"Task '{cat.value}' with '{complexity.value}' complexity is demonstrably suitable for "
            f"lower-energy tier '{recommended_tier.tier_id}' ({recommended_tier.display_name})."
        )
        explanation_msg = (
            f"Task requirements do not require high-capacity models. Downgrading to '{recommended_tier.tier_id}' "
            f"can save an estimated {e_comp.energy_saved_wh:.4f} Wh ({e_comp.energy_saved_pct:.1f}%) per inference."
        )

        return ModelRoutingRecommendation(
            current_model_tier=curr_prof.tier_id,
            recommended_model_tier=recommended_tier.tier_id,
            outcome=RoutingOutcome.RECOMMEND_LOWER_ENERGY_TIER,
            task_suitability=suitability_msg,
            confidence_level=confidence,
            explanation=explanation_msg,
            rejection_reasons=rejection_reasons,
            assumptions=assumptions,
            energy_comparison=e_comp,
            carbon_comparison=c_comp,
        )
