import os
import pytest
from promptgreen.analysis.diff_parser import PromptDiffAnalyzer
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.engine.carbon_engine import CarbonEngine, MODEL_ENERGY_PROFILES
from promptgreen.gate.prompt_gate import PromptGate
from promptgreen.ledger.database import PromptLedger
from promptgreen.validation.benchmark import BenchmarkSuiteRunner


def test_diff_analyzer_semantic_extraction():
    analyzer = PromptDiffAnalyzer()
    old_p = "Explain in detail with extensive examples how quantum computing works."
    new_p = "Summarize quantum computing in 3 bullet points."

    feats = analyzer.analyze_prompts(old_p, new_p)

    assert feats.old_input_tokens > 0
    assert feats.new_input_tokens > 0
    assert feats.verb_complexity_old > feats.verb_complexity_new
    assert feats.verb_complexity_delta < 0
    assert len(feats.detected_changes) > 0


def test_few_shot_counting():
    analyzer = PromptDiffAnalyzer()
    prompt_5shots = """
    Classify sentiment:
    Example 1: 'Good' -> Positive
    Example 2: 'Bad' -> Negative
    Example 3: 'Okay' -> Neutral
    Example 4: 'Great' -> Positive
    Example 5: 'Worst' -> Negative
    Input: 'Decent'
    """
    prompt_1shot = """
    Classify sentiment:
    Example 1: 'Good' -> Positive
    Input: 'Decent'
    """
    feats = analyzer.analyze_prompts(prompt_5shots, prompt_1shot)
    assert feats.few_shot_count_old == 5
    assert feats.few_shot_count_new == 1
    assert feats.few_shot_delta == -4


def test_cot_detection():
    analyzer = PromptDiffAnalyzer()
    cot_prompt = "Solve math problem: 2x+5=15. Think step-by-step and explain reasoning."
    simple_prompt = "Solve math problem: 2x+5=15. Return final answer only."

    feats = analyzer.analyze_prompts(cot_prompt, simple_prompt)
    assert feats.cot_triggered_old is True
    assert feats.cot_triggered_new is False
    assert feats.cot_delta == -1


def test_hybrid_predictor_blending():
    predictor = HybridPredictor(blend_weight=0.5)
    old_p = "Explain in detail with extensive examples how quantum computing works."
    new_p = "Summarize quantum computing in 3 bullet points."

    res = predictor.predict(old_p, new_p)
    assert res.predicted_output_token_delta < 0
    assert res.direction == "DECREASED"
    assert res.blend_weight == 0.5


def test_carbon_engine_calculation():
    engine = CarbonEngine(model_key="llama-3-8b", region="US")
    old_p = "Explain in detail with extensive examples how quantum computing works."
    new_p = "Summarize quantum computing in 3 bullet points."

    res = engine.calculate(old_p, new_p, monthly_inferences=10000)

    assert res.model_name == "Llama-3 8B"
    assert res.carbon_intensity_gco2_kwh == 385.0
    assert res.old_energy_per_inf_mj > 0.0
    assert res.new_energy_per_inf_mj > 0.0
    assert res.carbon_delta_per_1k_gco2 < 0.0
    assert res.monthly_carbon_delta_gco2 < 0.0


def test_prompt_gate_evaluation():
    gate_warn = PromptGate(budget_threshold_gco2_1k=0.0001, mode="warn", model_key="llama-3-8b")
    gate_block = PromptGate(budget_threshold_gco2_1k=0.0001, mode="block", model_key="llama-3-8b")

    old_p = "Classify sentiment: 'Great' -> Positive. Input: 'Decent'"
    new_p = "Classify sentiment with extensive examples: Example 1: 'A' -> Pos, Example 2: 'B' -> Neg, Example 3: 'C' -> Neu. Explain reasoning step-by-step."

    res_warn = gate_warn.evaluate(old_p, new_p)
    res_block = gate_block.evaluate(old_p, new_p)

    assert res_warn.status_code == "WARN"
    assert res_warn.passed is True

    assert res_block.status_code == "FAIL"
    assert res_block.passed is False
    assert "# " in res_block.markdown_report


def test_prompt_ledger_sqlite(tmp_path):
    db_file = os.path.join(tmp_path, "test_ledger.db")
    ledger = PromptLedger(db_path=db_file)

    rec_id = ledger.record_prompt_review(
        commit_hash="test1234",
        author="unit_test",
        team="QA",
        model_name="Llama-3 8B",
        region="US",
        old_prompt="old",
        new_prompt="new",
        input_token_delta=-5,
        predicted_output_token_delta=-100.0,
        carbon_delta_gco2_1k=-0.05,
        monthly_carbon_delta_gco2=-500.0,
        status="PASS"
    )

    assert rec_id == 1
    recs = ledger.get_recent_records(limit=10)
    assert len(recs) == 1
    assert recs[0]["commit_hash"] == "test1234"

    summary = ledger.get_cumulative_carbon_debt()
    assert summary["passed_reviews"] == 1


def test_benchmark_validation_suite():
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "benchmark_suite.json")
    runner = BenchmarkSuiteRunner(json_path=json_path)
    eval_res = runner.run_evaluation()

    assert eval_res["total_pairs"] == 50
    assert eval_res["directional_accuracy_pct"] >= 85.0
    assert eval_res["target_directional_accuracy_met"] is True
    assert eval_res["mape_pct"] > 0.0
