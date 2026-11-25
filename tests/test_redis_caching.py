"""
Unit and integration tests for PromptGreen V2 Redis Caching & Background Task Execution.
Verifies EmbeddingCacheManager LRU mechanics, fallback resilience, vector fidelity,
and TaskDispatcher asynchronous/synchronous execution modes.
"""

import numpy as np
import pytest
from promptgreen.cache.redis_cache import EmbeddingCacheManager
from promptgreen.tasks.benchmark_tasks import TaskDispatcher


def test_embedding_cache_memory_lifecycle():
    """Verifies get, set, hits, and misses in memory LRU mode."""
    cache = EmbeddingCacheManager(max_memory_entries=10)
    assert cache.backend == "memory"

    text = "Explain the benefits of renewable energy in datacenters."
    vec = np.random.randn(384).astype(np.float32)
    vec = vec / np.linalg.norm(vec)

    # Initially missing
    assert cache.get(text) is None
    stats = cache.get_stats()
    assert stats["misses"] == 1
    assert stats["hits"] == 0

    # Store in cache
    assert cache.set(text, vec) is True

    # Retrieve from cache
    cached_vec = cache.get(text)
    assert cached_vec is not None
    assert np.allclose(vec, cached_vec, atol=1e-6)

    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["hit_rate"] == 0.5


def test_embedding_cache_batch_operations():
    """Verifies get_many and set_many vector operations."""
    cache = EmbeddingCacheManager(max_memory_entries=50)
    texts = [f"Prompt sample number {i}" for i in range(5)]
    vectors = {
        t: (np.random.randn(384) / 10.0).astype(np.float32)
        for t in texts
    }

    # Batch set
    cached_count = cache.set_many(vectors)
    assert cached_count == 5

    # Batch get
    retrieved = cache.get_many(texts + ["Unseen prompt"])
    assert len(retrieved) == 6
    assert retrieved["Unseen prompt"] is None

    for t in texts:
        assert retrieved[t] is not None
        assert np.allclose(vectors[t], retrieved[t], atol=1e-6)


def test_embedding_cache_lru_eviction():
    """Verifies that LRU properly drops oldest entries when limit is exceeded."""
    max_items = 5
    cache = EmbeddingCacheManager(max_memory_entries=max_items)

    for i in range(10):
        vec = np.full(384, float(i), dtype=np.float32)
        cache.set(f"item_{i}", vec)

    stats = cache.get_stats()
    assert stats["memory_cache_entries"] == max_items

    # Earliest items (0-4) should have been evicted
    assert cache.get("item_0") is None
    assert cache.get("item_1") is None

    # Latest items (5-9) must be present
    assert cache.get("item_9") is not None
    assert cache.get("item_8") is not None


def test_unreachable_redis_fallback():
    """Verifies graceful fallback to memory when given an unreachable Redis URL."""
    fake_redis_url = "redis://:invalid_pass@127.0.0.1:63999/0"
    cache = EmbeddingCacheManager(redis_url=fake_redis_url)

    # Must fall back cleanly to memory
    assert cache.backend == "memory"

    # Should function identically without errors
    dummy_vec = np.ones(384, dtype=np.float32)
    assert cache.set("test_fallback", dummy_vec) is True
    res = cache.get("test_fallback")
    assert res is not None
    assert np.allclose(res, dummy_vec)


def test_task_dispatcher_synchronous_fallback():
    """Verifies that TaskDispatcher runs cleanly in synchronous mode when broker is offline."""
    dispatcher = TaskDispatcher(broker_url="redis://127.0.0.1:63999/0")
    assert dispatcher.is_broker_available() is False

    prompts = [
        "Please compare SQL and NoSQL in detail.",
        "List 3 docker commands to build a container."
    ]
    res = dispatcher.dispatch_batch_optimization(prompts, mode="balanced", run_async=True)

    assert res["status"] == "COMPLETED"
    assert res["mode"] == "synchronous_fallback"
    assert res["total_prompts"] == 2
    assert res["total_tokens_saved"] >= 0
    assert len(res["items"]) == 2

    # Check status lookup
    task_id = res["task_id"]
    status_info = dispatcher.get_task_status(task_id)
    assert status_info["status"] == "COMPLETED"
    assert status_info["total_prompts"] == 2
