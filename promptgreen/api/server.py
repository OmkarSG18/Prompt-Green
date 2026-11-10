from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from promptgreen.gate.prompt_gate import PromptGate, GateResult
from promptgreen.engine.carbon_engine import CarbonEngine
from promptgreen.ledger.database import PromptLedger
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer

app = FastAPI(
    title="PromptGreen REST API",
    description="Zero-Budget Carbon-Aware Prompt Review RESTful Service",
    version="1.0.0"
)

analyzer = PromptDiffAnalyzer()


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


@app.get("/")
def read_root():
    return {"status": "active", "system": "PromptGreen", "version": "1.0.0"}


@app.post("/api/v1/generate-green")
def generate_green_prompt(req: PromptGenerateRequest):
    """Generates a carbon-optimized green alternative prompt."""
    try:
        green_prompt = analyzer.generate_green_alternative(req.prompt)
        return {"original_prompt": req.prompt, "green_prompt": green_prompt}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/review")
def review_prompt(req: PromptReviewRequest):
    """Evaluates prompt change against carbon gate budget and logs to ledger."""
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
