"""
Read-Only Benchmark & Model Evaluation API Routes for PromptGreen V2.
Serves verified historical benchmark results (IGE-1000, LLMLingua-2 neural benchmark,
and Stage 3 Ollama model comparison) without modifying any datasets or databases.
"""

import csv
import io
import json
import os
from functools import lru_cache
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api/v2/benchmarks", tags=["benchmarks"])

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IGE_BALANCED_DIR = os.path.join(PROJECT_ROOT, "results", "ige_1000", "balanced")
NEURAL_BENCHMARK_PATH = os.path.join(
    PROJECT_ROOT, "results", "master_v2", "neural_compression_benchmark.json"
)

CANONICAL_CATEGORIES: List[str] = [
    "Code generation and debugging",
    "RAG and information retrieval",
    "Analytical reasoning",
    "Summarization and information extraction",
    "CI/CD and developer workflows",
    "Data science and machine learning",
    "Structured output and formatting constraints",
    "General technical instructions",
    "Creative writing and content generation",
    "Conversational and multilingual assistance",
    "Tool-use and agentic workflows",
    "Safety-sensitive and professional applications",
]

VALID_OUTCOMES = {
    "all",
    "accepted",
    "rollback",
    "positive_savings",
    "zero_savings",
    "carbon_debt",
}

VALID_SORT_FIELDS = {
    "prompt_id",
    "token_reduction",
    "token_reduction_pct",
    "semantic_similarity",
    "total_latency_ms",
    "net_energy_saved_wh",
}


@lru_cache(maxsize=1)
def _load_ige_summary() -> Dict[str, Any]:
    path = os.path.join(IGE_BALANCED_DIR, "summary.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("balanced", {})


@lru_cache(maxsize=1)
def _load_ige_category_summary() -> Dict[str, Any]:
    path = os.path.join(IGE_BALANCED_DIR, "category_summary.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("balanced", {})


@lru_cache(maxsize=1)
def _load_ige_raw_prompts() -> List[Dict[str, Any]]:
    path = os.path.join(IGE_BALANCED_DIR, "raw_results.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("balanced", [])


@lru_cache(maxsize=1)
def _load_neural_benchmark() -> Dict[str, Any]:
    with open(NEURAL_BENCHMARK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_category_rows() -> List[Dict[str, Any]]:
    raw = _load_ige_raw_prompts()
    cat_sum = _load_ige_category_summary()
    grouped: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CANONICAL_CATEGORIES}
    for rec in raw:
        cat = rec.get("category", "")
        grouped.setdefault(cat, []).append(rec)

    rows: List[Dict[str, Any]] = []
    for cat in CANONICAL_CATEGORIES:
        items = grouped.get(cat, [])
        n = len(items)
        cs = cat_sum.get(cat, {})
        accepted = sum(1 for x in items if x.get("accepted"))
        rollbacks = n - accepted
        total_tokens_saved = sum(int(x.get("token_reduction", 0)) for x in items)
        positive_savings = sum(1 for x in items if int(x.get("token_reduction", 0)) > 0)
        debt_cases = sum(1 for x in items if x.get("is_net_carbon_debt"))
        violations = sum(len(x.get("preservation_violations") or []) for x in items)
        total_co2 = round(sum(float(x.get("net_carbon_abated_gco2", 0.0)) for x in items), 4)
        total_water = round(sum(float(x.get("net_water_saved_ml", 0.0)) for x in items), 4)

        rows.append(
            {
                "category": cat,
                "prompt_count": cs.get("prompt_count", n),
                "accepted_count": cs.get("accepted_count", accepted),
                "rollback_count": rollbacks,
                "acceptance_rate_pct": cs.get(
                    "acceptance_rate_pct", round((accepted / n * 100.0) if n else 0.0, 2)
                ),
                "positive_savings_count": positive_savings,
                "total_tokens_saved": total_tokens_saved,
                "mean_token_reduction_tokens": cs.get(
                    "mean_token_reduction_tokens",
                    round(total_tokens_saved / n, 2) if n else 0.0,
                ),
                "mean_token_reduction_pct": cs.get("mean_token_reduction_pct", 0.0),
                "mean_semantic_similarity": cs.get("mean_semantic_similarity", 0.0),
                "min_semantic_similarity": cs.get("min_semantic_similarity", 0.0),
                "mean_latency_ms": cs.get("mean_latency_ms", 0.0),
                "total_net_energy_saved_wh": cs.get("total_net_energy_saved_wh", 0.0),
                "total_net_carbon_abated_gco2": total_co2,
                "total_net_water_saved_ml": total_water,
                "net_carbon_debt_count": debt_cases,
                "preservation_violations_count": violations,
                "limitations_note": (
                    f"100% deterministic Stage 2/3 fallback; {rollbacks} rollback(s), "
                    f"{debt_cases} net carbon debt case(s)."
                ),
            }
        )
    return rows


def _filter_prompts(
    category: str,
    outcome: str,
    search: str,
) -> List[Dict[str, Any]]:
    if category != "all" and category not in CANONICAL_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    if outcome not in VALID_OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Invalid outcome filter: {outcome}")

    items = _load_ige_raw_prompts()
    if category != "all":
        items = [x for x in items if x.get("category") == category]

    if outcome == "accepted":
        items = [x for x in items if x.get("accepted")]
    elif outcome == "rollback":
        items = [x for x in items if x.get("rollback_occurred")]
    elif outcome == "positive_savings":
        items = [x for x in items if int(x.get("token_reduction", 0)) > 0]
    elif outcome == "zero_savings":
        items = [x for x in items if int(x.get("token_reduction", 0)) == 0]
    elif outcome == "carbon_debt":
        items = [x for x in items if x.get("is_net_carbon_debt")]

    q = (search or "").strip().lower()
    if q:
        items = [
            x
            for x in items
            if q in str(x.get("prompt_id", "")).lower()
            or q in str(x.get("original_prompt", "")).lower()
            or q in str(x.get("optimized_prompt", "")).lower()
        ]
    return items


@router.get("/ige-1000/summary")
def get_ige_1000_summary():
    """Returns authoritative IGE-1000 Balanced summary, 12 category metrics, and disclosures."""
    summary = _load_ige_summary()
    raw = _load_ige_raw_prompts()
    total_co2 = round(sum(float(x.get("net_carbon_abated_gco2", 0.0)) for x in raw), 4)
    total_water = round(sum(float(x.get("net_water_saved_ml", 0.0)) for x in raw), 4)
    pos_count = sum(1 for x in raw if int(x.get("token_reduction", 0)) > 0)

    enriched_summary = dict(summary)
    enriched_summary["total_net_carbon_abated_gco2"] = total_co2
    enriched_summary["total_net_water_saved_ml"] = total_water
    enriched_summary["positive_savings_count"] = pos_count
    enriched_summary["positive_savings_rate_pct"] = round(pos_count / len(raw) * 100.0, 2) if raw else 0.0

    return {
        "benchmark_id": "ige_1000_balanced",
        "mode": "balanced",
        "summary": enriched_summary,
        "categories": _build_category_rows(),
        "disclaimers": {
            "execution_path": (
                "IGE-1000 Balanced executed on CPU with 100% Stage 2 deterministic fallback "
                "and 100% Stage 3 deterministic fallback. It evaluates the deterministic pipeline, "
                "not live LLMLingua-2 or Ollama SLM inference."
            ),
            "energy_carbon_water": (
                "Energy (Wh), carbon (gCO2e, ILLUSTRATIVE_385 = 385 gCO2e/kWh), and water "
                "(mL, 1.8 mL/Wh WUE) are mathematical model estimates (PUE=1.15, 35.0W nominal "
                "CPU overhead assumption), not physical watt-meter measurements."
            ),
        },
    }


@router.get("/ige-1000/prompts")
def get_ige_1000_prompts(
    category: str = Query("all"),
    outcome: str = Query("all"),
    search: str = Query("", max_length=120),
    sort_by: str = Query("prompt_id"),
    sort_dir: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """Returns server-side filtered, sorted, and paginated IGE-1000 prompt records."""
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")

    filtered = _filter_prompts(category=category, outcome=outcome, search=search)
    reverse = sort_dir == "desc"

    def _sort_key(rec: Dict[str, Any]):
        val = rec.get(sort_by)
        if sort_by == "prompt_id":
            return str(val or "")
        return float(val if val is not None else 0.0)

    filtered.sort(key=_sort_key, reverse=reverse)

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    safe_page = min(page, total_pages)
    start = (safe_page - 1) * page_size
    end = start + page_size

    return {
        "total": total,
        "page": safe_page,
        "page_size": page_size,
        "total_pages": total_pages,
        "items": filtered[start:end],
    }


@router.get("/ige-1000/export")
def export_ige_1000_prompts(
    format: str = Query("csv", pattern="^(csv|json)$"),
    category: str = Query("all"),
    outcome: str = Query("all"),
    search: str = Query("", max_length=120),
):
    """Exports filtered or complete IGE-1000 benchmark results as CSV or JSON."""
    items = _filter_prompts(category=category, outcome=outcome, search=search)
    slug = "all" if category == "all" else category.lower().replace(" ", "_").replace("/", "_")

    if format == "json":
        payload = json.dumps(
            {"benchmark": "ige_1000_balanced", "count": len(items), "records": items},
            indent=2,
        )
        return Response(
            content=payload,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="promptgreen_ige_1000_{slug}.json"'
            },
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "prompt_id",
            "category",
            "difficulty",
            "original_token_count",
            "optimized_token_count",
            "token_reduction",
            "token_reduction_pct",
            "semantic_similarity",
            "accepted",
            "rollback_occurred",
            "rollback_reason",
            "total_latency_ms",
            "stage_1_ms",
            "stage_2_ms",
            "stage_3_ms",
            "stage_4_ms",
            "stage_2_method",
            "stage_3_method",
            "net_energy_saved_wh",
            "net_carbon_abated_gco2",
            "net_water_saved_ml",
            "is_net_carbon_debt",
            "original_prompt",
            "optimized_prompt",
        ]
    )
    for rec in items:
        st = rec.get("stage_latencies_ms") or {}
        writer.writerow(
            [
                rec.get("prompt_id"),
                rec.get("category"),
                rec.get("difficulty"),
                rec.get("original_token_count"),
                rec.get("optimized_token_count"),
                rec.get("token_reduction"),
                rec.get("token_reduction_pct"),
                rec.get("semantic_similarity"),
                rec.get("accepted"),
                rec.get("rollback_occurred"),
                rec.get("rollback_reason") or "",
                rec.get("total_latency_ms"),
                st.get("stage_1_ms", ""),
                st.get("stage_2_ms", ""),
                st.get("stage_3_ms", ""),
                st.get("stage_4_ms", ""),
                rec.get("stage_2_method"),
                rec.get("stage_3_method"),
                rec.get("net_energy_saved_wh"),
                rec.get("net_carbon_abated_gco2"),
                rec.get("net_water_saved_ml"),
                rec.get("is_net_carbon_debt"),
                rec.get("original_prompt"),
                rec.get("optimized_prompt"),
            ]
        )

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="promptgreen_ige_1000_{slug}.csv"'
        },
    )


@router.get("/model-evaluation")
def get_model_evaluation_data():
    """Returns verified Stage 2 LLMLingua-2, Stage 3 Ollama, and V1 historical evaluation data."""
    neural = _load_neural_benchmark()
    return {
        "stage_3_ollama": {
            "source": "docs/DAY1_STAGE3_OLLAMA_MODEL_COMPARISON.md",
            "test_date": "November 21, 2026",
            "environment": "Windows 11, Intel Core i7-10610U CPU @ 1.80GHz (4c/8t), 16 GB RAM, CPU-first",
            "invocations_per_model": 13,
            "scenarios_count": 7,
            "models": [
                {
                    "id": "qwen2.5:0.5b",
                    "name": "Qwen 2.5 0.5B",
                    "parameters": "0.49B",
                    "disk_footprint": "397 MB",
                    "disk_mb": 397,
                    "invocations": 13,
                    "completed": 13,
                    "completion_rate_pct": 100.0,
                    "timeouts": 0,
                    "validator_accepted": 7,
                    "acceptance_rate_pct": 53.8,
                    "acceptance_completed_pct": 53.8,
                    "fallback_triggered": 6,
                    "fallback_rate_pct": 46.2,
                    "mean_latency_ms": 4531.2,
                    "role": "Selected optional Stage 3 neural shaper (guarded by deterministic validator)",
                    "weaknesses": "Conversational answers instead of prompt shaping, token expansion, 1 observed dropped negation ('never' on P4).",
                },
                {
                    "id": "gemma3:4b",
                    "name": "Gemma 3 4B",
                    "parameters": "4.0B",
                    "disk_footprint": "3.4 GB",
                    "disk_mb": 3481,
                    "invocations": 13,
                    "completed": 6,
                    "completion_rate_pct": 46.2,
                    "timeouts": 7,
                    "validator_accepted": 5,
                    "acceptance_rate_pct": 38.5,
                    "acceptance_completed_pct": 83.3,
                    "fallback_triggered": 8,
                    "fallback_rate_pct": 61.5,
                    "mean_latency_ms": 13797.9,
                    "role": "Tested alternative — rejected for CPU latency & 53.8% timeout rate",
                    "weaknesses": "7/13 timeouts (>30s threshold); slow CPU generation (13,797.9 ms mean).",
                },
                {
                    "id": "qwen3:8b",
                    "name": "Qwen 3 8B",
                    "parameters": "8.0B",
                    "disk_footprint": "5.2 GB",
                    "disk_mb": 5325,
                    "invocations": 13,
                    "completed": 0,
                    "completion_rate_pct": 0.0,
                    "timeouts": 13,
                    "validator_accepted": 0,
                    "acceptance_rate_pct": 0.0,
                    "acceptance_completed_pct": None,
                    "fallback_triggered": 13,
                    "fallback_rate_pct": 100.0,
                    "mean_latency_ms": None,
                    "unbounded_probe_ms": 58870.0,
                    "role": "Tested alternative — unviable on CPU within 25s timeout",
                    "weaknesses": "0/13 completed within 25s timeout; unbounded CPU probe took 58.87s.",
                },
                {
                    "id": "deterministic",
                    "name": "Deterministic Rule Engine",
                    "parameters": "Rule-based",
                    "disk_footprint": "~0 MB",
                    "disk_mb": 0,
                    "invocations": 13,
                    "completed": 13,
                    "completion_rate_pct": 100.0,
                    "timeouts": 0,
                    "validator_accepted": 13,
                    "acceptance_rate_pct": 100.0,
                    "acceptance_completed_pct": 100.0,
                    "fallback_triggered": 0,
                    "fallback_rate_pct": 0.0,
                    "mean_latency_ms": 0.25,
                    "role": "Reliable default & safety fallback engine",
                    "weaknesses": "100% acceptance applies strictly to the 7 tested scenarios/rules; does not perform open-ended generative rewriting.",
                },
            ],
            "scenarios": [
                {
                    "pid": "P1",
                    "category": "Simple explanation",
                    "prompt": "Explain the concept of database indexing in simple terms.",
                    "qwen25_05b": "Rejected (3,650.7 ms) — generated 439-char conversational answer",
                    "gemma3_4b": "Rejected (30,371.9 ms) — generated 1,139-char essay",
                    "qwen3_8b": "Timeout (27,086.7 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P2",
                    "category": "Comparison table",
                    "prompt": "Compare PostgreSQL and MongoDB in a table.",
                    "qwen25_05b": "Accepted (2,307.3 ms) — verbatim echo",
                    "gemma3_4b": "Timeout (32,083.9 ms)",
                    "qwen3_8b": "Timeout (27,062.0 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P3",
                    "category": "JSON-only with exact keys",
                    "prompt": "Return only valid JSON with keys hostname, ip_address, port and status.",
                    "qwen25_05b": "Accepted (2,988.5 ms)",
                    "gemma3_4b": "Accepted (11,414.6 ms)",
                    "qwen3_8b": "Timeout (27,066.1 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P4",
                    "category": "Negative instructions",
                    "prompt": "Explain how to configure nginx reverse proxy. Do not include Apache configuration and never expose port 8080 without SSL.",
                    "qwen25_05b": "Rejected (7,250.6 ms) — dropped negation 'never'",
                    "gemma3_4b": "Timeout (32,079.2 ms)",
                    "qwen3_8b": "Timeout (27,050.0 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P5",
                    "category": "Numerical constraints",
                    "prompt": "Set max_connections to 100, keepalive_timeout to 65s, and buffer size under 16mb.",
                    "qwen25_05b": "Accepted (3,028.1 ms)",
                    "gemma3_4b": "Accepted (12,303.1 ms)",
                    "qwen3_8b": "Timeout (27,065.6 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P6",
                    "category": "Technical identifiers & URLs",
                    "prompt": "Inspect https://api.example.com/v1/health and verify /var/log/syslog for ERR_CONNECTION_REFUSED.",
                    "qwen25_05b": "Accepted (2,646.1 ms)",
                    "gemma3_4b": "Accepted (9,951.5 ms)",
                    "qwen3_8b": "Timeout (27,053.3 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
                {
                    "pid": "P7",
                    "category": "Multiple output requirements",
                    "prompt": "Explain microservices architecture. Provide 3 key benefits in a numbered list, compare with monolithic architecture in a table, and return code only for a sample Dockerfile.",
                    "qwen25_05b": "Rejected (7,118.1 ms) — generated 1,317-char essay & Dockerfile",
                    "gemma3_4b": "Timeout (32,075.3 ms)",
                    "qwen3_8b": "Timeout (27,035.6 ms)",
                    "deterministic": "Accepted (<0.7 ms)",
                },
            ],
        },
        "stage_2_llmlingua2": {
            "source": "docs/LLMLINGUA2_INTEGRATION_REPORT.md & results/master_v2/neural_compression_benchmark.json",
            "model_name": "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            "architecture": "Distilled multilingual BERT/XLM-RoBERTa token classification head (extractive token selection)",
            "disk_footprint_mb": 540.3,
            "ram_resident_gb": 1.15,
            "eval_corpus_size": 10,
            "neural_execution_rate_pct": 100.0,
            "protected_preservation_pct": 100.0,
            "mean_semantic_similarity": "0.964 ± 0.018",
            "mean_warm_latency_ms": "38.0 ± 14.2 ms",
            "records": neural.get("records", []),
        },
        "v1_historical": {
            "label": "V1 Historical Model / Predictor Evaluation (Not V2 Stage 2/3)",
            "models": ["Llama-3 8B", "Mistral 7B", "Phi-3 3.8B"],
            "corpus": "Historical 50-pair benchmark evaluation",
            "reported_accuracy": "88% directional accuracy reported in V1 predictor (>85% in FINAL_REPORT.md)",
        },
        "not_tested_alternatives": [
            "LongLLMLingua (NOT TESTED IN THIS PROJECT — candidate for future comparative evaluation)",
            "Selective Context (NOT TESTED IN THIS PROJECT — candidate for future comparative evaluation)",
            "Commercial cloud compression/rewriting APIs (out of scope for zero-budget CPU-first architecture)",
        ],
    }
