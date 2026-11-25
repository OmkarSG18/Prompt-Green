"""
Unit and Integration Tests for Stage 4 Request-Level Embedding Memoization.
Validates hit/miss mechanics, thread-safety, request lifecycle isolation,
array immutability, exception safety, numerical equivalence, and redundancy reduction.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from promptgreen.optimizer.semantic_guard import (
    GuardrailConfig,
    GuardrailMode,
    GuardrailResult,
    LocalMiniLMEmbedder,
    SemanticFidelityGuard,
    _RequestEmbeddingCache,
    compute_cosine_similarity,
)


def _make_deterministic_mock_client():
    """Create a mock embedding function that counts invocations and produces deterministic vectors."""
    call_counts: Dict[str, int] = {}
    rng = np.random.default_rng(12345)
    base = rng.standard_normal(384).astype(np.float32)
    base /= np.linalg.norm(base)

    def mock_fn(text: str) -> List[float]:
        call_counts[text] = call_counts.get(text, 0) + 1
        # Create unique but deterministic vector based on text length and hash
        h = sum(ord(c) for c in text)
        shift = rng.standard_normal(384).astype(np.float32) * 0.01 * (h % 10)
        vec = base + shift
        vec /= np.linalg.norm(vec)
        return vec.tolist()

    mock_fn.call_counts = call_counts  # type: ignore
    return mock_fn


# ============================================================================
# 1. Hit / Miss Mechanics and Dedup Tests
# ============================================================================


def test_repeated_text_hits_cache_and_avoids_forward_pass():
    """Verify that identical text requests hit the ephemeral cache and do not re-execute encoding."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    test_text = "This is a single-chunk prompt testing memoization fidelity."

    with embedder.request_cache() as cache:
        # First call: miss
        vec1 = embedder.embed(test_text)
        assert cache.text_misses == 1
        assert cache.text_hits == 0
        assert mock_client.call_counts[test_text] == 1

        # Second call: hit
        vec2 = embedder.embed(test_text)
        assert cache.text_hits == 1
        assert mock_client.call_counts[test_text] == 1  # No second invocation!

        # Third call: hit
        vec3 = embedder.embed(test_text)
        assert cache.text_hits == 2
        assert mock_client.call_counts[test_text] == 1

        # Bitwise identical
        np.testing.assert_array_equal(vec1, vec2)
        np.testing.assert_array_equal(vec1, vec3)


def test_distinct_texts_create_distinct_cache_entries():
    """Verify that distinct text strings create separate cache entries with independent embeddings."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    text_a = "First unique prompt instruction for database query optimization."
    text_b = "Second completely different prompt asking for markdown documentation."

    with embedder.request_cache() as cache:
        vec_a = embedder.embed(text_a)
        vec_b = embedder.embed(text_b)

        assert cache.text_misses == 2
        assert cache.text_hits == 0
        assert len(cache.text_cache) == 2
        assert text_a in cache.text_cache
        assert text_b in cache.text_cache
        assert not np.array_equal(vec_a, vec_b)


# ============================================================================
# 2. Lifecycle and Request Isolation Tests
# ============================================================================


def test_request_isolation_and_zero_cross_request_leakage():
    """Verify that the cache is completely discarded when evaluate() exits and leaves no state."""
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"))

    prompt_a = "Optimize the execution time of this SQL query by adding indexes."
    cand_a = "Optimize the execution time of this SQL query by adding indexes."

    # Initial state: active_cache is None
    assert guard.embedder.active_cache is None

    res_a = guard.evaluate(prompt_a, cand_a)
    assert res_a.passed is True
    assert res_a.cache_stats is not None
    assert res_a.cache_stats["total_lookups"] > 0

    # After evaluate(): active_cache is completely cleaned up (None)
    assert guard.embedder.active_cache is None

    # Next independent request with new prompt
    prompt_b = "Translate the following user manual to Spanish."
    cand_b = "Translate the following user manual into Spanish."

    res_b = guard.evaluate(prompt_b, cand_b)
    assert res_b.passed is True
    assert guard.embedder.active_cache is None

    # Verify res_b started with a fresh cache (scoped only to request b)
    assert res_b.cache_stats is not None
    assert res_b.cache_stats["chunk_cached_items"] <= 5


def test_nested_request_cache_reuses_outer_context():
    """Verify that nesting request_cache() reuses the existing active cache and restores safely."""
    embedder = LocalMiniLMEmbedder(custom_client=_make_deterministic_mock_client())

    assert embedder.active_cache is None

    with embedder.request_cache() as outer_cache:
        assert embedder.active_cache is outer_cache
        embedder.embed("Test prompt level 1")

        with embedder.request_cache() as inner_cache:
            assert inner_cache is outer_cache  # Reused
            embedder.embed("Test prompt level 1")  # Hit!
            assert outer_cache.text_hits == 1

        # Still active in outer scope
        assert embedder.active_cache is outer_cache

    # Completely cleared outside
    assert embedder.active_cache is None


# ============================================================================
# 3. Defensive Copy and Immutability Tests
# ============================================================================


def test_immutability_defensive_copies():
    """Verify that mutating a returned embedding vector does not corrupt the cached array."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    test_text = "Prompt testing array immutability and defensive copy guarantees."

    with embedder.request_cache() as cache:
        v1 = embedder.embed(test_text)
        original_first_elem = float(v1[0])

        # Attempt to maliciously mutate caller's array
        v1[0] = 999.0
        assert v1[0] == 999.0

        # Retrieve again from cache
        v2 = embedder.embed(test_text)
        # Must NOT be 999.0!
        assert v2[0] == pytest.approx(original_first_elem, abs=1e-7)
        assert v2[0] != 999.0

        # Verify internal array is write-protected
        cached_internal = cache.text_cache[test_text]
        with pytest.raises((ValueError, RuntimeError)):
            cached_internal[0] = 888.0


# ============================================================================
# 4. Exception Safety Tests
# ============================================================================


def test_exception_safety_does_not_cache_partial_or_corrupt_data():
    """Verify that if embedding generation raises, no corrupted entry is left in cache."""
    failure_triggered = False

    def faulty_client(text: str):
        nonlocal failure_triggered
        if "fail" in text:
            failure_triggered = True
            raise RuntimeError("Synthetic model execution failure!")
        return [0.1] * 384

    embedder = LocalMiniLMEmbedder(custom_client=faulty_client)

    with embedder.request_cache() as cache:
        embedder.embed("Safe valid prompt")
        assert len(cache.text_cache) == 1

        with pytest.raises(RuntimeError, match="Synthetic model execution failure"):
            embedder.embed("This text will fail in model")

        assert failure_triggered is True
        # The failing key must not be in cache
        assert "This text will fail in model" not in cache.text_cache
        assert "This text will fail in model" not in cache.chunk_cache


# ============================================================================
# 5. Thread-Safety and Concurrency Isolation Tests
# ============================================================================


def test_thread_isolation_concurrent_contexts():
    """Verify that concurrent threads running with their own request_cache do not interfere."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    results: Dict[str, Any] = {}
    barrier = threading.Barrier(2)

    def worker(thread_id: str, prompt_text: str):
        barrier.wait()  # Synchronize starts
        with embedder.request_cache() as cache:
            v1 = embedder.embed(prompt_text)
            time.sleep(0.01)  # Interleave
            v2 = embedder.embed(prompt_text)
            results[thread_id] = {
                "hits": cache.text_hits,
                "misses": cache.text_misses,
                "cached_keys": list(cache.text_cache.keys()),
            }

    t1 = threading.Thread(target=worker, args=("T1", "Unique thread 1 prompt text."))
    t2 = threading.Thread(target=worker, args=("T2", "Unique thread 2 prompt text."))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Each thread must have observed exactly 1 hit and 1 miss
    assert results["T1"]["hits"] == 1
    assert results["T1"]["misses"] == 1
    assert results["T1"]["cached_keys"] == ["Unique thread 1 prompt text."]

    assert results["T2"]["hits"] == 1
    assert results["T2"]["misses"] == 1
    assert results["T2"]["cached_keys"] == ["Unique thread 2 prompt text."]


# ============================================================================
# 6. Real-Model Numerical Equivalence Tests
# ============================================================================


def test_numerical_equivalence_cached_vs_uncached_real_model():
    """Verify that cached evaluation produces bit-identical similarity scores and decisions."""
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="balanced"))
    if not guard.embedder.is_available:
        pytest.skip("Offline MiniLM model weights not installed on host.")

    prompt = (
        "Design a RESTful API specification for an e-commerce inventory system. "
        "The system must handle concurrent stock updates, reserve items for 15 minutes, "
        "and return errors with standard HTTP status codes. Provide the response as valid JSON."
    )
    candidate = (
        "Design a RESTful API specification for an e-commerce inventory system. "
        "The system must handle concurrent stock updates, reserve items for 15 minutes, "
        "and return errors with standard HTTP status codes. Format: JSON."
    )

    # 1. Standard evaluation with memoization active
    res_cached = guard.evaluate(prompt, candidate)

    # 2. Evaluation with memoization disabled (bypassed cache)
    # We patch active_cache to None to simulate completely uncached execution
    with patch.object(LocalMiniLMEmbedder, "active_cache", new_callable=lambda: property(lambda self: None)):
        res_uncached = guard.evaluate(prompt, candidate)

    # Must be mathematically identical
    assert res_cached.passed == res_uncached.passed
    assert res_cached.rollback_occurred == res_uncached.rollback_occurred
    assert res_cached.similarity_score == pytest.approx(res_uncached.similarity_score, abs=1e-6)
    assert res_cached.final_prompt == res_uncached.final_prompt
    if res_cached.chunk_coverage and res_uncached.chunk_coverage:
        assert len(res_cached.chunk_coverage) == len(res_uncached.chunk_coverage)
        for c1, c2 in zip(res_cached.chunk_coverage, res_uncached.chunk_coverage):
            assert c1 == pytest.approx(c2, abs=1e-4)


# ============================================================================
# 7. Redundancy Reduction on Long Prompts
# ============================================================================


def test_long_prompt_redundancy_reduction():
    """Verify that on long multi-chunk prompts, memoization eliminates >50% of forward passes."""
    guard = SemanticFidelityGuard(config=GuardrailConfig(mode="conservative"))
    if not guard.embedder.is_available:
        pytest.skip("Offline MiniLM model weights not installed on host.")

    # A long prompt spanning multiple sentences and >200 tokens
    long_prompt = (
        "Perform a comprehensive architectural analysis and security review of an enterprise Kubernetes deployment. "
        "First, analyze the pod security standards and ensure privileged containers are strictly forbidden across all production namespaces. "
        "Second, evaluate the ingress controller configuration, mutual TLS termination, and rate limiting policies. "
        "Third, review network policies to ensure default-deny egress rules are enforced for all database pods. "
        "Fourth, verify that cluster secrets are encrypted at rest using an external KMS provider with automatic key rotation. "
        "Fifth, audit RBAC permissions, service accounts, and cluster role bindings to eliminate wildcard permissions (*). "
        "Sixth, examine container vulnerability scanning pipelines, image signing with Cosign, and admission controllers. "
        "Seventh, assess monitoring, audit logging, Prometheus alerting rules, and SIEM forwarding pipelines. "
        "Eighth, inspect disaster recovery procedures, Velero backup schedules, and cross-region failover protocols. "
        "Format the output as a structured technical assessment table with severity ratings and remediation recommendations."
    )

    candidate = (
        "Perform a comprehensive architectural analysis and security review of an enterprise Kubernetes deployment. "
        "First, analyze pod security standards and ensure privileged containers are strictly forbidden in production namespaces. "
        "Second, evaluate ingress controller configuration, mutual TLS termination, and rate limiting policies. "
        "Third, review network policies to ensure default-deny egress rules are enforced for database pods. "
        "Fourth, verify cluster secrets are encrypted at rest using an external KMS provider with automatic key rotation. "
        "Fifth, audit RBAC permissions, service accounts, and cluster role bindings to eliminate wildcard permissions. "
        "Sixth, examine container vulnerability scanning pipelines, image signing with Cosign, and admission controllers. "
        "Seventh, assess monitoring, audit logging, Prometheus alerting rules, and SIEM forwarding pipelines. "
        "Eighth, inspect disaster recovery procedures, Velero backup schedules, and cross-region failover protocols. "
        "Format output as a structured technical assessment table with severity ratings and remediation recommendations."
    )

    res = guard.evaluate(long_prompt, candidate)

    assert res.cache_stats is not None
    stats = res.cache_stats

    # Verify significant cache hit rate and neural forward pass reduction
    hit_rate = stats["hit_rate"]
    total_hits = stats["total_hits"]
    forward_passes = stats["forward_passes_executed"]
    chunk_hits = stats["chunk_hits"]
    chunk_misses = stats["chunk_misses"]
    total_chunk_requests = chunk_hits + chunk_misses
    forward_pass_reduction = chunk_hits / total_chunk_requests if total_chunk_requests > 0 else 0.0

    assert total_hits > 0, f"Expected cache hits, got {stats}"
    assert forward_pass_reduction >= 0.50, f"Expected >= 50% chunk forward pass reduction on long prompt, got {forward_pass_reduction:.2%}"
    assert hit_rate >= 0.40, f"Expected >= 40% overall hit rate on long prompt, got {hit_rate:.2%}"
    assert forward_passes < stats["total_lookups"], "Forward passes should be strictly less than total lookups"


# ============================================================================
# 8. Edge Cases: Empty Text and embed_chunks Integration
# ============================================================================


def test_empty_and_whitespace_prompt_handling():
    """Verify empty and whitespace strings return zero vectors without corrupting cache."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    with embedder.request_cache() as cache:
        v_empty = embedder.embed("")
        v_space = embedder.embed("   \n\t  ")

        assert np.all(v_empty == 0.0)
        assert np.all(v_space == 0.0)
        assert cache.text_misses == 0
        assert cache.text_hits == 0


def test_embed_chunks_memoization_integration():
    """Verify embed_chunks() hits the chunk cache when chunks were already computed."""
    mock_client = _make_deterministic_mock_client()
    embedder = LocalMiniLMEmbedder(custom_client=mock_client)

    text = "First chunk sentence here. Second chunk sentence here."

    with embedder.request_cache() as cache:
        # Pre-populate via embed
        embedder.embed(text)
        initial_chunk_misses = cache.chunk_misses
        initial_chunk_hits = cache.chunk_hits

        # Now embed_chunks on the same text
        chunks = embedder.embed_chunks(text)
        assert len(chunks) == len(embedder.chunk_text(text))

        # All chunks should hit cache!
        assert cache.chunk_hits > initial_chunk_hits
        assert cache.chunk_misses == initial_chunk_misses
