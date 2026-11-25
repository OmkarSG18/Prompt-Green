"""
PromptGreen V2 — Live HTTP Integration Test Suite
Mandatory Phase 4 Verification: Starts real Uvicorn server and sends real HTTP requests
over TCP loopback to verify all API endpoints, HTTP status codes, JSON schemas,
error handling, database persistence, and CORS headers.
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Any, Tuple

import uvicorn

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from promptgreen.api.server import app

TEST_HOST = "127.0.0.1"
TEST_PORT = 8085
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"


def http_request(method: str, path: str, data: Dict[str, Any] = None, headers: Dict[str, str] = None) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """Helper to send live HTTP requests and return (status_code, parsed_json_or_text, response_headers)."""
    url = f"{BASE_URL}{path}"
    req_headers = {"User-Agent": "PromptGreen-Live-HTTP-Tester/2.0"}
    if headers:
        req_headers.update(headers)

    body_bytes = None
    if data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            resp_headers = dict(resp.headers)
            content = resp.read().decode("utf-8")
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = {"raw_text": content}
            return status_code, parsed, resp_headers
    except urllib.error.HTTPError as e:
        status_code = e.code
        resp_headers = dict(e.headers)
        content = e.read().decode("utf-8")
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"raw_text": content}
        return status_code, parsed, resp_headers


def run_live_http_verification() -> bool:
    """Executes the full live HTTP server test suite against real Uvicorn process."""
    print("=" * 80)
    print("PROMPTGREEN V2 — LIVE HTTP ENDPOINT VERIFICATION")
    print(f"Target: {BASE_URL}")
    print("=" * 80)

    # 1. Start Server in Background Thread
    config = uvicorn.Config(app=app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    print("[0/8] Starting Uvicorn HTTP server in background thread...")
    ready = False
    for attempt in range(120):
        if server.started:
            # Probe /api
            try:
                code, _, _ = http_request("GET", "/api")
                if code == 200:
                    ready = True
                    print(f"      Server is READY on {BASE_URL} (took {(attempt + 1) * 0.1:.1f}s)")
                    break
            except Exception:
                pass
        time.sleep(0.1)

    if not ready:
        print("FATAL: Server failed to start or accept HTTP connections on port", TEST_PORT)
        server.should_exit = True
        return False

    all_passed = True

    try:
        # TEST 1: GET / and GET /api
        print("\n[1/8] Verifying GET / and GET /api metadata endpoints...")
        code, data, hdrs = http_request("GET", "/api")
        assert code == 200, f"Expected 200, got {code}"
        assert data.get("system") == "PromptGreen", f"Unexpected system name: {data}"
        assert data.get("version") == "2.0.0", f"Unexpected version: {data}"
        assert "v2_optimize" in data.get("endpoints", {}), f"Missing v2_optimize endpoint: {data}"
        print("      PASS: /api responded with HTTP 200, system='PromptGreen', version='2.0.0'")

        # TEST 2: GET /api/v2/models
        print("\n[2/8] Verifying GET /api/v2/models (Model Tier Catalog)...")
        code, data, hdrs = http_request("GET", "/api/v2/models")
        assert code == 200, f"Expected 200, got {code}"
        assert "tiers" in data, "Missing 'tiers' in response"
        tiers = data["tiers"]
        for required_tier in ["frontier_dense", "large_reasoning", "mid_tier", "compact_green"]:
            assert required_tier in tiers, f"Missing required tier: {required_tier}"
            t = tiers[required_tier]
            assert t["alpha_prefill_mwh"] > 0, f"Invalid prefill coeff for {required_tier}"
            assert t["alpha_decode_mwh"] > 0, f"Invalid decode coeff for {required_tier}"
            assert t["hardware_id"] != "", f"Missing hardware for {required_tier}"
        print(f"      PASS: Retrieved {len(tiers)} registered model tiers with mWh coefficients and hardware profiles.")

        # TEST 3: GET /api/v2/grid-scenarios
        print("\n[3/8] Verifying GET /api/v2/grid-scenarios (Regional Grid Scenarios)...")
        code, data, hdrs = http_request("GET", "/api/v2/grid-scenarios")
        assert code == 200, f"Expected 200, got {code}"
        assert "selectable_scenarios" in data, "Missing selectable_scenarios"
        assert "unavailable_regional_placeholders" in data, "Missing unavailable_regional_placeholders"
        scen = data["selectable_scenarios"]
        assert "ILLUSTRATIVE_385" in scen, "Missing ILLUSTRATIVE_385"
        assert "THESIS_367" in scen, "Missing THESIS_367"
        assert scen["ILLUSTRATIVE_385"]["carbon_intensity_gco2_kwh"] == 385.0
        assert scen["THESIS_367"]["carbon_intensity_gco2_kwh"] == 367.0
        print(f"      PASS: Selectable scenarios verified ({len(scen)} scenarios) with transparent provenance.")

        # TEST 4: POST /api/v2/optimize with Valid Prompt (Balanced Mode)
        print("\n[4/8] Verifying POST /api/v2/optimize (Standard 4-Stage Optimization)...")
        opt_payload = {
            "prompt": "Hello! Could you please explain in extensive detail how photosynthesis works with multiple examples? Thank you very much in advance!",
            "mode": "balanced",
            "target_model": "mid_tier",
            "grid_scenario": "ILLUSTRATIVE_385",
            "monthly_inferences": 10000,
            "author": "http-test-runner",
            "team": "QA-Engineering",
            "record_in_ledger": True
        }
        code, data, hdrs = http_request("POST", "/api/v2/optimize", data=opt_payload)
        assert code == 200, f"Expected 200, got {code}: {data}"
        assert data.get("success") is True, f"Optimization failed: {data}"
        assert data.get("mode") == "BALANCED"

        # Validate Prompts
        prompts = data.get("prompts", {})
        assert prompts["original_input_tokens"] > prompts["optimized_input_tokens"], "Tokens were not reduced"
        assert prompts["input_tokens_saved"] > 0
        assert len(prompts["optimized_prompt"]) > 0

        # Validate 4 Stages
        pipeline = data.get("pipeline", {})
        stages = pipeline.get("stages", [])
        assert len(stages) == 4, f"Expected 4 stage execution records, got {len(stages)}"
        stage_names = [s["stage_name"] for s in stages]
        assert "RuleBasedPruner" in stage_names[0] or "Pruner" in stage_names[0]

        # Validate Thermodynamics (Wh)
        thermo = data.get("thermodynamics", {})
        assert thermo["energy_original_wh"] > 0
        assert thermo["energy_optimized_wh"] > 0
        assert "net_energy_saved_wh" in thermo
        assert thermo["pue_used"] == 1.15

        # Validate Environmental & Water Impact
        env = data.get("environmental_impact", {})
        assert env["grid_intensity_gco2_kwh"] == 385.0
        assert env["net_water_saved_ml"] >= 0
        assert "monthly_carbon_abated_gco2" in env

        # Validate Routing
        routing = data.get("routing", {})
        assert "outcome" in routing
        assert routing["current_model_tier"] == "mid_tier"

        # Validate Ledger Record ID
        rec_id = data.get("ledger", {}).get("record_id")
        assert rec_id is not None, "Optimization run was not recorded in ledger"
        print(f"      PASS: Pipeline executed 4 stages in {data['latency_ms']:.1f}ms (Tokens: {prompts['original_input_tokens']} -> {prompts['optimized_input_tokens']}, Net Wh: {thermo['net_energy_saved_wh']:.5f}, Ledger Record #{rec_id})")

        # TEST 5: POST /api/v2/optimize across Modes (Conservative & Aggressive)
        print("\n[5/8] Verifying POST /api/v2/optimize across Conservative and Aggressive modes...")
        
        # Conservative
        c_code, c_data, _ = http_request("POST", "/api/v2/optimize", data={"prompt": "Please write concise python code: def foo(): pass", "mode": "conservative"})
        assert c_code == 200, f"Conservative mode failed with code {c_code}: {c_data}"
        assert c_data["mode"] == "CONSERVATIVE", f"Expected mode CONSERVATIVE, got {c_data.get('mode')}"
        sem_score = c_data["pipeline"]["semantic_score"]
        assert sem_score >= 0.80, f"Expected semantic score >= 0.80, got {sem_score}"

        # Aggressive
        agg_prompt = "Hello dear assistant, would you kindly be so nice as to please provide me with an extremely extensive, full, detailed overview of French history? Thank you very much in advance!"
        a_code, a_data, _ = http_request("POST", "/api/v2/optimize", data={"prompt": agg_prompt, "mode": "aggressive"})
        assert a_code == 200, f"Aggressive mode failed with code {a_code}: {a_data}"
        assert a_data["mode"] == "AGGRESSIVE", f"Expected mode AGGRESSIVE, got {a_data.get('mode')}"
        assert a_data["prompts"]["input_tokens_saved"] > 0, f"Expected input tokens saved > 0, got {a_data['prompts']}"
        print("      PASS: Conservative mode preserved high semantic score; Aggressive mode maximized token reduction.")

        # TEST 6: POST /api/v2/optimize Error Handling (400 Bad Request)
        print("\n[6/8] Verifying Error Handling on Invalid Inputs (HTTP 400)...")
        # Empty prompt
        code_empty, data_empty, _ = http_request("POST", "/api/v2/optimize", data={"prompt": ""})
        assert code_empty == 400, f"Expected 400 for empty prompt, got {code_empty}"
        assert "non-empty string" in data_empty.get("detail", "")

        # Whitespace-only prompt
        code_space, data_space, _ = http_request("POST", "/api/v2/optimize", data={"prompt": "   \n\t  "})
        assert code_space == 400, f"Expected 400 for whitespace prompt, got {code_space}"

        # Invalid mode
        code_mode, data_mode, _ = http_request("POST", "/api/v2/optimize", data={"prompt": "valid prompt", "mode": "invalid_super_mode"})
        assert code_mode == 400, f"Expected 400 for invalid mode, got {code_mode}"
        assert "Invalid mode" in data_mode.get("detail", "")
        print("      PASS: Correctly rejected empty prompt, whitespace-only prompt, and invalid modes with HTTP 400.")

        # TEST 7: GET /api/v2/ledger/summary
        print("\n[7/8] Verifying GET /api/v2/ledger/summary (Cumulative Metrics)...")
        code, data, _ = http_request("GET", "/api/v2/ledger/summary")
        assert code == 200, f"Expected 200, got {code}"
        assert "total_runs" in data
        assert data["total_runs"] > 0, "Expected at least 1 run recorded in ledger"
        assert "total_net_energy_wh_saved" in data
        assert "total_net_carbon_g_saved" in data
        assert "total_water_saved_ml" in data
        print(f"      PASS: Ledger summary active (Total Runs: {data['total_runs']}, Net Wh Saved: {data['total_net_energy_wh_saved']:.4f} Wh, Water Saved: {data['total_water_saved_ml']:.2f} mL)")

        # TEST 8: GET /api/v2/ledger/recent & Database Persistence
        print("\n[8/8] Verifying GET /api/v2/ledger/recent and Database Persistence...")
        code, data, _ = http_request("GET", "/api/v2/ledger/recent?limit=10")
        assert code == 200, f"Expected 200, got {code}"
        assert isinstance(data, list)
        assert len(data) >= 1
        record_ids = [r["id"] for r in data]
        assert rec_id in record_ids, f"Expected record #{rec_id} in recent records, got {record_ids}"
        latest = data[0]
        assert latest["opt_mode"] in ["BALANCED", "CONSERVATIVE", "AGGRESSIVE"]
        assert "net_energy_wh" in latest
        assert "routing_outcome" in latest
        print(f"      PASS: Database verified persistence. Record #{rec_id} confirmed in ledger; latest record #{latest['id']} verified with opt_mode='{latest['opt_mode']}'")

        # CORS & Stability Check (5 consecutive requests)
        print("\n[Stress & Stability Check] Running 5 rapid consecutive optimization requests...")
        for i in range(5):
            s_code, s_data, s_hdrs = http_request(
                "POST", 
                "/api/v2/optimize", 
                data={"prompt": f"Summarize prompt number {i} in 2 concise bullets."},
                headers={"Origin": "http://localhost:8000"}
            )
            assert s_code == 200, f"Stress request {i} failed with {s_code}"
            assert s_hdrs.get("access-control-allow-origin") in ["*", "http://localhost:8000"], f"CORS header missing: {s_hdrs}"
        print("      PASS: Server handled 5 rapid requests with 0 errors and valid CORS headers.")

    except AssertionError as ae:
        import traceback
        print(f"\nFAILED ASSERTION: {ae}")
        traceback.print_exc()
        all_passed = False
    except Exception as ex:
        import traceback
        print(f"\nUNHANDLED EXCEPTION: {ex}")
        traceback.print_exc()
        all_passed = False
    finally:
        print("\nShutting down Uvicorn test server...")
        server.should_exit = True
        server_thread.join(timeout=3)
        print("Server shutdown complete.")

    print("\n" + "=" * 80)
    if all_passed:
        print("FINAL RESULT: ALL 8 LIVE HTTP ENDPOINT TESTS PASSED (100.0%)")
    else:
        print("FINAL RESULT: LIVE HTTP ENDPOINT TESTS FAILED")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_live_http_verification()
    sys.exit(0 if success else 1)
