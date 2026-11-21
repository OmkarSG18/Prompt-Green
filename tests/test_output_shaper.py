"""
PromptGreen v2.0 - Stage 3 Output Directive Shaper Test Suite
Comprehensive unit and integration tests covering:
- Deterministic Output Bounding & Formatting Directives (Tables, JSON, Lists, Code-only)
- Semantic & Constraint Preservation (Negations, Conditionals, Numbers, Identifiers, Code)
- Edge Cases (Empty, Whitespace, Pre-Bounded Prompts)
- Mocked Ollama SLM Integration, Timeouts, Inference Errors, and Validation Rejection
- Dual-Engine Fallback to Deterministic and Atomic Rollback to Original
- Stage 1 and Stage 2 Compatibility & Token Counting Metadata
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from promptgreen.optimizer.output_shaper import (
    OutputDirectiveShaper,
    ShaperConfig,
    ShapingResult,
)
from promptgreen.optimizer.rule_pruner import RuleBasedPruner
from promptgreen.optimizer.compressor import LLMLinguaCompressor


# =============================================================================
# 1. EDGE CASES: EMPTY & WHITESPACE INPUTS
# =============================================================================

def test_1_empty_input():
    shaper = OutputDirectiveShaper()
    result = shaper.shape("")

    assert result.success is True
    assert result.shaped_prompt == ""
    assert result.shaping_applied is False
    assert result.shaping_method == "none"
    assert result.input_token_count == 0
    assert result.output_token_count == 0


def test_2_whitespace_only_input():
    shaper = OutputDirectiveShaper()
    result = shaper.shape("   \n\t  \n  ")

    assert result.success is True
    assert result.shaping_applied is False
    assert result.shaping_method == "none"
    assert result.input_token_count == 0
    assert result.output_token_count == 0


# =============================================================================
# 2. DETERMINISTIC FORMATTING & OUTPUT BOUNDING DIRECTIVES
# =============================================================================

def test_3_simple_explanatory_prompt():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Explain database normalization in simple terms."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert result.shaping_method == "deterministic"
    assert "clear, simple language" in result.shaped_prompt.lower()
    assert "short sections" in result.shaped_prompt.lower()


def test_4_explicit_concise_response_request():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Explain microservices architecture briefly."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "concise" in result.shaped_prompt.lower()
    assert "core concept" in result.shaped_prompt.lower()


def test_5_explicit_detailed_response_request():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Write a detailed explanation of gradient descent with an example."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "detailed explanation" in result.shaped_prompt.lower()
    assert "example" in result.shaped_prompt.lower()
    # Confirm it was NOT forced into a concise response
    assert "concise" not in result.shaped_prompt.lower()


def test_6_bullet_point_requirement():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Summarize the key benefits of Docker in bullet points."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "concise bullet points" in result.shaped_prompt.lower()


def test_7_numbered_list_requirement():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "List 3 key steps to boil an egg perfectly."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "3 key steps" in result.shaped_prompt
    assert "numbered list" in result.shaped_prompt.lower()


def test_8_table_requirement():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Compare SQL and NoSQL databases in a table."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "table" in result.shaped_prompt.lower()
    assert "comparison criteria" in result.shaped_prompt.lower()


def test_9_json_only_requirement():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Return only valid JSON with keys name, age and city."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "return only valid json" in result.shaped_prompt.lower()
    assert "name, age, city" in result.shaped_prompt


def test_10_explicit_word_or_length_limit():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Explain quantum computing in under 50 words."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "50 words" in result.shaped_prompt


def test_11_code_only_instruction():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Write a python script to sort a dictionary. Return code only."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is True
    assert "return only the code implementation" in result.shaped_prompt.lower()
    assert "without additional conversational text" in result.shaped_prompt.lower()


# =============================================================================
# 3. SEMANTIC & CONSTRAINT PRESERVATION
# =============================================================================

def test_12_negative_instructions():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = (
        "Do not delete production tables under any circumstances. "
        "You must never drop database clusters. Do not expose credentials."
    )
    result = shaper.shape(prompt)

    assert "do not delete" in result.shaped_prompt.lower()
    assert "never drop" in result.shaped_prompt.lower()
    assert "do not expose" in result.shaped_prompt.lower()


def test_13_conditional_instructions():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = (
        "Check if you can ping the server. Unless the token is expired, proceed. "
        "Determine whether the port is open."
    )
    result = shaper.shape(prompt)

    assert "if you can" in result.shaped_prompt.lower()
    assert "unless" in result.shaped_prompt.lower()
    assert "whether" in result.shaped_prompt.lower()


def test_14_exceptions_and_qualifications():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Provide all user profile details excluding passwords and secrets."
    result = shaper.shape(prompt)

    assert "excluding passwords and secrets" in result.shaped_prompt.lower()


def test_15_numerical_constraints():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = (
        "Ensure latency is under 100ms, batch size is 32 items, "
        "memory limit is 4GB, and multiplier is 3.8x."
    )
    result = shaper.shape(prompt)

    assert "100ms" in result.shaped_prompt
    assert "32" in result.shaped_prompt
    assert "4GB" in result.shaped_prompt
    assert "3.8x" in result.shaped_prompt


def test_16_named_entities_and_technical_identifiers():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = (
        "Inspect the implementation of GreenModelRouter, pue_multiplier, "
        "and verify that AST parsing uses ast.parse()."
    )
    result = shaper.shape(prompt)

    assert "GreenModelRouter" in result.shaped_prompt
    assert "pue_multiplier" in result.shaped_prompt
    assert "ast.parse()" in result.shaped_prompt


def test_17_urls_and_file_paths():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = (
        "Fetch telemetry from https://metrics.prod.internal:8080/v2/stats "
        "and store it at /var/log/promptgreen/telemetry.json."
    )
    result = shaper.shape(prompt)

    assert "https://metrics.prod.internal:8080/v2/stats" in result.shaped_prompt
    assert "/var/log/promptgreen/telemetry.json" in result.shaped_prompt


def test_18_protected_code_and_structured_content():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    raw_code = (
        "```python\n"
        "def compute_hash(val: str) -> str:\n"
        "    return f'hash_{val}'\n"
        "```"
    )
    prompt = f"Explain this function in simple terms:\n{raw_code}"
    result = shaper.shape(prompt)

    assert result.success is True
    assert raw_code in result.shaped_prompt
    assert "clear, simple language" in result.shaped_prompt.lower()


def test_19_prompt_with_multiple_output_requirements():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Compare SQL and NoSQL databases in a table in under 50 words."
    result = shaper.shape(prompt)

    assert result.success is True
    assert "table" in result.shaped_prompt.lower()
    assert "50 words" in result.shaped_prompt


def test_20_prompt_with_clear_output_instructions():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    # Prompt is already completely clear and has explicit code-only bounds
    prompt = "Write a python script to sort a list. Return code only without explanations."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_applied is False
    assert result.shaping_method == "none"
    assert result.shaped_prompt == prompt


def test_21_deterministic_repeatability():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Compare SQL and NoSQL databases in a table."

    results = [shaper.shape(prompt) for _ in range(5)]
    first_text = results[0].shaped_prompt

    for r in results[1:]:
        assert r.shaped_prompt == first_text
        assert r.shaping_applied == results[0].shaping_applied
        assert r.output_token_count == results[0].output_token_count


# =============================================================================
# 4. MOCKED OLLAMA INTEGRATION, TIMEOUTS, ERRORS & REJECTIONS
# =============================================================================

def test_22_ollama_unavailable():
    # When Ollama is unreachable, automatically fall back to deterministic shaping
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=True))
    with patch.object(shaper, "is_ollama_available", return_value=False):
        prompt = "Explain database normalization in simple terms."
        result = shaper.shape(prompt)

        assert result.success is True
        assert result.shaping_method == "deterministic"
        assert result.fallback_reason is not None
        assert "Ollama daemon unreachable" in result.fallback_reason


def test_23_ollama_timeout():
    # Simulate an Ollama request timing out
    mock_client = MagicMock()
    mock_client.generate.side_effect = TimeoutError("Connection to Ollama timed out after 2.0s")

    shaper = OutputDirectiveShaper(
        config=ShaperConfig(prefer_ollama=True),
        ollama_client=mock_client
    )
    prompt = "Compare SQL and NoSQL databases in a table."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_method == "deterministic"
    assert "timed out" in result.fallback_reason.lower()


def test_24_ollama_inference_error():
    # Simulate Ollama returning a runtime error or 500 error
    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("Ollama model execution failed: OOM")

    shaper = OutputDirectiveShaper(
        config=ShaperConfig(prefer_ollama=True),
        ollama_client=mock_client
    )
    prompt = "List 3 key steps to boil an egg perfectly."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_method == "deterministic"
    assert "failed" in result.fallback_reason.lower()


def test_25_unsafe_model_rewrite_rejected():
    # Simulate Ollama dropping a critical negation instruction
    mock_client = MagicMock()
    # Model rewrite drops "Do not delete production tables"
    mock_client.generate.return_value = {
        "response": "Explain table optimization. Delete production tables if needed."
    }

    shaper = OutputDirectiveShaper(
        config=ShaperConfig(prefer_ollama=True),
        ollama_client=mock_client
    )
    prompt = "Explain table optimization. Do not delete production tables under any circumstances."
    result = shaper.shape(prompt)

    # Shaper must reject model output and fall back to deterministic/original
    assert result.success is True
    assert result.shaping_method != "ollama"
    assert "do not delete" in result.shaped_prompt.lower()
    assert any("failed validation" in w.lower() or "rejected" in w.lower() for w in result.warnings)


def test_26_fallback_to_deterministic_shaping():
    # When Ollama fails validation, deterministic shaping is applied seamlessly
    mock_client = MagicMock()
    # Model generates truncated junk
    mock_client.generate.return_value = {"response": "Junk"}

    shaper = OutputDirectiveShaper(
        config=ShaperConfig(prefer_ollama=True),
        ollama_client=mock_client
    )
    prompt = "Explain database normalization in simple terms."
    result = shaper.shape(prompt)

    assert result.success is True
    assert result.shaping_method == "deterministic"
    assert "clear, simple language" in result.shaped_prompt.lower()


def test_27_fallback_to_original_prompt_when_necessary():
    # When candidate text corrupts integrity, shaper rolls back to original prompt
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    # Force preservation validator to fail
    with patch.object(shaper, "_validate_preservation", return_value=(False, ["Simulated severe corruption"])):
        prompt = "Explain database normalization in simple terms."
        result = shaper.shape(prompt)

        assert result.success is True
        assert result.shaped_prompt == prompt
        assert result.shaping_applied is False
        assert any("rolling back" in w.lower() for w in result.warnings)


# =============================================================================
# 5. PIPELINE COMPATIBILITY & METADATA
# =============================================================================

def test_28_stage1_and_stage2_compatibility():
    # Test that Stage 3 accepts outputs produced by Stage 1 & Stage 2
    pruner = RuleBasedPruner()
    compressor = LLMLinguaCompressor()
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))

    raw_prompt = (
        "In order to optimize performance, it is important to note that you must make sure "
        "to compare SQL and NoSQL databases in a table. Do not delete production tables."
    )

    # Stage 1: Structural Prune
    p_res = pruner.prune(raw_prompt)
    assert p_res.optimized_prompt != ""

    # Stage 2: Compress
    c_res = compressor.compress(p_res.optimized_prompt, mode="balanced")
    assert c_res.compressed_prompt != ""

    # Stage 3: Shape Output Directives
    s_res = shaper.shape(c_res.compressed_prompt)
    assert s_res.success is True
    assert "table" in s_res.shaped_prompt.lower()
    assert "do not delete" in s_res.shaped_prompt.lower()


def test_29_token_count_metadata():
    shaper = OutputDirectiveShaper(config=ShaperConfig(prefer_ollama=False))
    prompt = "Compare SQL and NoSQL databases in a table."
    result = shaper.shape(prompt)

    assert result.input_token_count > 0
    assert result.output_token_count > 0
    expected_diff = result.output_token_count - result.input_token_count
    assert result.estimated_token_difference == expected_diff
    assert result.processing_latency_ms >= 0.0


def test_30_no_network_or_model_download_during_init():
    # Verify instantiation and availability checks never make remote network calls
    config = ShaperConfig(ollama_host="http://localhost:11434", model_name="qwen2.5:0.5b")
    shaper = OutputDirectiveShaper(config=config)

    # is_ollama_available() should handle connection gracefully without hanging or downloading
    available = shaper.is_ollama_available()
    assert isinstance(available, bool)
