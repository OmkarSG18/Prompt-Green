import json
import os
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.metrics import r2_score
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.engine.carbon_engine import CarbonEngine
from promptgreen.gate.prompt_gate import PromptGate


class BenchmarkSuiteRunner:
    """
    Deliverable D7: Validation Suite & GUI Simulator Engine.
    Runs evaluation over 50 prompt benchmark pairs and calculates Directional Accuracy,
    MAPE (Mean Absolute Percentage Error), R^2 score, and Gate Pass/Block Rates
    with customizable simulation parameters.
    """

    def __init__(self, json_path: Optional[str] = None):
        if json_path is None:
            json_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "benchmark_suite.json")
        self.json_path = json_path

    def run_evaluation(
        self,
        blend_weight: float = 0.5,
        model_key: str = "llama-3-8b",
        region: str = "US",
        budget_threshold: float = 0.5
    ) -> Dict[str, Any]:
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Benchmark dataset not found at {self.json_path}")

        with open(self.json_path, "r", encoding="utf-8") as f:
            pairs = json.load(f)

        predictor = HybridPredictor(blend_weight=blend_weight, benchmark_data_path=self.json_path)
        engine = CarbonEngine(model_key=model_key, region=region, blend_weight=blend_weight)
        gate = PromptGate(budget_threshold_gco2_1k=budget_threshold, mode="warn", model_key=model_key, region=region)

        actual_deltas = []
        predicted_deltas = []
        directional_correct = 0
        absolute_percentage_errors = []
        carbon_deltas_1k = []
        passed_gates = 0

        per_category_results: Dict[str, Dict[str, Any]] = {}

        for item in pairs:
            category = item["category"]
            old_p = item["baseline_prompt"]
            new_p = item["optimized_prompt"]

            ground_old = item.get("ground_truth_output_baseline", 250)
            ground_new = item.get("ground_truth_output_optimized", 100)
            actual_delta = float(ground_new - ground_old)

            pred_res = predictor.predict(old_p, new_p)
            predicted_delta = pred_res.predicted_output_token_delta

            carbon_res = engine.calculate(old_p, new_p)
            gate_res = gate.evaluate(old_p, new_p)

            actual_deltas.append(actual_delta)
            predicted_deltas.append(predicted_delta)
            carbon_deltas_1k.append(carbon_res.carbon_delta_per_1k_gco2)

            if gate_res.status_code in ["PASS", "WARN"]:
                passed_gates += 1

            # Directional accuracy check
            if (actual_delta < 0 and predicted_delta < 0) or (actual_delta > 0 and predicted_delta > 0) or (actual_delta == 0 and predicted_delta == 0):
                directional_correct += 1

            # Percentage error calculation
            denom = abs(actual_delta) if abs(actual_delta) > 0.001 else 1.0
            ape = (abs(actual_delta - predicted_delta) / denom) * 100.0
            absolute_percentage_errors.append(ape)

            if category not in per_category_results:
                per_category_results[category] = {"count": 0, "correct_direction": 0, "apes": [], "carbon_deltas": []}

            per_category_results[category]["count"] += 1
            if (actual_delta < 0 and predicted_delta < 0) or (actual_delta > 0 and predicted_delta > 0):
                per_category_results[category]["correct_direction"] += 1
            per_category_results[category]["apes"].append(ape)
            per_category_results[category]["carbon_deltas"].append(carbon_res.carbon_delta_per_1k_gco2)

        total = len(pairs)
        dir_acc_pct = (directional_correct / total) * 100.0 if total > 0 else 0.0
        mape_pct = float(np.mean(absolute_percentage_errors)) if total > 0 else 0.0

        y_true = np.array(actual_deltas)
        y_pred = np.array(predicted_deltas)
        r2 = float(r2_score(y_true, y_pred)) if total > 1 else 0.0

        category_summary = {}
        for cat, data in per_category_results.items():
            cnt = data["count"]
            category_summary[cat] = {
                "count": cnt,
                "directional_accuracy_pct": round((data["correct_direction"] / cnt) * 100.0, 1),
                "mean_ape_pct": round(float(np.mean(data["apes"])), 1),
                "avg_carbon_delta_1k": round(float(np.mean(data["carbon_deltas"])), 4)
            }

        return {
            "total_pairs": total,
            "directional_accuracy_pct": round(dir_acc_pct, 2),
            "target_directional_accuracy_met": dir_acc_pct >= 85.0,
            "mape_pct": round(mape_pct, 2),
            "r2_score": round(r2, 4),
            "gate_pass_rate_pct": round((passed_gates / total) * 100.0, 1),
            "avg_carbon_delta_1k_gco2": round(float(np.mean(carbon_deltas_1k)), 4),
            "total_carbon_saved_1k_gco2": round(float(np.sum(carbon_deltas_1k)), 4),
            "category_summary": category_summary,
            "simulation_params": {
                "blend_weight": blend_weight,
                "model_key": model_key,
                "region": region,
                "budget_threshold": budget_threshold
            }
        }
