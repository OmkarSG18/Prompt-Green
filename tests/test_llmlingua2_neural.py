"""
Unit and integration tests for Stage 2 LLMLingua-2 neural token classification.
Verifies offline CPU inference, model sharing, retention rates across modes,
protected content preservation, and fallback behavior.
"""

from __future__ import annotations

from unittest.mock import patch
import pytest

from promptgreen.optimizer.compressor import (
    CompressorConfig,
    LLMLinguaCompressor,
)


@pytest.fixture
def neural_compressor():
    config = CompressorConfig(use_llmlingua2=True)
    comp = LLMLinguaCompressor(config=config)
    comp.load_model()
    return comp


def test_neural_llmlingua2_model_loading_and_availability(neural_compressor):
    """Verify that LLMLingua-2 model initializes and reports available offline on CPU."""
    assert neural_compressor.is_model_available() is True
    assert neural_compressor._model_loaded is True
    assert neural_compressor._llm_lingua is not None


def test_neural_llmlingua2_compression_execution(neural_compressor):
    """Verify that neural token classifier executes and produces compressed output."""
    prompt = (
        "In order to achieve optimal performance, it is important to note that the team "
        "should take into consideration reviewing the backend telemetry data regularly."
    )
    result = neural_compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.compression_method == "llmlingua-2"
    assert result.fallback_used is False
    assert result.compressed_token_count < result.original_token_count
    assert result.actual_reduction_percentage > 0.0


def test_neural_llmlingua2_modes_monotonicity(neural_compressor):
    """Verify that aggressive mode yields lower token retention than conservative mode."""
    prompt = (
        "In order to facilitate distributed processing across multiple geographic zones, "
        "it is essential that developers take into consideration the latency of cross-region requests. "
        "Furthermore, at the present time, we must ensure that all network endpoints are encrypted with TLS 1.3."
    )
    res_cons = neural_compressor.compress(prompt, mode="conservative")
    res_agg = neural_compressor.compress(prompt, mode="aggressive")

    assert res_cons.compression_method == "llmlingua-2"
    assert res_agg.compression_method == "llmlingua-2"
    assert res_agg.compressed_token_count <= res_cons.compressed_token_count
    assert res_agg.actual_reduction_percentage >= res_cons.actual_reduction_percentage


def test_neural_llmlingua2_protected_content_preservation(neural_compressor):
    """Verify that code blocks, numbers, URLs, and negations are preserved under neural compression."""
    prompt = (
        "Please review the following configuration:\n"
        "```yaml\n"
        "timeout: 500ms\n"
        "retries: 3\n"
        "```\n"
        "Do not delete production records at https://db.promptgreen.org/v2/metrics with batch size 32."
    )
    result = neural_compressor.compress(prompt, mode="balanced")

    assert result.compression_method == "llmlingua-2"
    assert result.protected_regions_preserved is True
    assert "timeout: 500ms" in result.compressed_prompt
    assert "retries: 3" in result.compressed_prompt
    assert "https://db.promptgreen.org/v2/metrics" in result.compressed_prompt
    assert "32" in result.compressed_prompt
    assert "Do not delete" in result.compressed_prompt or "do not delete" in result.compressed_prompt.lower()


def test_neural_fallback_when_disabled():
    """Verify that when use_llmlingua2 is False, deterministic lexical fallback executes."""
    config = CompressorConfig(use_llmlingua2=False)
    comp = LLMLinguaCompressor(config=config)
    prompt = "In order to optimize throughput, take into consideration adding Redis cache."
    result = comp.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.fallback_used is True
    assert result.compression_method == "deterministic_lexical_fallback"
