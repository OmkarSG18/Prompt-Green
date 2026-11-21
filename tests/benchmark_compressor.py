"""
PromptGreen v2.0 - Stage 2 Compressor CPU Performance Benchmark
Measures actual CPU latency, token reduction, memory usage, and structural preservation
across Short, Medium, and Long prompts using LLMLinguaCompressor.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import time
import statistics
import psutil

from promptgreen.optimizer.compressor import LLMLinguaCompressor, CompressorConfig


BENCHMARK_PROMPTS = {
    "short": (
        "In order to optimize performance, it is important to note that you must make sure "
        "to verify the server response time. At the present time, check if you can reproduce the error."
    ),
    "medium": (
        "In order to test the new caching layer, it is important to note that you must make sure "
        "to inspect this configuration payload prior to starting the service:\n"
        "{\n"
        '  "host": "localhost",\n'
        '  "port": 6379,\n'
        '  "max_memory": "4GB",\n'
        '  "timeout_ms": 100\n'
        "}\n"
        "Furthermore, you must never drop production keys under any circumstances. "
        "Check if you can ping https://cache.internal.corp/health and verify the latency is under 10ms."
    ),
    "long": (
        "In order to successfully deploy the PromptGreen v2.0 optimization microservice, it is important to note "
        "that the platform engineer must make sure to verify all environment variables prior to launch.\n"
        "Take into consideration the following Python helper function which handles AST parsing:\n"
        "```python\n"
        "import ast\n"
        "from typing import Optional\n\n"
        "def validate_ast(source_code: str) -> bool:\n"
        "    try:\n"
        "        ast.parse(source_code)\n"
        "        return True\n"
        "    except SyntaxError:\n"
        "        return False\n"
        "```\n"
        "Due to the fact that memory allocation is strictly constrained on CPU nodes, you are required to ensure "
        "that peak memory does not exceed 2.0GB. In the event that the server encounters a 500 error, "
        "do not terminate the active database session. Instead, log the incident directly to /var/log/promptgreen/error.log.\n"
        "Check if you can establish a secure TLS connection with https://api.prod.promptgreen.org/v1/telemetry "
        "and verify whether the PUE multiplier 1.15 is correctly applied across all 240 benchmark evaluations.\n"
        "As a matter of fact, keep in mind that you must never expose API_SECRET_KEY in raw log outputs."
    )
}


def run_benchmark():
    process = psutil.Process(os.getpid())
    compressor = LLMLinguaCompressor()

    print("=" * 80)
    print("PROMPTGREEN v2.0 - STAGE 2 COMPRESSOR CPU PERFORMANCE BENCHMARK")
    print(f"Platform: {os.name} | CPU: {psutil.cpu_count(logical=False)} cores / {psutil.cpu_count(logical=True)} threads")
    print(f"Initial Memory RSS: {process.memory_info().rss / (1024 * 1024):.2f} MB")
    print("=" * 80)

    for category, prompt in BENCHMARK_PROMPTS.items():
        print(f"\n--- BENCHMARK SUITE: {category.upper()} PROMPT ---")
        latencies = []
        reduction_percentages = []
        orig_tokens_recorded = 0
        comp_tokens_recorded = 0
        comp_method = ""
        protected_preserved = True

        # Warm-up run
        warmup = compressor.compress(prompt, mode="balanced")
        orig_tokens_recorded = warmup.original_token_count
        comp_tokens_recorded = warmup.compressed_token_count
        comp_method = warmup.compression_method

        # 10 Measured iterations
        iterations = 10
        for _ in range(iterations):
            start = time.perf_counter()
            res = compressor.compress(prompt, mode="balanced")
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies.append(elapsed_ms)
            reduction_percentages.append(res.actual_reduction_percentage)
            if not res.protected_regions_preserved:
                protected_preserved = False

        mem_mb = process.memory_info().rss / (1024 * 1024)

        print(f"Original Tokens   : {orig_tokens_recorded}")
        print(f"Compressed Tokens : {comp_tokens_recorded}")
        print(f"Reduction Target  : Balanced (tau = 0.55)")
        print(f"Actual Reduction  : {statistics.mean(reduction_percentages):.2f}%")
        print(f"Compression Method: {comp_method}")
        print(f"Protected Regions : Preserved = {protected_preserved}")
        print(f"Current Memory RSS: {mem_mb:.2f} MB")
        print("Latency Profile (10 iterations):")
        print(f"  Min   : {min(latencies):.2f} ms")
        print(f"  Mean  : {statistics.mean(latencies):.2f} ms")
        print(f"  Median: {statistics.median(latencies):.2f} ms")
        print(f"  Max   : {max(latencies):.2f} ms")
        print(f"  Thesis Target (<100ms): {'ACHIEVED' if statistics.mean(latencies) < 100.0 else 'EXCEEDED'}")

    print("\n" + "=" * 80)
    print("BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
