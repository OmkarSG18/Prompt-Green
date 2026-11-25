"""
Regression tests for PromptGreen V2 telemetry persistence and History display corrections.
Verifies:
1. optimize_prompt_v2 creates exactly ONE row in prompt_records and ONE in optimization_events.
2. prompt_records.net_energy_wh stores net energy saved, not gross optimized prompt consumption.
3. get_recent_records() enriches prompt_records with modeled Joules via non-mutating LEFT JOIN.
4. Legacy records without event Joules preserve None (null) and are not coerced to 0.00 J.
5. Historical records with truncated prefix (like #518 'opt_f7ae') match and resolve modeled Joules.
6. Standalone record_optimization_event supports mirror_to_prompt_records toggle and preserves true net energy.

Runs strictly against an isolated temporary SQLite database. Production prompt_ledger.db is never touched.
"""

import os
import sqlite3
import pytest

from promptgreen.ledger.database import PromptLedger, OptimizationEvent
from promptgreen.api.server import (
    optimize_prompt_v2,
    get_v2_recent_ledger,
    V2OptimizeRequest,
)


@pytest.fixture(autouse=True)
def isolate_test_ledger(tmp_path, monkeypatch):
    """
    Ensures all tests run against an isolated temporary SQLite database,
    protecting prompt_ledger.db from any writes or modifications.
    """
    db_path = str(tmp_path / "test_telemetry_isolated.db")
    monkeypatch.setenv("PROMPTGREEN_DB_PATH", db_path)
    monkeypatch.setenv("PROMPTGREEN_SKIP_PREWARM", "1")
    yield db_path


def test_v2_optimize_single_record_in_prompt_records(isolate_test_ledger):
    """Verify that a single V2 optimization creates exactly ONE prompt_records row and ONE optimization_event."""
    req = V2OptimizeRequest(
        prompt="Could you please kindly write a detailed Python script to parse CSV files and extract headers?",
        mode="balanced",
        target_model="mid_tier",
        record_in_ledger=True,
    )
    resp = optimize_prompt_v2(req)
    assert resp["success"] is True

    db = PromptLedger(db_path=isolate_test_ledger)
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prompt_records")
        pr_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM optimization_events")
        oe_count = cur.fetchone()[0]

        cur.execute("SELECT id, commit_hash, net_energy_wh, carbon_delta_gco2_1k FROM prompt_records")
        pr_row = cur.fetchone()

        cur.execute("SELECT event_id, modeled_total_energy_j, modeled_carbon_gco2e FROM optimization_events")
        oe_row = cur.fetchone()

    # Crucial check: Exactly ONE row in each table, no duplicate mirror rows
    assert pr_count == 1, f"Expected exactly 1 prompt_records row, got {pr_count}"
    assert oe_count == 1, f"Expected exactly 1 optimization_events row, got {oe_count}"

    # Verify commit_hash is preserved as v2-api and record_id matches
    assert pr_row[1] == "v2-api", f"commit_hash must be 'v2-api', got '{pr_row[1]}'"
    assert resp["ledger"]["record_id"] == pr_row[0]


def test_net_energy_wh_is_savings_not_gross_consumption(isolate_test_ledger):
    """Verify that prompt_records.net_energy_wh stores net energy saved and NOT gross consumption."""
    req = V2OptimizeRequest(
        prompt="Please explain how convolutional neural networks perform feature extraction on image inputs.",
        mode="balanced",
        target_model="mid_tier",
        record_in_ledger=True,
    )
    resp = optimize_prompt_v2(req)
    assert resp["success"] is True

    thermo = resp["thermodynamics"]
    net_saved_wh = thermo["net_energy_saved_wh"]
    gross_opt_wh = thermo["energy_optimized_wh"]

    db = PromptLedger(db_path=isolate_test_ledger)
    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT net_energy_wh, commit_hash FROM prompt_records WHERE id = ?", (resp["ledger"]["record_id"],))
        stored_net_wh, commit_hash = cur.fetchone()

        cur.execute("SELECT modeled_total_energy_j FROM optimization_events ORDER BY rowid DESC LIMIT 1")
        event_total_j = cur.fetchone()[0]

    # Stored net energy must match net_energy_saved_wh
    assert stored_net_wh == pytest.approx(net_saved_wh, abs=1e-6)

    # Stored net energy must NOT equal gross optimized energy (or modeled_total_energy_j / 3600)
    gross_energy_from_j = event_total_j / 3600.0
    if abs(net_saved_wh - gross_energy_from_j) > 1e-4:
        assert stored_net_wh != pytest.approx(gross_energy_from_j, abs=1e-5), \
            "net_energy_wh must not be replaced by gross optimized prompt consumption!"


def test_get_recent_records_enriches_joules_from_events(isolate_test_ledger):
    """Verify that get_recent_records joins optimization_events and populates Joules fields."""
    req = V2OptimizeRequest(
        prompt="Can you provide a summary of distributed consensus algorithms like Raft and Paxos?",
        mode="balanced",
        target_model="mid_tier",
        record_in_ledger=True,
    )
    resp = optimize_prompt_v2(req)
    assert resp["success"] is True

    recent = get_v2_recent_ledger(limit=10)
    assert len(recent) == 1
    rec = recent[0]

    # Joules must be present and correctly populated
    assert "modeled_prefill_energy_j" in rec
    assert "modeled_decode_energy_j" in rec
    assert "modeled_total_energy_j" in rec

    assert rec["modeled_prefill_energy_j"] is not None
    assert rec["modeled_prefill_energy_j"] > 0.0
    assert rec["modeled_total_energy_j"] is not None
    assert rec["modeled_total_energy_j"] > 0.0
    # Decode energy is either modeled positive float (when output modeled) or None
    assert rec["modeled_decode_energy_j"] is None or rec["modeled_decode_energy_j"] > 0.0


def test_legacy_record_missing_joules_preserved_as_none(isolate_test_ledger):
    """Verify that legacy records without optimization_events retain None (null) and are not coerced to 0."""
    db = PromptLedger(db_path=isolate_test_ledger)

    # Insert a legacy record with no matching event
    db.record_v2_run(
        commit_hash="legacy_commit_123",
        author="legacy-user",
        team="Engineering",
        model_name="mid_tier",
        region="ILLUSTRATIVE_385",
        old_prompt="Legacy prompt test",
        new_prompt="Legacy prompt",
        input_token_delta=-5,
        predicted_output_token_delta=0.0,
        carbon_delta_gco2_1k=-1.25,
        monthly_carbon_delta_gco2=-37.5,
        status="PASS",
        net_energy_wh=0.0035,
    )

    recent = db.get_recent_records(limit=10)
    assert len(recent) == 1
    rec = recent[0]

    assert rec["commit_hash"] == "legacy_commit_123"
    assert rec["net_energy_wh"] == 0.0035
    # Modeled Joules must be None, NOT 0.0 or corrupted
    assert rec["modeled_prefill_energy_j"] is None
    assert rec["modeled_decode_energy_j"] is None
    assert rec["modeled_total_energy_j"] is None


def test_historical_record_518_prefix_matching(isolate_test_ledger):
    """Verify that historical records with 8-char commit_hash (like #518 'opt_f7ae') match event_id."""
    db = PromptLedger(db_path=isolate_test_ledger)

    # 1. Insert historical optimization event
    evt = OptimizationEvent(
        event_id="opt_f7aec9768b9e_1795537332",
        prompt_category="general",
        original_tokens=42,
        optimized_tokens=33,
        tokens_saved=9,
        modeled_prefill_energy_j=32.7888,
        modeled_decode_energy_j=None,
        modeled_total_energy_j=305.49888,
        modeled_carbon_gco2e=0.002258,
        net_energy_wh=0.005865,
    )
    db.record_optimization_event(evt, mirror_to_prompt_records=False)

    # 2. Insert historical prompt_record with truncated 8-char commit_hash as occurred in #518
    db.record_v2_run(
        commit_hash="opt_f7ae",
        author="api-user",
        team="Engineering",
        model_name="mid_tier",
        region="ILLUSTRATIVE_385",
        old_prompt="Historical prompt 518",
        new_prompt="Historical prompt",
        input_token_delta=-9,
        predicted_output_token_delta=0.0,
        carbon_delta_gco2_1k=-2.2580,
        monthly_carbon_delta_gco2=-67.74,
        status="PASS",
        net_energy_wh=0.005865,
    )

    recent = db.get_recent_records(limit=10)
    assert len(recent) == 1
    rec = recent[0]

    # Verify prefix matching successfully enriched historical record #518
    assert rec["commit_hash"] == "opt_f7ae"
    assert rec["modeled_prefill_energy_j"] == pytest.approx(32.7888, abs=1e-4)
    assert rec["modeled_total_energy_j"] == pytest.approx(305.49888, abs=1e-4)
    assert rec["modeled_decode_energy_j"] is None


def test_standalone_record_optimization_event_mirroring_control(isolate_test_ledger):
    """Verify mirror_to_prompt_records toggle on record_optimization_event."""
    db = PromptLedger(db_path=isolate_test_ledger)

    # 1. mirror_to_prompt_records=False: should NOT mirror
    evt1 = OptimizationEvent(
        event_id="opt_nomirror_001",
        original_tokens=20,
        optimized_tokens=15,
        tokens_saved=5,
        modeled_total_energy_j=10.0,
        modeled_carbon_gco2e=0.002,
        net_energy_wh=0.005,
    )
    db.record_optimization_event(evt1, mirror_to_prompt_records=False)

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prompt_records")
        assert cur.fetchone()[0] == 0, "No prompt_records should be created when mirror=False"

    # 2. mirror_to_prompt_records=True: should mirror with net_energy_wh, NOT modeled_total_energy_j / 3600
    evt2 = OptimizationEvent(
        event_id="opt_mirror_002",
        original_tokens=30,
        optimized_tokens=20,
        tokens_saved=10,
        modeled_total_energy_j=200.0,  # 200 / 3600 = 0.05555 Wh
        modeled_carbon_gco2e=0.004,
        net_energy_wh=0.008888,  # True net energy saved
    )
    db.record_optimization_event(evt2, mirror_to_prompt_records=True)

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prompt_records")
        assert cur.fetchone()[0] == 1, "Mirror=True must create exactly 1 prompt_records row"

        cur.execute("SELECT net_energy_wh FROM prompt_records WHERE commit_hash = 'opt_mirr'")
        net_wh = cur.fetchone()[0]
        assert net_wh == pytest.approx(0.008888, abs=1e-6)
        assert net_wh != pytest.approx(200.0 / 3600.0, abs=1e-4)
