"""
PromptGreen V2 — Targeted Test Suite for Independent V2 Benchmark (tests/test_benchmark_v2.py)
Validates dataset integrity, schema conformity, isolated persistence, aggregate metrics,
rollback safety, and complete protection of production databases.
"""

import json
import math
import os
import sqlite3
import sys
import pytest

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from promptgreen.validation.benchmark_v2 import BenchmarkV2Runner, PromptBenchmarkResult


DATASET_PATH = "data/benchmark_240_independent.json"
EXPECTED_CATEGORIES = {
    "Code generation and debugging",
    "RAG and information retrieval",
    "Analytical reasoning",
    "Summarization and information extraction",
    "CI/CD and developer workflows",
    "Data science and machine learning",
    "Structured output and formatting constraints",
    "General technical instructions",
}


def test_dataset_file_exists_and_parses():
    """Verify that the independent 240-prompt benchmark dataset exists and parses as valid JSON."""
    assert os.path.exists(DATASET_PATH), f"Dataset missing at {DATASET_PATH}"
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 240, f"Expected exactly 240 prompts, found {len(data)}"


def test_dataset_schema_and_uniqueness():
    """Verify schema compliance, non-emptiness, and uniqueness of IDs and prompt strings."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_fields = [
        "id", "category", "original_prompt", "expected_task_intent",
        "critical_constraints", "expected_output_characteristics",
        "difficulty", "length_profile"
    ]

    seen_ids = set()
    seen_prompts = set()

    for item in data:
        for rf in required_fields:
            assert rf in item, f"Missing field '{rf}' in item {item.get('id')}"
            assert item[rf], f"Field '{rf}' is empty in item {item.get('id')}"

        assert item["id"] not in seen_ids, f"Duplicate ID: {item['id']}"
        seen_ids.add(item["id"])

        assert item["original_prompt"] not in seen_prompts, f"Duplicate prompt text: {item['id']}"
        seen_prompts.add(item["original_prompt"])

    assert len(seen_ids) == 240
    assert len(seen_prompts) == 240


def test_dataset_category_distribution():
    """Verify that exactly 8 categories exist and each contains exactly 30 prompts."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cat_counts = {}
    for item in data:
        cat = item["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    assert set(cat_counts.keys()) == EXPECTED_CATEGORIES
    assert len(cat_counts) == 8

    for cat, count in cat_counts.items():
        assert count == 30, f"Category '{cat}' has {count} prompts (expected 30)"


def test_dataset_diversity_profiles():
    """Verify presence of all difficulty tiers and length profiles."""
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    difficulties = {item["difficulty"] for item in data}
    assert {"easy", "medium", "hard", "adversarial"}.issubset(difficulties)

    length_profiles = {item["length_profile"] for item in data}
    assert {"short", "medium", "long", "multi-paragraph"}.issubset(length_profiles)


def test_isolated_benchmark_persistence(tmp_path):
    """Verify benchmark persistence is strictly isolated from production prompt_ledger.db."""
    test_out = str(tmp_path / "bench_test_out")
    runner = BenchmarkV2Runner(
        dataset_path=DATASET_PATH,
        output_dir=test_out,
        model_tier="mid_tier",
        grid_scenario="ILLUSTRATIVE_385",
        prewarm_embedder=True,
    )

    # Check that production database path is guarded
    assert os.path.abspath(runner.isolated_db_path) != os.path.abspath("prompt_ledger.db")

    # Run smoke slice of 3 prompts
    res = runner.run_benchmark(modes=["balanced"], smoke_test_limit=3, record_isolated_db=True)

    # Verify isolated files created
    assert os.path.exists(os.path.join(test_out, "raw_results.json"))
    assert os.path.exists(os.path.join(test_out, "summary.json"))
    assert os.path.exists(os.path.join(test_out, "category_summary.json"))
    assert os.path.exists(os.path.join(test_out, "benchmark_report.md"))
    assert os.path.exists(os.path.join(test_out, "benchmark_ledger.db"))

    # Verify isolated database has exactly 3 records
    conn = sqlite3.connect(os.path.join(test_out, "benchmark_ledger.db"))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM prompt_records")
    iso_count = c.fetchone()[0]
    conn.close()
    assert iso_count == 3


def test_production_database_count_invariance(tmp_path):
    """Verify that running the benchmark never mutates or appends to prompt_ledger.db."""
    prod_db = "prompt_ledger.db"
    initial_count = None
    if os.path.exists(prod_db):
        conn = sqlite3.connect(prod_db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM prompt_records")
        initial_count = c.fetchone()[0]
        conn.close()

    test_out = str(tmp_path / "bench_prod_test")
    runner = BenchmarkV2Runner(
        dataset_path=DATASET_PATH,
        output_dir=test_out,
        model_tier="mid_tier",
        grid_scenario="ILLUSTRATIVE_385",
        prewarm_embedder=True,
    )
    runner.run_benchmark(modes=["conservative"], smoke_test_limit=2, record_isolated_db=True)

    if initial_count is not None:
        conn = sqlite3.connect(prod_db)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM prompt_records")
        final_count = c.fetchone()[0]
        conn.close()
        assert initial_count == final_count, f"Production ledger changed! {initial_count} -> {final_count}"


def test_aggregate_metric_calculations():
    """Verify precision and mathematical correctness of metric aggregation."""
    runner = BenchmarkV2Runner(output_dir="tmp_test_metrics")

    mock_results = [
        PromptBenchmarkResult(
            prompt_id="p1", category="Code", difficulty="easy", length_profile="short",
            original_prompt="hello", optimized_prompt="hi", optimization_mode="balanced",
            success=True, accepted=True, rollback_occurred=False, rollback_stage="none",
            rollback_reason=None, retry_count=0, original_token_count=10, optimized_token_count=8,
            token_reduction=2, token_reduction_pct=20.0, tokenizer_used="cl100k_base",
            is_exact_tokenizer=True, semantic_similarity=0.98, guardrail_passed=True,
            preservation_violations=[], stage_latencies_ms={}, total_latency_ms=100.0,
            is_cold_start=False, stage_2_method="deterministic", stage_3_method="none",
            stage_3_ollama_fallback_reason=None, predicted_original_output_tokens=100.0,
            predicted_optimized_output_tokens=80.0, predicted_output_token_delta=-20.0,
            gross_energy_saved_wh=0.05, optimizer_overhead_wh=0.001, net_energy_saved_wh=0.049,
            is_net_carbon_debt=False, net_carbon_abated_gco2=0.01, net_water_saved_ml=0.05,
            grid_scenario="ILLUSTRATIVE_385", model_tier="mid_tier"
        ),
        PromptBenchmarkResult(
            prompt_id="p2", category="Code", difficulty="hard", length_profile="medium",
            original_prompt="code", optimized_prompt="code", optimization_mode="balanced",
            success=True, accepted=False, rollback_occurred=True, rollback_stage="original",
            rollback_reason="violation", retry_count=1, original_token_count=20, optimized_token_count=20,
            token_reduction=0, token_reduction_pct=0.0, tokenizer_used="cl100k_base",
            is_exact_tokenizer=True, semantic_similarity=0.99, guardrail_passed=False,
            preservation_violations=["inline code altered"], stage_latencies_ms={}, total_latency_ms=200.0,
            is_cold_start=False, stage_2_method="deterministic", stage_3_method="none",
            stage_3_ollama_fallback_reason=None, predicted_original_output_tokens=100.0,
            predicted_optimized_output_tokens=100.0, predicted_output_token_delta=0.0,
            gross_energy_saved_wh=0.0, optimizer_overhead_wh=0.002, net_energy_saved_wh=-0.002,
            is_net_carbon_debt=True, net_carbon_abated_gco2=-0.001, net_water_saved_ml=-0.003,
            grid_scenario="ILLUSTRATIVE_385", model_tier="mid_tier"
        )
    ]

    summary, cat_summary, failures = runner._calculate_metrics(mock_results, "balanced")

    assert summary["total_prompts"] == 2
    assert summary["accepted_count"] == 1
    assert summary["acceptance_rate_pct"] == 50.0
    assert summary["rollback_count"] == 1
    assert summary["rollback_rate_pct"] == 50.0
    assert summary["net_carbon_debt_count"] == 1
    assert summary["preservation_violations_count"] == 1
    assert summary["latency_ms"]["mean"] == 150.0
    assert summary["latency_ms"]["median"] == 150.0
    assert summary["token_reduction_tokens"]["mean"] == 1.0
    assert summary["token_reduction_tokens"]["total_tokens_saved"] == 2
    assert summary["semantic_similarity"]["mean"] == 0.985
    assert len(failures) == 1
    assert failures[0]["prompt_id"] == "p2"


def test_rollback_fidelity_preserves_prompt():
    """Verify that when a rollback occurs, final_prompt is byte-for-byte identical to original_prompt."""
    summary_path = "results/benchmark_v2/failure_cases.json"
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            failures_by_mode = json.load(f)

        for mode, f_list in failures_by_mode.items():
            for f_item in f_list:
                if f_item["rollback_occurred"]:
                    # Delivered prompt must match original prompt exactly upon rollback
                    assert f_item["optimized_prompt"] == f_item["original_prompt"], (
                        f"Fidelity violation on {f_item['prompt_id']}: final prompt differed from original after rollback!"
                    )
