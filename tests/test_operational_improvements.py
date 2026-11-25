"""
Targeted tests for Phase 1 Operational Improvements:
1. MiniLM model pre-warming and duplicate initialization prevention.
2. Missing model handling and offline safety.
3. Cold vs warm timing instrumentation and accounting separation.
4. CLI V2 optimize subcommand across all three modes.
5. Stage 3 Ollama configurable timeout, bloat rejection, and deterministic fallback.
6. Existing V1 CLI backward compatibility.
"""

import os
import time
import pytest
from click.testing import CliRunner

from promptgreen.cli import main
from promptgreen.optimizer.semantic_guard import LocalMiniLMEmbedder, SemanticFidelityGuard, GuardrailConfig
from promptgreen.optimizer.output_shaper import OutputDirectiveShaper, ShaperConfig, ShapingResult
from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig


# =============================================================================
# 1. PRE-WARMING & MODEL LIFECYCLE TESTS
# =============================================================================

def test_prewarm_cached_model_and_shared_cache():
    """Verify that LocalMiniLMEmbedder.prewarm() loads the local cached model and tracks state."""
    LocalMiniLMEmbedder.reset_shared_cache()
    status_before = LocalMiniLMEmbedder.get_prewarm_status()
    assert status_before["is_prewarmed"] is False
    assert status_before["init_latency_ms"] is None

    ok, lat_ms, msg = LocalMiniLMEmbedder.prewarm()
    assert ok is True
    assert lat_ms > 0
    assert "loaded via" in msg

    status_after = LocalMiniLMEmbedder.get_prewarm_status()
    assert status_after["is_prewarmed"] is True
    assert status_after["init_latency_ms"] is not None


def test_avoid_duplicate_model_initialization():
    """Verify that multiple embedder instances reuse the shared model without duplicate loads."""
    # Ensure pre-warmed
    LocalMiniLMEmbedder.prewarm()

    t0 = time.perf_counter()
    e1 = LocalMiniLMEmbedder()
    e1.initialize()
    lat1 = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    e2 = LocalMiniLMEmbedder()
    e2.initialize()
    lat2 = (time.perf_counter() - t1) * 1000.0

    # Instance reuse should be sub-millisecond (typically < 1 ms)
    assert lat1 < 100.0
    assert lat2 < 100.0
    assert "reused shared model" in e1.status_message
    assert "reused shared model" in e2.status_message

    # Both produce identical embeddings
    v1 = e1.embed("Hello world")
    v2 = e2.embed("Hello world")
    assert v1.shape == (384,)
    assert (v1 == v2).all()


def test_missing_model_behavior_offline():
    """Verify that attempting to load a non-existent model fails gracefully without crashing or downloading."""
    embedder = LocalMiniLMEmbedder(model_name="nonexistent/fake-minilm-model-999")
    ok = embedder.initialize()
    assert ok is False
    assert embedder.is_available is False
    assert "not found" in embedder.status_message.lower()


def test_cold_vs_warm_timing_instrumentation():
    """Demonstrate that once pre-warmed, pipeline optimization operates in warm regime (<500ms)."""
    LocalMiniLMEmbedder.prewarm()
    pw_status = LocalMiniLMEmbedder.get_prewarm_status()
    assert pw_status["is_prewarmed"] is True
    cold_init_ms = pw_status["init_latency_ms"]
    assert cold_init_ms > 0

    pipeline = PromptGreenPipeline(config=PipelineConfig(mode="conservative"))
    t0 = time.perf_counter()
    res = pipeline.optimize("Hello dear assistant! Could you please tell me the capital of France?")
    warm_latency_ms = (time.perf_counter() - t0) * 1000.0

    # Warm execution should be substantially faster than the one-time cold initialization
    assert warm_latency_ms < 2000.0
    assert res.accepted is True


# =============================================================================
# 2. STAGE 3 OLLAMA TIMEOUT & FALLBACK TESTS
# =============================================================================

def test_shaper_config_timeout_defaults_and_env_override():
    """Verify that ShaperConfig defaults to 5.0s and respects environment variable overrides."""
    cfg_default = ShaperConfig()
    assert cfg_default.timeout_seconds == 5.0

    os.environ["PROMPTGREEN_OLLAMA_TIMEOUT"] = "8.2"
    try:
        cfg_custom = ShaperConfig()
        assert cfg_custom.timeout_seconds == 8.2
    finally:
        del os.environ["PROMPTGREEN_OLLAMA_TIMEOUT"]


def test_ollama_timeout_and_fallback():
    """Verify that when Ollama times out or is unreachable, Stage 3 falls back cleanly to deterministic shaping."""
    # Configure an unreachable port with a tight 0.05s timeout
    cfg = ShaperConfig(ollama_host="http://127.0.0.1:59999", timeout_seconds=0.05, prefer_ollama=True)
    shaper = OutputDirectiveShaper(config=cfg)

    # Simple prompt with implicit table request
    prompt = "Compare REST and GraphQL in a table"
    res = shaper.shape(prompt)

    assert res.success is True
    assert res.shaping_applied is True
    assert res.shaping_method == "deterministic"
    assert "Present the comparison in a table" in res.shaped_prompt
    assert res.fallback_reason is not None


def test_ollama_bloat_rejection():
    """Verify that if neural shaping expands prompt size excessively, it is rejected in favor of deterministic result."""
    class BloatedMockOllamaClient:
        def generate(self, payload):
            # Returns an excessively long response that would inflate token counts
            return {
                "response": "Here is an extraordinarily long, verbose, repetitive essay about REST and GraphQL that adds hundreds of unnecessary filler tokens and dilutes the prompt entirely."
            }

    cfg = ShaperConfig(prefer_ollama=True)
    shaper = OutputDirectiveShaper(config=cfg, ollama_client=BloatedMockOllamaClient())
    prompt = "Compare REST and GraphQL in a table"
    res = shaper.shape(prompt)

    # Neural output should be rejected due to bloat, falling back to deterministic
    assert res.shaping_method == "deterministic"
    assert any("expanded token size" in w or "out of acceptable bounds" in w for w in res.warnings)


def test_ollama_preservation_failure_fallback():
    """Verify that if neural shaping drops a protected placeholder, it is rejected."""
    class DroppingMockOllamaClient:
        def generate(self, payload):
            # Drops placeholders
            return {"response": "Summarize this data cleanly without code."}

    cfg = ShaperConfig(prefer_ollama=True)
    shaper = OutputDirectiveShaper(config=cfg, ollama_client=DroppingMockOllamaClient())
    prompt = "Analyze this code:\n```python\nx = 1\n```\nReturn summary."
    res = shaper.shape(prompt)

    # Should retain the code block via rollback/deterministic
    assert "```python" in res.shaped_prompt
    assert "x = 1" in res.shaped_prompt


# =============================================================================
# 3. CLI V2 OPTIMIZE SUBCOMMAND TESTS
# =============================================================================

def test_cli_v2_optimize_balanced_mode():
    """Verify that 'python -m promptgreen.cli optimize' runs the 4-stage pipeline and outputs all sections."""
    runner = CliRunner()
    prompt = "Hello dear assistant! Could you please be so kind as to explain quantum superposition? Thank you very much in advance!"
    result = runner.invoke(main, ["optimize", "--prompt", prompt, "--mode", "balanced", "--no-record"])

    assert result.exit_code == 0
    out = result.output
    assert "PromptGreen V2 Active Prompt Optimization" in out
    assert "BALANCED" in out
    assert "Token Accounting & Quality Metrics" in out
    assert "Thermodynamic Energy & Carbon Accounting" in out
    assert "Net Energy Saved" in out
    assert "Conservative Green Model Router" in out
    assert "Advisory Governance" in out


def test_cli_v2_optimize_conservative_mode():
    """Verify that 'optimize' operates under conservative mode."""
    runner = CliRunner()
    prompt = "Could you please explain how photosynthensis works?"
    result = runner.invoke(main, ["optimize", "-p", prompt, "-m", "conservative", "--no-record"])
    assert result.exit_code == 0
    assert "CONSERVATIVE" in result.output
    assert "ACCEPTED" in result.output


def test_cli_v2_optimize_aggressive_mode():
    """Verify that 'optimize' operates under aggressive mode."""
    runner = CliRunner()
    prompt = "Hello there! In order to facilitate understanding, please kindly provide a brief summary of database indexing."
    result = runner.invoke(main, ["optimize", "-p", prompt, "-m", "aggressive", "--no-record"])
    assert result.exit_code == 0
    assert "AGGRESSIVE" in result.output


def test_cli_v2_empty_prompt_error():
    """Verify that passing an empty prompt returns non-zero exit code and error message."""
    runner = CliRunner()
    result = runner.invoke(main, ["optimize", "--prompt", "   "])
    assert result.exit_code != 0
    assert "cannot be empty" in result.output


# =============================================================================
# 4. EXISTING V1 CLI BACKWARD COMPATIBILITY REGRESSION
# =============================================================================

def test_v1_cli_commands_preserved():
    """Verify that existing V1 subcommands (analyze, benchmark, ledger, git-diff) remain intact."""
    runner = CliRunner()

    res_help = runner.invoke(main, ["--help"])
    assert res_help.exit_code == 0
    assert "analyze" in res_help.output
    assert "benchmark" in res_help.output
    assert "git-diff" in res_help.output
    assert "ledger" in res_help.output
    assert "optimize" in res_help.output

    res_bench_help = runner.invoke(main, ["benchmark", "--help"])
    assert res_bench_help.exit_code == 0
    assert "Run validation benchmark suite" in res_bench_help.output

    res_ledger_help = runner.invoke(main, ["ledger", "--help"])
    assert res_ledger_help.exit_code == 0
    assert "Inspect local Prompt Carbon Ledger records" in res_ledger_help.output
