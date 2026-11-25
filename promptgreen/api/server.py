"""
PromptGreen REST API Server (v2.0)
Unified RESTful service exposing 4-stage prompt optimization, thermodynamic energy and carbon
modeling, conservative model routing, and persistent telemetry ledger.
"""

import math
import os
import time
from typing import Optional, List, Dict, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from promptgreen.optimizer.pipeline import (
    PromptGreenPipeline,
    PipelineConfig,
    PipelineResult,
)
from promptgreen.optimizer.semantic_guard import LocalMiniLMEmbedder, GuardrailConfig
from promptgreen.engine.model_profiles import (
    DEFAULT_PROFILE_REGISTRY,
    STANDARD_MODEL_TIERS,
    STANDARD_GRID_SCENARIOS,
    UNAVAILABLE_REGIONAL_PLACEHOLDERS,
    ModelTierProfile,
    GridIntensityScenario,
    THESIS_PROVENANCE_WARNING,
    WATER_COEFFICIENT_WARNING,
    CPU_POWER_ESTIMATE_WARNING,
)
from promptgreen.engine.thermodynamics import (
    calculate_thermodynamic_impact,
    calculate_multi_scenario_impact,
    EnergyCarbonResult,
    MultiScenarioEnergyResult,
    AccountingScenario,
)
from promptgreen.engine.model_router import (
    GreenModelRouter,
    RoutingOutcome,
    RoutingConfidence,
    TaskCategory,
    TaskComplexity,
    TaskContext,
    ModelRoutingRecommendation,
)
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.ledger.database import PromptLedger, OptimizationEvent
from promptgreen.gate.prompt_gate import PromptGate, GateResult
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm the cached MiniLM embedding model during server startup without downloading."""
    if not os.environ.get("PROMPTGREEN_SKIP_PREWARM"):
        try:
            import asyncio
            await asyncio.to_thread(LocalMiniLMEmbedder.prewarm)
        except Exception as exc:
            pass
    yield


app = FastAPI(
    title="PromptGreen REST API",
    description="Active Prompt Optimization and Carbon-Aware Telemetry Engine for Sustainable LLM Inference",
    version="2.0.0",
    lifespan=lifespan
)

# Enable robust CORS for local web UI, development servers, and evaluation tools
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = PromptDiffAnalyzer()
predictor = HybridPredictor()
router = GreenModelRouter(registry=DEFAULT_PROFILE_REGISTRY)

# Mapping of legacy model names and aliases to standard V2 model tiers
TIER_ALIAS_MAP: Dict[str, str] = {
    "frontier_dense": "frontier_dense",
    "gpt-4": "frontier_dense",
    "gpt-4o": "frontier_dense",
    "claude-3-5-sonnet": "frontier_dense",
    "large_reasoning": "large_reasoning",
    "llama-3-70b": "large_reasoning",
    "qwen-2.5-72b": "large_reasoning",
    "mid_tier": "mid_tier",
    "llama-3-8b": "mid_tier",
    "mistral-7b": "mid_tier",
    "mixtral-8x7b": "mid_tier",
    "compact_green": "compact_green",
    "phi-3-3.8b": "compact_green",
    "phi-3.5": "compact_green",
    "llama-3.2-3b": "compact_green",
}


# ==============================================================================
# V1 REQUEST / RESPONSE SCHEMAS & ENDPOINTS (BACKWARD COMPATIBILITY)
# ==============================================================================

class PromptReviewRequest(BaseModel):
    old_prompt: str
    new_prompt: str
    model_name: Optional[str] = "llama-3-8b"
    region: Optional[str] = "US"
    budget_threshold: Optional[float] = 0.5
    mode: Optional[str] = "warn"
    monthly_inferences: Optional[int] = 10000
    author: Optional[str] = "api-user"
    team: Optional[str] = "Engineering"


class PromptGenerateRequest(BaseModel):
    prompt: str


@app.get("/api")
@app.get("/api/v2")
@app.get("/api/health")
@app.get("/health")
def read_root():
    pw = LocalMiniLMEmbedder.get_prewarm_status()
    cold_energy_wh = None
    if pw.get("init_latency_ms") is not None:
        cold_energy_wh = round(35.0 * (float(pw["init_latency_ms"]) / 3_600_000.0), 6)

    return {
        "status": "active",
        "system": "PromptGreen",
        "version": "2.0.0",
        "model_prewarming": {
            "is_prewarmed": pw["is_prewarmed"],
            "model_name": pw["model_name"],
            "status_message": pw["status_message"],
            "cold_init_latency_ms": pw["init_latency_ms"],
            "cold_init_energy_wh_modeled": cold_energy_wh,
        },
        "endpoints": {
            "v2_optimize": "/api/v2/optimize",
            "v2_models": "/api/v2/models",
            "v2_grid_scenarios": "/api/v2/grid-scenarios",
            "v2_ledger_summary": "/api/v2/ledger/summary",
            "v1_generate_green": "/api/v1/generate-green",
            "v1_review": "/api/v1/review",
        }
    }


@app.get("/")
@app.get("/app")
@app.get("/website")
@app.get("/studio")
def serve_root_ui():
    """Serves the Green Prompt Studio web interface at the root URL."""
    import os
    website_html = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Website", "index.html"))
    if os.path.exists(website_html):
        return FileResponse(website_html)
    return read_root()


@app.get("/evaluation")
@app.get("/evolution")
def serve_evaluation_ui():
    """Serves the PromptGreen V1 vs V2 Evolution & Evaluation page."""
    import os
    eval_html = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Website", "evaluation.html"))
    if os.path.exists(eval_html):
        return FileResponse(eval_html)
    return serve_root_ui()


@app.post("/api/v1/generate-green")
def generate_green_prompt(req: PromptGenerateRequest):
    """Generates a carbon-optimized green alternative prompt (V1 endpoint)."""
    try:
        if not req.prompt or not req.prompt.strip():
            raise HTTPException(status_code=400, detail="Prompt must be a non-empty string.")
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode="balanced"))
        opt_res = pipeline.optimize(req.prompt)
        return {
            "original_prompt": req.prompt,
            "green_prompt": opt_res.final_prompt,
            "token_reduction_pct": opt_res.net_token_reduction_pct,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/review")
def review_prompt(req: PromptReviewRequest):
    """Evaluates prompt change against carbon gate budget and logs to ledger (V1 endpoint)."""
    try:
        gate = PromptGate(
            budget_threshold_gco2_1k=req.budget_threshold,
            mode=req.mode,
            model_key=req.model_name,
            region=req.region
        )
        res = gate.evaluate(
            req.old_prompt,
            req.new_prompt,
            monthly_inferences=req.monthly_inferences
        )

        c = res.carbon_result

        # Record to ledger
        db = PromptLedger()
        db.record_prompt_review(
            commit_hash="api-call",
            author=req.author,
            team=req.team,
            model_name=c.model_name,
            region=req.region,
            old_prompt=req.old_prompt[:100],
            new_prompt=req.new_prompt[:100],
            input_token_delta=c.features.input_token_delta,
            predicted_output_token_delta=c.prediction.predicted_output_token_delta,
            carbon_delta_gco2_1k=c.carbon_delta_per_1k_gco2,
            monthly_carbon_delta_gco2=c.monthly_carbon_delta_gco2,
            status=res.status_code
        )

        diff_summary = "; ".join(c.features.detected_changes) if c.features.detected_changes else "Minor textual edits."
        model_matrix = gate.engine.compare_all_models(req.old_prompt, req.new_prompt)

        return {
            "passed": res.passed,
            "status_code": res.status_code,
            "budget_threshold_gco2_1k": res.budget_threshold_gco2_1k,
            "actual_delta_gco2_1k": res.actual_delta_gco2_1k,
            "monthly_carbon_delta_gco2": c.monthly_carbon_delta_gco2,

            "old_input_tokens": c.features.old_input_tokens,
            "new_input_tokens": c.features.new_input_tokens,
            "input_token_delta": c.features.input_token_delta,

            "predicted_old_output_tokens": c.prediction.predicted_old_output_tokens,
            "predicted_new_output_tokens": c.prediction.predicted_new_output_tokens,
            "predicted_output_token_delta": c.prediction.predicted_output_token_delta,
            "inflation_percentage": c.prediction.inflation_percentage,

            "old_energy_per_inf_mj": c.old_energy_per_inf_mj,
            "new_energy_per_inf_mj": c.new_energy_per_inf_mj,
            "energy_delta_per_inf_mj": c.energy_delta_per_inf_mj,

            "old_carbon_per_inf_gco2": c.old_carbon_per_inf_gco2,
            "new_carbon_per_inf_gco2": c.new_carbon_per_inf_gco2,
            "carbon_delta_per_inf_gco2": c.carbon_delta_per_inf_gco2,

            "equiv_smartphone_charges_monthly": c.equiv_smartphone_charges_monthly,
            "equiv_car_miles_monthly": c.equiv_car_miles_monthly,
            "equiv_tree_absorption_days": c.equiv_tree_absorption_days,

            "model_matrix": model_matrix,
            "detected_changes": c.features.detected_changes,
            "difference_summary": diff_summary,
            "suggestions": res.suggestions,
            "markdown_report": res.markdown_report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/ledger/recent")
def get_recent_ledger(limit: int = 20):
    db = PromptLedger()
    return db.get_recent_records(limit=limit)


@app.get("/api/v1/ledger/summary")
def get_ledger_summary():
    db = PromptLedger()
    return db.get_cumulative_carbon_debt()


# ==============================================================================
# V2 UNIFIED REQUEST / RESPONSE SCHEMAS & ENDPOINTS
# ==============================================================================

class V2OptimizeRequest(BaseModel):
    prompt: str = Field(..., description="Prompt text to be analyzed and optimized")
    mode: Optional[str] = Field("balanced", description="Optimization mode: conservative, balanced, or aggressive")
    target_model: Optional[str] = Field("mid_tier", description="Target model tier: frontier_dense, large_reasoning, mid_tier, compact_green")
    grid_scenario: Optional[str] = Field("ILLUSTRATIVE_385", description="Regional grid scenario: ILLUSTRATIVE_385 or THESIS_367")
    custom_grid_intensity: Optional[float] = Field(None, description="Optional user-supplied grid intensity in gCO2e/kWh")
    custom_grid_provenance: Optional[str] = Field(None, description="Optional provenance documentation for custom grid intensity")
    monthly_inferences: Optional[int] = Field(10000, description="Projected monthly request volume for footprint calculation")
    task_description: Optional[str] = Field(None, description="Optional task description for model router classification")
    task_category: Optional[str] = Field(None, description="Optional task category: creative, coding, reasoning, administrative, etc.")
    task_complexity: Optional[str] = Field(None, description="Optional task complexity: simple, moderate, complex")
    author: Optional[str] = Field("api-user", description="Author identifier for audit ledger")
    team: Optional[str] = Field("Engineering", description="Team identifier for audit ledger")
    record_in_ledger: Optional[bool] = Field(True, description="Whether to persist this optimization run into the SQLite ledger")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Optional target cosine similarity threshold (enforces minimum universal floor of 0.92)")
    measured_output_original: Optional[int] = Field(None, description="Optional empirically measured baseline output token count")
    measured_output_optimized: Optional[int] = Field(None, description="Optional empirically measured optimized output token count")


@app.post("/api/v2/optimize")
def optimize_prompt_v2(req: V2OptimizeRequest):
    """
    Unified PromptGreen V2 Orchestration Endpoint.
    Executes:
    1. 4-Stage Active Optimization Pipeline (Structural Pruner -> Lingua Compressor -> Directive Shaper -> Semantic Guard).
    2. Hybrid Token Inflation Predictor for downstream output token count estimation.
    3. Thermodynamic Energy, Carbon, and Water Footprint Impact Calculation in canonical Watt-hours (Wh).
    4. Conservative Green Model Router Evaluation with like-for-like physical energy comparison.
    5. Persistent Telemetry Logging into the Prompt Carbon Ledger.
    """
    total_start_time = time.perf_counter()

    # 1. Validation
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must be a non-empty string.")

    req_mode = (req.mode or "balanced").lower().strip()
    valid_modes = {"conservative", "balanced", "aggressive"}
    if req_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{req.mode}'. Must be one of: {sorted(list(valid_modes))}"
        )

    # 2. Resolve Model Tier
    raw_model = (req.target_model or "mid_tier").lower().strip()
    tier_id = TIER_ALIAS_MAP.get(raw_model, raw_model)
    try:
        tier_profile = DEFAULT_PROFILE_REGISTRY.get_tier(tier_id)
    except KeyError:
        # Fallback to mid_tier if unknown
        tier_id = "mid_tier"
        tier_profile = DEFAULT_PROFILE_REGISTRY.get_tier(tier_id)

    # 3. Resolve Grid Intensity Scenario
    grid_input = (req.grid_scenario or "ILLUSTRATIVE_385").strip()
    custom_prov: Optional[str] = None
    grid_arg: Union[str, float]

    if req.custom_grid_intensity is not None and req.custom_grid_intensity > 0:
        grid_arg = float(req.custom_grid_intensity)
        custom_prov = req.custom_grid_provenance or f"User-supplied custom grid intensity: {grid_arg:.1f} gCO2e/kWh (unverified user input)."
    elif grid_input.upper() in {"US", "385", "385.0", "ILLUSTRATIVE_385"}:
        grid_arg = "ILLUSTRATIVE_385"
    elif grid_input.upper() in {"THESIS_GLOBAL", "367", "367.0", "THESIS_367"}:
        grid_arg = "THESIS_367"
    else:
        try:
            val = float(grid_input)
            if val > 0:
                grid_arg = val
                custom_prov = req.custom_grid_provenance or f"User-supplied custom grid intensity: {val:.1f} gCO2e/kWh (unverified user input)."
            else:
                grid_arg = "ILLUSTRATIVE_385"
        except ValueError:
            try:
                DEFAULT_PROFILE_REGISTRY.get_grid_scenario(grid_input)
                grid_arg = grid_input.upper()
            except KeyError:
                grid_arg = "ILLUSTRATIVE_385"

    # 4. Execute 4-Stage Active Optimization Pipeline
    active_threshold: Optional[float] = None
    if req.threshold is not None:
        # Strict academic compliance: enforce universal 0.92 floor
        active_threshold = max(float(req.threshold), 0.92)

    t_pipeline_start = time.perf_counter()
    if active_threshold is not None:
        guardrail_cfg = GuardrailConfig(mode=req_mode, threshold=active_threshold)
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=req_mode, guardrail_config=guardrail_cfg))
    else:
        pipeline = PromptGreenPipeline(config=PipelineConfig(mode=req_mode))
    opt_res: PipelineResult = pipeline.optimize(req.prompt)
    pipeline_latency_ms = (time.perf_counter() - t_pipeline_start) * 1000.0

    # 4.1 Establish Outcome Category & Expansion Handling
    if not opt_res.success:
        outcome = "ERROR"
        outcome_label = "ERROR — Execution failed"
        status_code = "FAIL"
        effective_prompt = opt_res.original_prompt
        effective_tokens = opt_res.original_token_count
        tokens_saved = 0
        reduction_pct = 0.0
        expansion_prevented = False
        attempted_expansion_tokens = 0
        attempted_candidate_prompt = None
    elif opt_res.rollback_occurred or not opt_res.guardrail_passed:
        outcome = "ROLLBACK"
        outcome_label = "ROLLBACK — Original restored"
        status_code = "WARN"
        effective_prompt = opt_res.original_prompt
        effective_tokens = opt_res.original_token_count
        tokens_saved = 0
        reduction_pct = 0.0
        expansion_prevented = False
        attempted_expansion_tokens = 0
        attempted_candidate_prompt = None
    elif opt_res.net_token_reduction < 0:
        outcome = "EXPANSION"
        outcome_label = "EXPANSION — Original retained"
        status_code = "WARN"
        # Candidate expanded without token reduction benefit; retain original prompt
        effective_prompt = opt_res.original_prompt
        effective_tokens = opt_res.original_token_count
        tokens_saved = 0
        reduction_pct = 0.0
        expansion_prevented = True
        attempted_expansion_tokens = opt_res.final_token_count - opt_res.original_token_count
        attempted_candidate_prompt = opt_res.final_prompt
    elif opt_res.net_token_reduction == 0:
        outcome = "NO_CHANGE"
        outcome_label = "NO CHANGE — Original retained"
        status_code = "WARN"
        effective_prompt = opt_res.final_prompt
        effective_tokens = opt_res.final_token_count
        tokens_saved = 0
        reduction_pct = 0.0
        expansion_prevented = False
        attempted_expansion_tokens = 0
        attempted_candidate_prompt = None
    else:
        outcome = "SUCCESS"
        outcome_label = "SUCCESS — Optimized"
        status_code = "PASS"
        effective_prompt = opt_res.final_prompt
        effective_tokens = opt_res.final_token_count
        tokens_saved = opt_res.net_token_reduction
        reduction_pct = round(opt_res.net_token_reduction_pct, 2)
        expansion_prevented = False
        attempted_expansion_tokens = 0
        attempted_candidate_prompt = None

    # 5. Predict Output Tokens using Hybrid Predictor
    pred_res = predictor.predict(opt_res.original_prompt, effective_prompt)
    tout_orig = max(1.0, float(pred_res.predicted_old_output_tokens))
    if effective_prompt.strip() == opt_res.original_prompt.strip():
        # Physical consistency: When the prompt is completely unchanged, downstream output distribution is identical
        tout_opt = tout_orig
    else:
        tout_opt = max(1.0, float(pred_res.predicted_new_output_tokens))

    # 6. Multi-Scenario Thermodynamic Impact Calculation
    is_identical = (effective_prompt.strip() == opt_res.original_prompt.strip())
    multi_thermo: MultiScenarioEnergyResult = calculate_multi_scenario_impact(
        tin_original=opt_res.original_token_count,
        tin_optimized=effective_tokens,
        optimizer_latency_ms=pipeline_latency_ms,
        model_tier=tier_profile,
        grid_scenario=grid_arg,
        custom_grid_provenance=custom_prov,
        predicted_tout_original=tout_orig,
        predicted_tout_optimized=tout_opt,
        measured_tout_original=req.measured_output_original,
        measured_tout_optimized=req.measured_output_optimized,
        is_prompt_identical=is_identical,
    )
    thermo_res: EnergyCarbonResult = multi_thermo.input_plus_predicted_output

    # 7. Conservative Green Model Router Recommendation
    # Map or detect task category
    cat = TaskCategory.UNKNOWN
    if req.task_category:
        try:
            cat = TaskCategory[req.task_category.upper().strip()]
        except KeyError:
            try:
                cat = TaskCategory(req.task_category.lower().strip())
            except ValueError:
                cat = TaskCategory.UNKNOWN
    elif "def " in req.prompt or "function" in req.prompt or "python" in req.prompt.lower():
        cat = TaskCategory.CODE_GENERATION
    elif "step-by-step" in req.prompt.lower() or "calculate" in req.prompt.lower():
        cat = TaskCategory.COMPLEX_REASONING

    complexity = TaskComplexity.MEDIUM
    if req.task_complexity:
        try:
            complexity = TaskComplexity[req.task_complexity.upper().strip()]
        except KeyError:
            try:
                complexity = TaskComplexity(req.task_complexity.lower().strip())
            except ValueError:
                complexity = TaskComplexity.MEDIUM

    task_ctx = TaskContext(
        task_category=cat,
        task_complexity=complexity,
        task_description=req.task_description or req.prompt[:150],
        requires_code_generation=(cat == TaskCategory.CODE_GENERATION),
        requires_deep_reasoning=(cat == TaskCategory.COMPLEX_REASONING),
    )

    routing_rec: ModelRoutingRecommendation = router.recommend(
        current_model_tier=tier_profile,
        task_context=task_ctx,
        input_tokens=effective_tokens,
        expected_output_tokens=tout_opt,
        grid_scenario=grid_arg,
        custom_grid_provenance=custom_prov,
    )

    # 8. Record in Prompt Carbon Ledger
    monthly_inf = max(1, req.monthly_inferences or 10000)

    # Disambiguate compressor target retention rate vs. final token retention ratio
    last_compressor_attempt_retention_rate = getattr(opt_res, "last_compressor_attempt_retention_rate", None)
    accepted_compressor_retention_rate = getattr(opt_res, "accepted_compressor_retention_rate", None)
    compressor_retention_rate = accepted_compressor_retention_rate  # Backward-compatible alias
    final_token_retention_ratio = round(effective_tokens / opt_res.original_token_count, 4) if opt_res.original_token_count > 0 else 1.0
    actual_retention_rate = final_token_retention_ratio  # Backward-compatible alias for final token retention ratio

    # Genuine modeled energy components in Joules (no manufactured zeros)
    modeled_prefill_energy_j = thermo_res.modeled_prefill_energy_j
    modeled_decode_energy_j = thermo_res.modeled_decode_energy_j
    modeled_total_energy_j = thermo_res.modeled_total_energy_j if thermo_res.modeled_total_energy_j is not None else round(thermo_res.energy_opt_wh * 3600.0, 6)

    # Format Pipeline Stage Details and Token Breakdown
    stage_breakdown = []
    stage_breakdown_dict = {}
    for s_name, s_exec in opt_res.stage_executions.items():
        s_data = {
            "stage_id": s_exec.stage_id,
            "stage_name": s_exec.stage_name,
            "status": s_exec.status,
            "input_tokens": s_exec.input_tokens,
            "output_tokens": s_exec.output_tokens,
            "token_delta": s_exec.token_delta,
            "latency_ms": round(s_exec.latency_ms, 2),
            "method_used": s_exec.method_used,
            "warnings": s_exec.warnings,
        }
        stage_breakdown.append(s_data)
        stage_breakdown_dict[s_name] = s_data

    token_breakdown_dict = {
        "original_tokens": opt_res.original_token_count,
        "stage_1_tokens": opt_res.stage_1_token_count,
        "stage_2_tokens": opt_res.stage_2_token_count,
        "stage_3_tokens": opt_res.stage_3_token_count,
        "final_tokens": effective_tokens,
        "tokens_saved": tokens_saved,
        "last_compressor_attempt_retention_rate": last_compressor_attempt_retention_rate,
        "accepted_compressor_retention_rate": accepted_compressor_retention_rate,
        "compressor_retention_rate": compressor_retention_rate,
        "final_token_retention_ratio": final_token_retention_ratio,
        "actual_retention_rate": actual_retention_rate,
    }

    rec_id: Optional[int] = None
    if req.record_in_ledger:
        db = PromptLedger()
        opt_latency_ms = (time.perf_counter() - total_start_time) * 1000.0
        evt = OptimizationEvent(
            prompt_category="general",
            author=req.author or "api-user",
            team=req.team or "Engineering",
            model_name=tier_profile.tier_id,
            region=str(grid_arg),
            original_text=opt_res.original_prompt,
            optimized_text=effective_prompt,
            original_tokens=opt_res.original_token_count,
            optimized_tokens=effective_tokens,
            tokens_saved=max(0, opt_res.original_token_count - effective_tokens),
            compression_ratio=actual_retention_rate,
            semantic_similarity=opt_res.semantic_similarity if opt_res.semantic_similarity is not None else 1.0,
            optimization_latency_ms=opt_latency_ms,
            pipeline_stages_applied=req_mode.upper(),
            routing_decision=routing_rec.outcome.name,
            recommended_tier=routing_rec.recommended_model_tier or tier_profile.tier_id,
            modeled_prefill_energy_j=modeled_prefill_energy_j,
            modeled_decode_energy_j=modeled_decode_energy_j,
            modeled_total_energy_j=modeled_total_energy_j,
            modeled_carbon_gco2e=thermo_res.net_carbon_abated_gco2,
            net_energy_wh=thermo_res.net_energy_saved_wh,
            water_saved_ml=thermo_res.net_water_saved_ml,
            grid_carbon_intensity=thermo_res.grid_intensity_gco2_kwh,
            status=status_code,
            stage_breakdown=stage_breakdown_dict,
            token_breakdown=token_breakdown_dict,
            retry_count=opt_res.retry_count,
            fallback_type=getattr(opt_res, "fallback_type", "none") or "none",
            actual_retention_rate=actual_retention_rate,
            rollback_stage=opt_res.rollback_stage or "none",
            compressor_retention_rate=compressor_retention_rate,
            final_token_retention_ratio=final_token_retention_ratio,
            accepted_compressor_retention_rate=accepted_compressor_retention_rate,
            last_compressor_attempt_retention_rate=last_compressor_attempt_retention_rate,
        )
        rec_id = db.record_v2_run(
            commit_hash="v2-api",
            author=req.author or "api-user",
            team=req.team or "Engineering",
            model_name=tier_profile.tier_id,
            region=str(grid_arg),
            old_prompt=opt_res.original_prompt[:100],
            new_prompt=effective_prompt[:100],
            input_token_delta=effective_tokens - opt_res.original_token_count,
            predicted_output_token_delta=tout_opt - tout_orig,
            carbon_delta_gco2_1k=-(thermo_res.net_carbon_abated_per_1k_gco2),
            monthly_carbon_delta_gco2=-(thermo_res.net_carbon_abated_gco2 * monthly_inf),
            status=status_code,
            opt_mode=req_mode.upper(),
            semantic_score=opt_res.semantic_similarity if opt_res.semantic_similarity is not None else 1.0,
            net_energy_wh=thermo_res.net_energy_saved_wh,
            net_carbon_g=thermo_res.net_carbon_abated_gco2,
            water_saved_ml=thermo_res.net_water_saved_ml,
            routing_outcome=routing_rec.outcome.name,
            recommended_tier=routing_rec.recommended_model_tier or tier_profile.tier_id,
            latency_ms=opt_latency_ms,
            retry_count=opt_res.retry_count,
            fallback_type=getattr(opt_res, "fallback_type", "none") or "none",
            actual_retention_rate=actual_retention_rate,
            rollback_stage=opt_res.rollback_stage or "none",
            compressor_retention_rate=compressor_retention_rate,
            final_token_retention_ratio=final_token_retention_ratio,
            accepted_compressor_retention_rate=accepted_compressor_retention_rate,
            last_compressor_attempt_retention_rate=last_compressor_attempt_retention_rate,
        )
        db.record_optimization_event(evt, mirror_to_prompt_records=False)

    # Energy comparison serialization for router
    energy_comp_dict = None
    if routing_rec.energy_comparison:
        ec = routing_rec.energy_comparison
        energy_comp_dict = {
            "current_tier_id": ec.current_tier_id,
            "candidate_tier_id": ec.candidate_tier_id,
            "current_energy_wh": round(ec.current_energy_wh, 6),
            "candidate_energy_wh": round(ec.candidate_energy_wh, 6),
            "energy_saved_wh": round(ec.energy_saved_wh, 6),
            "energy_saved_pct": round(ec.energy_saved_pct, 1),
            "pue_used": ec.pue_used,
        }

    carbon_comp_dict = None
    if routing_rec.carbon_comparison:
        cc = routing_rec.carbon_comparison
        carbon_comp_dict = {
            "current_tier_id": cc.current_tier_id,
            "candidate_tier_id": cc.candidate_tier_id,
            "grid_intensity_gco2_kwh": round(cc.grid_intensity_gco2_kwh, 2),
            "grid_provenance": cc.grid_provenance,
            "current_carbon_gco2": round(cc.current_carbon_gco2, 6),
            "candidate_carbon_gco2": round(cc.candidate_carbon_gco2, 6),
            "carbon_saved_gco2": round(cc.carbon_saved_gco2, 6),
            "carbon_saved_per_1k_gco2": round(cc.carbon_saved_per_1k_gco2, 4),
        }

    total_duration_ms = (time.perf_counter() - total_start_time) * 1000.0

    return {
        "success": opt_res.success,
        "status_code": status_code,
        "outcome": outcome,
        "outcome_label": outcome_label,
        "mode": req_mode.upper(),
        "latency_ms": round(total_duration_ms, 2),
        "pipeline_latency_ms": round(pipeline_latency_ms, 2),

        # Prompts & Token Accounting
        "prompts": {
            "original_prompt": opt_res.original_prompt,
            "optimized_prompt": effective_prompt,
            "original_input_tokens": opt_res.original_token_count,
            "optimized_input_tokens": effective_tokens,
            "input_tokens_saved": tokens_saved,
            "input_reduction_pct": reduction_pct,
            "last_compressor_attempt_retention_rate": last_compressor_attempt_retention_rate,
            "accepted_compressor_retention_rate": accepted_compressor_retention_rate,
            "compressor_retention_rate": compressor_retention_rate,
            "final_token_retention_ratio": final_token_retention_ratio,
            "actual_retention_rate": actual_retention_rate,
            "expansion_prevented": expansion_prevented,
            "attempted_expansion_tokens": attempted_expansion_tokens,
            "attempted_candidate_prompt": attempted_candidate_prompt,
            "predicted_original_output_tokens": round(tout_orig, 1),
            "predicted_optimized_output_tokens": round(tout_opt, 1),
            "output_tokens_saved": round(tout_orig - tout_opt, 1),
            "output_reduction_pct": round(((tout_orig - tout_opt) / tout_orig * 100.0) if tout_orig > 0 else 0.0, 2),
            "tokenizer_used": opt_res.tokenizer_name,
            "token_breakdown": token_breakdown_dict,
        },

        # Pipeline Optimization Stages
        "pipeline": {
            "semantic_score": round(opt_res.semantic_similarity, 4) if opt_res.semantic_similarity is not None else 1.0,
            "guardrail_passed": opt_res.guardrail_passed,
            "rollback_occurred": opt_res.rollback_occurred,
            "rollback_stage": opt_res.rollback_stage or "none",
            "rollback_reason": opt_res.rollback_reason,
            "retry_count": opt_res.retry_count,
            "fallback_type": getattr(opt_res, "fallback_type", "none") or "none",
            "last_compressor_attempt_retention_rate": last_compressor_attempt_retention_rate,
            "accepted_compressor_retention_rate": accepted_compressor_retention_rate,
            "compressor_retention_rate": compressor_retention_rate,
            "final_token_retention_ratio": final_token_retention_ratio,
            "actual_retention_rate": actual_retention_rate,
            "active_retention_rate": last_compressor_attempt_retention_rate,
            "active_threshold": round(active_threshold if active_threshold is not None else (0.96 if req_mode == "conservative" else 0.92), 4),
            "stages": stage_breakdown,
            "stage_breakdown": stage_breakdown_dict,
            "token_breakdown": token_breakdown_dict,
            "warnings": opt_res.warnings,
        },

        # Thermodynamic Energy & Carbon Balances (Canonical Wh & gCO2e)
        "thermodynamics": {
            "accounting_scenario": thermo_res.accounting_scenario,
            "accounting_notes": thermo_res.accounting_notes,
            "model_tier_id": thermo_res.model_tier_id,
            "model_tier_provenance": thermo_res.model_tier_provenance,
            "energy_original_wh": round(thermo_res.energy_orig_wh, 6),
            "energy_optimized_wh": round(thermo_res.energy_opt_wh, 6),
            "modeled_prefill_energy_j": modeled_prefill_energy_j,
            "modeled_decode_energy_j": modeled_decode_energy_j,
            "modeled_total_energy_j": modeled_total_energy_j,
            "gross_energy_saved_wh": round(thermo_res.gross_energy_saved_wh, 6),
            "optimizer_overhead_wh": round(thermo_res.optimizer_overhead_wh, 8),
            "net_energy_saved_wh": round(thermo_res.net_energy_saved_wh, 6),
            "energy_saved_pct": round((thermo_res.net_energy_saved_wh / thermo_res.energy_orig_wh * 100.0) if thermo_res.energy_orig_wh > 0 else 0.0, 2),
            "is_net_carbon_debt": thermo_res.is_net_carbon_debt,
            "pue_used": thermo_res.pue_used,
            "cpu_power_w_used": thermo_res.cpu_power_w_used,
        },

        # Explicit Multi-Scenario Accounting Breakdown
        "accounting_scenarios": {
            "input_only": {
                "scenario": "INPUT_ONLY",
                "status": "VERIFIED_BASELINE",
                "description": "Conservative verified accounting based exclusively on measured input token reductions. Downstream decode energy is unmodeled and must not be interpreted as complete inference energy.",
                "gross_energy_saved_wh": round(multi_thermo.input_only.gross_energy_saved_wh, 6),
                "optimizer_overhead_wh": round(multi_thermo.input_only.optimizer_overhead_wh, 8),
                "net_energy_saved_wh": round(multi_thermo.input_only.net_energy_saved_wh, 6),
                "net_carbon_abated_gco2": round(multi_thermo.input_only.net_carbon_abated_gco2, 6),
                "net_water_saved_ml": round(multi_thermo.input_only.net_water_saved_ml, 4),
                "is_net_carbon_debt": multi_thermo.input_only.is_net_carbon_debt,
                "is_measured": True,
                "notes": multi_thermo.input_only.accounting_notes,
            },
            "input_plus_predicted_output": {
                "scenario": "INPUT_PLUS_PREDICTED_OUTPUT",
                "status": "EXPLORATORY_MODELED",
                "description": "Exploratory modeled estimate combining measured input tokens with HybridPredictor downstream output estimates.",
                "gross_energy_saved_wh": round(multi_thermo.input_plus_predicted_output.gross_energy_saved_wh, 6),
                "optimizer_overhead_wh": round(multi_thermo.input_plus_predicted_output.optimizer_overhead_wh, 8),
                "net_energy_saved_wh": round(multi_thermo.input_plus_predicted_output.net_energy_saved_wh, 6),
                "net_carbon_abated_gco2": round(multi_thermo.input_plus_predicted_output.net_carbon_abated_gco2, 6),
                "net_water_saved_ml": round(multi_thermo.input_plus_predicted_output.net_water_saved_ml, 4),
                "is_net_carbon_debt": multi_thermo.input_plus_predicted_output.is_net_carbon_debt,
                "is_measured": False,
                "notes": multi_thermo.input_plus_predicted_output.accounting_notes,
            },
            "input_plus_measured_output": (
                {
                    "scenario": "INPUT_PLUS_MEASURED_OUTPUT",
                    "status": "EMPIRICAL_MEASURED",
                    "description": "Empirical downstream generation measured on target LLM.",
                    "gross_energy_saved_wh": round(multi_thermo.input_plus_measured_output.gross_energy_saved_wh, 6),
                    "optimizer_overhead_wh": round(multi_thermo.input_plus_measured_output.optimizer_overhead_wh, 8),
                    "net_energy_saved_wh": round(multi_thermo.input_plus_measured_output.net_energy_saved_wh, 6),
                    "net_carbon_abated_gco2": round(multi_thermo.input_plus_measured_output.net_carbon_abated_gco2, 6),
                    "net_water_saved_ml": round(multi_thermo.input_plus_measured_output.net_water_saved_ml, 4),
                    "is_net_carbon_debt": multi_thermo.input_plus_measured_output.is_net_carbon_debt,
                    "is_measured": True,
                    "notes": multi_thermo.input_plus_measured_output.accounting_notes,
                }
                if multi_thermo.measured_output_available and multi_thermo.input_plus_measured_output is not None
                else {
                    "scenario": "INPUT_PLUS_MEASURED_OUTPUT",
                    "status": "NOT AVAILABLE",
                    "description": "Empirical downstream generation requires live model execution which is not performed during offline optimization.",
                    "is_measured": False,
                    "notes": "No empirical output token measurements were supplied for this run.",
                }
            ),
        },

        # Environmental Carbon & Water Impact
        "environmental_impact": {
            "grid_intensity_gco2_kwh": round(thermo_res.grid_intensity_gco2_kwh, 2),
            "grid_provenance": thermo_res.grid_intensity_provenance,
            "net_carbon_abated_gco2": round(thermo_res.net_carbon_abated_gco2, 6),
            "net_carbon_abated_per_1k_gco2": round(thermo_res.net_carbon_abated_per_1k_gco2, 4),
            "monthly_carbon_abated_gco2": round(thermo_res.net_carbon_abated_gco2 * monthly_inf, 4),
            "net_water_saved_ml": round(thermo_res.net_water_saved_ml, 4),
            "net_water_saved_per_1k_ml": round(thermo_res.net_water_saved_per_1k_ml, 2),
            "monthly_water_saved_liters": round((thermo_res.net_water_saved_ml * monthly_inf) / 1000.0, 4),
            "wue_ml_per_wh": thermo_res.wue_used_ml_per_wh,
            "projected_monthly_inferences": monthly_inf,
            "startup_initialization": {
                "is_prewarmed": bool(LocalMiniLMEmbedder.get_prewarm_status().get("is_prewarmed")),
                "cold_init_latency_ms": LocalMiniLMEmbedder.get_prewarm_status().get("init_latency_ms"),
                "cold_init_energy_wh_modeled": (
                    round(35.0 * (float(LocalMiniLMEmbedder.get_prewarm_status()["init_latency_ms"]) / 3_600_000.0), 6)
                    if LocalMiniLMEmbedder.get_prewarm_status().get("init_latency_ms") is not None
                    else None
                ),
            },
        },

        # Conservative Green Model Routing Recommendation
        "routing": {
            "outcome": routing_rec.outcome.name,
            "current_model_tier": routing_rec.current_model_tier,
            "recommended_model_tier": routing_rec.recommended_model_tier,
            "task_suitability": routing_rec.task_suitability,
            "confidence_level": routing_rec.confidence_level.name,
            "explanation": routing_rec.explanation,
            "energy_comparison": energy_comp_dict,
            "carbon_comparison": carbon_comp_dict,
            "rejection_reasons": routing_rec.rejection_reasons,
            "assumptions": routing_rec.assumptions,
        },

        # Ledger Telemetry Record
        "ledger": {
            "record_id": rec_id,
            "recorded": req.record_in_ledger,
        }
    }


@app.get("/api/v2/models")
def list_v2_model_tiers():
    """Returns all registered model tier profiles and their canonical mWh/token parameters."""
    tiers = {}
    for tid in DEFAULT_PROFILE_REGISTRY.list_tiers():
        prof = DEFAULT_PROFILE_REGISTRY.get_tier(tid)
        hw = DEFAULT_PROFILE_REGISTRY.get_hardware(prof.hardware_id)
        tiers[tid] = {
            "tier_id": prof.tier_id,
            "display_name": prof.display_name,
            "alpha_prefill_mwh": prof.alpha_prefill_mwh,
            "alpha_decode_mwh": prof.alpha_decode_mwh,
            "decode_to_prefill_ratio": round(prof.decode_to_prefill_ratio, 2),
            "hardware_id": prof.hardware_id,
            "hardware_name": hw.name,
            "hardware_tdp_w": hw.tdp_watts,
            "provenance": prof.provenance,
            "description": prof.description,
        }
    return {"tiers": tiers}


@app.get("/api/v2/grid-scenarios")
def list_v2_grid_scenarios():
    """Returns verified selectable grid intensity scenarios and unavailable regional placeholders."""
    selectable = {}
    for gid in DEFAULT_PROFILE_REGISTRY.list_grid_scenarios():
        scen = DEFAULT_PROFILE_REGISTRY.get_grid_scenario(gid)
        selectable[gid] = {
            "region_code": scen.region_code,
            "carbon_intensity_gco2_kwh": scen.carbon_intensity_gco2_kwh,
            "provenance": scen.provenance,
            "is_illustrative": scen.is_illustrative,
        }
    return {
        "selectable_scenarios": selectable,
        "unavailable_regional_placeholders": UNAVAILABLE_REGIONAL_PLACEHOLDERS,
    }


@app.get("/api/v2/ledger/recent")
def get_v2_recent_ledger(limit: int = 25):
    """Retrieves recent V2 telemetry records from the SQLite ledger."""
    db = PromptLedger()
    return db.get_recent_records(limit=limit)


@app.get("/api/v2/ledger/summary")
def get_v2_ledger_summary():
    """Retrieves aggregated V2 environmental metrics from the SQLite ledger."""
    db = PromptLedger()
    return db.get_v2_summary()


@app.get("/api/v2/telemetry/events")
def get_v2_telemetry_events(
    category: Optional[str] = Query(None, description="Filter by prompt category"),
    routing: Optional[str] = Query(None, description="Filter by routing outcome"),
    status: Optional[str] = Query(None, description="Filter by status (PASS, WARN, FAIL)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Queries detailed time-series telemetry events with optional filtering."""
    db = PromptLedger()
    events = db.query_events(category=category, routing=routing, status=status, limit=limit, offset=offset)
    return {"count": len(events), "events": events}


@app.get("/api/v2/telemetry/time-series")
def get_v2_telemetry_time_series(
    interval: str = Query("hour", pattern="^(hour|day)$"),
    limit: int = Query(100, ge=1, le=1000),
):
    """Retrieves aggregated time-series buckets (hourly or daily) for dashboard plotting."""
    db = PromptLedger()
    series = db.get_time_series_aggregates(interval=interval, limit=limit)
    return {"interval": interval, "buckets": series}


@app.get("/api/v2/telemetry/stats")
def get_v2_telemetry_stats():
    """Retrieves aggregated telemetry metrics and ledger statistics."""
    db = PromptLedger()
    summary = db.get_v2_summary()
    engine_status = db.get_engine_status()
    debt = db.get_cumulative_carbon_debt()
    return {
        "summary": summary,
        "engine": engine_status,
        "carbon_debt": debt,
    }


@app.get("/api/v2/telemetry/status")
def get_v2_database_status():
    """Returns database backend status, hypertable availability, and table statistics."""
    db = PromptLedger()
    return db.get_engine_status()

