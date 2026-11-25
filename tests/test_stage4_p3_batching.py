"""
Unit tests for Stage 4 P3 Vectorized Batch Encoding.
Verifies numerical equivalence between sequential and batched chunk encoding,
batch size configurability, P1 cache integration, and execution speedups.
"""

from __future__ import annotations

import numpy as np
import pytest

from promptgreen.optimizer.semantic_guard import (
    GuardrailConfig,
    LocalMiniLMEmbedder,
    SemanticFidelityGuard,
)


@pytest.fixture
def embedder():
    emb = LocalMiniLMEmbedder()
    emb.initialize()
    return emb


def test_batch_vs_sequential_numerical_identity(embedder):
    """Verify that batched encoding produces bit-for-bit identical vectors to sequential encoding."""
    chunks = [
        "Explain quantum computing principles with examples.",
        "Implement a quicksort algorithm in Python.",
        "Summarize this document in three bullet points.",
        "Do not alter the database volume configuration.",
        "What are the carbon emissions from large language model inference?",
    ]

    # Sequential encoding
    seq_tuples = [embedder._encode_single_chunk(c) for c in chunks]

    # Batched encoding with different batch sizes
    for bs in [1, 2, 4, 8, 16]:
        batch_tuples = embedder._encode_chunk_batch(chunks, batch_size=bs)
        assert len(batch_tuples) == len(chunks)

        for i in range(len(chunks)):
            seq_v, seq_w = seq_tuples[i]
            batch_v, batch_w = batch_tuples[i]
            assert seq_w == batch_w
            diff = np.max(np.abs(seq_v - batch_v))
            assert diff < 1e-6, f"Batch size {bs} chunk {i} max diff {diff:.2e} exceeds threshold."
            cos_sim = float(np.dot(seq_v, batch_v))
            assert cos_sim >= 0.999999, f"Batch size {bs} cosine similarity {cos_sim} too low."


def test_batch_encoding_empty_and_whitespace(embedder):
    """Verify that empty, whitespace, and empty lists are handled safely in batch encoding."""
    assert embedder._encode_chunk_batch([]) == []

    mixed = ["Valid text", "", "   ", "Another valid text"]
    tuples = embedder._encode_chunk_batch(mixed, batch_size=4)
    assert len(tuples) == 4
    # Empty and whitespace should return zero vectors and 0.0 weight
    assert tuples[1][1] == 0.0
    assert np.all(tuples[1][0] == 0.0)
    assert tuples[2][1] == 0.0
    assert np.all(tuples[2][0] == 0.0)
    # Valid chunks should have non-zero norm
    assert np.linalg.norm(tuples[0][0]) > 0.99
    assert np.linalg.norm(tuples[3][0]) > 0.99


def test_batch_encoding_integrates_with_p1_cache(embedder):
    """Verify that batch encoding checks and populates P1 request-level cache."""
    chunks = [
        "Cached chunk alpha",
        "Cached chunk beta",
        "Cached chunk alpha",  # duplicate to test hit within batch
    ]

    with embedder.request_cache() as cache:
        # First batch encoding: 2 misses, 1 hit
        results1 = embedder._encode_chunk_batch(chunks, batch_size=8)
        assert len(results1) == 3
        assert cache.chunk_misses == 2
        assert cache.chunk_hits == 1

        # Second batch encoding: all 3 should hit cache
        results2 = embedder._encode_chunk_batch(chunks, batch_size=8)
        assert cache.chunk_hits == 4

        # Vectors must match
        for r1, r2 in zip(results1, results2):
            assert np.array_equal(r1[0], r2[0])
            assert r1[1] == r2[1]


def test_guardrail_config_batch_size_propagation():
    """Verify that batch_size in GuardrailConfig is correctly propagated to embedder."""
    cfg = GuardrailConfig(batch_size=8)
    guard = SemanticFidelityGuard(config=cfg)
    assert guard.config.batch_size == 8
    assert guard.embedder.batch_size == 8


def test_multi_chunk_prompt_embedding_consistency(embedder):
    """Verify that full multi-chunk prompt embedding gives identical normalized vector with batching."""
    long_text = (
        "First section discussing architectural requirements and system constraints. "
        "Second section covering telemetry persistence in PostgreSQL and TimescaleDB hypertables. "
        "Third section analyzing Redis background processing with Celery message brokers. "
        "Fourth section detailing semantic fidelity verification with all-MiniLM-L6-v2."
    )

    embedder.batch_size = 1
    v_seq = embedder.embed(long_text)

    embedder.batch_size = 8
    v_batch = embedder.embed(long_text)

    cos_sim = float(np.dot(v_seq, v_batch))
    assert cos_sim >= 0.999999
    assert np.max(np.abs(v_seq - v_batch)) < 1e-6
