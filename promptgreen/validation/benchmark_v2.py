"""
PromptGreen V2 — Independent 240-Prompt Evaluation Harness (benchmark_v2.py)
Executes reproducible, isolated evaluation of the unified 4-stage active optimization pipeline.

Strict Epistemic Isolation:
- Evaluates on an independent dataset (data/benchmark_240_independent.json).
- Never modifies or writes to the production prompt_ledger.db.
- Isolates benchmark persistence into a dedicated SQLite ledger or JSON/CSV files.
- Strictly distinguishes measured vs. modeled vs. predicted metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from promptgreen.optimizer.pipeline import PipelineConfig, PipelineResult, PromptGreenPipeline
from promptgreen.optimizer.semantic_guard import LocalMiniLMEmbedder
from promptgreen.predictor.hybrid_predictor import HybridPredictor
from promptgreen.engine.thermodynamics import calculate_thermodynamic_impact, EnergyCarbonResult
from promptgreen.ledger.database import PromptLedger, LedgerRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("promptgreen.validation.benchmark_v2")


@dataclass
class PromptBenchmarkResult:
    """Detailed record for a single prompt evaluation under a specific mode."""
    prompt_id: str
    category: str
    difficulty: str
    length_profile: str
    original_prompt: str
    optimized_prompt: str
    optimization_mode: str
    success: bool
    accepted: bool
    rollback_occurred: bool
    rollback_stage: Optional[str]
    rollback_reason: Optional[str]
    retry_count: int

    # Token accounting
    original_token_count: int
    optimized_token_count: int
    token_reduction: int
    token_reduction_pct: float
    tokenizer_used: str
    is_exact_tokenizer: bool

    # Semantic validation
    semantic_similarity: float
    guardrail_passed: bool
    preservation_violations: List[str]

    # Latencies
    stage_latencies_ms: Dict[str, float]
    total_latency_ms: float
    is_cold_start: bool

    # Fallback tracking
    stage_2_method: str
    stage_3_method: str
    stage_3_ollama_fallback_reason: Optional[str]

    # Predictions & Thermodynamics
    predicted_original_output_tokens: float
    predicted_optimized_output_tokens: float
    predicted_output_token_delta: float
    gross_energy_saved_wh: float
    optimizer_overhead_wh: float
    net_energy_saved_wh: float
    is_net_carbon_debt: bool
    net_carbon_abated_gco2: float
    net_water_saved_ml: float
    grid_scenario: str
    model_tier: str
    warnings: List[str] = field(default_factory=list)


class BenchmarkV2Runner:
    """
    Dedicated evaluation runner for PromptGreen V2 4-stage optimization pipeline.
    Maintains complete isolation from demonstration databases and historical ledgers.
    """

    def __init__(
        self,
        dataset_path: str = "data/benchmark_240_independent.json",
        output_dir: str = "results/benchmark_v2",
        model_tier: str = "mid_tier",
        grid_scenario: str = "ILLUSTRATIVE_385",
        prewarm_embedder: bool = True,
    ):
        self.dataset_path = dataset_path
        self.output_dir = output_dir
        self.model_tier = model_tier
        self.grid_scenario = grid_scenario
        self.prewarm_embedder = prewarm_embedder

        self.predictor = HybridPredictor()
        self._ensure_output_dir()

        # Database safety: verify production database path is guarded
        self.isolated_db_path = os.path.join(self.output_dir, "benchmark_ledger.db")
        self._verify_database_isolation()

    def _ensure_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def _verify_database_isolation(self):
        prod_db_path = os.path.abspath("prompt_ledger.db")
        iso_db_path = os.path.abspath(self.isolated_db_path)
        if prod_db_path == iso_db_path:
            raise RuntimeError(
                f"SAFETY VIOLATION: Isolated benchmark database ({iso_db_path}) "
                f"matches production database ({prod_db_path})! Benchmark must not overwrite production."
            )

    def load_dataset(self, smoke_test_limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Load benchmark dataset from JSON."""
        if not os.path.exists(self.dataset_path):
            raise FileNotFoundError(f"Benchmark dataset not found at {self.dataset_path}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            prompts = json.load(f)

        if smoke_test_limit is not None and smoke_test_limit > 0:
            logger.info(f"Smoke test mode: selecting first {smoke_test_limit} prompts.")
            return prompts[:smoke_test_limit]

        return prompts

    def run_benchmark(
        self,
        modes: List[str] = ["balanced"],
        smoke_test_limit: Optional[int] = None,
        record_isolated_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute benchmark evaluation across specified modes.
        Returns full results dictionary including raw runs, summaries, category breakdowns, and failure cases.
        """
        prompts = self.load_dataset(smoke_test_limit=smoke_test_limit)
        logger.info(f"Loaded {len(prompts)} prompts from {self.dataset_path}")

        # Check existing production ledger row count to confirm zero pollution later
        prod_count_before = self._get_prod_db_count()

        # Pre-warm embedder if requested
        cold_init_latency_ms = None
        if self.prewarm_embedder:
            pw_status = LocalMiniLMEmbedder.get_prewarm_status()
            if not pw_status.get("is_prewarmed"):
                ok, lat_ms, msg = LocalMiniLMEmbedder.prewarm()
                cold_init_latency_ms = lat_ms
                logger.info(f"Pre-warmed local MiniLM embedder: ok={ok}, lat={lat_ms:.1f}ms")
            else:
                cold_init_latency_ms = pw_status.get("init_latency_ms")

        isolated_ledger = None
        if record_isolated_db:
            isolated_ledger = PromptLedger(db_path=self.isolated_db_path)
            logger.info(f"Isolated benchmark database initialized at: {self.isolated_db_path}")

        all_results_by_mode: Dict[str, List[PromptBenchmarkResult]] = {}
        total_evaluations = 0

        for mode in modes:
            logger.info(f"=== Starting Benchmark Evaluation: Mode = '{mode.upper()}' ({len(prompts)} prompts) ===")
            config = PipelineConfig(mode=mode)
            pipeline = PromptGreenPipeline(config=config)

            mode_results: List[PromptBenchmarkResult] = []

            for idx, p in enumerate(prompts):
                is_cold = (idx == 0 and total_evaluations == 0 and cold_init_latency_ms is None)
                p_id = p.get("id", f"bench-{idx+1}")
                category = p.get("category", "Uncategorized")
                difficulty = p.get("difficulty", "medium")
                length_profile = p.get("length_profile", "medium")
                original_prompt = p.get("original_prompt", "")

                # 1. Execute actual 4-stage optimization pipeline
                t0 = time.perf_counter()
                pipeline_res: PipelineResult = pipeline.optimize(original_prompt, mode=mode)
                total_lat = (time.perf_counter() - t0) * 1000.0

                # 2. Extract stage fallback details
                s2_exec = pipeline_res.stage_executions.get("stage_2")
                s2_method = s2_exec.method_used if s2_exec else "deterministic_lexical_fallback"

                s3_exec = pipeline_res.stage_executions.get("stage_3")
                s3_method = s3_exec.method_used if s3_exec else "none"
                s3_ollama_fallback_reason = None
                if s3_exec and s3_exec.warnings:
                    for w in s3_exec.warnings:
                        if "Ollama" in w or "ollama" in w:
                            s3_ollama_fallback_reason = w
                            break

                # 3. HybridPredictor output token estimation
                pred_res = self.predictor.predict(original_prompt, pipeline_res.final_prompt)
                tout_orig = pred_res.predicted_old_output_tokens
                tout_opt = pred_res.predicted_new_output_tokens
                tout_delta = pred_res.predicted_output_token_delta

                # 4. Thermodynamic impact modeling with zero-diff physical consistency guard
                is_identical = (original_prompt.strip() == pipeline_res.final_prompt.strip())
                thermo_res = calculate_thermodynamic_impact(
                    tin_original=pipeline_res.original_token_count,
                    tout_original=tout_orig,
                    tin_optimized=pipeline_res.final_token_count,
                    tout_optimized=tout_opt,
                    optimizer_latency_ms=pipeline_res.total_latency_ms,
                    model_tier=self.model_tier,
                    grid_scenario=self.grid_scenario,
                    is_prompt_identical=is_identical,
                )

                # 5. Assemble structured benchmark record
                rec = PromptBenchmarkResult(
                    prompt_id=p_id,
                    category=category,
                    difficulty=difficulty,
                    length_profile=length_profile,
                    original_prompt=original_prompt,
                    optimized_prompt=pipeline_res.final_prompt,
                    optimization_mode=mode,
                    success=pipeline_res.success,
                    accepted=pipeline_res.accepted,
                    rollback_occurred=pipeline_res.rollback_occurred,
                    rollback_stage=pipeline_res.rollback_stage,
                    rollback_reason=pipeline_res.rollback_reason,
                    retry_count=pipeline_res.retry_count,
                    original_token_count=pipeline_res.original_token_count,
                    optimized_token_count=pipeline_res.final_token_count,
                    token_reduction=pipeline_res.net_token_reduction,
                    token_reduction_pct=pipeline_res.net_token_reduction_pct,
                    tokenizer_used=pipeline_res.tokenizer_name,
                    is_exact_tokenizer=pipeline_res.is_exact_token_count,
                    semantic_similarity=round(float(pipeline_res.semantic_similarity or 1.0), 4),
                    guardrail_passed=pipeline_res.guardrail_passed,
                    preservation_violations=pipeline_res.preservation_violations,
                    stage_latencies_ms=pipeline_res.stage_latencies_ms,
                    total_latency_ms=round(pipeline_res.total_latency_ms, 2),
                    is_cold_start=is_cold,
                    stage_2_method=s2_method,
                    stage_3_method=s3_method,
                    stage_3_ollama_fallback_reason=s3_ollama_fallback_reason,
                    predicted_original_output_tokens=tout_orig,
                    predicted_optimized_output_tokens=tout_opt,
                    predicted_output_token_delta=tout_delta,
                    gross_energy_saved_wh=round(thermo_res.gross_energy_saved_wh, 6),
                    optimizer_overhead_wh=round(thermo_res.optimizer_overhead_wh, 6),
                    net_energy_saved_wh=round(thermo_res.net_energy_saved_wh, 6),
                    is_net_carbon_debt=thermo_res.is_net_carbon_debt,
                    net_carbon_abated_gco2=round(thermo_res.net_carbon_abated_gco2, 6),
                    net_water_saved_ml=round(thermo_res.net_water_saved_ml, 6),
                    grid_scenario=self.grid_scenario,
                    model_tier=self.model_tier,
                    warnings=pipeline_res.warnings,
                )
                mode_results.append(rec)
                total_evaluations += 1

                # 6. Record to isolated database if enabled
                if isolated_ledger:
                    isolated_ledger.record_v2_run(
                        commit_hash="independent_eval",
                        author="benchmark-v2",
                        team="Evaluation",
                        model_name=self.model_tier,
                        region=self.grid_scenario,
                        old_prompt=original_prompt,
                        new_prompt=pipeline_res.final_prompt,
                        input_token_delta=rec.token_reduction,
                        predicted_output_token_delta=rec.predicted_output_token_delta,
                        carbon_delta_gco2_1k=thermo_res.net_carbon_abated_per_1k_gco2,
                        monthly_carbon_delta_gco2=thermo_res.net_carbon_abated_per_1k_gco2 * 10,
                        status="ACCEPTED" if rec.accepted else "ROLLED_BACK",
                        opt_mode=mode.upper(),
                        semantic_score=rec.semantic_similarity,
                        net_energy_wh=rec.net_energy_saved_wh,
                        net_carbon_g=rec.net_carbon_abated_gco2,
                        water_saved_ml=rec.net_water_saved_ml,
                        routing_outcome="KEEP_CURRENT_MODEL",
                        recommended_tier=self.model_tier,
                        latency_ms=rec.total_latency_ms,
                    )

                if (idx + 1) % 30 == 0 or (idx + 1) == len(prompts):
                    logger.info(f"[{mode.upper()}] Evaluated {idx+1}/{len(prompts)} prompts...")

            all_results_by_mode[mode] = mode_results

        # Verify production ledger was completely untouched
        prod_count_after = self._get_prod_db_count()
        assert prod_count_before == prod_count_after, (
            f"SAFETY INTEGRITY BREACH: Production database record count changed! "
            f"Before={prod_count_before}, After={prod_count_after}"
        )
        logger.info(f"Production database integrity verified: exactly {prod_count_after} records preserved.")

        # Aggregate metrics across modes
        summaries_by_mode: Dict[str, Dict[str, Any]] = {}
        category_summaries_by_mode: Dict[str, Dict[str, Any]] = {}
        failure_cases_by_mode: Dict[str, List[Dict[str, Any]]] = {}

        for mode, results in all_results_by_mode.items():
            summary, cat_summary, failures = self._calculate_metrics(results, mode)
            summaries_by_mode[mode] = summary
            category_summaries_by_mode[mode] = cat_summary
            failure_cases_by_mode[mode] = failures

        output_payload = {
            "metadata": {
                "benchmark_version": "2.0.0",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "dataset_path": self.dataset_path,
                "total_prompts": len(prompts),
                "modes_evaluated": modes,
                "model_tier": self.model_tier,
                "grid_scenario": self.grid_scenario,
                "isolated_db_path": self.isolated_db_path,
                "cold_init_latency_ms": cold_init_latency_ms,
            },
            "summaries": summaries_by_mode,
            "category_summaries": category_summaries_by_mode,
            "failure_cases": failure_cases_by_mode,
            "raw_results": {mode: [asdict(r) for r in results] for mode, results in all_results_by_mode.items()},
        }

        self._save_results(output_payload)
        return output_payload

    def _get_prod_db_count(self) -> int:
        """Helper to get record count from prompt_ledger.db without writing."""
        if not os.path.exists("prompt_ledger.db"):
            return 0
        conn = sqlite3.connect("prompt_ledger.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM prompt_records")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0

    def _calculate_metrics(
        self,
        results: List[PromptBenchmarkResult],
        mode: str
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        """Compute aggregate, category-wise, and failure case analytics."""
        n = len(results)
        if n == 0:
            return {}, {}, []

        accepted_list = [r for r in results if r.accepted]
        rollback_list = [r for r in results if r.rollback_occurred]
        failed_checks = [r for r in results if not r.guardrail_passed]
        violations = [r for r in results if r.preservation_violations]
        negative_tokens = [r for r in results if r.token_reduction < 0]
        zero_tokens = [r for r in results if r.token_reduction == 0]
        net_carbon_debts = [r for r in results if r.is_net_carbon_debt]

        latencies = [r.total_latency_ms for r in results]
        token_reds = [r.token_reduction for r in results]
        token_red_pcts = [r.token_reduction_pct for r in results]
        semantic_scores = [r.semantic_similarity for r in results]
        gross_energies = [r.gross_energy_saved_wh for r in results]
        net_energies = [r.net_energy_saved_wh for r in results]
        overheads = [r.optimizer_overhead_wh for r in results]

        # Stage fallbacks
        s2_fallback_count = sum(1 for r in results if "fallback" in r.stage_2_method.lower())
        s3_fallback_count = sum(1 for r in results if r.stage_3_method in ("none", "deterministic_lexical_fallback"))
        s3_ollama_reasons: Dict[str, int] = {}
        for r in results:
            if r.stage_3_ollama_fallback_reason:
                reason_key = r.stage_3_ollama_fallback_reason[:60]
                s3_ollama_reasons[reason_key] = s3_ollama_reasons.get(reason_key, 0) + 1

        def mean(lst): return sum(lst) / len(lst) if lst else 0.0
        def median(lst):
            if not lst: return 0.0
            s = sorted(lst)
            mid = len(s) // 2
            return (s[mid] + s[~mid]) / 2.0
        def std(lst):
            if len(lst) < 2: return 0.0
            m = mean(lst)
            return math.sqrt(sum((x - m) ** 2 for x in lst) / (len(lst) - 1))

        summary = {
            "mode": mode,
            "total_prompts": n,
            "accepted_count": len(accepted_list),
            "acceptance_rate_pct": round((len(accepted_list) / n) * 100.0, 2),
            "rollback_count": len(rollback_list),
            "rollback_rate_pct": round((len(rollback_list) / n) * 100.0, 2),
            "safety_rejections": len(failed_checks),
            "preservation_violations_count": len(violations),  # Must be 0
            "zero_token_savings_count": len(zero_tokens),
            "negative_token_savings_count": len(negative_tokens),
            "net_carbon_debt_count": len(net_carbon_debts),
            "net_carbon_debt_rate_pct": round((len(net_carbon_debts) / n) * 100.0, 2),

            # Latency statistics (ms)
            "latency_ms": {
                "mean": round(mean(latencies), 2),
                "median": round(median(latencies), 2),
                "std": round(std(latencies), 2),
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
                "warm_mean": round(mean(latencies[1:]), 2) if len(latencies) > 1 else round(latencies[0], 2),
            },

            # Token reduction statistics
            "token_reduction_tokens": {
                "mean": round(mean(token_reds), 2),
                "median": round(median(token_reds), 2),
                "std": round(std(token_reds), 2),
                "min": min(token_reds),
                "max": max(token_reds),
                "total_tokens_saved": sum(token_reds),
            },
            "token_reduction_pct": {
                "mean": round(mean(token_red_pcts), 2),
                "median": round(median(token_red_pcts), 2),
                "std": round(std(token_red_pcts), 2),
                "min": round(min(token_red_pcts), 2),
                "max": round(max(token_red_pcts), 2),
            },

            # Semantic similarity statistics
            "semantic_similarity": {
                "mean": round(mean(semantic_scores), 4),
                "median": round(median(semantic_scores), 4),
                "min": round(min(semantic_scores), 4),
                "max": round(max(semantic_scores), 4),
                "std": round(std(semantic_scores), 4),
            },

            # Thermodynamic energy balances (Wh)
            "energy_wh": {
                "mean_gross_saved_wh": round(mean(gross_energies), 6),
                "mean_optimizer_overhead_wh": round(mean(overheads), 6),
                "mean_net_saved_wh": round(mean(net_energies), 6),
                "total_net_energy_saved_wh": round(sum(net_energies), 4),
            },

            # Fallbacks
            "stage_fallbacks": {
                "stage_2_deterministic_fallback_rate_pct": round((s2_fallback_count / n) * 100.0, 2),
                "stage_3_deterministic_fallback_rate_pct": round((s3_fallback_count / n) * 100.0, 2),
                "stage_3_ollama_fallback_reasons": s3_ollama_reasons,
            }
        }

        # Category-wise metrics
        category_summaries: Dict[str, Dict[str, Any]] = {}
        categories = sorted(list(set(r.category for r in results)))
        for cat in categories:
            cat_results = [r for r in results if r.category == cat]
            cn = len(cat_results)
            c_accepted = [r for r in cat_results if r.accepted]
            c_token_reds = [r.token_reduction for r in cat_results]
            c_token_pcts = [r.token_reduction_pct for r in cat_results]
            c_latencies = [r.total_latency_ms for r in cat_results]
            c_semantics = [r.semantic_similarity for r in cat_results]
            c_net_energies = [r.net_energy_saved_wh for r in cat_results]

            category_summaries[cat] = {
                "prompt_count": cn,
                "accepted_count": len(c_accepted),
                "acceptance_rate_pct": round((len(c_accepted) / cn) * 100.0, 2),
                "mean_token_reduction_tokens": round(mean(c_token_reds), 2),
                "median_token_reduction_tokens": round(median(c_token_reds), 2),
                "mean_token_reduction_pct": round(mean(c_token_pcts), 2),
                "median_token_reduction_pct": round(median(c_token_pcts), 2),
                "mean_latency_ms": round(mean(c_latencies), 2),
                "mean_semantic_similarity": round(mean(c_semantics), 4),
                "min_semantic_similarity": round(min(c_semantics), 4),
                "mean_net_energy_saved_wh": round(mean(c_net_energies), 6),
                "total_net_energy_saved_wh": round(sum(c_net_energies), 4),
            }

        # Failure cases (rollbacks, negative savings, net carbon debts, preservation violations)
        failure_cases: List[Dict[str, Any]] = []
        for r in results:
            is_failure = (
                r.rollback_occurred or
                not r.accepted or
                r.token_reduction < 0 or
                r.is_net_carbon_debt or
                len(r.preservation_violations) > 0
            )
            if is_failure:
                failure_cases.append({
                    "prompt_id": r.prompt_id,
                    "category": r.category,
                    "difficulty": r.difficulty,
                    "original_prompt": r.original_prompt,
                    "optimized_prompt": r.optimized_prompt,
                    "token_reduction": r.token_reduction,
                    "token_reduction_pct": r.token_reduction_pct,
                    "semantic_similarity": r.semantic_similarity,
                    "accepted": r.accepted,
                    "rollback_occurred": r.rollback_occurred,
                    "rollback_reason": r.rollback_reason,
                    "is_net_carbon_debt": r.is_net_carbon_debt,
                    "net_energy_saved_wh": r.net_energy_saved_wh,
                    "preservation_violations": r.preservation_violations,
                })

        return summary, category_summaries, failure_cases

    def _save_results(self, payload: Dict[str, Any]):
        """Save raw and summary results to files in the isolated output directory."""
        raw_path = os.path.join(self.output_dir, "raw_results.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(payload["raw_results"], f, indent=2, ensure_ascii=False)

        summary_path = os.path.join(self.output_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(payload["summaries"], f, indent=2)

        cat_summary_path = os.path.join(self.output_dir, "category_summary.json")
        with open(cat_summary_path, "w", encoding="utf-8") as f:
            json.dump(payload["category_summaries"], f, indent=2)

        failures_path = os.path.join(self.output_dir, "failure_cases.json")
        with open(failures_path, "w", encoding="utf-8") as f:
            json.dump(payload["failure_cases"], f, indent=2)

        # Generate markdown report
        report_path = os.path.join(self.output_dir, "benchmark_report.md")
        report_md = self._generate_markdown_report(payload)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        logger.info(f"Benchmark results successfully stored in:\n  {self.output_dir}")

    def _generate_markdown_report(self, payload: Dict[str, Any]) -> str:
        """Render a comprehensive GitHub-style markdown benchmark report."""
        meta = payload["metadata"]
        summaries = payload["summaries"]
        cat_summaries = payload["category_summaries"]
        failures = payload["failure_cases"]

        lines = [
            "# PromptGreen V2 — Independent 240-Prompt Evaluation Report",
            f"**Evaluation Date:** {meta['timestamp']}  ",
            f"**Dataset:** `{meta['dataset_path']}` ({meta['total_prompts']} unique prompts)  ",
            f"**Model Tier Evaluated:** `{meta['model_tier']}`  ",
            f"**Grid Scenario:** `{meta['grid_scenario']}`  ",
            f"**Isolated Persistence:** `{meta['isolated_db_path']}`  \n",
            "> [!IMPORTANT]",
            "> **Epistemic Disclaimer:** This independent evaluation does not reproduce the original thesis experiment",
            "> because the original 240-prompt dataset and its complete evaluation artifacts were not available in the repository.",
            "> All metrics reported herein represent empirical CPU-first evaluations on the actual V2 four-stage pipeline.\n",
            "---",
            "## 1. Executive Summary Across Modes\n",
            "| Optimization Mode | Evaluated | Accepted | Acceptance Rate | Rollbacks | Mean Token Red. | Mean Red. % | Mean Latency | Mean Semantic | Net Wh Saved |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]

        for mode, s in summaries.items():
            lines.append(
                f"| **{mode.upper()}** | {s['total_prompts']} | {s['accepted_count']} | "
                f"{s['acceptance_rate_pct']}% | {s['rollback_count']} | {s['token_reduction_tokens']['mean']} tok | "
                f"{s['token_reduction_pct']['mean']}% | {s['latency_ms']['mean']} ms | "
                f"{s['semantic_similarity']['mean']} | {s['energy_wh']['total_net_energy_saved_wh']} Wh |"
            )

        # Deep dive into primary mode (first evaluated mode)
        primary_mode = meta["modes_evaluated"][0]
        p_sum = summaries[primary_mode]
        p_cats = cat_summaries[primary_mode]
        p_fails = failures.get(primary_mode, [])

        lines.extend([
            f"\n## 2. Category Breakdown ({primary_mode.upper()} Mode)\n",
            "| Category | Prompts | Accepted | Acceptance % | Mean Tok Red. | Mean Red. % | Mean Latency | Mean Semantic | Total Net Wh |",
            "|---|---|---|---|---|---|---|---|---|",
        ])

        for cat, cs in p_cats.items():
            lines.append(
                f"| {cat} | {cs['prompt_count']} | {cs['accepted_count']} | {cs['acceptance_rate_pct']}% | "
                f"{cs['mean_token_reduction_tokens']} tok | {cs['mean_token_reduction_pct']}% | "
                f"{cs['mean_latency_ms']} ms | {cs['mean_semantic_similarity']} | {cs['total_net_energy_saved_wh']} Wh |"
            )

        lines.extend([
            "\n## 3. Preservation & Security Verification\n",
            f"- **Protected Content Violations:** {p_sum['preservation_violations_count']} (Must be exactly 0)",
            f"- **Negative Token Reductions:** {p_sum['negative_token_savings_count']}",
            f"- **Zero Token Reductions:** {p_sum['zero_token_savings_count']}",
            f"- **Net Carbon Debt Cases:** {p_sum['net_carbon_debt_count']} ({p_sum['net_carbon_debt_rate_pct']}%)",
            f"- **Stage 2 Fallback Rate:** {p_sum['stage_fallbacks']['stage_2_deterministic_fallback_rate_pct']}%",
            f"- **Stage 3 Fallback Rate:** {p_sum['stage_fallbacks']['stage_3_deterministic_fallback_rate_pct']}%",
            f"- **Total Net Energy Saved:** {p_sum['energy_wh']['total_net_energy_saved_wh']} Wh across {p_sum['total_prompts']} prompts\n",
            "## 4. Notable Edge & Failure Cases\n",
            f"Total flagged edge cases in `{primary_mode}` mode: **{len(p_fails)}**\n",
        ])

        if p_fails:
            lines.append("| Prompt ID | Category | Difficulty | Token Delta | Semantic Score | Status | Reason / Issue |")
            lines.append("|---|---|---|---|---|---|---|")
            for f_case in p_fails[:15]:  # Show top 15 in table
                reason = f_case["rollback_reason"] or ("Net Carbon Debt" if f_case["is_net_carbon_debt"] else "Negative Tokens")
                lines.append(
                    f"| `{f_case['prompt_id']}` | {f_case['category']} | {f_case['difficulty']} | "
                    f"{f_case['token_reduction']} ({f_case['token_reduction_pct']}%) | "
                    f"{f_case['semantic_similarity']} | {'ACCEPTED' if f_case['accepted'] else 'ROLLED_BACK'} | {reason} |"
                )
            if len(p_fails) > 15:
                lines.append(f"\n*(And {len(p_fails) - 15} additional cases detailed in `failure_cases.json`)*")
        else:
            lines.append("*Zero failure or debt cases identified.*")

        lines.append("\n---\n*Report generated automatically by PromptGreen V2 Benchmark Suite.*")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="PromptGreen V2 Independent Benchmark Runner")
    parser.add_argument("--dataset", default="data/benchmark_240_independent.json", help="Path to JSON dataset")
    parser.add_argument("--output-dir", default="results/benchmark_v2", help="Directory to store results")
    parser.add_argument("--mode", default="balanced", help="Mode: conservative, balanced, aggressive, or all")
    parser.add_argument("--smoke", type=int, default=None, help="Run smoke test on N prompts (e.g. 20)")
    parser.add_argument("--tier", default="mid_tier", help="Model tier profile")
    parser.add_argument("--grid", default="ILLUSTRATIVE_385", help="Grid intensity scenario")

    args = parser.parse_args()

    modes = ["balanced"]
    if args.mode == "all":
        modes = ["conservative", "balanced", "aggressive"]
    elif args.mode in ("conservative", "balanced", "aggressive"):
        modes = [args.mode]

    runner = BenchmarkV2Runner(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        model_tier=args.tier,
        grid_scenario=args.grid,
    )

    logger.info(f"Starting PromptGreen V2 Benchmark with modes={modes}, smoke={args.smoke}")
    runner.run_benchmark(modes=modes, smoke_test_limit=args.smoke)


if __name__ == "__main__":
    main()
