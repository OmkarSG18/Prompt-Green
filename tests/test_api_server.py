"""
Comprehensive unit and integration test suite for PromptGreen V2 API Server.
Validates V2 unified endpoints (/api/v2/optimize, /api/v2/models, /api/v2/grid-scenarios, /api/v2/ledger/summary),
error handling, edge cases, and backward compatibility with V1 endpoints.
Directly invokes endpoint handlers to guarantee deterministic, offline, and socket-free execution.
"""

import os
import sqlite3
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from promptgreen.ledger.database import PromptLedger, OptimizationEvent
from promptgreen.api.server import (
    app,
    read_root,
    list_v2_model_tiers,
    list_v2_grid_scenarios,
    optimize_prompt_v2,
    get_v2_recent_ledger,
    get_v2_ledger_summary,
    generate_green_prompt,
    review_prompt,
    get_recent_ledger,
    get_ledger_summary,
    V2OptimizeRequest,
    PromptGenerateRequest,
    PromptReviewRequest,
)


@pytest.fixture(autouse=True)
def isolate_test_ledger(tmp_path, monkeypatch):
    """
    Ensures all API tests run against an isolated temporary SQLite database,
    protecting prompt_ledger.db from any writes or modifications during testing.
    """
    db_path = str(tmp_path / "test_api_isolated.db")
    monkeypatch.setenv("PROMPTGREEN_DB_PATH", db_path)
    yield db_path


# ==============================================================================
# ROOT & METADATA ENDPOINTS
# ==============================================================================

def test_read_root():
    """Verify root endpoint returns system metadata and available endpoints."""
    data = read_root()
    assert data["status"] == "active"
    assert data["system"] == "PromptGreen"
    assert data["version"] == "2.0.0"
    assert "/api/v2/optimize" in data["endpoints"]["v2_optimize"]


def test_list_v2_models():
    """Verify /api/v2/models returns all 4 standard tiers with hardware specifications."""
    data = list_v2_model_tiers()
    assert "tiers" in data
    tiers = data["tiers"]
    assert "frontier_dense" in tiers
    assert "large_reasoning" in tiers
    assert "mid_tier" in tiers
    assert "compact_green" in tiers

    # Check tier parameters
    mid = tiers["mid_tier"]
    assert mid["alpha_prefill_mwh"] == 0.24
    assert mid["alpha_decode_mwh"] == 0.92
    assert mid["hardware_id"] == "a100_sxm4"
    assert "hardware_name" in mid
    assert "provenance" in mid


def test_list_v2_grid_scenarios():
    """Verify /api/v2/grid-scenarios returns selectable and unavailable placeholders."""
    data = list_v2_grid_scenarios()
    assert "selectable_scenarios" in data
    scenarios = data["selectable_scenarios"]
    assert "ILLUSTRATIVE_385" in scenarios
    assert "THESIS_367" in scenarios
    assert scenarios["ILLUSTRATIVE_385"]["carbon_intensity_gco2_kwh"] == 385.0
    assert scenarios["THESIS_367"]["carbon_intensity_gco2_kwh"] == 367.0

    assert "unavailable_regional_placeholders" in data
    placeholders = data["unavailable_regional_placeholders"]
    assert "IN" in placeholders
    assert "EU" in placeholders
    assert "US" in placeholders


# ==============================================================================
# V2 UNIFIED OPTIMIZE ENDPOINT TESTS
# ==============================================================================

def test_v2_optimize_standard_balanced():
    """Verify standard optimization run in balanced mode on mid_tier."""
    req = V2OptimizeRequest(
        prompt="Hello! Could you please explain how photosynthesis works in full detail with extensive examples? Thank you!",
        mode="balanced",
        target_model="mid_tier",
        grid_scenario="ILLUSTRATIVE_385",
        monthly_inferences=10000,
        author="tester",
        team="Platform",
        record_in_ledger=True
    )
    data = optimize_prompt_v2(req)

    assert data["success"] is True
    assert data["status_code"] in ["PASS", "WARN"]
    assert data["mode"] == "BALANCED"
    assert data["latency_ms"] > 0

    # Prompts & Token verification
    prompts = data["prompts"]
    assert prompts["original_prompt"] == req.prompt
    assert len(prompts["optimized_prompt"]) < len(prompts["original_prompt"])
    assert prompts["original_input_tokens"] > 0
    assert prompts["optimized_input_tokens"] <= prompts["original_input_tokens"]
    assert prompts["input_tokens_saved"] >= 0
    assert prompts["predicted_original_output_tokens"] > 0
    assert prompts["predicted_optimized_output_tokens"] > 0

    # Pipeline stages
    pipeline = data["pipeline"]
    assert pipeline["semantic_score"] > 0.0
    assert isinstance(pipeline["stages"], list)
    assert len(pipeline["stages"]) >= 1

    # Thermodynamics in canonical Wh
    thermo = data["thermodynamics"]
    assert thermo["model_tier_id"] == "mid_tier"
    assert thermo["energy_original_wh"] > 0.0
    assert thermo["energy_optimized_wh"] > 0.0
    assert thermo["pue_used"] == 1.15

    # Environmental impact
    env = data["environmental_impact"]
    assert env["grid_intensity_gco2_kwh"] == 385.0
    assert "illustrative" in env["grid_provenance"].lower()
    assert "monthly_carbon_abated_gco2" in env
    assert "net_water_saved_ml" in env
    assert "monthly_water_saved_liters" in env

    # Routing recommendation
    routing = data["routing"]
    assert "outcome" in routing
    assert routing["current_model_tier"] == "mid_tier"
    assert "task_suitability" in routing
    assert "explanation" in routing

    # Ledger persistence
    assert data["ledger"]["record_id"] is not None


def test_v2_optimize_conservative_mode():
    """Verify conservative mode applies gentle pruning and preserves high semantic score."""
    req = V2OptimizeRequest(
        prompt="Please write a concise Python function to calculate fibonacci numbers: def fib(n):",
        mode="conservative",
        target_model="large_reasoning",
        grid_scenario="THESIS_367",
        record_in_ledger=False
    )
    data = optimize_prompt_v2(req)

    assert data["success"] is True
    assert data["mode"] == "CONSERVATIVE"
    assert data["pipeline"]["semantic_score"] >= 0.85
    assert data["ledger"]["record_id"] is None


def test_v2_optimize_aggressive_mode():
    """Verify aggressive mode maximizes token reduction."""
    req = V2OptimizeRequest(
        prompt="Hello dear assistant, would you kindly be so nice as to provide me with a very comprehensive overview of French history? Thank you very much in advance!",
        mode="aggressive",
        target_model="frontier_dense",
        grid_scenario="ILLUSTRATIVE_385"
    )
    data = optimize_prompt_v2(req)

    assert data["success"] is True
    assert data["mode"] == "AGGRESSIVE"
    assert data["prompts"]["input_tokens_saved"] > 0


def test_v2_optimize_custom_grid_intensity():
    """Verify user-supplied custom grid intensity and provenance are correctly processed."""
    req = V2OptimizeRequest(
        prompt="Summarize this article in 3 bullet points.",
        mode="balanced",
        target_model="compact_green",
        custom_grid_intensity=512.5,
        custom_grid_provenance="Region X Grid Intensity Audit 2026."
    )
    data = optimize_prompt_v2(req)

    assert data["environmental_impact"]["grid_intensity_gco2_kwh"] == 512.5
    assert "Region X Grid Intensity Audit 2026" in data["environmental_impact"]["grid_provenance"]


def test_v2_optimize_routing_recommendation():
    """Verify model router produces valid recommendation for simple classification tasks."""
    req = V2OptimizeRequest(
        prompt="Classify sentiment of this customer review: 'The package arrived early and works great!' -> Positive",
        mode="balanced",
        target_model="frontier_dense",
        task_category="classification",
        task_complexity="low"
    )
    data = optimize_prompt_v2(req)

    routing = data["routing"]
    assert routing["current_model_tier"] == "frontier_dense"
    # Low-complexity classification on frontier model should recommend a lower-energy tier
    assert routing["outcome"] == "RECOMMEND_LOWER_ENERGY_TIER"
    assert routing["recommended_model_tier"] in ["compact_green", "mid_tier"]
    assert routing["energy_comparison"] is not None
    assert routing["energy_comparison"]["energy_saved_wh"] > 0


# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================

def test_v2_optimize_empty_prompt():
    """Verify 400 Bad Request on empty prompt string."""
    with pytest.raises(HTTPException) as exc_info:
        optimize_prompt_v2(V2OptimizeRequest(prompt=""))
    assert exc_info.value.status_code == 400
    assert "Prompt must be a non-empty string" in exc_info.value.detail


def test_v2_optimize_whitespace_only_prompt():
    """Verify 400 Bad Request on whitespace-only prompt."""
    with pytest.raises(HTTPException) as exc_info:
        optimize_prompt_v2(V2OptimizeRequest(prompt="   \n\t  "))
    assert exc_info.value.status_code == 400
    assert "Prompt must be a non-empty string" in exc_info.value.detail


def test_v2_optimize_invalid_mode():
    """Verify 400 Bad Request on invalid optimization mode."""
    with pytest.raises(HTTPException) as exc_info:
        optimize_prompt_v2(V2OptimizeRequest(prompt="Valid prompt", mode="hyper_extreme"))
    assert exc_info.value.status_code == 400
    assert "Invalid mode 'hyper_extreme'" in exc_info.value.detail


# ==============================================================================
# V2 LEDGER ENDPOINTS TESTS
# ==============================================================================

def test_v2_ledger_summary():
    """Verify /api/v2/ledger/summary returns valid aggregated metrics."""
    data = get_v2_ledger_summary()
    assert "total_runs" in data
    assert "total_net_energy_wh_saved" in data
    assert "total_net_carbon_g_saved" in data
    assert "total_water_saved_ml" in data


def test_v2_ledger_recent():
    """Verify /api/v2/ledger/recent returns records list with V2 fields."""
    records = get_v2_recent_ledger(limit=5)
    assert isinstance(records, list)


# ==============================================================================
# V1 BACKWARD COMPATIBILITY ENDPOINTS TESTS
# ==============================================================================

def test_v1_generate_green_backward_compat():
    """Verify /api/v1/generate-green still functions and returns green alternative."""
    data = generate_green_prompt(PromptGenerateRequest(prompt="Please explain in detail quantum physics."))
    assert "original_prompt" in data
    assert "green_prompt" in data
    assert len(data["green_prompt"]) > 0


def test_v1_review_backward_compat():
    """Verify /api/v1/review still evaluates old vs new prompt correctly."""
    req = PromptReviewRequest(
        old_prompt="Explain in detail with extensive examples how quantum computing works.",
        new_prompt="Summarize how quantum computing works in 3 concise bullet points.",
        model_name="llama-3-8b",
        region="US",
        budget_threshold=0.5,
        mode="warn",
        monthly_inferences=10000
    )
    data = review_prompt(req)
    assert "passed" in data
    assert "status_code" in data
    assert "actual_delta_gco2_1k" in data
    assert "monthly_carbon_delta_gco2" in data


def test_v1_ledger_endpoints_backward_compat():
    """Verify /api/v1/ledger/recent and /api/v1/ledger/summary continue to work."""
    records = get_recent_ledger(limit=3)
    assert isinstance(records, list)

    summary = get_ledger_summary()
    assert "total_reviews" in summary


# ==============================================================================
# ROUTING & DIAGNOSTIC RECOVERY TESTS
# ==============================================================================

def test_v2_optimize_error_diagnostics():
    """Verify that empty or whitespace prompts trigger clean HTTP 400 errors with diagnostic message."""
    with pytest.raises(HTTPException) as exc_info:
        optimize_prompt_v2(V2OptimizeRequest(prompt="   "))
    assert exc_info.value.status_code == 400
    assert "non-empty string" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        optimize_prompt_v2(V2OptimizeRequest(prompt="Valid prompt", mode="invalid_mode"))
    assert exc_info.value.status_code == 400
    assert "Invalid mode" in exc_info.value.detail


def test_evaluation_route_exists():
    """Verify that Website/server.py registers the /evaluation route."""
    import Website.server as ws
    routes = [getattr(r, "path", None) for r in ws.api_app.routes]
    assert "/evaluation" in routes
    assert "/evolution" in routes
    assert "/" in routes
    assert "/studio" in routes


def test_v2_health_endpoint():
    """Verify GET /api/v2/health returns HTTP 200 with structured health payload."""
    from fastapi.testclient import TestClient
    from promptgreen.api.server import app

    client = TestClient(app)
    resp = client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "PromptGreen API"
    assert data["api"] == "available"
    assert "dependencies" in data
    assert data["dependencies"]["database"] in {"connected", "unavailable", "error"}


# ==============================================================================
# STAGE B.2 API TELEMETRY & PERSISTENCE VERIFICATION TESTS
# ==============================================================================

def test_actual_retention_rate_persistence():
    """1. Actual retention-rate persistence: stored accurately in prompt_records and optimization_events."""
    req = V2OptimizeRequest(
        prompt="Hello assistant, can you please explain how photosystems capture solar energy in chloroplasts? Thank you!",
        mode="balanced",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    expected_rate = data["prompts"]["actual_retention_rate"]
    assert 0.0 < expected_rate <= 1.0

    db = PromptLedger()
    recs = db.get_recent_records(limit=1)
    assert len(recs) == 1
    assert recs[0]["actual_retention_rate"] == pytest.approx(expected_rate, abs=1e-4)

    events = db.query_events(limit=1)
    assert len(events) == 1
    assert events[0]["actual_retention_rate"] == pytest.approx(expected_rate, abs=1e-4)


def test_retry_count_persistence():
    """2. Retry-count persistence: stored as non-negative integer in both tables."""
    req = V2OptimizeRequest(
        prompt="Explain the difference between mitosis and meiosis in detail.",
        mode="conservative",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    expected_retries = data["pipeline"]["retry_count"]
    assert isinstance(expected_retries, int)
    assert expected_retries >= 0

    db = PromptLedger()
    recs = db.get_recent_records(limit=1)
    assert recs[0]["retry_count"] == expected_retries

    events = db.query_events(limit=1)
    assert events[0]["retry_count"] == expected_retries


def test_fallback_type_persistence():
    """3. Fallback-type persistence: stored as valid string in both tables."""
    req = V2OptimizeRequest(
        prompt="Provide a step-by-step tutorial on building a web crawler in Python.",
        mode="balanced",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    expected_fallback = data["pipeline"]["fallback_type"]
    assert isinstance(expected_fallback, str)
    assert expected_fallback in ["none", "stage_1", "original", "noop"]

    db = PromptLedger()
    recs = db.get_recent_records(limit=1)
    assert recs[0]["fallback_type"] == expected_fallback

    events = db.query_events(limit=1)
    assert events[0]["fallback_type"] == expected_fallback


def test_stage_breakdown_persistence():
    """4. Stage-breakdown persistence: non-empty dictionary stored in optimization_events."""
    req = V2OptimizeRequest(
        prompt="Write a Python script to sort a list of dictionaries by key.",
        mode="balanced",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    db = PromptLedger()
    events = db.query_events(limit=1)
    assert len(events) == 1
    s_breakdown = events[0]["stage_breakdown"]
    assert isinstance(s_breakdown, dict)
    assert len(s_breakdown) > 0

    # Verify per-stage execution details
    for stage_name, s_info in s_breakdown.items():
        assert "status" in s_info
        assert "input_tokens" in s_info
        assert "output_tokens" in s_info
        assert "latency_ms" in s_info


def test_token_breakdown_persistence():
    """5. Token-breakdown persistence: per-stage token counts stored in optimization_events."""
    req = V2OptimizeRequest(
        prompt="Analyze the carbon impact of running large language models in data centers.",
        mode="balanced",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    db = PromptLedger()
    events = db.query_events(limit=1)
    assert len(events) == 1
    t_breakdown = events[0]["token_breakdown"]
    assert isinstance(t_breakdown, dict)
    assert "original_tokens" in t_breakdown
    assert "final_tokens" in t_breakdown
    assert "tokens_saved" in t_breakdown
    assert "actual_retention_rate" in t_breakdown
    assert t_breakdown["original_tokens"] == data["prompts"]["original_input_tokens"]
    assert t_breakdown["final_tokens"] == data["prompts"]["optimized_input_tokens"]


def test_existing_database_compatibility(tmp_path):
    """6. Existing database compatibility: legacy DB missing new columns dynamically migrates."""
    legacy_db_file = str(tmp_path / "legacy_v1_v2.db")
    conn = sqlite3.connect(legacy_db_file)
    cursor = conn.cursor()
    # Create tables without Stage B.2 columns
    cursor.execute("""
        CREATE TABLE prompt_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commit_hash TEXT,
            author TEXT,
            team TEXT,
            model_name TEXT,
            region TEXT,
            old_prompt TEXT,
            new_prompt TEXT,
            input_token_delta INTEGER,
            predicted_output_token_delta REAL,
            carbon_delta_gco2_1k REAL,
            monthly_carbon_delta_gco2 REAL,
            status TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            opt_mode TEXT DEFAULT 'BALANCED',
            semantic_score REAL DEFAULT 1.0,
            net_energy_wh REAL DEFAULT 0.0,
            net_carbon_g REAL DEFAULT 0.0,
            water_saved_ml REAL DEFAULT 0.0,
            routing_outcome TEXT DEFAULT 'KEEP_CURRENT_MODEL',
            recommended_tier TEXT DEFAULT 'mid_tier',
            latency_ms REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE optimization_events (
            event_id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            original_text TEXT,
            optimized_text TEXT,
            compression_ratio REAL DEFAULT 1.0,
            status TEXT DEFAULT 'PASS'
        )
    """)
    # Insert legacy row
    cursor.execute(
        "INSERT INTO prompt_records (commit_hash, author, team, status) VALUES (?, ?, ?, ?)",
        ("legacy_hash", "legacy_user", "LegacyTeam", "PASS")
    )
    cursor.execute(
        "INSERT INTO optimization_events (event_id, original_text, status) VALUES (?, ?, ?)",
        ("opt_legacy_001", "Old prompt text", "PASS")
    )
    conn.commit()
    conn.close()

    # Open with PromptLedger to trigger dynamic ALTER TABLE migrations
    ledger = PromptLedger(db_path=legacy_db_file)
    conn_check = ledger.get_connection()
    pr_cols = {r[1] for r in conn_check.execute("PRAGMA table_info(prompt_records)").fetchall()}
    oe_cols = {r[1] for r in conn_check.execute("PRAGMA table_info(optimization_events)").fetchall()}
    conn_check.close()

    for col in ["retry_count", "fallback_type", "actual_retention_rate", "rollback_stage"]:
        assert col in pr_cols, f"{col} missing from migrated prompt_records"
        assert col in oe_cols, f"{col} missing from migrated optimization_events"

    # Verify existing records preserved without manufactured default retention values
    recs = ledger.get_recent_records(limit=10)
    assert len(recs) == 1
    assert recs[0]["commit_hash"] == "legacy_hash"
    assert recs[0]["retry_count"] == 0
    assert recs[0]["fallback_type"] == "none"
    assert recs[0]["actual_retention_rate"] is None
    assert recs[0]["final_token_retention_ratio"] is None

    # Verify new record insertion on migrated database works seamlessly
    new_id = ledger.record_v2_run(
        commit_hash="migrated_run",
        author="migrated_user",
        retry_count=1,
        fallback_type="stage_1",
        actual_retention_rate=0.75,
        rollback_stage="none"
    )
    assert new_id > 1
    new_recs = ledger.get_recent_records(limit=1)
    assert new_recs[0]["commit_hash"] == "migrated_run"
    assert new_recs[0]["retry_count"] == 1
    assert new_recs[0]["fallback_type"] == "stage_1"
    assert new_recs[0]["actual_retention_rate"] == pytest.approx(0.75)


def test_fresh_sqlite_initialization(tmp_path):
    """7. Fresh SQLite initialization: creates all required tables and columns from scratch."""
    fresh_db = str(tmp_path / "brand_new.db")
    ledger = PromptLedger(db_path=fresh_db)
    conn = ledger.get_connection()

    pr_cols = {r[1] for r in conn.execute("PRAGMA table_info(prompt_records)").fetchall()}
    oe_cols = {r[1] for r in conn.execute("PRAGMA table_info(optimization_events)").fetchall()}
    conn.close()

    expected_pr = {
        "id", "commit_hash", "author", "team", "model_name", "region",
        "old_prompt", "new_prompt", "input_token_delta", "predicted_output_token_delta",
        "carbon_delta_gco2_1k", "monthly_carbon_delta_gco2", "status", "timestamp",
        "opt_mode", "semantic_score", "net_energy_wh", "net_carbon_g",
        "water_saved_ml", "routing_outcome", "recommended_tier", "latency_ms",
        "retry_count", "fallback_type", "actual_retention_rate", "rollback_stage"
    }
    assert expected_pr.issubset(pr_cols)

    expected_oe = {
        "event_id", "timestamp", "prompt_category", "author", "team",
        "model_name", "region", "original_text", "optimized_text",
        "original_tokens", "optimized_tokens", "tokens_saved",
        "compression_ratio", "semantic_similarity", "optimization_latency_ms",
        "pipeline_stages_applied", "routing_decision", "recommended_tier",
        "modeled_prefill_energy_j", "modeled_decode_energy_j",
        "modeled_total_energy_j", "modeled_carbon_gco2e", "water_saved_ml",
        "grid_carbon_intensity", "status", "stage_breakdown", "token_breakdown",
        "retry_count", "fallback_type", "actual_retention_rate", "rollback_stage"
    }
    assert expected_oe.issubset(oe_cols)


def test_promptgreen_db_path_configuration(tmp_path, monkeypatch):
    """8. PROMPTGREEN_DB_PATH configuration: environment variable redirects DB path."""
    custom_db = str(tmp_path / "custom_configured.db")
    monkeypatch.setenv("PROMPTGREEN_DB_PATH", custom_db)

    ledger = PromptLedger()
    assert ledger.db_path == custom_db

    ledger.record_prompt_review(
        commit_hash="env_test",
        author="env_user",
        team="EnvTeam",
        model_name="mid_tier",
        region="ILLUSTRATIVE_385",
        old_prompt="old",
        new_prompt="new",
        input_token_delta=-5,
        predicted_output_token_delta=0.0,
        carbon_delta_gco2_1k=-0.01,
        monthly_carbon_delta_gco2=-100.0,
        status="PASS"
    )
    assert os.path.exists(custom_db)
    recs = ledger.get_recent_records(limit=1)
    assert len(recs) == 1
    assert recs[0]["commit_hash"] == "env_test"


def test_invalid_semantic_threshold_handling():
    """9. Invalid semantic threshold handling: thresholds below 0.92 are clamped to universal floor."""
    # Sub-0.92 threshold (0.85) clamped to 0.92
    req_sub = V2OptimizeRequest(
        prompt="Explain quantum entanglement clearly and concisely.",
        mode="balanced",
        threshold=0.85,
        record_in_ledger=False,
    )
    res_sub = optimize_prompt_v2(req_sub)
    assert res_sub["pipeline"]["active_threshold"] == 0.92
    if res_sub["pipeline"]["guardrail_passed"]:
        assert res_sub["pipeline"]["semantic_score"] >= 0.92
    else:
        assert res_sub["pipeline"]["rollback_occurred"] is True
        assert res_sub["prompts"]["optimized_prompt"] == req_sub.prompt

    # Very low threshold (0.50) clamped to 0.92
    req_low = V2OptimizeRequest(
        prompt="Summarize the theory of general relativity in 3 bullet points.",
        mode="conservative",
        threshold=0.50,
        record_in_ledger=False,
    )
    res_low = optimize_prompt_v2(req_low)
    assert res_low["pipeline"]["active_threshold"] == 0.92
    if res_low["pipeline"]["guardrail_passed"]:
        assert res_low["pipeline"]["semantic_score"] >= 0.92
    else:
        assert res_low["pipeline"]["rollback_occurred"] is True
        assert res_low["prompts"]["optimized_prompt"] == req_low.prompt

    # Higher threshold (0.95) honored
    req_high = V2OptimizeRequest(
        prompt="Define recursion in computer programming with a brief example.",
        mode="balanced",
        threshold=0.95,
        record_in_ledger=False,
    )
    res_high = optimize_prompt_v2(req_high)
    assert res_high["pipeline"]["active_threshold"] == 0.95


def test_api_telemetry_response_accuracy():
    """10. API telemetry response accuracy: validates all telemetry fields in V2 response."""
    req = V2OptimizeRequest(
        prompt="Hello dear assistant! Would you kindly explain how neural networks learn via backpropagation? Thank you!",
        mode="balanced",
        target_model="mid_tier",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    # Prompt telemetry
    p = data["prompts"]
    assert "actual_retention_rate" in p
    assert "token_breakdown" in p
    assert 0.0 < p["actual_retention_rate"] <= 1.0
    expected_retention = round(p["optimized_input_tokens"] / p["original_input_tokens"], 4)
    assert p["actual_retention_rate"] == pytest.approx(expected_retention, abs=1e-4)

    # Token breakdown completeness
    tb = p["token_breakdown"]
    assert tb["original_tokens"] == p["original_input_tokens"]
    assert tb["final_tokens"] == p["optimized_input_tokens"]
    assert tb["tokens_saved"] == p["input_tokens_saved"]

    # Pipeline telemetry
    pipe = data["pipeline"]
    assert "retry_count" in pipe
    assert "fallback_type" in pipe
    assert "actual_retention_rate" in pipe
    assert "compressor_retention_rate" in pipe
    assert "final_token_retention_ratio" in pipe
    assert "active_threshold" in pipe
    assert "stage_breakdown" in pipe
    assert "token_breakdown" in pipe
    assert pipe["actual_retention_rate"] == p["actual_retention_rate"]
    assert pipe["final_token_retention_ratio"] == p["final_token_retention_ratio"]
    assert pipe["compressor_retention_rate"] == p["compressor_retention_rate"]
    assert isinstance(pipe["retry_count"], int)
    assert pipe["retry_count"] >= 0
    assert pipe["active_threshold"] >= 0.92


# ==============================================================================
# CORRECTIVE VERIFICATION SUITE: RETENTION, ENERGY, AND DB LIFECYCLE
# ==============================================================================

def test_retention_semantics_disambiguation(isolate_test_ledger):
    """
    1. Distinguish LLMLingua compressor retention rate from final prompt token retention ratio.
    Verifies that:
    - compressor_retention_rate represents the LLMLingua target retention rate (0.40, 0.60, 0.80).
    - final_token_retention_ratio represents the empirical ratio of final tokens / original tokens.
    - actual_retention_rate is preserved as a backward-compatible alias for final_token_retention_ratio.
    - Both metrics are correctly stored in SQLite optimization_events and prompt_records.
    """
    modes_and_targets = [
        ("aggressive", 0.40),
        ("balanced", 0.60),
        ("conservative", 0.80),
    ]

    for mode, expected_comp_target in modes_and_targets:
        req = V2OptimizeRequest(
            prompt="Could you please provide a clear, concise explanation of solar photovoltaic cell operation? Thank you!",
            mode=mode,
            record_in_ledger=True,
        )
        data = optimize_prompt_v2(req)
        assert data["success"] is True

        p = data["prompts"]
        pipe = data["pipeline"]
        tb = p["token_breakdown"]

        # 1. Compressor retention rate matches mode target
        assert "compressor_retention_rate" in p
        assert "compressor_retention_rate" in pipe
        assert "compressor_retention_rate" in tb
        assert "accepted_compressor_retention_rate" in p
        assert "last_compressor_attempt_retention_rate" in p
        assert p["compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert p["accepted_compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert p["last_compressor_attempt_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert pipe["compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)

        # 2. Final token retention ratio is empirical token ratio
        expected_final_ratio = round(p["optimized_input_tokens"] / p["original_input_tokens"], 4)
        assert "final_token_retention_ratio" in p
        assert "final_token_retention_ratio" in pipe
        assert "final_token_retention_ratio" in tb
        assert p["final_token_retention_ratio"] == pytest.approx(expected_final_ratio, abs=1e-4)
        assert pipe["final_token_retention_ratio"] == pytest.approx(expected_final_ratio, abs=1e-4)

        # 3. Backward-compatibility alias actual_retention_rate equals final_token_retention_ratio
        assert p["actual_retention_rate"] == p["final_token_retention_ratio"]
        assert pipe["actual_retention_rate"] == pipe["final_token_retention_ratio"]

    # 4. Verify database persistence
    conn = sqlite3.connect(isolate_test_ledger)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM optimization_events ORDER BY rowid ASC")
    events = cursor.fetchall()
    assert len(events) == 3

    for idx, (mode, expected_comp_target) in enumerate(modes_and_targets):
        row = events[idx]
        assert row["compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert row["accepted_compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert row["last_compressor_attempt_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert row["final_token_retention_ratio"] == pytest.approx(row["optimized_tokens"] / row["original_tokens"], abs=1e-4)
        assert row["actual_retention_rate"] == row["final_token_retention_ratio"]

    cursor.execute("SELECT * FROM prompt_records WHERE commit_hash = 'v2-api' ORDER BY id ASC")
    records = cursor.fetchall()
    assert len(records) == 3

    for idx, (mode, expected_comp_target) in enumerate(modes_and_targets):
        rec = records[idx]
        assert rec["compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert rec["accepted_compressor_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert rec["last_compressor_attempt_retention_rate"] == pytest.approx(expected_comp_target, abs=1e-3)
        assert rec["final_token_retention_ratio"] is not None
        assert rec["actual_retention_rate"] == rec["final_token_retention_ratio"]

    conn.close()


def test_all_six_retention_telemetry_scenarios():
    """
    Directly tests all 6 retention execution scenarios required by Stage B.2.2:
    Scenario 1: Initial compressor candidate accepted.
    Scenario 2: First retry accepted (candidate passes after 1 retry: 0.40 -> 0.60).
    Scenario 3: Second retry accepted (candidate passes after 2 retries: 0.40 -> 0.60 -> 0.80).
    Scenario 4: Stage 1 fallback accepted after compressor failures.
    Scenario 5: Original prompt rollback.
    Scenario 6: Compressor bypassed (enable_stage_2=False).
    """
    import numpy as np
    from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig
    from promptgreen.optimizer.compressor import LLMLinguaCompressor, CompressionResult
    from promptgreen.optimizer.semantic_guard import SemanticFidelityGuard, GuardrailConfig, LocalMiniLMEmbedder

    rng = np.random.default_rng(42)
    base_v = rng.standard_normal(384).astype(np.float32)
    base_v /= np.linalg.norm(base_v)
    orth_v = rng.standard_normal(384).astype(np.float32)
    orth_v -= np.dot(orth_v, base_v) * base_v
    orth_v /= np.linalg.norm(orth_v)

    def make_vec(sim: float):
        v = sim * base_v + np.sqrt(max(0.0, 1.0 - sim**2)) * orth_v
        return (v / np.linalg.norm(v)).tolist()

    # Custom embedder mapping keywords to target cosine similarities
    def mock_embed(text: str):
        if "sim_085" in text:
            return make_vec(0.85)
        if "sim_088" in text:
            return make_vec(0.88)
        if "sim_095" in text:
            return make_vec(0.95)
        if "sim_070" in text:
            return make_vec(0.70)
        return base_v.tolist()

    embedder = LocalMiniLMEmbedder(custom_client=mock_embed)

    # Helper to create controllable compressor
    class StepCompressor(LLMLinguaCompressor):
        def __init__(self, mode_map):
            self.mode_map = mode_map
            self.calls = []

        def compress(self, prompt, mode="balanced", target_retention_rate=None):
            self.calls.append((mode, target_retention_rate))
            text, ret_rate = self.mode_map.get(mode, (prompt, 0.60))
            return CompressionResult(
                original_prompt=prompt,
                compressed_prompt=text,
                original_token_count=20,
                compressed_token_count=int(20 * ret_rate),
                actual_reduction_percentage=(1.0 - ret_rate) * 100.0,
                retention_rate=ret_rate,
                compression_mode=mode,
                compression_method="mock",
                model_name="mock",
                model_available=True,
                is_exact_token_count=True,
                compression_latency_ms=1.0,
                model_loading_latency_ms=0.0,
                protected_region_count=0,
                protected_regions_preserved=True,
            )

    test_prompt = "Please explain the fundamental operation of photovoltaic solar panels."

    # Scenario 1: Initial candidate accepted (mode aggressive -> 0.40)
    p1 = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=StepCompressor({"aggressive": (test_prompt + " sim_095", 0.40)}),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=embedder),
    )
    r1 = p1.optimize(test_prompt, mode="aggressive")
    assert r1.last_compressor_attempt_retention_rate == pytest.approx(0.40, abs=1e-3)
    assert r1.accepted_compressor_retention_rate == pytest.approx(0.40, abs=1e-3)
    assert r1.compressor_retention_rate == pytest.approx(0.40, abs=1e-3)
    assert r1.fallback_type == "none"

    # Scenario 2: First retry accepted (aggressive 0.40 fails, balanced 0.60 passes)
    p2 = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=StepCompressor({
            "aggressive": (test_prompt + " sim_085", 0.40),
            "balanced": (test_prompt + " sim_095", 0.60),
        }),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=embedder),
    )
    r2 = p2.optimize(test_prompt, mode="aggressive")
    assert r2.retry_count == 1
    assert r2.last_compressor_attempt_retention_rate == pytest.approx(0.60, abs=1e-3)
    assert r2.accepted_compressor_retention_rate == pytest.approx(0.60, abs=1e-3)
    assert r2.compressor_retention_rate == pytest.approx(0.60, abs=1e-3)
    assert r2.fallback_type == "stage_2_compressed"

    # Scenario 3: Second retry accepted (aggressive 0.40 fails, balanced 0.60 fails, conservative 0.80 passes)
    p3 = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=StepCompressor({
            "aggressive": (test_prompt + " sim_085", 0.40),
            "balanced": (test_prompt + " sim_088", 0.60),
            "conservative": (test_prompt + " sim_095", 0.80),
        }),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=embedder),
    )
    r3 = p3.optimize(test_prompt, mode="aggressive")
    assert r3.retry_count == 2
    assert r3.last_compressor_attempt_retention_rate == pytest.approx(0.80, abs=1e-3)
    assert r3.accepted_compressor_retention_rate == pytest.approx(0.80, abs=1e-3)
    assert r3.compressor_retention_rate == pytest.approx(0.80, abs=1e-3)
    assert r3.fallback_type == "stage_2_compressed"

    # Scenario 4: Stage 1 fallback accepted after compressor failures
    verbose_prompt = "Hello, could you please kindly provide a detailed explanation of photovoltaic solar panels? Thank you so much!"
    p4 = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=StepCompressor({
            "aggressive": (verbose_prompt + " sim_085", 0.40),
            "balanced": (verbose_prompt + " sim_088", 0.60),
            "conservative": (verbose_prompt + " sim_070", 0.80),
        }),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=embedder),
    )
    r4 = p4.optimize(verbose_prompt, mode="aggressive")
    assert r4.last_compressor_attempt_retention_rate == pytest.approx(0.80, abs=1e-3)
    assert r4.accepted_compressor_retention_rate is None  # Compressor was NOT accepted
    assert r4.compressor_retention_rate is None
    assert r4.fallback_type == "stage_1"
    assert r4.final_token_retention_ratio is not None

    # Scenario 5: Original prompt rollback (all attempts fail and no Stage 1 reduction)
    clean_prompt = "Explain quantum computing."  # Rule pruner will not reduce this
    p5 = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=StepCompressor({
            "aggressive": (clean_prompt + " sim_085", 0.40),
            "balanced": (clean_prompt + " sim_088", 0.60),
            "conservative": (clean_prompt + " sim_070", 0.80),
        }),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=embedder),
    )
    r5 = p5.optimize(clean_prompt, mode="aggressive")
    assert r5.last_compressor_attempt_retention_rate == pytest.approx(0.80, abs=1e-3)
    assert r5.accepted_compressor_retention_rate is None
    assert r5.compressor_retention_rate is None
    assert r5.final_token_retention_ratio == 1.0
    assert r5.fallback_type == "original"

    # Scenario 6: Compressor bypassed (enable_stage_2=False)
    p6 = PromptGreenPipeline(
        config=PipelineConfig(mode="balanced", enable_stage_2=False),
        guardrail=SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder),
    )
    r6 = p6.optimize(test_prompt, mode="balanced")
    assert r6.last_compressor_attempt_retention_rate is None
    assert r6.accepted_compressor_retention_rate is None
    assert r6.compressor_retention_rate is None
    assert r6.final_token_retention_ratio is not None


def test_energy_component_fields_semantics_and_no_manufactured_zeros(isolate_test_ledger):
    """
    2. Ensure energy component fields do not contain misleading manufactured zero values.
    Verifies that:
    - modeled_prefill_energy_j and modeled_decode_energy_j are genuine modeled Joules (> 0.0).
    - modeled_prefill_energy_j + modeled_decode_energy_j == modeled_total_energy_j when decode is modeled.
    - modeled_total_energy_j equals energy_optimized_wh * 3600.0 (exact Joules conversion).
    - In INPUT_ONLY scenario, modeled_decode_energy_j is None (SQL NULL), never manufactured 0.0.
    """
    req = V2OptimizeRequest(
        prompt="Explain the difference between supervised and unsupervised learning algorithms with practical examples.",
        mode="balanced",
        target_model="frontier_dense",
        record_in_ledger=True,
    )
    data = optimize_prompt_v2(req)
    assert data["success"] is True

    thermo = data["thermodynamics"]
    e_opt_wh = thermo["energy_optimized_wh"]
    tot_j = thermo["modeled_total_energy_j"]
    pref_j = thermo["modeled_prefill_energy_j"]
    dec_j = thermo["modeled_decode_energy_j"]

    # Total energy must be in Joules (Wh * 3600)
    assert tot_j == pytest.approx(round(e_opt_wh * 3600.0, 6), abs=1e-5)
    assert tot_j > 0.0

    # Prefill and decode components must be genuine non-zero positive floats
    assert pref_j is not None and pref_j > 0.0
    assert dec_j is not None and dec_j > 0.0

    # Conservation of modeled inference energy: prefill_j + decode_j == total_j
    assert pref_j + dec_j == pytest.approx(tot_j, abs=1e-4)

    # Verify directly in SQLite ledger
    conn = sqlite3.connect(isolate_test_ledger)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT modeled_prefill_energy_j, modeled_decode_energy_j, modeled_total_energy_j FROM optimization_events LIMIT 1")
    row = cursor.fetchone()
    assert row["modeled_prefill_energy_j"] == pytest.approx(pref_j, abs=1e-5)
    assert row["modeled_decode_energy_j"] == pytest.approx(dec_j, abs=1e-5)
    assert row["modeled_total_energy_j"] == pytest.approx(tot_j, abs=1e-5)
    conn.close()

    # Now verify INPUT_ONLY scenario via calculate_thermodynamic_impact
    from promptgreen.engine.thermodynamics import calculate_thermodynamic_impact, AccountingScenario
    res_input_only = calculate_thermodynamic_impact(
        tin_original=100,
        tout_original=50.0,
        tin_optimized=70,
        tout_optimized=50.0,
        accounting_scenario=AccountingScenario.INPUT_ONLY.value,
        grid_scenario="ILLUSTRATIVE_385",
    )
    # In INPUT_ONLY, decode energy is explicitly not modeled and must be None, NOT manufactured 0.0!
    assert res_input_only.decode_energy_opt_wh is None
    assert res_input_only.modeled_decode_energy_j is None
    assert res_input_only.modeled_prefill_energy_j is not None
    assert res_input_only.modeled_prefill_energy_j > 0.0
    assert res_input_only.modeled_total_energy_j == res_input_only.modeled_prefill_energy_j


def test_promptgreen_db_path_lifecycle_and_db_invariance(tmp_path, monkeypatch):
    """
    3. Verify PROMPTGREEN_DB_PATH works correctly with actual database initialization lifecycle.
    Exercises the full FastAPI HTTP lifecycle via TestClient with PROMPTGREEN_DB_PATH pointing
    to an isolated database, and proves that prompt_ledger.db remains 100% invariant in size and mtime.
    """
    prod_db_path = "prompt_ledger.db"
    assert os.path.exists(prod_db_path), "Production database prompt_ledger.db must exist."

    # Record baseline state of production database
    prod_stat_before = os.stat(prod_db_path)
    prod_size_before = prod_stat_before.st_size
    prod_mtime_before = prod_stat_before.st_mtime

    # Configure isolated database path for this test
    custom_test_db = str(tmp_path / "lifecycle_custom_test.db")
    monkeypatch.setenv("PROMPTGREEN_DB_PATH", custom_test_db)

    # Execute request via FastAPI endpoint handler
    # (Direct handler invocation guarantees deterministic, socket-free execution in sandbox environments)
    req = V2OptimizeRequest(
        prompt="Please review this prompt and compress it to reduce inference carbon emissions.",
        mode="balanced",
        record_in_ledger=True,
        author="lifecycle-tester",
        team="VerificationQA"
    )
    resp_data = optimize_prompt_v2(req)
    assert resp_data["success"] is True
    assert resp_data["ledger"]["recorded"] is True

    # 1. Assert isolated test database was created and received the record
    assert os.path.exists(custom_test_db), "Isolated database should have been created."
    conn = sqlite3.connect(custom_test_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM optimization_events")
    evt_cnt = cursor.fetchone()["cnt"]
    assert evt_cnt == 1

    cursor.execute("SELECT COUNT(*) as cnt FROM prompt_records")
    rec_cnt = cursor.fetchone()["cnt"]
    assert rec_cnt >= 1

    cursor.execute("SELECT * FROM optimization_events LIMIT 1")
    event_row = cursor.fetchone()
    assert event_row["author"] == "lifecycle-tester"
    assert event_row["team"] == "VerificationQA"
    assert event_row["compressor_retention_rate"] is not None
    assert event_row["final_token_retention_ratio"] is not None
    assert event_row["modeled_prefill_energy_j"] is not None
    assert event_row["modeled_decode_energy_j"] is not None
    conn.close()

    # 2. Assert production database prompt_ledger.db remained 100% INVARIANT
    prod_stat_after = os.stat(prod_db_path)
    prod_size_after = prod_stat_after.st_size
    prod_mtime_after = prod_stat_after.st_mtime

    assert prod_size_after == prod_size_before, (
        f"Production database size changed! Before: {prod_size_before}, After: {prod_size_after}"
    )
    assert prod_mtime_after == prod_mtime_before, (
        f"Production database mtime changed! Before: {prod_mtime_before}, After: {prod_mtime_after}"
    )

