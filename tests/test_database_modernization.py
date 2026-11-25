"""
Unit and integration tests for PromptGreen V2 Database Modernization.
Tests dual-engine functionality, fallback mechanics, hypertable schemas, and time-series aggregation.
"""

import os
import pytest
from datetime import datetime, timezone
from promptgreen.ledger.database import PromptLedger, LedgerRecord, OptimizationEvent


@pytest.fixture
def temp_ledger(tmp_path):
    """Provides a fresh isolated SQLite database instance."""
    db_file = os.path.join(tmp_path, "test_ledger_v2.db")
    ledger = PromptLedger(db_path=db_file)
    return ledger


def test_sqlite_schema_initialization(temp_ledger):
    """Verifies that both prompt_records and optimization_events tables are created."""
    status = temp_ledger.get_engine_status()
    assert status["backend"] == "sqlite"
    assert status["prompt_records_count"] == 0
    assert status["optimization_events_count"] == 0


def test_legacy_v1_record_and_query(temp_ledger):
    """Verifies backward-compatible record_prompt_review insertion and querying."""
    rec_id = temp_ledger.record_prompt_review(
        commit_hash="abc1234",
        author="alice",
        team="CoreAI",
        model_name="llama-3-8b",
        region="US-East",
        old_prompt="Explain machine learning in great detail with examples.",
        new_prompt="Explain machine learning briefly.",
        input_token_delta=-8,
        predicted_output_token_delta=-150.0,
        carbon_delta_gco2_1k=-0.045,
        monthly_carbon_delta_gco2=-450.0,
        status="PASS"
    )
    assert rec_id == 1
    recs = temp_ledger.get_recent_records(limit=10)
    assert len(recs) == 1
    assert recs[0]["commit_hash"] == "abc1234"
    assert recs[0]["input_token_delta"] == -8

    leaderboard = temp_ledger.get_team_leaderboard()
    assert len(leaderboard) == 1
    assert leaderboard[0]["team"] == "CoreAI"


def test_v2_run_and_summary(temp_ledger):
    """Verifies record_v2_run telemetry metrics calculation."""
    temp_ledger.record_v2_run(
        commit_hash="v2-test",
        author="bob",
        team="GreenInfra",
        model_name="mid_tier",
        region="ILLUSTRATIVE_385",
        old_prompt="Write a long essay on cloud emissions.",
        new_prompt="Summarize cloud emissions in 3 bullets.",
        input_token_delta=-15,
        predicted_output_token_delta=-200.0,
        carbon_delta_gco2_1k=-0.08,
        monthly_carbon_delta_gco2=-800.0,
        status="PASS",
        opt_mode="stage1,stage2,stage3,stage4",
        semantic_score=0.98,
        net_energy_wh=1.25,
        net_carbon_g=0.48,
        water_saved_ml=2.1,
        routing_outcome="KEEP_CURRENT_MODEL",
        recommended_tier="mid_tier",
        latency_ms=45.2
    )

    summary = temp_ledger.get_v2_summary()
    assert summary["total_runs"] == 1
    assert summary["passed_runs"] == 1
    assert summary["total_net_energy_wh_saved"] == pytest.approx(1.25)
    assert summary["total_net_carbon_g_saved"] == pytest.approx(0.48)
    assert summary["avg_semantic_score"] == pytest.approx(0.98)


def test_modern_optimization_event_persistence(temp_ledger):
    """Verifies full OptimizationEvent persistence, JSON serialization, and queries."""
    event = OptimizationEvent(
        event_id="opt_test_001",
        timestamp=datetime.now(timezone.utc),
        prompt_category="coding",
        author="carol",
        team="Platform",
        model_name="compact_green",
        region="ILLUSTRATIVE_385",
        original_text="def foo(): pass",
        optimized_text="def foo(): return 42",
        original_tokens=10,
        optimized_tokens=8,
        tokens_saved=2,
        compression_ratio=0.8,
        semantic_similarity=0.99,
        optimization_latency_ms=12.5,
        pipeline_stages_applied="stage1,stage2",
        routing_decision="ROUTE_DOWN",
        recommended_tier="compact_green",
        modeled_prefill_energy_j=0.05,
        modeled_decode_energy_j=0.15,
        modeled_total_energy_j=0.20,
        modeled_carbon_gco2e=0.00008,
        water_saved_ml=0.05,
        status="PASS",
        stage_breakdown={"stage1": {"latency_ms": 1.2}, "stage2": {"latency_ms": 11.3}},
        token_breakdown={"input_saved": 2}
    )

    evt_id = temp_ledger.record_optimization_event(event)
    assert evt_id == "opt_test_001"

    # Query events
    events = temp_ledger.query_events(category="coding")
    assert len(events) == 1
    assert events[0]["event_id"] == "opt_test_001"
    assert events[0]["tokens_saved"] == 2
    assert isinstance(events[0]["stage_breakdown"], dict)
    assert "stage1" in events[0]["stage_breakdown"]


def test_time_series_aggregates(temp_ledger):
    """Verifies time-series aggregation query in SQLite mode."""
    for i in range(3):
        temp_ledger.record_optimization_event(OptimizationEvent(
            event_id=f"evt_ts_{i}",
            tokens_saved=5 * (i + 1),
            modeled_total_energy_j=1.0,
            modeled_carbon_gco2e=0.001
        ))

    ts_data = temp_ledger.get_time_series_aggregates(interval="hour")
    assert len(ts_data) >= 1
    assert ts_data[0]["total_optimizations"] == 3
    assert ts_data[0]["total_tokens_saved"] == 30  # 5 + 10 + 15


def test_unreachable_postgres_fallback(tmp_path):
    """Verifies that PromptLedger transparently falls back to SQLite when PostgreSQL is offline."""
    db_file = os.path.join(tmp_path, "fallback_test.db")
    fake_pg_url = "postgresql://invalid_user:invalid_pass@127.0.0.1:54399/nonexistent_db"
    ledger = PromptLedger(db_path=db_file, connection_url=fake_pg_url)

    # Must fall back to SQLite without crashing
    assert ledger.engine_type == "sqlite"
    status = ledger.get_engine_status()
    assert status["backend"] == "sqlite"
    assert status["has_timescaledb"] is False


def test_historical_migration_retention_and_token_counts(tmp_path):
    """
    Verifies that historical database migration correctly handles retention ratios:
    - Rows without genuine token counts (or original_tokens == 0 or NULL) remain NULL (never manufactured 1.0).
    - Rows with genuine token counts (original_tokens > 0) receive accurately computed ratio.
    - Default values on new columns do not manufacture 1.0 for historical records.
    - Newly recorded events populate calculated metrics normally.
    """
    import sqlite3
    legacy_db = tmp_path / "legacy_migration.db"
    conn = sqlite3.connect(legacy_db)
    cur = conn.cursor()

    # Create older schema without v2 retention or energy columns
    cur.execute("""
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        INSERT INTO prompt_records (commit_hash, author, team, model_name, old_prompt, new_prompt, input_token_delta, status)
        VALUES ('legacy_commit', 'legacy_author', 'Research', 'llama-2', 'Tell me about solar energy in detail.', 'Tell me about solar energy.', -4, 'PASS')
    """)

    cur.execute("""
        CREATE TABLE optimization_events (
            event_id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            prompt_category TEXT DEFAULT 'general',
            author TEXT DEFAULT 'local-user',
            team TEXT DEFAULT 'Engineering',
            model_name TEXT DEFAULT 'mid_tier',
            region TEXT DEFAULT 'ILLUSTRATIVE_385',
            original_text TEXT,
            optimized_text TEXT,
            original_tokens INTEGER,
            optimized_tokens INTEGER,
            tokens_saved INTEGER DEFAULT 0,
            compression_ratio REAL DEFAULT 1.0,
            semantic_similarity REAL DEFAULT 1.0,
            optimization_latency_ms REAL DEFAULT 0.0,
            pipeline_stages_applied TEXT DEFAULT 'stage1,stage2,stage3,stage4',
            routing_decision TEXT DEFAULT 'KEEP_CURRENT_MODEL',
            recommended_tier TEXT DEFAULT 'mid_tier'
        )
    """)
    # Row A: original_tokens = 0 (token counts unavailable)
    cur.execute("""
        INSERT INTO optimization_events (event_id, original_text, optimized_text, original_tokens, optimized_tokens)
        VALUES ('hist_row_a_zero_tokens', 'Some prompt', 'Some prompt', 0, 0)
    """)
    # Row B: original_tokens = 100, optimized_tokens = 60 (genuine token counts)
    cur.execute("""
        INSERT INTO optimization_events (event_id, original_text, optimized_text, original_tokens, optimized_tokens)
        VALUES ('hist_row_b_valid_tokens', 'Original prompt with 100 tokens', 'Optimized prompt with 60 tokens', 100, 60)
    """)
    # Row C: original_tokens = NULL
    cur.execute("""
        INSERT INTO optimization_events (event_id, original_text, optimized_text, original_tokens, optimized_tokens)
        VALUES ('hist_row_c_null_tokens', 'Another prompt', 'Another prompt', NULL, NULL)
    """)
    conn.commit()
    conn.close()

    # Now instantiate PromptLedger to trigger _init_sqlite_schema() additive migration
    ledger = PromptLedger(db_path=str(legacy_db))
    assert ledger.engine_type == "sqlite"

    # Query back using raw sqlite3 connection to inspect persisted values
    conn2 = sqlite3.connect(legacy_db)
    conn2.row_factory = sqlite3.Row
    cur2 = conn2.cursor()

    # 1. Check prompt_records historical row: must NOT have fabricated 1.0
    cur2.execute("SELECT * FROM prompt_records WHERE commit_hash = 'legacy_commit'")
    pr_row = cur2.fetchone()
    assert pr_row["final_token_retention_ratio"] is None
    assert pr_row["actual_retention_rate"] is None
    assert pr_row["accepted_compressor_retention_rate"] is None
    assert pr_row["last_compressor_attempt_retention_rate"] is None

    # 2. Check optimization_events historical rows
    cur2.execute("SELECT * FROM optimization_events WHERE event_id = 'hist_row_a_zero_tokens'")
    row_a = cur2.fetchone()
    assert row_a["final_token_retention_ratio"] is None
    assert row_a["actual_retention_rate"] is None
    assert row_a["accepted_compressor_retention_rate"] is None

    cur2.execute("SELECT * FROM optimization_events WHERE event_id = 'hist_row_b_valid_tokens'")
    row_b = cur2.fetchone()
    assert row_b["final_token_retention_ratio"] == pytest.approx(0.60, abs=1e-4)
    assert row_b["actual_retention_rate"] == pytest.approx(0.60, abs=1e-4)
    assert row_b["accepted_compressor_retention_rate"] is None

    cur2.execute("SELECT * FROM optimization_events WHERE event_id = 'hist_row_c_null_tokens'")
    row_c = cur2.fetchone()
    assert row_c["final_token_retention_ratio"] is None
    assert row_c["actual_retention_rate"] is None

    # 3. Insert new V2 optimization event with genuine telemetry
    ledger.record_optimization_event(OptimizationEvent(
        event_id="new_event_v2",
        original_tokens=50,
        optimized_tokens=30,
        final_token_retention_ratio=0.60,
        accepted_compressor_retention_rate=0.60,
        last_compressor_attempt_retention_rate=0.60,
        modeled_prefill_energy_j=1.234,
        modeled_decode_energy_j=None,  # INPUT_ONLY
        modeled_total_energy_j=1.234,
    ))

    cur2.execute("SELECT * FROM optimization_events WHERE event_id = 'new_event_v2'")
    new_row = cur2.fetchone()
    assert new_row["final_token_retention_ratio"] == pytest.approx(0.60, abs=1e-4)
    assert new_row["accepted_compressor_retention_rate"] == pytest.approx(0.60, abs=1e-4)
    assert new_row["last_compressor_attempt_retention_rate"] == pytest.approx(0.60, abs=1e-4)
    assert new_row["modeled_prefill_energy_j"] == pytest.approx(1.234, abs=1e-3)
    assert new_row["modeled_decode_energy_j"] is None  # genuine SQL NULL, not 0.0

    conn2.close()


def test_energy_field_nullability_and_no_table_rebuild(tmp_path):
    """
    Verifies SQLite energy-field nullability:
    - Confirms PRAGMA table_info verifies notnull == 0 (NULL permitted).
    - Confirms no table-rebuild migration is required because existing schema permits NULL.
    - Confirms inserting an optimization event with modeled_decode_energy_j = None persists NULL (not 0.0).
    """
    import sqlite3
    db_file = tmp_path / "nullability_test.db"
    ledger = PromptLedger(db_path=str(db_file))

    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # Inspect PRAGMA table_info
    cur.execute("PRAGMA table_info(optimization_events)")
    col_info = {row[1]: {"type": row[2], "notnull": row[3], "dflt_value": row[4]} for row in cur.fetchall()}

    assert "modeled_prefill_energy_j" in col_info
    assert "modeled_decode_energy_j" in col_info
    assert col_info["modeled_prefill_energy_j"]["notnull"] == 0, "modeled_prefill_energy_j must allow NULL"
    assert col_info["modeled_decode_energy_j"]["notnull"] == 0, "modeled_decode_energy_j must allow NULL"
    assert col_info["final_token_retention_ratio"]["notnull"] == 0, "final_token_retention_ratio must allow NULL"

    # Insert event with explicit None for decode energy
    ledger.record_optimization_event(OptimizationEvent(
        event_id="evt_null_energy",
        modeled_prefill_energy_j=2.5,
        modeled_decode_energy_j=None,
        modeled_total_energy_j=2.5,
    ))

    cur.execute("SELECT modeled_prefill_energy_j, modeled_decode_energy_j FROM optimization_events WHERE event_id = 'evt_null_energy'")
    row = cur.fetchone()
    assert row[0] == pytest.approx(2.5, abs=1e-4)
    assert row[1] is None, f"Expected SQL NULL, got {row[1]}"

    conn.close()
