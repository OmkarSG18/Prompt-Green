from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from promptgreen.engine.carbon_engine import CarbonEngine, CarbonImpactResult


@dataclass
class GateResult:
    """Result of Pre-Deploy Prompt Gate evaluation."""
    passed: bool
    status_code: str  # "PASS", "WARN", "FAIL"
    budget_threshold_gco2_1k: float
    actual_delta_gco2_1k: float
    mode: str  # "warn", "block"
    carbon_result: CarbonImpactResult
    markdown_report: str
    suggestions: List[str]


class PromptGate:
    """
    Deliverable D4: Pre-Deploy Prompt Gate.
    Enforces deployment carbon budget constraints:
      Prompt_Carbon_Delta(D) <= Budget_threshold
    Generates inline GitHub Pull Request markdown reports.
    """

    def __init__(
        self,
        budget_threshold_gco2_1k: float = 0.5,
        mode: str = "warn",
        model_key: str = "llama-3-8b",
        region: str = "US"
    ):
        self.budget_threshold = float(budget_threshold_gco2_1k)
        self.mode = mode.lower() if mode.lower() in ["warn", "block"] else "warn"
        self.engine = CarbonEngine(model_key=model_key, region=region)

    def generate_suggestions(self, result: CarbonImpactResult) -> List[str]:
        """Generates actionable prompt rewrite suggestions based on detected changes."""
        suggestions = []
        feats = result.features

        if feats.verb_complexity_delta > 0.1:
            suggestions.append(
                "[Verb Optimization]: Replace verbose phrases like 'explain in detail with examples' "
                "with concise directives like 'summarize in 3 bullet points'."
            )

        if feats.few_shot_delta > 0:
            suggestions.append(
                f"[Few-Shot Trimming]: Consider reducing few-shot examples from {feats.few_shot_count_new} "
                "to 1 representative example."
            )

        if feats.cot_triggered_new and not feats.cot_triggered_old:
            suggestions.append(
                "[Chain-of-Thought Review]: Remove explicit CoT triggers ('think step-by-step') "
                "if simple classification or structured output is required."
            )

        if feats.format_complexity_delta > 0.1:
            suggestions.append(
                "[Format Constraint]: Restrict open-ended narrative requests to JSON output "
                "with explicit key-value schema definitions."
            )

        if feats.context_ratio > 1.5:
            suggestions.append(
                "[Context Pruning]: Pre-filter or slice reference context prior to inserting into prompt."
            )

        if not suggestions:
            suggestions.append("[Optimal]: Prompt delta is efficiently structured.")

        return suggestions

    def evaluate(
        self,
        old_prompt: str,
        new_prompt: str,
        monthly_inferences: int = 10000
    ) -> GateResult:
        """Evaluates prompt change against carbon budget and returns GateResult with report."""
        carbon_res = self.engine.calculate(old_prompt, new_prompt, monthly_inferences)
        actual_delta_1k = carbon_res.carbon_delta_per_1k_gco2

        exceeded = actual_delta_1k > self.budget_threshold

        if not exceeded:
            status_code = "PASS"
            passed = True
        else:
            if self.mode == "warn":
                status_code = "WARN"
                passed = True  # warn mode allows check to pass with warnings
            else:
                status_code = "FAIL"
                passed = False

        suggestions = self.generate_suggestions(carbon_res)

        # Build Markdown PR Report
        status_badge = (
            "![PASS](https://img.shields.io/badge/PromptGreen-PASS-success)"
            if status_code == "PASS" else
            ("![WARN](https://img.shields.io/badge/PromptGreen-WARN-warning)"
             if status_code == "WARN" else
             "![FAIL](https://img.shields.io/badge/PromptGreen-BLOCKED-critical)")
        )

        md_lines = [
            f"# {status_badge} — Prompt Carbon Review",
            "",
            f"**Model:** `{carbon_res.model_name}` | **Region:** `{carbon_res.region}` (`{carbon_res.carbon_intensity_gco2_kwh}` gCO2/kWh)",
            f"**Policy Mode:** `{self.mode.upper()}` | **Budget Threshold:** `{self.budget_threshold}` gCO2 / 1K inferences",
            "",
            "### 📊 Carbon Delta Summary",
            "| Metric | Baseline (Old) | Proposed (New) | Delta |",
            "| :--- | :--- | :--- | :--- |",
            f"| **Input Tokens** | {carbon_res.features.old_input_tokens} | {carbon_res.features.new_input_tokens} | `{carbon_res.features.input_token_delta:+d}` |",
            f"| **Predicted Output Tokens** | {carbon_res.prediction.predicted_old_output_tokens:.1f} | {carbon_res.prediction.predicted_new_output_tokens:.1f} | `{carbon_res.prediction.predicted_output_token_delta:+.1f}` ({carbon_res.prediction.inflation_percentage:+.1f}%) |",
            f"| **Energy per Inference (mJ)** | {carbon_res.old_energy_per_inf_mj:.2f} | {carbon_res.new_energy_per_inf_mj:.2f} | `{carbon_res.energy_delta_per_inf_mj:+.2f}` |",
            f"| **Carbon Impact per 1K Inferences** | {carbon_res.old_carbon_per_inf_gco2 * 1000:.4f} gCO2 | {carbon_res.new_carbon_per_inf_gco2 * 1000:.4f} gCO2 | **`{carbon_res.carbon_delta_per_1k_gco2:+.4f} gCO2`** |",
            f"| **Est. Monthly Footprint ({monthly_inferences:,} inf)** | - | - | **`{carbon_res.monthly_carbon_delta_gco2:+.2f} gCO2`** |",
            "",
            "### 🔍 Detected Semantic Changes",
        ]

        if carbon_res.features.detected_changes:
            for ch in carbon_res.features.detected_changes:
                md_lines.append(f"- {ch}")
        else:
            md_lines.append("- Minor textual edits detected.")

        md_lines.extend([
            "",
            "### 💡 Suggested Optimizations",
        ])
        for sg in suggestions:
            md_lines.append(f"- {sg}")

        md_lines.extend([
            "",
            "---",
            "*Generated by PromptGreen Pre-Deploy Prompt Gate (Zero-Budget Open Source)*"
        ])

        report_md = "\n".join(md_lines)

        return GateResult(
            passed=passed,
            status_code=status_code,
            budget_threshold_gco2_1k=self.budget_threshold,
            actual_delta_gco2_1k=actual_delta_1k,
            mode=self.mode,
            carbon_result=carbon_res,
            markdown_report=report_md,
            suggestions=suggestions
        )
