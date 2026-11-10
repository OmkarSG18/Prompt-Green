import json
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from promptgreen.analysis.diff_parser import PromptDeltaFeatures, PromptDiffAnalyzer


@dataclass
class PredictionResult:
    """Output prediction result from the Hybrid Token Inflation Predictor."""
    predicted_old_output_tokens: float
    predicted_new_output_tokens: float
    predicted_output_token_delta: float
    rule_output_delta: float
    ml_output_delta: float
    blend_weight: float
    inflation_percentage: float
    direction: str  # "INCREASED", "DECREASED", "UNCHANGED"


class HybridPredictor:
    """
    Deliverable D2: Hybrid Token Inflation Predictor.
    Combines Layer 1 (Rule-based semantic analysis) and Layer 2 (Scikit-Learn ML Regression)
    to predict output token inflation from prompt diffs.
    """

    def __init__(self, blend_weight: float = 0.5, benchmark_data_path: Optional[str] = None):
        self.blend_weight = max(0.0, min(1.0, blend_weight))
        self.analyzer = PromptDiffAnalyzer()
        self.ml_model = RandomForestRegressor(n_estimators=50, random_state=42)
        self.is_trained = False

        # Attempt auto-training on benchmark data if path provided or file exists
        if benchmark_data_path is None:
            default_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "benchmark_suite.json")
            if os.path.exists(default_path):
                benchmark_data_path = default_path

        if benchmark_data_path and os.path.exists(benchmark_data_path):
            self.train_on_benchmark(benchmark_data_path)

    def predict_rule_based(self, prompt: str) -> float:
        """Layer 1: Rule-based output token estimation for a single prompt."""
        tokens = self.analyzer.count_tokens(prompt)
        verb_score = self.analyzer._score_verb_complexity(prompt)
        few_shots = self.analyzer._count_few_shots(prompt)
        has_cot = self.analyzer._check_cot(prompt)
        fmt_score = self.analyzer._score_format_complexity(prompt)
        role_score = self.analyzer._score_role_complexity(prompt)

        # Baseline output estimate (~200 tokens)
        base_output = 200.0

        # Multipliers
        verb_mult = 0.5 + (verb_score * 1.0)  # 0.6x to 1.5x
        fmt_mult = 0.3 + (fmt_score * 1.1)    # 0.4x to 1.4x
        cot_mult = 2.8 if has_cot else 1.0     # CoT expands output significantly
        role_mult = 1.0 + (role_score * 0.4)

        few_shot_reduction = max(0.4, 1.0 - (few_shots * 0.15))

        estimated_output = base_output * verb_mult * fmt_mult * cot_mult * role_mult * few_shot_reduction
        return max(10.0, estimated_output)

    def train_on_benchmark(self, json_path: str):
        """Trains Layer 2 ML regressor on benchmark suite data."""
        if not os.path.exists(json_path):
            return

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        X = []
        y = []
        for item in data:
            old_p = item["baseline_prompt"]
            new_p = item["optimized_prompt"]
            feats = self.analyzer.analyze_prompts(old_p, new_p)

            ground_old = item.get("ground_truth_output_baseline", 250)
            ground_new = item.get("ground_truth_output_optimized", 100)
            actual_delta = ground_new - ground_old

            X.append(feats.to_feature_vector())
            y.append(actual_delta)

        if len(X) > 0:
            X_arr = np.array(X)
            y_arr = np.array(y)
            self.ml_model.fit(X_arr, y_arr)
            self.is_trained = True

    def predict(self, old_prompt: str, new_prompt: str) -> PredictionResult:
        """Generates hybrid output token delta prediction combining Rule + ML layers."""
        features = self.analyzer.analyze_prompts(old_prompt, new_prompt)

        # Layer 1: Rule-Based Estimation
        rule_old_out = self.predict_rule_based(old_prompt)
        rule_new_out = self.predict_rule_based(new_prompt)
        rule_delta = rule_new_out - rule_old_out

        # Layer 2: ML Regression Estimation
        if self.is_trained:
            vec = np.array(features.to_feature_vector()).reshape(1, -1)
            ml_delta = float(self.ml_model.predict(vec)[0])
        else:
            ml_delta = rule_delta  # Fallback to rule if ML model not trained

        # Blended Prediction
        final_delta = (self.blend_weight * rule_delta) + ((1.0 - self.blend_weight) * ml_delta)

        # Output Token Delta and Percentage
        predicted_new_out = max(5.0, rule_old_out + final_delta)
        denom = max(1.0, rule_old_out)
        pct = (final_delta / denom) * 100.0

        if final_delta > 5.0:
            direction = "INCREASED"
        elif final_delta < -5.0:
            direction = "DECREASED"
        else:
            direction = "UNCHANGED"

        return PredictionResult(
            predicted_old_output_tokens=round(rule_old_out, 1),
            predicted_new_output_tokens=round(predicted_new_out, 1),
            predicted_output_token_delta=round(final_delta, 1),
            rule_output_delta=round(rule_delta, 1),
            ml_output_delta=round(ml_delta, 1),
            blend_weight=self.blend_weight,
            inflation_percentage=round(pct, 2),
            direction=direction
        )
