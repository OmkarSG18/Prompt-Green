"""
PromptGreen v2.0 - End-to-End Pipeline Performance Benchmark (Stage 5)
CPU-First Empirical Measurement on Intel Core i7-10610U (4 Cores / 8 Threads, 32 GB RAM).

Measures:
- Original token count vs. Final token count
- Net input token reduction and percentage
- Stage-level latencies (Stage 1, Stage 2, Stage 3, Stage 4)
- Total pipeline latency (ms)
- Semantic cosine similarity score (all-MiniLM-L6-v2)
- Multi-chunk coverage metrics
- Number of adaptive relaxation retries
- Stage fallback usage
- Acceptance verdict (Accepted vs. Rolled back)

Strictly separates empirically measured values from modeled estimates.
Zero GPU acceleration claims.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

from promptgreen.optimizer.compressor import CompressionResult, LLMLinguaCompressor
from promptgreen.optimizer.pipeline import PipelineConfig, PipelineResult, PromptGreenPipeline
from promptgreen.optimizer.semantic_guard import LocalMiniLMEmbedder


# Benchmark prompt suite across multiple length profiles
BENCHMARK_PROMPTS: List[Dict[str, str]] = [
    {
        "category": "Short",
        "description": "Simple technical question with polite conversational boilerplate",
        "prompt": (
            "Could you please kindly explain how database connection pooling works in detail? "
            "Thank you so much in advance!"
        ),
    },
    {
        "category": "Medium",
        "description": "Architecture task with discourse fillers and technical constraints",
        "prompt": (
            "Hello dear AI assistant! In order to ensure high reliability across our microservices architecture, "
            "it is important to note that all inter-service requests must include a correlation ID header. "
            "Due to the fact that network latency can vary, requests must time out after 500ms. "
            "Please summarize key recommendations for circuit breaking. Hope this helps, thanks!"
        ),
    },
    {
        "category": "Long",
        "description": "Multi-paragraph enterprise specification with JSON schema and URL",
        "prompt": (
            "Please kindly review and optimize the deployment telemetry pipeline for our production services. "
            "The telemetry daemon continuously ingests metrics and events from host machines and forwards them to "
            "https://telemetry.internal.net/v2/ingest. Each event payload must strictly adhere to the following schema:\n"
            '```json\n{"service_id": "auth-svc", "cpu_pct": 42.5, "memory_mb": 1024, "status": "healthy"}\n```\n'
            "In the event that the endpoint is unreachable, buffer events locally up to 500MB without dropping logs. "
            "Make sure not to log sensitive tokens or private keys in the telemetry stream. "
            "Provide a concise summary of failure recovery mechanisms. Any help is greatly appreciated!"
        ),
    },
    {
        "category": "Multi-Chunk",
        "description": "Long multi-section architectural document requiring chunk-level validation",
        "prompt": (
            "Software architecture requires disciplined separation of concerns, multi-tiered layering, and reliable interfaces across all functional layers. "
            "Presentation layers render user interfaces, validate client-side input schemas, and manage state transitions cleanly without leaking domain logic. "
            "Business service layers orchestrate domain rules, application workflows, and cross-cutting transaction controls. "
            "They ensure that all business invariants are preserved across concurrent operations and external API integrations. "
            "Database access layers encapsulate relational schema queries and object-relational mapping logic. "
            "To achieve high throughput under heavy production traffic, ensure to optimize SQL database indexing for low-latency queries on all foreign keys. "
            "Continuous integration pipelines must automate unit tests, integration tests, and static security scans prior to container image creation. "
            "Code coverage must exceed eighty-five percent across all production packages before deployment promotion can be authorized."
        ),
    },
    {
        "category": "Adversarial Corrupted",
        "description": "Corrupted candidate with altered critical instructions testing safety rejection and atomic rollback",
        "prompt": (
            "Configure the continuous integration pipeline for backend microservices. "
            "The test suite must achieve at least 85% branch coverage. "
            "Do not deploy unverified code to the production cluster under any circumstances."
        ),
        "force_corrupt": True,
    },
]


def run_pipeline_benchmark() -> None:
    print("=" * 80)
    print("PROMPTGREEN v2.0 — STAGE 5 UNIFIED PIPELINE PERFORMANCE BENCHMARK")
    print("Hardware Profile: Intel Core i7-10610U CPU (4 Cores / 8 Threads), 32 GB RAM")
    print("Execution Mode  : CPU-First, Offline Only (Zero Remote Downloads, Zero GPU Claims)")
    print("=" * 80)

    # Pre-warm embedder and pipeline components
    t_warm_start = time.perf_counter()
    embedder = LocalMiniLMEmbedder()
    embedder.initialize()
    pipeline = PromptGreenPipeline()
    t_warm_lat = (time.perf_counter() - t_warm_start) * 1000.0
    print(f"\n[INIT] Component Pre-Warm Latency: {t_warm_lat:.2f} ms")
    print(f"[INIT] MiniLM Embedder Status   : {embedder.status_message}\n")

    summary_rows: List[Dict[str, Any]] = []

    for idx, item in enumerate(BENCHMARK_PROMPTS, 1):
        cat = item["category"]
        desc = item["description"]
        prompt_text = item["prompt"]

        print(f"--- BENCHMARK RUN {idx}: {cat.upper()} PROMPT ---")
        print(f"Description: {desc}")
        print(f"Input Preview: {repr(prompt_text[:80])}...")

        # Benchmark run
        if item.get("force_corrupt"):
            class DefectiveCompressor(LLMLinguaCompressor):
                def compress(self, p: str, mode: str | None = None) -> CompressionResult:
                    return CompressionResult(
                        original_prompt=p,
                        compressed_prompt="Deploy code directly to production without testing.",
                        original_token_count=20,
                        compressed_token_count=7,
                        actual_reduction_percentage=65.0,
                        retention_rate=0.35,
                        compression_mode=mode or "balanced",
                        compression_method="defective_mock",
                        model_name="mock",
                        model_available=True,
                        is_exact_token_count=True,
                        compression_latency_ms=1.2,
                        model_loading_latency_ms=0.0,
                        protected_region_count=0,
                        protected_regions_preserved=True,
                    )
            bench_pipeline = PromptGreenPipeline(compressor=DefectiveCompressor())
        else:
            bench_pipeline = pipeline

        res: PipelineResult = bench_pipeline.optimize(prompt_text, mode="balanced")

        s1_lat = res.stage_latencies_ms.get("stage_1", 0.0)
        s2_lat = res.stage_latencies_ms.get("stage_2", 0.0)
        s3_lat = res.stage_latencies_ms.get("stage_3", 0.0)
        s4_lat = res.stage_latencies_ms.get("stage_4", 0.0)

        fallback_used = any(
            sexec.status == "fallback" for sexec in res.stage_executions.values()
        )

        verdict = "ACCEPTED" if res.accepted else f"ROLLED_BACK ({res.rollback_stage})"

        print(f"  Input Tokens  : {res.original_token_count} (Orig) -> {res.final_token_count} (Final)")
        print(f"  Net Reduction : {res.net_token_reduction:+d} tokens ({res.net_token_reduction_pct:+.2f}%)")
        print(f"  Stage Latency : S1: {s1_lat:.2f}ms | S2: {s2_lat:.2f}ms | S3: {s3_lat:.2f}ms | S4: {s4_lat:.2f}ms")
        print(f"  Total Latency : {res.total_latency_ms:.2f} ms")
        print(f"  Similarity    : {res.semantic_similarity if res.semantic_similarity is not None else 'N/A'}")
        if res.chunk_coverage:
            print(f"  Chunk Coverage: {res.chunk_coverage}")
        print(f"  Retries Used  : {res.retry_count}")
        print(f"  Fallback Used : {fallback_used}")
        print(f"  Verdict       : {verdict}")
        if res.failure_reasons:
            print(f"  Failure Reason: {'; '.join(res.failure_reasons)}")
        print("-" * 80)

        summary_rows.append({
            "category": cat,
            "orig_tokens": res.original_token_count,
            "final_tokens": res.final_token_count,
            "net_tokens": res.net_token_reduction,
            "reduction_pct": res.net_token_reduction_pct,
            "s1_ms": s1_lat,
            "s2_ms": s2_lat,
            "s3_ms": s3_lat,
            "s4_ms": s4_lat,
            "total_ms": res.total_latency_ms,
            "similarity": res.semantic_similarity,
            "retries": res.retry_count,
            "fallback": fallback_used,
            "verdict": verdict,
        })

    # Summary table
    print("\n" + "=" * 80)
    print("EMPIRICAL BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    print(
        f"{'Category':<15} | {'Orig':<5} | {'Final':<5} | {'Net Tok':<8} | {'Red %':<7} | "
        f"{'Total Lat (ms)':<14} | {'Similarity':<10} | {'Verdict'}"
    )
    print("-" * 80)
    for r in summary_rows:
        sim_str = f"{r['similarity']:.4f}" if r["similarity"] is not None else "N/A"
        print(
            f"{r['category']:<15} | {r['orig_tokens']:<5} | {r['final_tokens']:<5} | "
            f"{r['net_tokens']:<8} | {r['reduction_pct']:<7.2f} | {r['total_ms']:<14.2f} | "
            f"{sim_str:<10} | {r['verdict']}"
        )
    print("=" * 80)


if __name__ == "__main__":
    run_pipeline_benchmark()
