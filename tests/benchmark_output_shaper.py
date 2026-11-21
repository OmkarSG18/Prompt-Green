"""
PromptGreen v2.0 - Stage 3 Output Directive Shaper CPU Performance Benchmark
Measures actual CPU latency, token differences, and directive clarity
across Short, Medium, and Long representative prompts using OutputDirectiveShaper.
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))
import time
import statistics
import psutil

from promptgreen.optimizer.output_shaper import OutputDirectiveShaper, ShaperConfig


BENCHMARK_PROMPTS = {
    "short": (
        "Explain database normalization in simple terms."
    ),
    "medium": (
        "In order to test the system, compare SQL and NoSQL databases in a table. "
        "Do not delete production data under any circumstances. Ensure latency is under 100ms."
    ),
    "long": (
        "Explain how the PromptGreen v2.0 optimization microservice processes prompt payloads. "
        "Take into consideration the following Python helper function which handles AST parsing:\n"
        "```python\n"
        "import ast\n\n"
        "def validate_ast(source_code: str) -> bool:\n"
        "    try:\n"
        "        ast.parse(source_code)\n"
        "        return True\n"
        "    except SyntaxError:\n"
        "        return False\n"
        "```\n"
        "Due to the fact that memory allocation is strictly constrained on CPU nodes, "
        "summarize the key implementation requirements in bullet points. "
        "Check if you can ping https://api.prod.promptgreen.org/v1/telemetry and verify the memory limit is 2.0GB."
    )
}


def run_benchmark():
    process = psutil.Process(os.getpid())
    # Benchmarking deterministic shaping engine
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))

    print("=" * 80)
    print("PROMPTGREEN v2.0 - STAGE 3 OUTPUT SHAPER CPU PERFORMANCE BENCHMARK")
    print(f"Platform: {os.name} | CPU: {psutil.cpu_count(logical=False)} cores / {psutil.cpu_count(logical=True)} threads")
    print(f"Initial Memory RSS: {process.memory_info().rss / (1024 * 1024):.2f} MB")
    print("=" * 80)

    for category, prompt in BENCHMARK_PROMPTS.items():
        print(f"\n--- BENCHMARK SUITE: {category.upper()} PROMPT ---")
        latencies = []
        input_tokens_recorded = 0
        output_tokens_recorded = 0
        token_diff_recorded = 0
        shaping_method = ""
        shaping_applied = False
        integrity_ok = True

        # Warm-up run
        warmup = shaper.shape(prompt)
        input_tokens_recorded = warmup.input_token_count
        output_tokens_recorded = warmup.output_token_count
        token_diff_recorded = warmup.estimated_token_difference
        shaping_method = warmup.shaping_method
        shaping_applied = warmup.shaping_applied
        integrity_ok = warmup.integrity_preserved

        # 10 Measured iterations
        iterations = 10
        for _ in range(iterations):
            start = time.perf_counter()
            res = shaper.shape(prompt)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            latencies.append(elapsed_ms)
            if not res.integrity_preserved:
                integrity_ok = False

        mem_mb = process.memory_info().rss / (1024 * 1024)

        print(f"Input Prompt Tokens : {input_tokens_recorded}")
        print(f"Output Prompt Tokens: {output_tokens_recorded}")
        print(f"Token Difference    : {token_diff_recorded:+d} tokens ({'+' if token_diff_recorded > 0 else ''}{(token_diff_recorded / input_tokens_recorded * 100.0) if input_tokens_recorded else 0:.1f}%)")
        print(f"Shaping Applied     : {shaping_applied}")
        print(f"Shaping Method      : {shaping_method}")
        print(f"Integrity Preserved : {integrity_ok}")
        print(f"Current Memory RSS  : {mem_mb:.2f} MB")
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
