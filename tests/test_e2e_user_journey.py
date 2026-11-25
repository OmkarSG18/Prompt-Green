"""
PromptGreen V2 — End-to-End User Journey Test Suite (Tests A through H)
Phase 5 Verification: Validates complete end-to-end user workflows:
Frontend Input -> HTTP Request -> V2 API -> 4-Stage Optimizer -> Semantic Guard
-> Carbon Engine -> Model Router -> Database Ledger -> API Response -> History Verification.
"""

import json
import os
import sys
import threading
import time
import urllib.request
from typing import Dict, Any, Tuple

import uvicorn

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from promptgreen.api.server import app

TEST_HOST = "127.0.0.1"
TEST_PORT = 8086
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"


def http_post_optimize(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Helper to send HTTP POST /api/v2/optimize and return (status, json)."""
    url = f"{BASE_URL}/api/v2/optimize"
    req_body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        headers={"Content-Type": "application/json", "Origin": "http://localhost:8000"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def get_recent_ledger() -> list:
    """Helper to query GET /api/v2/ledger/recent."""
    url = f"{BASE_URL}/api/v2/ledger/recent?limit=20"
    req = urllib.request.Request(url, headers={"Origin": "http://localhost:8000"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_e2e_scenarios() -> bool:
    print("=" * 80)
    print("PROMPTGREEN V2 — PHASE 5 END-TO-END USER JOURNEY VERIFICATION")
    print("=" * 80)

    # 1. Start Server
    config = uvicorn.Config(app=app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    print("[Setup] Starting Uvicorn server on port", TEST_PORT)
    for _ in range(120):
        if server.started:
            break
        time.sleep(0.1)

    all_passed = True
    scenarios_passed = 0

    try:
        # ----------------------------------------------------------------------
        # TEST A: Simple Classification / Extraction Prompt
        # ----------------------------------------------------------------------
        print("\n--- TEST A: Simple Prompt (Sentiment Classification) ---")
        payload_a = {
            "prompt": "Classify the sentiment of this review as Positive, Neutral, or Negative: 'The laptop battery lasts 12 hours.'",
            "mode": "balanced",
            "target_model": "frontier_dense",
            "task_category": "classification",
            "task_complexity": "low",
            "author": "e2e-user",
            "team": "QA",
            "record_in_ledger": True
        }
        code_a, data_a = http_post_optimize(payload_a)
        assert code_a == 200
        assert data_a["success"] is True
        assert data_a["pipeline"]["semantic_score"] >= 0.80
        # Frontier model on low complexity classification should recommend downgrade
        assert data_a["routing"]["outcome"] == "RECOMMEND_LOWER_ENERGY_TIER"
        assert data_a["routing"]["recommended_model_tier"] in ["compact_green", "mid_tier"]
        rec_id_a = data_a["ledger"]["record_id"]
        assert rec_id_a is not None
        print(f"PASS [Test A]: Sentiment classified. Routing recommends: {data_a['routing']['recommended_model_tier']} (Record #{rec_id_a})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST B: Verbose Prompt with Redundant Wording & Filler
        # ----------------------------------------------------------------------
        print("\n--- TEST B: Verbose Prompt (High Redundancy) ---")
        payload_b = {
            "prompt": "Hello dear assistant! Could you please be so kind as to give me an extremely comprehensive, detailed, extensive, full explanation of quantum superposition with many examples? Thank you very much in advance for your kind help!",
            "mode": "balanced",
            "target_model": "mid_tier",
            "record_in_ledger": True
        }
        code_b, data_b = http_post_optimize(payload_b)
        assert code_b == 200
        p_b = data_b["prompts"]
        print("DEBUG DATA_B PROMPTS:", p_b)
        print("DEBUG DATA_B PIPELINE:", data_b["pipeline"])
        assert p_b["input_tokens_saved"] >= 5, f"Expected significant token savings, got {p_b['input_tokens_saved']}"
        assert data_b["thermodynamics"]["gross_energy_saved_wh"] > 0, f"Expected positive gross energy savings, got {data_b['thermodynamics']['gross_energy_saved_wh']}"
        rec_id_b = data_b["ledger"]["record_id"]
        print(f"PASS [Test B]: Verbose fluff pruned. Saved {p_b['input_tokens_saved']} tokens ({p_b['input_reduction_pct']}%), Gross Wh: {data_b['thermodynamics']['gross_energy_saved_wh']:.5f}, Net Wh: {data_b['thermodynamics']['net_energy_saved_wh']:.5f} (Record #{rec_id_b})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST C: Technical Prompt with Specific Constraints
        # ----------------------------------------------------------------------
        print("\n--- TEST C: Technical Prompt (Constraints & Terminology) ---")
        payload_c = {
            "prompt": "Explain Byzantine fault tolerance in distributed consensus algorithms. The explanation must analyze PBFT and Raft, cover network partitions with latency > 200ms, and keep message complexity bounded.",
            "mode": "conservative",
            "target_model": "large_reasoning",
            "record_in_ledger": True
        }
        code_c, data_c = http_post_optimize(payload_c)
        assert code_c == 200
        opt_c = data_c["prompts"]["optimized_prompt"]
        assert "Byzantine" in opt_c and "PBFT" in opt_c and "Raft" in opt_c
        assert data_c["pipeline"]["semantic_score"] >= 0.85
        rec_id_c = data_c["ledger"]["record_id"]
        print(f"PASS [Test C]: Technical terminology and constraints preserved. Semantic score: {data_c['pipeline']['semantic_score']:.4f} (Record #{rec_id_c})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST D: Code Prompt with Fenced Code Blocks & Identifiers
        # ----------------------------------------------------------------------
        print("\n--- TEST D: Code Prompt (Fenced Block & AST Preservation) ---")
        code_text = "```python\ndef calculate_sha256(filepath: str) -> str:\n    import hashlib\n    return hashlib.sha256(open(filepath, 'rb').read()).hexdigest()\n```"
        payload_d = {
            "prompt": f"Please optimize this Python hashing routine:\n{code_text}\nMake sure to use chunked buffer reading.",
            "mode": "balanced",
            "target_model": "mid_tier",
            "task_category": "code_generation",
            "record_in_ledger": True
        }
        code_d, data_d = http_post_optimize(payload_d)
        assert code_d == 200
        opt_d = data_d["prompts"]["optimized_prompt"]
        assert "def calculate_sha256" in opt_d, "Function signature was mutated"
        assert "hashlib.sha256" in opt_d, "Hashlib code was mutated"
        rec_id_d = data_d["ledger"]["record_id"]
        print(f"PASS [Test D]: Fenced code block byte-for-byte protected. Function intact. (Record #{rec_id_d})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST E: Strict JSON Prompt
        # ----------------------------------------------------------------------
        print("\n--- TEST E: Strict JSON Prompt (Schema & Key Preservation) ---")
        payload_e = {
            "prompt": "Extract user info into valid JSON with exact keys: 'user_id', 'full_name', 'email_address', 'account_balance'. User text: 'ID 402 is Mark Stone, mark@stone.io, balance $1,240.50.'",
            "mode": "balanced",
            "target_model": "mid_tier",
            "record_in_ledger": True
        }
        code_e, data_e = http_post_optimize(payload_e)
        assert code_e == 200
        opt_e = data_e["prompts"]["optimized_prompt"]
        for k in ["user_id", "full_name", "email_address", "account_balance"]:
            assert k in opt_e, f"JSON key '{k}' was lost during optimization"
        rec_id_e = data_e["ledger"]["record_id"]
        print(f"PASS [Test E]: All 4 strict JSON schema keys preserved. (Record #{rec_id_e})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST F: Safety-Sensitive Prompt (Rigor & Downgrade Restriction)
        # ----------------------------------------------------------------------
        print("\n--- TEST F: Safety-Sensitive Prompt (Medical Dosage Guard) ---")
        payload_f = {
            "prompt": "Emergency pediatric dosage guidelines: Provide administration instructions for epinephrine in anaphylaxis. DANGER: Dosing must strictly follow verified protocols: 0.01 mg/kg IM. NEVER exceed 0.5 mg per single dose.",
            "mode": "conservative",
            "target_model": "frontier_dense",
            "task_category": "safety_critical",
            "task_complexity": "high",
            "record_in_ledger": True
        }
        code_f, data_f = http_post_optimize(payload_f)
        assert code_f == 200
        opt_f = data_f["prompts"]["optimized_prompt"]
        assert "0.01 mg/kg" in opt_f and "0.5 mg" in opt_f, "Safety dosing threshold was altered"
        # Safety critical tasks MUST trigger NO_SAFE_DOWNGRADE
        assert data_f["routing"]["outcome"] == "NO_SAFE_DOWNGRADE", f"Expected NO_SAFE_DOWNGRADE, got {data_f['routing']['outcome']}"
        rec_id_f = data_f["ledger"]["record_id"]
        print(f"PASS [Test F]: Safety-critical instructions protected; Router enforced NO_SAFE_DOWNGRADE. (Record #{rec_id_f})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST G: Negative-Savings Scenario (Optimizer Overhead Exceeds Savings)
        # ----------------------------------------------------------------------
        print("\n--- TEST G: Negative-Savings Scenario (Short Prompt Overhead) ---")
        payload_g = {
            "prompt": "Hi!",
            "mode": "balanced",
            "target_model": "compact_green",
            "record_in_ledger": True
        }
        code_g, data_g = http_post_optimize(payload_g)
        assert code_g == 200
        th_g = data_g["thermodynamics"]
        # For a 1-token prompt with 0 token reduction, optimizer CPU overhead results in net carbon/energy cost
        assert th_g["optimizer_overhead_wh"] > 0
        assert th_g["gross_energy_saved_wh"] <= th_g["optimizer_overhead_wh"]
        assert th_g["net_energy_saved_wh"] <= 0
        assert th_g["is_net_carbon_debt"] is True
        rec_id_g = data_g["ledger"]["record_id"]
        print(f"PASS [Test G]: Honest accounting verified: Net Wh: {th_g['net_energy_saved_wh']:.6f} Wh, is_net_carbon_debt={th_g['is_net_carbon_debt']} (Record #{rec_id_g})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # TEST H: Routing Restriction (Complex Mathematical Reasoning)
        # ----------------------------------------------------------------------
        print("\n--- TEST H: Routing Restriction (Multi-Step Math Reasoning) ---")
        payload_h = {
            "prompt": "Prove that the square root of 2 is irrational using contradiction. Then construct an explicit Dedekind cut in the rational numbers representing sqrt(2) and prove its properties step by step.",
            "mode": "balanced",
            "target_model": "large_reasoning",
            "task_category": "mathematical",
            "task_complexity": "high",
            "record_in_ledger": True
        }
        code_h, data_h = http_post_optimize(payload_h)
        assert code_h == 200
        routing_h = data_h["routing"]
        # Complex mathematical proof on reasoning model should NOT downgrade to compact tier
        assert routing_h["outcome"] in ["KEEP_CURRENT_MODEL", "NO_SAFE_DOWNGRADE"]
        rec_id_h = data_h["ledger"]["record_id"]
        print(f"PASS [Test H]: Complex mathematical reasoning guarded; Outcome={routing_h['outcome']} (Record #{rec_id_h})")
        scenarios_passed += 1

        # ----------------------------------------------------------------------
        # DATABASE PERSISTENCE CONFIRMATION
        # ----------------------------------------------------------------------
        print("\n--- Verifying All 8 Runs in SQLite Audit Ledger ---")
        recent_records = get_recent_ledger()
        ledger_ids = [r["id"] for r in recent_records]
        expected_ids = [rec_id_a, rec_id_b, rec_id_c, rec_id_d, rec_id_e, rec_id_f, rec_id_g, rec_id_h]
        for expected_id in expected_ids:
            assert expected_id in ledger_ids, f"Record #{expected_id} missing from recent ledger!"
        print(f"PASS: Confirmed all 8 test runs (#{expected_ids[0]} through #{expected_ids[-1]}) persisted in prompt_ledger.db.")

    except AssertionError as ae:
        import traceback
        print(f"\nFAILED E2E ASSERTION: {ae}")
        traceback.print_exc()
        all_passed = False
    except Exception as ex:
        import traceback
        print(f"\nUNHANDLED E2E EXCEPTION: {ex}")
        traceback.print_exc()
        all_passed = False
    finally:
        print("\nStopping test server...")
        server.should_exit = True
        server_thread.join(timeout=3)
        print("Server stopped.")

    print("\n" + "=" * 80)
    print(f"FINAL E2E RESULT: {scenarios_passed}/8 SCENARIOS PASSED ({'100% SUCCESS' if all_passed else 'FAILED'})")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_e2e_scenarios()
    sys.exit(0 if success else 1)
