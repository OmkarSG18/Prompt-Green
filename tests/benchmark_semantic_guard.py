"""
Benchmark script for PromptGreen v2.0 Stage 4 Semantic Fidelity Guardrail.
Measures real CPU embedding latency, cosine similarity calculation time,
and preservation validation overhead across short, medium, long, and multi-chunk prompts.
Explicitly separates model-loading time from inference time.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from promptgreen.optimizer.semantic_guard import (
    GuardrailConfig,
    LocalMiniLMEmbedder,
    SemanticFidelityGuard,
    compute_cosine_similarity,
)

BENCHMARK_PROMPTS = [
    {
        "name": "Short",
        "original": "Explain the concept of database indexing in simple terms.",
        "candidate": "Explain database indexing. Use clear, simple language. Organize the explanation into short sections.",
    },
    {
        "name": "Medium",
        "original": (
            "Compare PostgreSQL and MongoDB in a table. Include query language, data model, "
            "and scalability. Do not omit ACID compliance and verify https://postgresql.org/docs."
        ),
        "candidate": (
            "Compare PostgreSQL and MongoDB in a table. Include query language, data model, "
            "and scalability. Do not omit ACID compliance and verify https://postgresql.org/docs."
        ),
    },
    {
        "name": "Long",
        "original": (
            "Write a Python script to sort a dictionary by key and value. "
            "Return only the code implementation without additional conversational text. "
            "Ensure the script handles nested dictionaries:\n"
            "```python\n"
            "def sort_nested(d):\n"
            "    if isinstance(d, dict):\n"
            "        return {k: sort_nested(v) for k, v in sorted(d.items())}\n"
            "    return d\n"
            "```\n"
            "Benchmark execution time and memory consumption for 1000 items under 50ms."
        ),
        "candidate": (
            "Write a Python script to sort a dictionary by key and value. "
            "Return only the code implementation without additional conversational text. "
            "Ensure the script handles nested dictionaries:\n"
            "```python\n"
            "def sort_nested(d):\n"
            "    if isinstance(d, dict):\n"
            "        return {k: sort_nested(v) for k, v in sorted(d.items())}\n"
            "    return d\n"
            "```\n"
            "Benchmark execution time and memory consumption for 1000 items under 50ms."
        ),
    },
    {
        "name": "Multi-Chunk",
        "original": (
            "Architectural design for distributed transaction systems requires formal consensus mechanisms. "
            "Two-phase commit guarantees atomicity across heterogeneous partitions, but introduces blocking latency. "
            "Modern event-driven architectures favor saga orchestration or choreography using compensation transactions. "
            "Idempotency keys must be enforced at every API boundary to prevent duplicate side effects during network retries. "
            "Ensure that database isolation levels are set to Serializable when executing balance ledger updates. "
            "Benchmark distributed transaction throughput under 5000 transactions per second with p99 latency under 25ms. "
            "Do not disable WAL logging or bypass distributed commit coordinators under any failure scenario."
        ),
        "candidate": (
            "Architectural design for distributed transaction systems requires formal consensus mechanisms. "
            "Two-phase commit guarantees atomicity across heterogeneous partitions, but introduces blocking latency. "
            "Modern event-driven architectures favor saga orchestration or choreography using compensation transactions. "
            "Idempotency keys must be enforced at every API boundary to prevent duplicate side effects during network retries. "
            "Ensure that database isolation levels are set to Serializable when executing balance ledger updates. "
            "Benchmark distributed transaction throughput under 5000 transactions per second with p99 latency under 25ms. "
            "Do not disable WAL logging or bypass distributed commit coordinators under any failure scenario."
        ),
    },
]


def run_benchmark(iterations: int = 5) -> None:
    print("=" * 80)
    print("PROMPTGREEN V2 - STAGE 4 SEMANTIC FIDELITY GUARDRAIL BENCHMARK (CPU)")
    print("=" * 80)

    # 1. Measure model loading time separately from inference time
    t_load_start = time.perf_counter()
    embedder = LocalMiniLMEmbedder()
    is_ready = embedder.initialize()
    load_time_ms = (time.perf_counter() - t_load_start) * 1000.0

    print(f"Embedding Engine Status : {embedder.status_message}")
    print(f"Model Initialization    : {load_time_ms:.2f} ms (cold model weight & tokenizer loading)")
    if not is_ready:
        print("Real embedding model is not available. Aborting real benchmark.")
        return

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    # 2. Warmup execution pipeline
    print("\nWarming up CPU execution pipeline (unmeasured pass)...")
    _ = guard.evaluate(BENCHMARK_PROMPTS[0]["original"], BENCHMARK_PROMPTS[0]["candidate"])
    print("Warmup complete.\n")

    print(f"{'Prompt':<12} | {'Chars':<12} | {'Chunks':<8} | {'Mean Total':<13} | {'Median':<10} | {'Emb. Latency':<14} | {'Cosine Sim':<11} | {'Verdict'}")
    print("-" * 105)

    for p in BENCHMARK_PROMPTS:
        name = p["name"]
        orig = p["original"]
        cand = p["candidate"]
        char_info = f"{len(orig)}/{len(cand)}"

        total_latencies: List[float] = []
        emb_latencies: List[float] = []
        sim_scores: List[float] = []
        last_res = None

        # Check chunk count
        orig_chunks = embedder.chunk_text(orig)
        chunk_count = len(orig_chunks)

        for _ in range(iterations):
            res = guard.evaluate(orig, cand)
            last_res = res
            total_latencies.append(res.guardrail_latency_ms)
            emb_latencies.append(res.embedding_latency_ms)
            if res.similarity_score is not None:
                sim_scores.append(res.similarity_score)

        mean_lat = statistics.mean(total_latencies)
        median_lat = statistics.median(total_latencies)
        mean_emb = statistics.mean(emb_latencies)
        avg_sim = statistics.mean(sim_scores) if sim_scores else 0.0
        verdict = "PASS" if last_res and last_res.passed else "FAIL"

        print(
            f"{name:<12} | {char_info:<12} | {chunk_count:<8} | {mean_lat:7.2f} ms   | {median_lat:6.2f} ms | "
            f"{mean_emb:7.2f} ms    | {avg_sim:8.4f}  | {verdict}"
        )

    print("-" * 105)
    print("Benchmark complete across all prompt categories.")
    print("Note: Latencies are host CPU-specific (Intel Core i7-10610U) and reflect measured prompts only.\n")


if __name__ == "__main__":
    run_benchmark(iterations=5)
