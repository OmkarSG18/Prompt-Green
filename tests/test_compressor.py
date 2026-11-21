"""
PromptGreen v2.0 - Stage 2 LLMLingua-2 Extractive Token Compressor Test Suite
Comprehensive unit and integration tests covering:
- Modes (Conservative, Balanced, Aggressive)
- Structural & Code Protection (Python, JSON, YAML, Inline, URLs, Paths)
- Semantic & Constraint Preservation (Negations, Conditionals, Numbers, Identifiers)
- Fallback Execution, Error Handling & Rollbacks
- Determinism, Exact Byte-for-Byte Restoration & Metadata Consistency
- Mocked Neural LLMLingua-2 Integration
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from promptgreen.optimizer.compressor import (
    CompressorConfig,
    CompressionResult,
    LLMLinguaCompressor,
    PromptCompressor,
    RETENTION_MODES,
)
from promptgreen.optimizer.rule_pruner import RuleBasedPruner


# =============================================================================
# 1. COMPRESSION MODES
# =============================================================================

def test_mode_conservative():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize performance, verify the server response time and evaluate "
        "the database connection. Check if you can reproduce the error."
    )
    result = compressor.compress(prompt, mode="conservative")

    assert result.success is True
    assert result.compression_mode == "conservative"
    assert result.compressed_token_count <= result.original_token_count
    assert result.retention_rate >= 0.70
    assert "verify" in result.compressed_prompt.lower()
    assert "server" in result.compressed_prompt.lower()
    assert "error" in result.compressed_prompt.lower()


def test_mode_balanced():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize performance, it is important to note that you must make sure "
        "to verify the server response time. At the present time, check if you can reproduce the error."
    )
    res_cons = compressor.compress(prompt, mode="conservative")
    res_bal = compressor.compress(prompt, mode="balanced")

    assert res_bal.success is True
    assert res_bal.compression_mode == "balanced"
    assert res_bal.compressed_token_count <= res_cons.compressed_token_count
    assert res_bal.actual_reduction_percentage >= res_cons.actual_reduction_percentage


def test_mode_aggressive():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize performance, it is important to note that you must make sure "
        "to verify the server response time. At the present time, check if you can reproduce the error."
    )
    res_bal = compressor.compress(prompt, mode="balanced")
    res_agg = compressor.compress(prompt, mode="aggressive")

    assert res_agg.success is True
    assert res_agg.compression_mode == "aggressive"
    assert res_agg.compressed_token_count <= res_bal.compressed_token_count
    assert res_agg.actual_reduction_percentage >= res_bal.actual_reduction_percentage


# =============================================================================
# 2. EDGE CASES: EMPTY & WHITESPACE INPUTS
# =============================================================================

def test_empty_input():
    compressor = LLMLinguaCompressor()
    result = compressor.compress("", mode="balanced")

    assert result.success is True
    assert result.compressed_prompt == ""
    assert result.original_token_count == 0
    assert result.compressed_token_count == 0
    assert result.actual_reduction_percentage == 0.0
    assert result.protected_regions_preserved is True


def test_whitespace_only_input():
    compressor = LLMLinguaCompressor()
    result = compressor.compress("   \n\t  \n  ", mode="balanced")

    assert result.success is True
    assert result.original_token_count == 0
    assert result.compressed_token_count == 0
    assert result.protected_regions_preserved is True


# =============================================================================
# 3. STRUCTURAL PROTECTION: CODE, SCHEMAS, CONFIGS
# =============================================================================

def test_python_code_protection():
    compressor = LLMLinguaCompressor()
    raw_code = (
        "```python\n"
        "import sys\n\n"
        "def compute_hash(val: str) -> str:\n"
        "    # Indented block with internal whitespace\n"
        "    result = f'hash_{val}'\n"
        "    return result.strip()\n"
        "```"
    )
    prompt = f"In order to test the pipeline, make sure to examine this code:\n{raw_code}\nVerify if you can run it."
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.protected_regions_preserved is True
    assert raw_code in result.compressed_prompt
    assert result.protected_region_count >= 1


def test_json_schema_protection():
    compressor = LLMLinguaCompressor()
    json_block = (
        "{\n"
        '  "service": "promptgreen",\n'
        '  "version": "2.0",\n'
        '  "settings": {\n'
        '    "pue_multiplier": 1.15,\n'
        '    "debug": false\n'
        "  }\n"
        "}"
    )
    prompt = f"Please take into consideration the following configuration payload:\n{json_block}\nEnsure it validates."
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.protected_regions_preserved is True
    assert json_block in result.compressed_prompt
    # Verify JSON is still valid parseable JSON
    parsed = json.loads(json_block)
    assert parsed["service"] == "promptgreen"


def test_yaml_protection():
    compressor = LLMLinguaCompressor()
    yaml_block = (
        "---\n"
        "database:\n"
        "  host: localhost\n"
        "  port: 5432\n"
        "  ssl_mode: require\n"
        "  pool_size: 20\n"
    )
    prompt = f"In order to configure the server, apply this YAML configuration:\n{yaml_block}\nCheck if you can ping it."
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.protected_regions_preserved is True
    assert yaml_block in result.compressed_prompt


def test_inline_code_protection():
    compressor = LLMLinguaCompressor()
    prompt = (
        "Make sure to call `calculate_pue(1.15)` prior to invoking `router.forward()` in the engine."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert "`calculate_pue(1.15)`" in result.compressed_prompt
    assert "`router.forward()`" in result.compressed_prompt


def test_multiple_protected_blocks():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to test, check URL https://api.internal.corp/v1 and inspect `get_status()`. "
        "Then evaluate this function:\n"
        "```python\n"
        "def ping(): return True\n"
        "```\n"
        "Ensure latency remains under 50ms."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert "https://api.internal.corp/v1" in result.compressed_prompt
    assert "`get_status()`" in result.compressed_prompt
    assert "def ping(): return True" in result.compressed_prompt
    assert "50ms" in result.compressed_prompt
    assert result.protected_regions_preserved is True


# =============================================================================
# 4. CONSTRAINT & INSTRUCTION PRESERVATION
# =============================================================================

def test_numerical_constraints():
    compressor = LLMLinguaCompressor()
    prompt = (
        "You must make sure that memory limit is strictly set to 4GB, timeout is 100ms, "
        "and batch size is 32 items with 3.8x multiplier."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "4GB" in result.compressed_prompt
    assert "100ms" in result.compressed_prompt
    assert "32" in result.compressed_prompt
    assert "3.8x" in result.compressed_prompt


def test_negative_instructions():
    compressor = LLMLinguaCompressor()
    prompt = (
        "Do not delete production tables under any circumstances. "
        "You must never drop database clusters. Do not expose credentials."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "Do not delete" in result.compressed_prompt or "do not delete" in result.compressed_prompt.lower()
    assert "never" in result.compressed_prompt.lower()
    assert "not expose" in result.compressed_prompt.lower()


def test_conditional_instructions():
    compressor = LLMLinguaCompressor()
    prompt = (
        "Check if you can reproduce the error. Unless the token is expired, proceed. "
        "Determine whether the port is open."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "if you can" in result.compressed_prompt.lower()
    assert "unless" in result.compressed_prompt.lower()
    assert "whether" in result.compressed_prompt.lower()


def test_technical_identifiers():
    compressor = LLMLinguaCompressor()
    prompt = (
        "Inspect the implementation of GreenModelRouter, pue_multiplier, "
        "and verify that AST parsing uses ast.parse() with CL100K_BASE."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "GreenModelRouter" in result.compressed_prompt
    assert "pue_multiplier" in result.compressed_prompt
    assert "ast.parse()" in result.compressed_prompt
    assert "CL100K_BASE" in result.compressed_prompt


def test_urls_and_paths():
    compressor = LLMLinguaCompressor()
    prompt = (
        "Download telemetry from https://metrics.prod.internal:8080/v2/stats "
        "and store it at /var/log/promptgreen/telemetry.json."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "https://metrics.prod.internal:8080/v2/stats" in result.compressed_prompt
    assert "/var/log/promptgreen/telemetry.json" in result.compressed_prompt


def test_unicode_text():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to test unicode support, café con crème brûlée must maintain naïve accents "
        "with λ-calculus and 100ms latency. Check if you can verify."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "café" in result.compressed_prompt.lower()
    assert "brûlée" in result.compressed_prompt.lower()
    assert "λ" in result.compressed_prompt
    assert "100ms" in result.compressed_prompt


def test_placeholder_collision_immunity():
    compressor = LLMLinguaCompressor()
    # Prompt literally containing standard placeholder substrings as user text
    prompt = (
        "The documentation states that __CODE_BLOCK_0__ is used internally. "
        "In order to test, verify that __PG_PROT_CODE_0__ is safely processed."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert "__CODE_BLOCK_0__" in result.compressed_prompt
    assert "__PG_PROT_CODE_0__" in result.compressed_prompt
    assert result.protected_regions_preserved is True


# =============================================================================
# 5. FALLBACK & ERROR HANDLING
# =============================================================================

def test_llmlingua_unavailable_fallback():
    # Test that when neural model is unavailable, fallback is seamlessly used
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize throughput, it is important to note that you must make sure "
        "to verify the database connection prior to running benchmark tests."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.fallback_used is True
    assert result.compression_method == "deterministic_lexical_fallback"
    assert result.compressed_token_count < result.original_token_count


def test_model_loading_failure_fallback():
    # Simulate an error during model loading (e.g., RuntimeError or OSError)
    compressor = LLMLinguaCompressor()
    mock_llmlingua = MagicMock()
    mock_llmlingua.PromptCompressor.side_effect = RuntimeError("Out of memory on CPU")
    with patch.object(compressor, "is_model_available", return_value=True):
        with patch.dict("sys.modules", {"llmlingua": mock_llmlingua}):
            prompt = "In order to test fallback, verify the application status."
            result = compressor.compress(prompt, mode="balanced")

            assert result.success is True
            assert result.fallback_used is True
            assert result.compression_method == "deterministic_lexical_fallback"
            assert any("failed" in w.lower() for w in result.warnings)


def test_compression_failure_rollback():
    # Simulate a neural compressor that corrupts or drops protected placeholders
    mock_llm = MagicMock()
    # Mock returns text that strips all placeholders
    mock_llm.compress_prompt.return_value = {"compressed_prompt": "Stripped text without placeholders"}

    compressor = LLMLinguaCompressor(llm_lingua_instance=mock_llm)
    prompt = "Here is protected code:\n```python\nx = 1\n```\nVerify output."
    result = compressor.compress(prompt, mode="balanced")

    # Compressor should detect placeholder drop, warn, and rollback without losing the code
    assert result.success is True
    assert "```python\nx = 1\n```" in result.compressed_prompt
    assert result.protected_regions_preserved is True


def test_no_unnecessary_model_download():
    # Verify initializing compressor does not trigger downloads or imports
    config = CompressorConfig(model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank")
    compressor = LLMLinguaCompressor(config=config)

    # Calling is_model_available should safely return a bool without exceptions
    available = compressor.is_model_available()
    assert isinstance(available, bool)
    assert compressor._model_loaded is False


def test_deterministic_fallback_reproducibility():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize performance, it is important to note that you must make sure "
        "to verify the server response time. At the present time, check if you can reproduce the error."
    )

    results = [compressor.compress(prompt, mode="balanced") for _ in range(5)]
    first_text = results[0].compressed_prompt
    first_tokens = results[0].compressed_token_count

    for r in results[1:]:
        assert r.compressed_prompt == first_text
        assert r.compressed_token_count == first_tokens
        assert r.actual_reduction_percentage == results[0].actual_reduction_percentage


def test_protected_region_exact_restoration():
    compressor = LLMLinguaCompressor()
    raw_code = (
        "```python\n"
        "for i in range(10):\n"
        "    if i % 2 == 0:\n"
        "        print(f'Even: {i}')\n"
        "```"
    )
    prompt = f"In order to analyze performance, inspect this block:\n{raw_code}\nVerify output."
    result = compressor.compress(prompt, mode="balanced")

    # Byte-for-byte slice verification
    start_idx = result.compressed_prompt.find("```python")
    end_idx = result.compressed_prompt.find("```", start_idx + 8) + 3
    extracted_block = result.compressed_prompt[start_idx:end_idx]

    assert extracted_block == raw_code


def test_token_count_metadata_correctness():
    compressor = LLMLinguaCompressor()
    prompt = (
        "In order to optimize performance, it is important to note that you must make sure "
        "to verify the server response time."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert result.original_token_count > 0
    assert result.compressed_token_count > 0
    assert result.compressed_token_count <= result.original_token_count
    expected_reduction = result.original_token_count - result.compressed_token_count
    expected_pct = round((expected_reduction / result.original_token_count) * 100.0, 2)
    assert result.actual_reduction_percentage == expected_pct
    assert isinstance(result.is_exact_token_count, bool)
    assert result.compression_latency_ms >= 0.0


# =============================================================================
# 6. MOCKED NEURAL LLMLINGUA-2 INTEGRATION
# =============================================================================

def test_mock_neural_compression_integration():
    # Test proper neural path execution when an LLMLingua instance is present
    mock_llm = MagicMock()
    mock_llm.compress_prompt.return_value = {
        "compressed_prompt": "Optimize performance. Verify server __URL_0__ before testing.",
        "origin_tokens": 20,
        "compressed_tokens": 10,
    }

    compressor = LLMLinguaCompressor(llm_lingua_instance=mock_llm)
    prompt = (
        "In order to optimize performance, verify server https://api.corp.internal "
        "prior to testing."
    )
    result = compressor.compress(prompt, mode="balanced")

    assert result.success is True
    assert result.compression_method == "llmlingua-2"
    assert result.fallback_used is False
    assert "https://api.corp.internal" in result.compressed_prompt
    assert result.protected_regions_preserved is True
    # Verify mock was called with rate and force_tokens
    mock_llm.compress_prompt.assert_called_once()
    call_kwargs = mock_llm.compress_prompt.call_args[1]
    assert "rate" in call_kwargs or "target_rate" in call_kwargs or "force_tokens" in call_kwargs
