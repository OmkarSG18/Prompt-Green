"""
PromptGreen V2 — Enterprise Embedding & Telemetry Cache Layer.
Provides high-throughput Redis caching for MiniLM prompt embeddings and prompt candidates,
with thread-safe in-memory LRU fallback for zero-budget CPU environments.
"""

import hashlib
import json
import logging
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("promptgreen.cache")


class EmbeddingCacheManager:
    """
    Manages vector embedding caching with SHA-256 text fingerprinting.
    Supports dual-mode execution:
    1. Remote Redis cache (when REDIS_URL is provided and reachable).
    2. Local In-Memory LRU cache (thread-safe, zero-budget CPU fallback).
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl_seconds: int = 86400,
        max_memory_entries: int = 5000,
        key_prefix: str = "pg:emb:"
    ):
        self.requested_url = redis_url or os.environ.get("REDIS_URL")
        self.default_ttl = default_ttl_seconds
        self.max_memory_entries = max_memory_entries
        self.key_prefix = key_prefix

        self.backend = "memory"
        self._redis_client = None
        self._memory_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._lock = threading.Lock()

        # Telemetry counters
        self._hits = 0
        self._misses = 0

        self._init_backend()

    def _init_backend(self):
        """Attempts connection to Redis; falls back to in-memory LRU if unreachable."""
        if self.requested_url:
            try:
                import redis
                client = redis.Redis.from_url(
                    self.requested_url,
                    socket_connect_timeout=2.0,
                    socket_timeout=2.0
                )
                client.ping()
                self._redis_client = client
                self.backend = "redis"
                logger.info(f"EmbeddingCacheManager connected to Redis at: {self._redact_url(self.requested_url)}")
                return
            except Exception as exc:
                logger.warning(
                    f"EmbeddingCacheManager failed connecting to Redis ({exc}). "
                    f"Falling back to thread-safe in-memory LRU cache (max={self.max_memory_entries})."
                )
                self.backend = "memory"
                self._redis_client = None

        self.backend = "memory"
        logger.debug(f"EmbeddingCacheManager initialized with in-memory LRU cache (max={self.max_memory_entries}).")

    @staticmethod
    def _redact_url(url: str) -> str:
        """Masks Redis authentication tokens in logs."""
        try:
            from urllib.parse import urlparse, urlunparse
            p = urlparse(url)
            if p.password:
                netloc = f":***@{p.hostname}:{p.port or ''}"
                return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
            return url
        except Exception:
            return "redis://***"

    def _hash_key(self, text: str) -> str:
        """Computes deterministic SHA-256 fingerprint for input text."""
        normalized = text.strip()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}{digest}"

    # --------------------------------------------------------------------------
    # Single-item operations
    # --------------------------------------------------------------------------

    def get(self, text: str) -> Optional[np.ndarray]:
        """Retrieves cached embedding vector by text."""
        key = self._hash_key(text)

        if self.backend == "redis" and self._redis_client:
            try:
                raw_bytes = self._redis_client.get(key)
                if raw_bytes is not None:
                    with self._lock:
                        self._hits += 1
                    vec = np.frombuffer(raw_bytes, dtype=np.float32)
                    return vec
                with self._lock:
                    self._misses += 1
                return None
            except Exception as e:
                logger.debug(f"Redis get error ({e}), falling back to memory check")

        # In-memory LRU lookup
        with self._lock:
            if key in self._memory_cache:
                self._memory_cache.move_to_end(key)
                self._hits += 1
                return self._memory_cache[key].copy()
            self._misses += 1
            return None

    def set(self, text: str, embedding: np.ndarray, ttl: Optional[int] = None) -> bool:
        """Caches embedding vector for text."""
        key = self._hash_key(text)
        vec_f32 = np.ascontiguousarray(embedding, dtype=np.float32)
        ttl_sec = ttl or self.default_ttl

        if self.backend == "redis" and self._redis_client:
            try:
                self._redis_client.setex(key, ttl_sec, vec_f32.tobytes())
                return True
            except Exception as e:
                logger.debug(f"Redis set error ({e}), mirroring to memory")

        # In-memory LRU storage
        with self._lock:
            if key in self._memory_cache:
                self._memory_cache.move_to_end(key)
            self._memory_cache[key] = vec_f32.copy()
            if len(self._memory_cache) > self.max_memory_entries:
                self._memory_cache.popitem(last=False)
        return True

    # --------------------------------------------------------------------------
    # Batch operations (Vectorized Multi-Get / Multi-Set)
    # --------------------------------------------------------------------------

    def get_many(self, texts: List[str]) -> Dict[str, Optional[np.ndarray]]:
        """
        Retrieves multiple cached embeddings efficiently.
        Returns dict mapping normalized text to numpy embedding or None.
        """
        results: Dict[str, Optional[np.ndarray]] = {}
        if not texts:
            return results

        keys = [self._hash_key(t) for t in texts]

        if self.backend == "redis" and self._redis_client:
            try:
                pipeline = self._redis_client.pipeline()
                for k in keys:
                    pipeline.get(k)
                raw_values = pipeline.execute()

                with self._lock:
                    for t, raw in zip(texts, raw_values):
                        if raw is not None:
                            self._hits += 1
                            results[t] = np.frombuffer(raw, dtype=np.float32)
                        else:
                            self._misses += 1
                            results[t] = None
                return results
            except Exception as e:
                logger.debug(f"Redis pipeline error ({e}), delegating to memory")

        # Memory lookup
        with self._lock:
            for t, k in zip(texts, keys):
                if k in self._memory_cache:
                    self._memory_cache.move_to_end(k)
                    self._hits += 1
                    results[t] = self._memory_cache[k].copy()
                else:
                    self._misses += 1
                    results[t] = None

        return results

    def set_many(self, mapping: Dict[str, np.ndarray], ttl: Optional[int] = None) -> int:
        """
        Stores multiple embeddings into cache via pipeline or memory lock.
        Returns the number of successfully cached items.
        """
        if not mapping:
            return 0

        ttl_sec = ttl or self.default_ttl
        success_count = 0

        if self.backend == "redis" and self._redis_client:
            try:
                pipeline = self._redis_client.pipeline()
                for text, vec in mapping.items():
                    k = self._hash_key(text)
                    vec_f32 = np.ascontiguousarray(vec, dtype=np.float32)
                    pipeline.setex(k, ttl_sec, vec_f32.tobytes())
                pipeline.execute()
                return len(mapping)
            except Exception as e:
                logger.debug(f"Redis pipeline set error ({e})")

        # Memory storage
        with self._lock:
            for text, vec in mapping.items():
                k = self._hash_key(text)
                vec_f32 = np.ascontiguousarray(vec, dtype=np.float32)
                if k in self._memory_cache:
                    self._memory_cache.move_to_end(k)
                self._memory_cache[k] = vec_f32
                if len(self._memory_cache) > self.max_memory_entries:
                    self._memory_cache.popitem(last=False)
                success_count += 1

        return success_count

    # --------------------------------------------------------------------------
    # Maintenance & Diagnostics
    # --------------------------------------------------------------------------

    def clear(self) -> bool:
        """Clears all cached embeddings."""
        with self._lock:
            self._memory_cache.clear()
            self._hits = 0
            self._misses = 0

        if self.backend == "redis" and self._redis_client:
            try:
                # Delete keys matching prefix
                cursor = 0
                while True:
                    cursor, keys = self._redis_client.scan(cursor=cursor, match=f"{self.key_prefix}*", count=500)
                    if keys:
                        self._redis_client.delete(*keys)
                    if cursor == 0:
                        break
                return True
            except Exception as e:
                logger.debug(f"Redis clear error ({e})")
                return False
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry: hits, misses, hit rate, and total cached items."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0
            memory_count = len(self._memory_cache)

        redis_key_count = 0
        if self.backend == "redis" and self._redis_client:
            try:
                redis_key_count = len(self._redis_client.keys(f"{self.key_prefix}*"))
            except Exception:
                pass

        return {
            "backend": self.backend,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "total_requests": total_requests,
            "memory_cache_entries": memory_count,
            "redis_cache_entries": redis_key_count if self.backend == "redis" else 0,
            "max_memory_entries": self.max_memory_entries,
            "default_ttl_seconds": self.default_ttl,
        }


# Global shared instance singleton
_GLOBAL_EMBEDDING_CACHE: Optional[EmbeddingCacheManager] = None
_GLOBAL_CACHE_LOCK = threading.Lock()


def get_embedding_cache() -> EmbeddingCacheManager:
    """Returns the singleton EmbeddingCacheManager instance."""
    global _GLOBAL_EMBEDDING_CACHE
    if _GLOBAL_EMBEDDING_CACHE is None:
        with _GLOBAL_CACHE_LOCK:
            if _GLOBAL_EMBEDDING_CACHE is None:
                _GLOBAL_EMBEDDING_CACHE = EmbeddingCacheManager()
    return _GLOBAL_EMBEDDING_CACHE
