"""
Unit and Integration Test Suite for PromptGreen v2.0 Stage 4 Semantic Fidelity Guardrail.
Covers similarity behavior, critical instruction preservation, adaptive retry/rollback,
offline error handling, configuration validation, and real-model execution.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from promptgreen.optimizer.semantic_guard import (
    GuardrailConfig,
    GuardrailMode,
    GuardrailResult,
    LocalMiniLMEmbedder,
    SemanticFidelityGuard,
    compute_cosine_similarity,
)


def create_deterministic_mock_embedder(seed_map: Optional[Dict[str, float]] = None) -> LocalMiniLMEmbedder:
    """
    Creates a deterministic mock embedder that maps specific text patterns
    to predetermined 384-dimensional unit vectors for strict unit testing.
    """
    rng = np.random.default_rng(42)
    base_vector = rng.standard_normal(384).astype(np.float32)
    base_vector /= np.linalg.norm(base_vector)

    orth_vector = rng.standard_normal(384).astype(np.float32)
    orth_vector -= np.dot(orth_vector, base_vector) * base_vector
    orth_vector /= np.linalg.norm(orth_vector)

    def mock_embed_fn(text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 384

        # Check custom seed map
        if seed_map:
            for key, sim_target in seed_map.items():
                if key in text:
                    res = sim_target * base_vector + np.sqrt(max(0.0, 1.0 - sim_target**2)) * orth_vector
                    res /= np.linalg.norm(res)
                    return res.tolist()

        # Unrelated text default has low similarity (~0.10)
        if "unrelated" in text.lower() or "recipe" in text.lower() or "random" in text.lower():
            res = 0.10 * base_vector + np.sqrt(1.0 - 0.10**2) * orth_vector
            return res.tolist()

        # Failing prompts
        if "fail_" in text or "low_sim" in text or "corrupted" in text:
            res = 0.75 * base_vector + np.sqrt(1.0 - 0.75**2) * orth_vector
            return res.tolist()

        # If it's the base original prompt or identical, return base_vector
        return base_vector.tolist()

    return LocalMiniLMEmbedder(custom_client=mock_embed_fn)


# =============================================================================
# GROUP A: SIMILARITY BEHAVIOR
# =============================================================================

def test_1_identical_prompts() -> None:
    """Identical prompts must achieve cosine similarity of exactly 1.0."""
    guard = SemanticFidelityGuard()
    vec = [0.5, 0.5, 0.5, 0.5]
    sim = compute_cosine_similarity(vec, vec)
    assert abs(sim - 1.0) < 1e-5

    # Via Guardrail with mock
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    prompt = "Explain database indexing in simple terms."
    res = guard.evaluate(prompt, prompt)
    assert res.passed is True
    assert res.similarity_score is not None
    assert abs(res.similarity_score - 1.0) < 1e-3
    assert res.rollback_occurred is False


def test_2_slightly_reformatted_prompts() -> None:
    """Slightly reformatted prompts with high similarity pass the guardrail."""
    mock_emb = create_deterministic_mock_embedder({"concise": 0.96})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Explain database indexing in simple terms."
    cand = "Explain database indexing in concise terms."
    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.similarity_score >= 0.92
    assert res.final_prompt == cand


def test_3_meaning_preserving_shorter_prompts() -> None:
    """Meaning-preserving shorter prompt above threshold is accepted."""
    mock_emb = create_deterministic_mock_embedder({"shorter": 0.94})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Could you please explain how to configure nginx reverse proxy?"
    cand = "Explain how to configure nginx reverse proxy (shorter)."
    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.similarity_score >= 0.92
    assert res.final_prompt == cand


def test_4_semantically_unrelated_prompts() -> None:
    """Semantically unrelated prompts below threshold must be rejected."""
    mock_emb = create_deterministic_mock_embedder({"unrelated": 0.25})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Explain how database indexing works."
    cand = "Bake a chocolate cake with chocolate frosting (unrelated)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.similarity_score < 0.92
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert any("below active threshold" in r for r in res.failure_reasons)


def test_5_empty_input() -> None:
    """Empty or whitespace-only inputs must be handled safely without crashing."""
    guard = SemanticFidelityGuard()
    res = guard.evaluate("", "")
    assert res.passed is True
    assert res.final_prompt == ""
    assert res.rollback_occurred is False

    res_ws = guard.evaluate("   ", "   ")
    assert res_ws.passed is True


def test_6_long_prompts() -> None:
    """Long prompts spanning multiple paragraphs must evaluate without truncation errors."""
    mock_emb = create_deterministic_mock_embedder({"long_cand": 0.95})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    long_orig = "Detailed description: " + ("database normalization rules and forms " * 50)
    long_cand = "Detailed description: " + ("database normalization rules and forms " * 45) + " (long_cand)"
    res = guard.evaluate(long_orig, long_cand)
    assert res.passed is True
    assert res.similarity_score is not None
    assert res.guardrail_latency_ms >= 0.0


# =============================================================================
# GROUP B: CRITICAL INSTRUCTION AND STRUCTURAL PRESERVATION
# =============================================================================

def test_7_negation_removal() -> None:
    """Removing a negation ('never', 'not', 'must not') must cause immediate rejection."""
    # Even if similarity is high (0.99), missing negation must trigger failure
    mock_emb = create_deterministic_mock_embedder({"danger": 0.99})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Configure the firewall. Never open port 8080 without SSL."
    cand = "Configure the firewall. Open port 8080 without SSL (danger)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert any("Missing mandatory negation 'never'" in v for v in res.preservation_violations)


def test_8_changed_numerical_constraints() -> None:
    """Modifying or dropping a numerical constraint must cause rejection."""
    mock_emb = create_deterministic_mock_embedder({"changed": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Set max_connections to 100."
    cand = "Set max_connections to 500 (changed)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("Missing numerical constraint/unit '100'" in v for v in res.preservation_violations)


def test_9_changed_units() -> None:
    """Modifying units (e.g. 65s to 65ms) must be caught by preservation check."""
    mock_emb = create_deterministic_mock_embedder({"changed_unit": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Set keepalive_timeout to 65s."
    cand = "Set keepalive_timeout to 65ms (changed_unit)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("65s" in v for v in res.preservation_violations)


def test_10_removed_conditions() -> None:
    """Removing an 'if' or 'unless' condition must cause rejection."""
    mock_emb = create_deterministic_mock_embedder({"no_cond": 0.97})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Restart the server if memory usage exceeds 90%."
    cand = "Restart the server memory usage exceeds 90% (no_cond)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("condition" in v for v in res.preservation_violations)


def test_11_removed_exceptions() -> None:
    """Removing an exception ('except', 'excluding') must cause rejection."""
    mock_emb = create_deterministic_mock_embedder({"no_except": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Delete all logs except production logs."
    cand = "Delete all logs production logs (no_except)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("except" in v for v in res.preservation_violations)


def test_12_changed_json_keys() -> None:
    """Omission or alteration of requested JSON keys must be rejected."""
    mock_emb = create_deterministic_mock_embedder({"bad_keys": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Return only valid JSON with keys hostname, ip_address and port."
    cand = "Return only valid JSON with keys host, ip and port (bad_keys)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("JSON key" in v for v in res.preservation_violations)


def test_13_modified_urls() -> None:
    """Altering or omitting a URL must trigger preservation violation."""
    mock_emb = create_deterministic_mock_embedder({"bad_url": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Verify endpoint at https://api.example.com/v1/health."
    cand = "Verify endpoint at https://api.corrupted.com/v1/health (bad_url)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("URL" in v for v in res.preservation_violations)


def test_14_modified_file_paths() -> None:
    """Altering or omitting a file path must trigger preservation violation."""
    mock_emb = create_deterministic_mock_embedder({"bad_path": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Check system logs in /var/log/syslog for errors."
    cand = "Check system logs in /tmp/log/syslog for errors (bad_path)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("file path" in v for v in res.preservation_violations)


def test_15_modified_programming_identifiers() -> None:
    """Altering a technical constant or variable name must cause rejection."""
    mock_emb = create_deterministic_mock_embedder({"bad_ident": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Catch and handle ERR_CONNECTION_REFUSED gracefully."
    cand = "Catch and handle connection_error gracefully (bad_ident)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("ERR_CONNECTION_REFUSED" in v for v in res.preservation_violations)


def test_16_changed_output_format_requirements() -> None:
    """Dropping a required output format (e.g. table requirement) must cause rejection."""
    mock_emb = create_deterministic_mock_embedder({"no_table": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Compare PostgreSQL and MongoDB in a table."
    cand = "Compare PostgreSQL and MongoDB in paragraphs (no_table)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("output format 'table'" in v for v in res.preservation_violations)


# =============================================================================
# GROUP C: GUARDRAIL DECISIONS & ADAPTIVE RELAXATION
# =============================================================================

def test_17_candidate_above_threshold() -> None:
    """Candidate exceeding active threshold with valid preservation passes."""
    mock_emb = create_deterministic_mock_embedder({"valid": 0.95})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Explain database indexing in simple terms."
    cand = "Explain database indexing clearly and concisely (valid)."
    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.active_threshold == 0.92
    assert res.similarity_score == 0.95
    assert res.rollback_occurred is False
    assert res.final_prompt == cand


def test_18_candidate_below_threshold() -> None:
    """Candidate below active threshold is rejected and rolls back to original."""
    mock_emb = create_deterministic_mock_embedder({"low_sim": 0.88})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Explain database indexing in simple terms."
    cand = "Database indexing summary (low_sim)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.active_threshold == 0.92
    assert res.similarity_score == 0.88
    assert res.rollback_occurred is True
    assert res.final_prompt == orig


def test_19_retry_with_less_aggressive_compression() -> None:
    """
    When aggressive candidate fails threshold, retry loop queries the callback
    with 'balanced' and succeeds when new candidate passes.
    """
    mock_emb = create_deterministic_mock_embedder({"cand_agg": 0.80, "cand_bal": 0.93})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive"), embedder=mock_emb)

    orig = "Explain the detailed architecture of microservices with examples."

    def retry_generator(mode: str, retry_idx: int) -> str:
        if mode == "balanced":
            return "Explain microservices architecture with examples (cand_bal)."
        return "Microservices (cand_agg)."

    res = guard.evaluate(orig, "Microservices (cand_agg).", retry_callback=retry_generator)
    assert res.passed is True
    assert res.retry_count == 1
    assert res.active_threshold == 0.92
    assert res.similarity_score == 0.93
    assert "cand_bal" in res.final_prompt
    assert res.rollback_occurred is False


def test_20_retry_exhaustion() -> None:
    """When all retries fail, retry exhaustion rolls back safely to original prompt."""
    mock_emb = create_deterministic_mock_embedder({"fail_1": 0.70, "fail_2": 0.75, "fail_3": 0.78})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)

    orig = "Explain database indexing in simple terms."

    def always_failing_retry(mode: str, retry_idx: int) -> str:
        return f"Fail prompt {retry_idx} (fail_{retry_idx})."

    res = guard.evaluate(orig, "Initial fail (fail_1).", retry_callback=always_failing_retry)
    assert res.passed is False
    assert res.retry_count == 2
    assert res.rollback_occurred is True
    assert res.final_prompt == orig


def test_21_safe_rollback() -> None:
    """Rollback guarantees that original prompt is restored byte-for-byte."""
    mock_emb = create_deterministic_mock_embedder({"corrupted": 0.40})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Critical command: do not format C:\\ drive."
    cand = "Format drive (corrupted)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.final_prompt == "Critical command: do not format C:\\ drive."


def test_22_missing_embedding_model() -> None:
    """When embedding model is completely unavailable, guardrail fails safely to original prompt."""
    embedder = LocalMiniLMEmbedder(model_name="nonexistent/model")
    embedder._is_available = False
    embedder._status_message = "Mocked model unavailable error for testing"

    guard = SemanticFidelityGuard(embedder=embedder)
    orig = "Explain quantum computing in simple terms."
    cand = "Explain quantum computing simply."
    res = guard.evaluate(orig, cand)

    assert res.passed is False
    assert res.similarity_score is None
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.model_available is False
    assert "unavailable" in res.model_status.lower()


def test_23_embedding_exception() -> None:
    """Runtime exceptions during embedding generation must be caught safely."""
    embedder = LocalMiniLMEmbedder()
    embedder._is_available = True
    embedder.embed = MagicMock(side_effect=RuntimeError("PyTorch OOM or device failure"))

    guard = SemanticFidelityGuard(embedder=embedder)
    orig = "Explain database indexing."
    cand = "Explain indexing."
    res = guard.evaluate(orig, cand)

    assert res.passed is False
    assert res.similarity_score is None
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert any("Embedding generation error" in r for r in res.failure_reasons)


def test_24_invalid_optimization_mode() -> None:
    """Configuring an unknown optimization mode must raise a clear ValueError."""
    with pytest.raises(ValueError, match="Invalid optimization mode 'extreme'"):
        GuardrailConfig(mode="extreme")  # type: ignore


def test_25_invalid_threshold_configuration() -> None:
    """Configuring out-of-bounds or non-numeric thresholds must raise ValueError."""
    with pytest.raises(ValueError, match="Invalid threshold '-0.1'"):
        GuardrailConfig(threshold=-0.1)

    with pytest.raises(ValueError, match="Invalid threshold '1.5'"):
        GuardrailConfig(threshold=1.5)

    with pytest.raises(ValueError, match="Invalid threshold '0.0'"):
        GuardrailConfig(threshold=0.0)


# =============================================================================
# GROUP D: INTERMEDIATE PIPELINE COMPARISON & ADVANCED STRUCTURAL CHECKS
# =============================================================================

def test_26_intermediate_pipeline_stage_comparison() -> None:
    """Stage 4 compares candidate against intermediate pipeline stages."""
    mock_emb = create_deterministic_mock_embedder({
        "s1_pruned": 0.98,
        "s2_compressed": 0.94,
        "s3_shaped": 0.95,
    })
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Could you please explain database indexing in simple terms?"
    intermediate = {
        "stage_1": "Explain database indexing in simple terms (s1_pruned).",
        "stage_2": "Explain database indexing in simple terms (s2_compressed).",
        "stage_3": "Explain database indexing. Organize into short sections (s3_shaped).",
    }
    cand = "Explain database indexing. Organize into short sections (s3_shaped)."

    res = guard.evaluate(orig, cand, intermediate_stages=intermediate)
    assert res.passed is True
    assert "stage_1" in res.stage_similarities
    assert "stage_2" in res.stage_similarities
    assert "stage_3" in res.stage_similarities
    assert res.stage_similarities["stage_1"] == 0.98
    assert res.stage_similarities["stage_2"] == 0.94


def test_27_numerical_range_preservation() -> None:
    """Numerical ranges (e.g. '10-20' or '5 to 10') must be preserved."""
    mock_emb = create_deterministic_mock_embedder({"altered_range": 0.98})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Select between 10-20 sample records."
    cand = "Select between 30-50 sample records (altered_range)."
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("10-20" in v for v in res.preservation_violations)


def test_28_code_block_preservation() -> None:
    """Altering fenced code blocks must cause immediate preservation failure."""
    mock_emb = create_deterministic_mock_embedder({"corrupt_code": 0.99})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Refactor this python script:\n```python\ndef add(a, b): return a + b\n```"
    cand = "Refactor this python script:\n```python\ndef sub(a, b): return a - b\n``` (corrupt_code)"
    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("Fenced code block" in v for v in res.preservation_violations)


def test_29_high_similarity_cannot_override_preservation_violation() -> None:
    """Explicit test: High cosine similarity (e.g. 0.999) cannot override a critical violation."""
    mock_emb = create_deterministic_mock_embedder({"almost_identical": 0.999})
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Export the user accounts. Do not include passwords."
    cand = "Export the user accounts. Include passwords (almost_identical)."
    res = guard.evaluate(orig, cand)
    # Cosine score is 0.999, but negation was removed -> MUST FAIL
    assert res.passed is False
    assert res.similarity_score == 0.999
    assert res.rollback_occurred is True
    assert res.final_prompt == orig


# =============================================================================
# REAL-MODEL SMOKE TEST (SEPARATE & EXPLICIT)
# =============================================================================

def test_30_real_minilm_model_smoke_test() -> None:
    """
    Real-model smoke test on CPU using cached weights if available.
    Explicitly distinguishes real local model execution from deterministic mocks.
    """
    embedder = LocalMiniLMEmbedder()
    is_ready = embedder.initialize()

    if not is_ready:
        pytest.skip(f"Real model skipped: {embedder.status_message}")

    # If real model initialized, verify real forward pass
    text1 = "Explain database indexing in simple terms."
    text2 = "Explain database indexing clearly and concisely."
    text3 = "How to bake a chocolate cake recipe."

    emb1 = embedder.embed(text1)
    emb2 = embedder.embed(text2)
    emb3 = embedder.embed(text3)

    assert isinstance(emb1, np.ndarray)
    assert emb1.shape == (384,)
    assert abs(np.linalg.norm(emb1) - 1.0) < 1e-3

    sim_related = compute_cosine_similarity(emb1, emb2)
    sim_unrelated = compute_cosine_similarity(emb1, emb3)

    # Related prompts must have higher similarity than unrelated prompts
    assert sim_related > sim_unrelated
    assert sim_related > 0.50
    assert sim_unrelated < 0.30


# =============================================================================
# GROUP E: NUMERICAL SAFETY TESTS (TASK 1)
# =============================================================================

def test_31_numerical_safety_nan_input() -> None:
    """Vectors containing NaN values must safely return 0.0 without raising."""
    v1 = [float("nan"), 1.0, 0.5]
    v2 = [1.0, 1.0, 0.5]
    assert compute_cosine_similarity(v1, v2) == 0.0
    assert compute_cosine_similarity(v2, v1) == 0.0
    assert compute_cosine_similarity(v1, v1) == 0.0


def test_32_numerical_safety_pos_infinity() -> None:
    """Vectors containing positive infinity must safely return 0.0."""
    v1 = [float("inf"), 1.0, 0.5]
    v2 = [1.0, 1.0, 0.5]
    assert compute_cosine_similarity(v1, v2) == 0.0


def test_33_numerical_safety_neg_infinity() -> None:
    """Vectors containing negative infinity must safely return 0.0."""
    v1 = [float("-inf"), 1.0, 0.5]
    v2 = [1.0, 1.0, 0.5]
    assert compute_cosine_similarity(v1, v2) == 0.0


def test_34_numerical_safety_zero_vectors() -> None:
    """Zero vectors (norm == 0.0) must safely return 0.0 without division by zero."""
    v_zero = [0.0, 0.0, 0.0]
    v_valid = [1.0, 2.0, 3.0]
    assert compute_cosine_similarity(v_zero, v_valid) == 0.0
    assert compute_cosine_similarity(v_zero, v_zero) == 0.0


def test_35_numerical_safety_different_dimensions() -> None:
    """Vectors of differing dimensions must return 0.0 safely."""
    v1 = [1.0, 2.0]
    v2 = [1.0, 2.0, 3.0]
    assert compute_cosine_similarity(v1, v2) == 0.0


def test_36_numerical_safety_valid_identical_and_unrelated() -> None:
    """Identical vectors return 1.0; orthogonal vectors return 0.0."""
    v1 = [1.0, 2.0, 3.0]
    assert abs(compute_cosine_similarity(v1, v1) - 1.0) < 1e-5
    v_orth1 = [1.0, 0.0]
    v_orth2 = [0.0, 1.0]
    assert abs(compute_cosine_similarity(v_orth1, v_orth2) - 0.0) < 1e-5


def test_37_guardrail_result_never_stores_nan_or_inf() -> None:
    """GuardrailResult must never store NaN or Inf as its similarity score."""
    # Subcase A: Original embedding fails with NaN -> Handled as safe failure with similarity_score=None
    def nan_mock(text: str) -> List[float]:
        return [float("nan")] * 384

    embedder_a = LocalMiniLMEmbedder(custom_client=nan_mock)
    guard_a = SemanticFidelityGuard(embedder=embedder_a)
    res_a = guard_a.evaluate("Explain database indexing.", "Explain database indexing.")
    assert res_a.passed is False
    assert res_a.similarity_score is None
    assert res_a.rollback_occurred is True

    # Subcase B: Candidate embedding produces NaN while original is valid
    base_vec = np.ones(384, dtype=np.float32) / np.sqrt(384)
    def cand_nan_mock(text: str) -> List[float]:
        if "corrupt" in text:
            return [float("nan")] * 384
        return base_vec.tolist()

    embedder_b = LocalMiniLMEmbedder(custom_client=cand_nan_mock)
    guard_b = SemanticFidelityGuard(embedder=embedder_b)
    res_b = guard_b.evaluate("Explain database indexing.", "Explain database indexing (corrupt).")
    assert res_b.passed is False
    assert res_b.similarity_score is not None
    assert np.isfinite(res_b.similarity_score)
    assert res_b.similarity_score == 0.0
    assert res_b.rollback_occurred is True


# =============================================================================
# GROUP F: ADVANCED PRESERVATION REGRESSION TESTS (TASK 2)
# =============================================================================

def test_38_preservation_polarity_inversion() -> None:
    """
    Polarity inversion: swapping negated and non-negated actions must cause rejection.
    Original: 'Do not delete A, but delete B.'
    Candidate: 'Delete A, but do not delete B.'
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Do not delete A, but delete B."
    cand = "Delete A, but do not delete B."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("Polarity inversion" in v for v in violations)


def test_39_preservation_repeated_negation() -> None:
    """
    Repeated negation: dropping one of multiple negations must cause rejection.
    Original: 'Do not format C and do not wipe D.'
    Candidate: 'Do not format C and wipe D.'
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Do not format C and do not wipe D."
    cand = "Do not format C and wipe D."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("Missing mandatory negation" in v or "Polarity inversion" in v for v in violations)


def test_40_preservation_conditional_removal() -> None:
    """
    Conditional removal: dropping the condition predicate of a critical rule must fail.
    Original: 'If the database is unavailable, do not retry.'
    Candidate: 'Do not retry.'
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "If the database is unavailable, do not retry."
    cand = "Do not retry."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("condition" in v.lower() for v in violations)


def test_41_preservation_exception_removal() -> None:
    """
    Exception removal: dropping an exception clause ('except protected files') must fail.
    Original: 'Delete temporary files except protected files.'
    Candidate: 'Delete temporary files.'
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Delete temporary files except protected files."
    cand = "Delete temporary files."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("exception" in v.lower() for v in violations)


def test_42_preservation_numerical_constraints_and_operators() -> None:
    """
    Numerical constraints with operators (<, <=, >=), decimals (0.5s), and units (ms, mb)
    must all be preserved.
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Ensure query latency is < 50ms and memory <= 256mb for 0.5s intervals."
    cand = "Ensure query latency is fast and memory is low."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("< 50ms" in v for v in violations)
    assert any("<= 256mb" in v for v in violations)
    assert any("0.5s" in v for v in violations)


def test_43_preservation_format_inversion() -> None:
    """
    Output-format inversion: candidate explicitly negating required format must fail.
    Original: 'Return the answer in a table.'
    Candidate: 'Never use a table.'
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)
    orig = "Return the answer in a table."
    cand = "Never use a table."
    ok, violations = guard.verify_preservation(orig, cand)
    assert ok is False
    assert any("Output format inversion" in v for v in violations)


def test_44_preservation_json_fields_and_schemas() -> None:
    """
    JSON requirements: checks explicit keys/fields/attributes and raw JSON schema keys.
    """
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)

    # Phrasing with "fields:"
    orig1 = "Return JSON with fields: hostname, port, status."
    cand1 = "Return JSON with fields: hostname and status."
    ok1, viols1 = guard.verify_preservation(orig1, cand1)
    assert ok1 is False
    assert any("port" in v for v in viols1)

    # Raw JSON schema keys
    orig2 = 'Return JSON adhering to schema: {"user_id": 123, "auth_token": "abc"}.'
    cand2 = 'Return JSON with user info.'
    ok2, viols2 = guard.verify_preservation(orig2, cand2)
    assert ok2 is False
    assert any("user_id" in v or "auth_token" in v for v in viols2)


# =============================================================================
# GROUP G: FULL-LENGTH SEMANTIC EVALUATION / CHUNKED EMBEDDING (TASK 3)
# =============================================================================

def test_45_chunked_embedding_under_128_tokens() -> None:
    """Prompt within single chunk limits produces exactly 1 chunk and passes."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for chunking test.")

    text = "Explain database indexing in simple terms."
    chunks = embedder.chunk_text(text)
    assert len(chunks) == 1
    vec = embedder.embed(text)
    assert vec.shape == (384,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-3


def test_46_chunked_embedding_over_128_tokens_identical() -> None:
    """A long prompt (> 128 tokens) chunked across multiple segments evaluates to 1.0 when identical."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for chunking test.")

    long_prompt = (
        "Database indexing is an essential optimization technique in relational systems. "
        "B-trees and hash indexes structure data to minimize disk read operations. "
        "Clustered indexes determine physical row order, while non-clustered indexes provide pointers. "
        "Write operations must update both the table and its associated indexes, incurring overhead. "
        "Careful index design balances read latency against insert and update write penalties. "
    ) * 3

    chunks = embedder.chunk_text(long_prompt)
    assert len(chunks) > 1

    v1 = embedder.embed(long_prompt)
    v2 = embedder.embed(long_prompt)
    sim = compute_cosine_similarity(v1, v2)
    assert abs(sim - 1.0) < 1e-4


def test_47_chunked_embedding_tail_semantic_change() -> None:
    """Semantic change occurring strictly after token 128 is captured by chunked evaluation."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for chunking test.")

    guard = SemanticFidelityGuard(embedder=embedder)

    prefix = (
        "Software architecture requires clear separation of concerns, disciplined layering, and reliable interfaces. "
        "Database access layers encapsulate relational schema queries and object-relational mapping logic. "
        "Service layers orchestrate business rules, domain workflows, and cross-cutting transaction controls. "
        "Presentation layers render user interfaces, validate input schemas, and manage state transitions. "
    ) * 2  # ~110 words, comfortably exceeds 128 tokens

    orig = prefix + "Optimize SQL database indexing for low-latency queries under high concurrent loads."
    cand = prefix + "Bake a layered chocolate cake with cherries, frosting, and sweet confectionery decorations."

    res = guard.evaluate(orig, cand)

    # Candidate must be rejected due to semantic deflection and missing constraints
    assert res.passed is False
    assert res.similarity_score is not None
    assert res.similarity_score < 0.99
    # Chunk similarities must reflect the localized tail divergence
    assert len(res.chunk_similarities) >= 2
    assert res.chunk_similarities[0] >= 0.99
    assert res.chunk_similarities[-1] < 0.85


def test_48_chunked_embedding_tail_negation() -> None:
    """A critical negation appearing after token 128 must be caught by preservation checks."""
    mock_emb = create_deterministic_mock_embedder()
    guard = SemanticFidelityGuard(embedder=mock_emb)

    prefix = "Configure the deployment pipeline with standard linting, static analysis, and packaging. " * 5
    orig = prefix + "Do not push unreviewed code to production."
    cand = prefix + "Push unreviewed code to production."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert any("do not" in v for v in res.preservation_violations)


def test_49_chunked_embedding_final_chunk_divergence() -> None:
    """Prompt where final chunk diverges is captured with chunk-level diagnostics."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for chunking test.")

    guard = SemanticFidelityGuard(embedder=embedder)
    c1 = "Database management systems store structured records efficiently. " * 3
    orig = c1 + "Optimize query execution plans."
    cand = c1 + "Design a fantasy video game environment."

    res = guard.evaluate(orig, cand)
    assert res.chunk_similarities is not None
    if res.chunk_similarities:
        # Final chunk similarity must be significantly lower than initial chunk
        assert res.chunk_similarities[-1] < 0.50


def test_50_chunked_embedding_single_huge_sentence() -> None:
    """A single run-on sentence with no punctuation exceeding chunk limit is sub-chunked safely."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for chunking test.")

    huge_sentence = "word " * 200
    chunks = embedder.chunk_text(huge_sentence, max_words_per_chunk=70)
    assert len(chunks) >= 3
    vec = embedder.embed(huge_sentence)
    assert vec.shape == (384,)
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-3


def test_51_chunked_embedding_empty_and_whitespace_chunks() -> None:
    """Empty and whitespace strings produce empty chunk lists and zero vectors safely."""
    embedder = LocalMiniLMEmbedder()
    assert embedder.chunk_text("") == []
    assert embedder.chunk_text("   \n\t  ") == []
    if embedder.initialize():
        v = embedder.embed("   ")
        assert np.all(v == 0.0)


# =============================================================================
# GROUP H: STAGE 3 SHORT-PROMPT DIRECTIVE DISAMBIGUATION (TASK 4)
# =============================================================================

def test_52_stage3_short_prompt_directive_dilution_rejected_under_strict_policy() -> None:
    """
    STRICT ACADEMIC COMPLIANCE: When Stage 3 formatting directives dilute full prompt
    similarity below 0.92, the candidate must be rejected, even if core task similarity >= 0.92.
    Directive disambiguation telemetries are recorded, but full similarity governs acceptance.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for Stage 3 disambiguation test.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)
    orig = "Explain the concept of database indexing in simple terms."
    cand = "Explain database indexing. Use clear, simple language. Organize the explanation into short sections."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.directive_disambiguation_applied is True
    assert res.core_similarity is not None
    assert res.core_similarity >= 0.92
    assert res.full_prompt_similarity is not None
    assert res.full_prompt_similarity < 0.92
    assert res.similarity_score == res.full_prompt_similarity


def test_53_stage3_short_prompt_harmful_task_change_rejected() -> None:
    """
    If Stage 3 directives are added but the core task is mutated (e.g. database -> baking),
    the guardrail must reject the candidate despite the presence of standard directives.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for Stage 3 disambiguation test.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)
    orig = "Explain the concept of database indexing in simple terms."
    cand = "Bake a chocolate cake with cherries. Use clear, simple language. Organize the explanation into short sections."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig


def test_54_stage3_intermediate_stage_eval_and_directive_separation() -> None:
    """Providing intermediate stages populates stage similarities and assists audit trail."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable for Stage 3 disambiguation test.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)
    orig = "Explain the concept of database indexing in simple terms."
    intermediate = {
        "stage_1": "Explain the concept of database indexing in simple terms.",
        "stage_2": "Explain database indexing.",
    }
    cand = "Explain database indexing. Use clear, simple language. Organize the explanation into short sections."

    res = guard.evaluate(orig, cand, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert "stage_1" in res.stage_similarities
    assert "stage_2" in res.stage_similarities
    assert res.stage_similarities["stage_2"] >= 0.92


# =============================================================================
# GROUP I: RETRY AND API CONTRACT TESTS (TASK 5)
# =============================================================================

def test_55_retry_callback_success() -> None:
    """
    Candidate failing aggressive threshold triggers callback with 'balanced',
    succeeding when regenerated candidate passes.
    """
    mock_emb = create_deterministic_mock_embedder({"cand_agg": 0.80, "cand_bal": 0.93})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive"), embedder=mock_emb)

    orig = "Explain database indexing with examples."

    def retry_gen(mode: str, retry_idx: int) -> str:
        if mode == "balanced":
            return "Explain database indexing with examples (cand_bal)."
        return "Indexing (cand_agg)."

    res = guard.evaluate(orig, "Indexing (cand_agg).", retry_callback=retry_gen)
    assert res.passed is True
    assert res.retry_count == 1
    assert res.final_mode == "balanced"
    assert res.rollback_occurred is False


def test_56_retry_callback_failure_safe_rollback() -> None:
    """Exceptions raised inside retry callback must fail safely and roll back."""
    mock_emb = create_deterministic_mock_embedder({"fail_initial": 0.70})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive"), embedder=mock_emb)

    orig = "Explain database indexing."

    def crashing_callback(mode: str, retry_idx: int) -> str:
        raise RuntimeError("SLM daemon disconnected or OOM occurred.")

    res = guard.evaluate(orig, "Fail (fail_initial).", retry_callback=crashing_callback)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert any("Retry callback execution failed" in r for r in res.failure_reasons)


def test_57_retry_without_callback_standalone_rollback() -> None:
    """Failing candidate without retry_callback rolls back immediately and safely."""
    mock_emb = create_deterministic_mock_embedder({"low_score": 0.75})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)

    orig = "Explain database indexing in simple terms."
    cand = "Indexing summary (low_score)."

    res = guard.evaluate(orig, cand, retry_callback=None)
    assert res.passed is False
    assert res.retry_count == 0
    assert res.rollback_occurred is True
    assert res.final_prompt == orig


def test_58_retry_modes_and_attempt_counts_accurate() -> None:
    """Guardrail accurately reports initial selected_mode, final_mode, and retry attempts."""
    mock_emb = create_deterministic_mock_embedder({"fail_1": 0.70, "fail_2": 0.75})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)

    orig = "Explain database indexing."

    def multi_retry(mode: str, retry_idx: int) -> str:
        return f"Fail candidate {retry_idx} (fail_{retry_idx})."

    res = guard.evaluate(orig, "Fail (fail_1).", retry_callback=multi_retry)
    assert res.passed is False
    assert res.retry_count == 2
    assert res.selected_mode == "aggressive"
    assert res.final_mode == "conservative"
    assert res.rollback_occurred is True


# =============================================================================
# GROUP J: STAGE 5 AUDIT DEFECT REGRESSION TESTS (MAJOR-01, MAJOR-02, DILUTION)
# =============================================================================

def test_59_candidate_duplication_aba_rejected() -> None:
    """
    MAJOR-02 REGRESSION: Candidate reusing an earlier section [A, B, A] from [A, B]
    is rejected due to non-contiguous section reuse and ordering inversion.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )

    orig = sec_a + "\n\n" + sec_b
    cand = sec_a + "\n\n" + sec_b + "\n\n" + sec_a

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("sequence disruption" in r or "Duplicate candidate section" in r for r in res.failure_reasons)


def test_60_candidate_duplication_aab_rejected() -> None:
    """
    MAJOR-02 REGRESSION: Candidate duplicating adjacent section [A, A, B] from [A, B]
    is rejected due to spurious candidate section duplication.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )

    orig = sec_a + "\n\n" + sec_b
    cand = sec_a + "\n\n" + sec_a + "\n\n" + sec_b

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("Spurious candidate section duplication" in r for r in res.failure_reasons)


def test_61_candidate_duplicated_final_section_abb_rejected() -> None:
    """
    MAJOR-02 REGRESSION: Candidate duplicating final section [A, B, B] from [A, B]
    is rejected due to spurious candidate section duplication.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )

    orig = sec_a + "\n\n" + sec_b
    cand = sec_a + "\n\n" + sec_b + "\n\n" + sec_b

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("Spurious candidate section duplication" in r for r in res.failure_reasons)


def test_62_reordered_sequence_cba_rejected() -> None:
    """
    MAJOR-01 REGRESSION: Candidate completely inverting original sections [C, B, A] from [A, B, C]
    is rejected due to sequence disruption and monotonic alignment failure.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )
    sec_c = (
        "Continuous telemetry pipelines ingest structured metrics through distributed message brokers with partitioning. "
        "Alerting rules evaluate sliding time windows to suppress transient anomalies and alert fatigue. "
        "System health dashboards summarize service level indicators and request error rates in real time."
    )

    orig = sec_a + "\n\n" + sec_b + "\n\n" + sec_c
    cand = sec_c + "\n\n" + sec_b + "\n\n" + sec_a

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("sequence disruption" in r for r in res.failure_reasons)


def test_63_partially_reordered_sequence_bac_rejected() -> None:
    """
    MAJOR-01 REGRESSION: Candidate partially inverting original sections [B, A, C] from [A, B, C]
    is rejected due to localized sequence disruption.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )
    sec_c = (
        "Continuous telemetry pipelines ingest structured metrics through distributed message brokers with partitioning. "
        "Alerting rules evaluate sliding time windows to suppress transient anomalies and alert fatigue. "
        "System health dashboards summarize service level indicators and request error rates in real time."
    )

    orig = sec_a + "\n\n" + sec_b + "\n\n" + sec_c
    cand = sec_b + "\n\n" + sec_a + "\n\n" + sec_c

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("sequence disruption" in r for r in res.failure_reasons)


def test_64_legitimate_adjacent_chunk_merge_accepted() -> None:
    """
    MAJOR-01 / MAJOR-02 COMPATIBILITY: Legitimate compression merging adjacent original chunks
    into a concise combined candidate passage is accepted without false rejections.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(threshold=0.82), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )

    orig = sec_a + "\n\n" + sec_b

    # Legitimate compression merging the two sections into candidate sentences with high fidelity
    cand = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability, where synchronous write replication provides zero data loss guarantees. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes. "
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting, while mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.similarity_score is not None
    assert res.similarity_score >= 0.92


def test_65_legitimate_boundary_shift_accepted() -> None:
    """
    MAJOR-01 COMPATIBILITY: Legitimate paragraph boundary shifts that preserve
    full semantic meaning and ordering are accepted.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    sec_a = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees."
    )
    sec_b = (
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints."
    )

    orig = sec_a + "\n\n" + sec_b
    cand = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability.\n\n"
        "Synchronous write replication provides zero data loss guarantees. Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting.\n\n"
        "Mutual certificate verification authenticates microservice endpoints."
    )

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False


def test_66_changed_instruction_sentence_surrounded_by_unchanged_text_rejected() -> None:
    """
    INTRA-CHUNK DILUTION REGRESSION: An altered instruction sentence embedded in a 70-word passage
    with 90% identical surrounding text is caught and rejected by localized sentence validation.
    """
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    prefix = (
        "System performance metrics must be monitored continuously across all distributed compute clusters. "
        "All incoming telemetry spans should be recorded with high fidelity and dispatched to the centralized logging queue. "
    )
    s_orig = "The engineering staff will convene weekly to examine structural latency bottlenecks."
    s_bad = "The tourists traveled along the scenic mountain trail to photograph local wildlife."
    suffix = " Ensure that memory utilization thresholds are enforced at all times."

    orig = prefix + s_orig + suffix
    cand = prefix + s_bad + suffix

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("sentence abandonment" in r or "below active threshold" in r for r in res.failure_reasons)


def test_67_changed_negative_or_conditional_instruction_rejected() -> None:
    """Altered negation or conditional restriction is caught and rejected."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    orig = "When exporting database tables, do not include temporary customer records in the export file."
    cand = "When exporting database tables, include temporary customer records in the export file."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("negation" in r.lower() or "polarity inversion" in r.lower() for r in res.failure_reasons)


def test_68_changed_numerical_requirement_rejected() -> None:
    """Altered numerical latency constraint (e.g. < 50ms changed to < 100ms) is rejected."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    orig = "Configure database pool connections so query latency remains strictly < 50ms."
    cand = "Configure database pool connections so query latency remains strictly < 100ms."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert any("numerical constraint" in r.lower() for r in res.failure_reasons)


def test_69_harmless_sentence_paraphrase_accepted() -> None:
    """Harmless paraphrasing of an instruction sentence with preserved meaning is accepted."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    prefix = (
        "System performance metrics must be monitored continuously across all distributed compute clusters. "
        "All incoming telemetry spans should be recorded with high fidelity and dispatched to the centralized logging queue. "
    )
    s_orig = "The engineering staff will convene weekly to examine structural latency bottlenecks."
    s_good = "Engineering team will meet weekly to review latency bottlenecks."
    suffix = " Ensure that memory utilization thresholds are enforced at all times."

    orig = prefix + s_orig + suffix
    cand = prefix + s_good + suffix

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.similarity_score is not None
    assert res.similarity_score >= 0.92


def test_70_legitimate_sentence_merge_and_split_accepted() -> None:
    """Legitimate sentence merging and splitting that preserves all clauses is accepted."""
    embedder = LocalMiniLMEmbedder()
    if not embedder.initialize():
        pytest.skip("Local model unavailable.")

    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=embedder)

    orig = (
        "Analyze the database schema structure carefully. "
        "Verify that foreign keys are indexed properly across tables. "
        "Generate an execution plan summary report."
    )
    cand = (
        "Analyze the database schema structure carefully and verify foreign keys are properly indexed. "
        "Generate an execution plan summary report."
    )

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.similarity_score is not None
    assert res.similarity_score >= 0.92


# =============================================================================
# GROUP K: STRICT ACADEMIC COMPLIANCE VERIFICATION TESTS (TASK 5)
# =============================================================================

# A. Similarity Boundaries
def test_71_boundary_0_9199_rejected() -> None:
    """Candidate with similarity 0.9199 is strictly below 0.92 quality floor and rejected."""
    mock_emb = create_deterministic_mock_embedder({"cand_9199": 0.9199})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    cand = "Analyze database query performance (cand_9199)."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.similarity_score == 0.9199
    assert res.fallback_type == "original"


def test_72_boundary_0_9200_accepted() -> None:
    """Candidate with similarity exactly 0.9200 meets universal quality floor and is accepted."""
    mock_emb = create_deterministic_mock_embedder({"cand_9200": 0.9200})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    cand = "Analyze database query performance (cand_9200)."

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.final_prompt == cand
    assert res.similarity_score == 0.9200


def test_73_boundary_0_9201_accepted() -> None:
    """Candidate with similarity 0.9201 strictly exceeds universal quality floor and is accepted."""
    mock_emb = create_deterministic_mock_embedder({"cand_9201": 0.9201})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    cand = "Analyze database query performance (cand_9201)."

    res = guard.evaluate(orig, cand)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.final_prompt == cand
    assert res.similarity_score == 0.9201


# B. Aggressive Mode Quality Floor
def test_74_aggressive_mode_0_88_rejected() -> None:
    """Aggressive mode must never lower the quality floor: candidate at 0.88 is rejected."""
    mock_emb = create_deterministic_mock_embedder({"cand_88": 0.88})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive"), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    cand = "Analyze database query performance (cand_88)."

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.active_threshold == 0.92
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.similarity_score == 0.88


def test_75_aggressive_mode_retry_0_93_accepted() -> None:
    """Aggressive mode initial candidate at 0.88 rejected, retry at 0.93 accepted."""
    mock_emb = create_deterministic_mock_embedder({
        "fail_initial": 0.88,
        "cand_retry_93": 0.93,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    cand_init = "Analyze query performance (fail_initial)."

    def retry_gen(relaxed_mode: str, iteration: int) -> str:
        return f"Analyze database query performance plans (cand_retry_93)."

    res = guard.evaluate(orig, cand_init, retry_callback=retry_gen)
    assert res.passed is True
    assert res.retry_count == 1
    assert res.similarity_score == 0.93
    assert res.rollback_occurred is False
    assert "cand_retry_93" in res.final_prompt
    assert res.fallback_type == "stage_2_compressed"


# C. Retention Progression Sequence
def test_76_academic_retention_progression_sequence() -> None:
    """Adaptive Fallback Controller follows tau = 0.40 -> 0.60 -> 0.80 progression."""
    recorded_modes: List[str] = []
    mock_emb = create_deterministic_mock_embedder({
        "cand_40": 0.70,
        "cand_60": 0.82,
        "cand_80": 0.94,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)
    orig = "Software architecture requires clean separation of concerns and disciplined layering."
    cand_init = "Architecture separation concerns (cand_40)."

    def tracking_retry(relaxed_mode: str, iteration: int) -> str:
        recorded_modes.append(relaxed_mode)
        if iteration == 1:
            return "Software architecture requires clean separation of concerns (cand_60)."
        return "Software architecture requires clean separation of concerns and disciplined layering (cand_80)."

    res = guard.evaluate(orig, cand_init, retry_callback=tracking_retry)
    assert recorded_modes == ["balanced", "conservative"]
    assert res.passed is True
    assert res.retry_count == 2
    assert res.similarity_score == 0.94
    assert res.active_retention_rate == 0.80
    assert res.fallback_type == "stage_2_compressed"


# D. Stage 1 Rescue Fallback
def test_77_stage_1_fallback_rescue_accepted() -> None:
    """When compression attempts fail but Stage 1 output has similarity >= 0.92, Stage 1 is accepted."""
    mock_emb = create_deterministic_mock_embedder({
        "s2_fail": 0.75,
        "s1_pruned": 0.988,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Hello, please kindly analyze the database execution plans in detail. Thank you very much."
    s1_pruned = "Analyze the database execution plans (s1_pruned)."
    s2_compressed = "Plans execution (s2_fail)."

    intermediate = {
        "stage_1": s1_pruned,
        "stage_2": s2_compressed,
    }

    res = guard.evaluate(orig, s2_compressed, intermediate_stages=intermediate)
    assert res.passed is True
    assert res.rollback_occurred is False
    assert res.rollback_stage == "stage_1"
    assert res.fallback_type == "stage_1"
    assert res.final_prompt == s1_pruned
    assert res.similarity_score == 0.988


def test_78_stage_1_fallback_fails_original_rollback() -> None:
    """When Stage 1 also fails quality threshold (< 0.92), system rolls back to raw original prompt."""
    mock_emb = create_deterministic_mock_embedder({
        "s2_fail": 0.72,
        "s1_bad": 0.85,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."
    s1_bad = "Query plans (s1_bad)."
    s2_compressed = "Plans (s2_fail)."

    intermediate = {
        "stage_1": s1_bad,
        "stage_2": s2_compressed,
    }

    res = guard.evaluate(orig, s2_compressed, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.rollback_stage == "original"
    assert res.fallback_type == "original"
    assert res.final_prompt == orig


# E. Directive Override Removal & Preservation Gate
def test_79_directive_override_full_0_84_core_0_95_rejected() -> None:
    """Full prompt similarity (0.84) governs acceptance; high core similarity (0.95) does not bypass."""
    mock_emb = create_deterministic_mock_embedder({
        "full_candidate": 0.84,
        "core_stage2": 0.95,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Explain database indexing in simple terms."
    cand = "Explain database indexing (full_candidate). Use clear language. Format as markdown list."
    intermediate = {
        "stage_2": "Explain database indexing (core_stage2).",
    }

    res = guard.evaluate(orig, cand, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert res.core_similarity == 0.95
    assert res.full_prompt_similarity == 0.84
    assert res.similarity_score == 0.84


def test_80_directive_override_full_0_94_preservation_failure_rejected() -> None:
    """Candidate with full similarity 0.94 is rejected when structural preservation is violated."""
    mock_emb = create_deterministic_mock_embedder({"cand_pres_fail": 0.94})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Execute query with timeout 100ms and batch size 32. Verify memory limit 4GB."
    cand = "Execute query with timeout 100ms and batch size 32 (cand_pres_fail)."  # Dropped 4GB

    res = guard.evaluate(orig, cand)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.final_prompt == orig
    assert len(res.preservation_violations) > 0
    assert any("4GB" in v for v in res.preservation_violations)


# F. Telemetry Integrity
def test_81_telemetry_full_similarity_never_overwritten_by_core() -> None:
    """GuardrailResult.similarity_score must always reflect full prompt similarity, never core similarity."""
    mock_emb = create_deterministic_mock_embedder({
        "full_text": 0.87,
        "core_text": 0.96,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Analyze PostgreSQL indexing structures."
    cand = "Analyze PostgreSQL indexing (full_text). Organize output into concise bullet points."
    intermediate = {
        "stage_2": "Analyze PostgreSQL indexing (core_text).",
    }

    res = guard.evaluate(orig, cand, intermediate_stages=intermediate)
    assert res.full_prompt_similarity == 0.87
    assert res.similarity_score == 0.87
    assert res.core_similarity == 0.96
    assert res.similarity_score != res.core_similarity


def test_82_telemetry_fallback_types_and_audit_trail() -> None:
    """Verify fallback_type accurately captures 'none', 'stage_2_compressed', 'stage_1', 'original'."""
    # Scenario 1: Clean pass without retries -> "none"
    mock_emb = create_deterministic_mock_embedder({"clean_cand": 0.95})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    res_none = guard.evaluate("Explain indexing.", "Explain indexing (clean_cand).")
    assert res_none.fallback_type == "none"

    # Scenario 2: Rollback to original -> "original"
    mock_emb_fail = create_deterministic_mock_embedder({"bad_cand": 0.60})
    guard_fail = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb_fail)
    res_orig = guard_fail.evaluate("Explain indexing.", "Explain indexing (bad_cand).")
    assert res_orig.fallback_type == "original"
    assert res_orig.rollback_stage == "original"


# =============================================================================
# GROUP L: STAGE A.1 STRICT ACADEMIC CLOSURE VERIFICATION TESTS
# =============================================================================

# Section 2: Universal 0.92 floor enforcement across custom configurations
def test_83_explicit_threshold_0_88_balanced_enforces_0_92_floor() -> None:
    """Balanced mode with explicit threshold 0.88 must still enforce the universal 0.92 floor."""
    mock_emb = create_deterministic_mock_embedder({
        "cand_9199": 0.9199,
        "cand_9200": 0.9200,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced", threshold=0.88), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."

    # 0.9199 candidate must be rejected despite threshold=0.88
    res_fail = guard.evaluate(orig, "Analyze query plans (cand_9199).")
    assert res_fail.active_threshold == 0.92
    assert res_fail.passed is False
    assert res_fail.rollback_occurred is True

    # 0.9200 candidate must pass the universal floor
    res_pass = guard.evaluate(orig, "Analyze query plans (cand_9200).")
    assert res_pass.active_threshold == 0.92
    assert res_pass.passed is True
    assert res_pass.rollback_occurred is False


def test_84_explicit_threshold_0_90_conservative_enforces_0_92_floor() -> None:
    """Conservative mode with explicit threshold 0.90 must enforce the universal 0.92 floor."""
    mock_emb = create_deterministic_mock_embedder({
        "cand_9199": 0.9199,
        "cand_9200": 0.9200,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="conservative", threshold=0.90), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."

    res_fail = guard.evaluate(orig, "Analyze query plans (cand_9199).")
    assert res_fail.active_threshold == 0.92
    assert res_fail.passed is False
    assert res_fail.rollback_occurred is True

    res_pass = guard.evaluate(orig, "Analyze query plans (cand_9200).")
    assert res_pass.active_threshold == 0.92
    assert res_pass.passed is True
    assert res_pass.rollback_occurred is False


def test_85_explicit_threshold_0_86_aggressive_enforces_0_92_floor() -> None:
    """Aggressive mode with explicit threshold 0.86 must enforce the universal 0.92 floor."""
    mock_emb = create_deterministic_mock_embedder({
        "cand_9199": 0.9199,
        "cand_9200": 0.9200,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", threshold=0.86), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."

    res_fail = guard.evaluate(orig, "Analyze query plans (cand_9199).")
    assert res_fail.active_threshold == 0.92
    assert res_fail.passed is False
    assert res_fail.rollback_occurred is True

    res_pass = guard.evaluate(orig, "Analyze query plans (cand_9200).")
    assert res_pass.active_threshold == 0.92
    assert res_pass.passed is True
    assert res_pass.rollback_occurred is False


def test_86_explicit_threshold_above_default_remains_stricter() -> None:
    """A deliberately configured threshold above mode default (e.g. 0.98) remains stricter."""
    mock_emb = create_deterministic_mock_embedder({
        "cand_97": 0.97,
        "cand_98": 0.98,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="conservative", threshold=0.98), embedder=mock_emb)
    orig = "Analyze database query performance and execution plans."

    # 0.97 is rejected under threshold=0.98
    res_fail = guard.evaluate(orig, "Analyze query plans (cand_97).")
    assert res_fail.active_threshold == 0.98
    assert res_fail.passed is False
    assert res_fail.rollback_occurred is True

    # 0.98 passes
    res_pass = guard.evaluate(orig, "Analyze query plans (cand_98).")
    assert res_pass.active_threshold == 0.98
    assert res_pass.passed is True
    assert res_pass.rollback_occurred is False


# Section 3 & 5: Stage 1 Fallback Completeness & Conservative Operating Threshold
def test_87_stage1_fails_structural_preservation_triggers_original_rollback() -> None:
    """Stage 1 output with high similarity (0.95) but missing a code block fails and rolls back to original."""
    mock_emb = create_deterministic_mock_embedder({
        "s2_fail": 0.70,
        "s1_no_code": 0.95,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Review this implementation:\n```python\nprint('hello')\n```\nEnsure correctness."
    s1_bad = "Review this implementation. Ensure correctness (s1_no_code)."  # dropped code block
    s2_fail = "Review implementation (s2_fail)."

    intermediate = {"stage_1": s1_bad, "stage_2": s2_fail}
    res = guard.evaluate(orig, s2_fail, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.rollback_stage == "original"
    assert res.fallback_type == "original"
    assert res.final_prompt == orig


def test_88_stage1_fails_chunk_validation_triggers_original_rollback() -> None:
    """Stage 1 output failing chunk-level coverage (< chunk_threshold) rolls back to original prompt."""
    mock_emb = create_deterministic_mock_embedder({"s2_fail": 0.70})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced", enable_chunk_validation=True), embedder=mock_emb)
    orig = (
        "Database replication distributes transactional mutations across secondary replicas to safeguard data durability. "
        "Synchronous write replication provides zero data loss guarantees at the cost of higher round-trip commit latency. "
        "Read queries can be directed to local replicas to alleviate connection saturation on primary cluster nodes.\n\n"
        "Network transport encryption requires TLS 1.3 protocol negotiation with strict cipher suite whitelisting. "
        "Mutual certificate verification authenticates microservice endpoints before establishing bidirectional gRPC channels. "
        "All expired session tokens must be immediately revoked across edge gateway proxies."
    )
    # Stage 1 candidate that drops the entire second section (chunk coverage failure)
    s1_dropped_section = "Database replication distributes transactional mutations across secondary replicas to safeguard data durability."
    s2_fail = "Replication distributes mutations (s2_fail)."

    intermediate = {"stage_1": s1_dropped_section, "stage_2": s2_fail}
    res = guard.evaluate(orig, s2_fail, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.rollback_stage == "original"
    assert res.fallback_type == "original"
    assert res.final_prompt == orig


def test_89_stage1_fails_sentence_coverage_triggers_original_rollback() -> None:
    """Stage 1 candidate that abandons an instruction sentence fails sentence coverage and rolls back."""
    mock_emb = create_deterministic_mock_embedder({"s2_fail": 0.70, "tourists": 0.10, "wildlife": 0.10})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced", enable_chunk_validation=True), embedder=mock_emb)
    prefix = "System performance metrics must be monitored continuously across all distributed compute clusters. "
    s_orig = "The engineering staff will convene weekly to examine structural latency bottlenecks."
    s_abandoned = "The tourists traveled along the scenic mountain trail to photograph local wildlife."
    suffix = " Ensure that memory utilization thresholds are enforced at all times."
    orig = prefix + s_orig + suffix
    s1_bad = prefix + s_abandoned + suffix
    s2_fail = "System performance monitored (s2_fail)."

    intermediate = {"stage_1": s1_bad, "stage_2": s2_fail}
    res = guard.evaluate(orig, s2_fail, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.rollback_stage == "original"
    assert res.fallback_type == "original"
    assert res.final_prompt == orig


def test_90_stage1_zero_token_reduction_triggers_original_rollback() -> None:
    """When Stage 1 provides zero token reduction (identical text), it is rejected as an optimization."""
    mock_emb = create_deterministic_mock_embedder({"s2_fail": 0.70})
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"), embedder=mock_emb)
    orig = "Explain the fundamentals of database query optimization and execution plans."
    s1_identical = orig  # Zero token reduction
    s2_fail = "Explain query optimization (s2_fail)."

    intermediate = {"stage_1": s1_identical, "stage_2": s2_fail}
    res = guard.evaluate(orig, s2_fail, intermediate_stages=intermediate)
    assert res.passed is False
    assert res.rollback_occurred is True
    assert res.rollback_stage == "original"
    assert res.fallback_type == "original"
    assert res.final_prompt == orig


def test_91_conservative_mode_stage1_fallback_enforces_0_96_operating_threshold() -> None:
    """Conservative mode operating threshold (0.96) is enforced on Stage 1 rescue: 0.93 fails, 0.97 passes."""
    mock_emb_fail = create_deterministic_mock_embedder({
        "s2_fail": 0.70,
        "s1_93": 0.93,
    })
    guard_cons = SemanticFidelityGuard(config=GuardrailConfig(mode="conservative"), embedder=mock_emb_fail)
    orig = "Hello, please explain database query optimization and execution plans. Thank you."
    s1_93 = "Explain database query optimization execution plans (s1_93)."
    s2_fail = "Query plans (s2_fail)."

    intermediate_fail = {"stage_1": s1_93, "stage_2": s2_fail}
    res_fail = guard_cons.evaluate(orig, s2_fail, intermediate_stages=intermediate_fail)
    assert res_fail.active_threshold == 0.96
    assert res_fail.passed is False
    assert res_fail.rollback_occurred is True
    assert res_fail.fallback_type == "original"

    # Stage 1 with 0.97 meets conservative operating threshold (0.96)
    mock_emb_pass = create_deterministic_mock_embedder({
        "s2_fail": 0.70,
        "s1_97": 0.97,
    })
    guard_cons_pass = SemanticFidelityGuard(config=GuardrailConfig(mode="conservative"), embedder=mock_emb_pass)
    s1_97 = "Explain database query optimization execution plans (s1_97)."
    intermediate_pass = {"stage_1": s1_97, "stage_2": s2_fail}
    res_pass = guard_cons_pass.evaluate(orig, s2_fail, intermediate_stages=intermediate_pass)
    assert res_pass.active_threshold == 0.96
    assert res_pass.passed is True
    assert res_pass.rollback_stage == "stage_1"
    assert res_pass.fallback_type == "stage_1"
    assert res_pass.final_prompt == s1_97


# Section 4: Verification of actual retention-rate argument passed to compressor
def test_92_retry_compressor_receives_exact_target_retention_rates() -> None:
    """Verify that PromptGreenPipeline and LLMLinguaCompressor apply the exact retention sequence (0.40 -> 0.60 -> 0.80)."""
    from unittest.mock import MagicMock
    from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig
    from promptgreen.optimizer.compressor import LLMLinguaCompressor

    mock_llm = MagicMock()
    call_records: List[Dict[str, Any]] = []

    def mock_compress_prompt(context, rate, force_tokens):
        call_records.append({
            "rate": rate,
            "force_tokens": force_tokens,
        })
        if rate == 0.40 or len(call_records) == 1:
            text = "Architecture distributed (cand_fail_40)."
        elif rate == 0.60 or len(call_records) == 2:
            text = "Architecture modular interfaces distributed (cand_fail_60)."
        else:
            text = "Software architecture modular interfaces across systems (cand_pass_80)."
        return {"compressed_prompt": text, "origin_tokens": 35, "compressed_tokens": 10}

    mock_llm.compress_prompt.side_effect = mock_compress_prompt

    comp = LLMLinguaCompressor(llm_lingua_instance=mock_llm)
    mock_emb = create_deterministic_mock_embedder({
        "cand_fail_40": 0.70,
        "cand_fail_60": 0.82,
        "cand_pass_80": 0.95,
    })
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="aggressive", max_retries=2), embedder=mock_emb)
    pipeline = PromptGreenPipeline(
        config=PipelineConfig(mode="aggressive", max_retries=2),
        compressor=comp,
        guardrail=guard,
    )

    prompt = (
        "Software architecture requires clean separation of concerns across all distributed compute "
        "clusters in enterprise cloud environments. All telemetry spans must be recorded with high "
        "fidelity and dispatched to the centralized logging queue to ensure complete observability."
    )

    res = pipeline.optimize(prompt, mode="aggressive")
    assert res.accepted is True
    assert res.retry_count == 2
    assert len(call_records) == 3

    # Initial call (Attempt 0): aggressive mode resolves to 0.40 at the engine point
    assert call_records[0]["rate"] == 0.40

    # Retry 1 (Attempt 1): balanced mode explicit target resolves to 0.60
    assert call_records[1]["rate"] == 0.60

    # Retry 2 (Attempt 2): conservative mode explicit target resolves to 0.80
    assert call_records[2]["rate"] == 0.80

    # Verify pipeline telemetry agrees with effective applied rates
    assert len(res.retry_history) == 2
    assert res.retry_history[0]["retention_rate"] == 0.60
    assert res.retry_history[1]["retention_rate"] == 0.80


