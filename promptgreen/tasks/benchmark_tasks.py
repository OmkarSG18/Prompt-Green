"""
PromptGreen V2 — Background Processing and Celery Task Infrastructure.
Provides asynchronous job dispatch for batch prompt benchmarking, continuous aggregate refresh,
and telemetry exports, with seamless synchronous fallback when broker is offline.
"""

import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from concurrent.futures import ThreadPoolExecutor

from celery import Celery

logger = logging.getLogger("promptgreen.tasks")

# Initialize Celery app instance
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL") or os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND") or os.environ.get("REDIS_URL") or "redis://localhost:6379/0"

celery_app = Celery("promptgreen_tasks", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="promptgreen.tasks.run_batch_optimization", bind=True)
def run_batch_optimization(self, prompts: List[str], mode: str = "balanced") -> Dict[str, Any]:
    """
    Celery background worker task: optimizes a batch of prompts and records telemetry.
    """
    from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig
    from promptgreen.ledger.database import PromptLedger, OptimizationEvent

    pipeline = PromptGreenPipeline(PipelineConfig())
    ledger = PromptLedger()

    results = []
    total_tokens_saved = 0
    total_latency_ms = 0.0

    for idx, prompt_text in enumerate(prompts):
        start_t = time.perf_counter()
        opt_res = pipeline.optimize(prompt_text, mode=mode)
        latency = (time.perf_counter() - start_t) * 1000.0

        saved = max(0, opt_res.original_token_count - opt_res.final_token_count)
        total_tokens_saved += saved
        total_latency_ms += latency

        evt = OptimizationEvent(
            event_id=f"task_{self.request.id[:8]}_{idx}",
            original_text=prompt_text,
            optimized_text=opt_res.final_prompt,
            original_tokens=opt_res.original_token_count,
            optimized_tokens=opt_res.final_token_count,
            tokens_saved=saved,
            compression_ratio=(opt_res.final_token_count / max(1, opt_res.original_token_count)),
            semantic_similarity=opt_res.semantic_similarity or 1.0,
            optimization_latency_ms=latency,
            pipeline_stages_applied=mode,
        )
        ledger.record_optimization_event(evt)
        results.append({
            "index": idx,
            "original_tokens": opt_res.original_token_count,
            "optimized_tokens": opt_res.final_token_count,
            "tokens_saved": saved,
            "latency_ms": round(latency, 2),
        })

    return {
        "task_id": self.request.id,
        "total_prompts": len(prompts),
        "total_tokens_saved": total_tokens_saved,
        "average_latency_ms": round(total_latency_ms / len(prompts), 2) if prompts else 0.0,
        "items": results,
    }


@celery_app.task(name="promptgreen.tasks.export_telemetry_dataset")
def export_telemetry_dataset(output_path: str, format: str = "json") -> Dict[str, Any]:
    """
    Exports telemetry records to a structured artifact.
    """
    from promptgreen.ledger.database import PromptLedger
    ledger = PromptLedger()
    records = ledger.get_recent_records(limit=1000)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    return {
        "status": "COMPLETED",
        "record_count": len(records),
        "output_path": output_path,
        "format": format
    }


class TaskDispatcher:
    """
    Dispatches compute-intensive workloads to Celery if broker is reachable,
    or falls back to synchronous local execution if offline (zero-budget CPU safety).
    """

    def __init__(self, broker_url: Optional[str] = None):
        self.broker_url = broker_url or CELERY_BROKER_URL
        self._sync_task_store: Dict[str, Dict[str, Any]] = {}

    def is_broker_available(self) -> bool:
        """Tests whether Celery Redis/AMQP broker is reachable within 1 second."""
        try:
            import redis
            from urllib.parse import urlparse
            p = urlparse(self.broker_url)
            if p.scheme in ("redis", "rediss"):
                r = redis.Redis.from_url(self.broker_url, socket_connect_timeout=1.0, socket_timeout=1.0)
                r.ping()
                return True
        except Exception:
            pass
        return False

    def dispatch_batch_optimization(
        self,
        prompts: List[str],
        mode: str = "balanced",
        run_async: bool = True
    ) -> Dict[str, Any]:
        """Dispatches batch optimization to Celery async worker or synchronous fallback."""
        if run_async and self.is_broker_available():
            try:
                async_res = run_batch_optimization.delay(prompts, mode=mode)
                return {
                    "task_id": async_res.id,
                    "status": "QUEUED",
                    "mode": "celery_async",
                    "prompts_count": len(prompts)
                }
            except Exception as e:
                logger.warning(f"Failed enqueueing to Celery ({e}). Running synchronous fallback.")

        # Synchronous fallback execution
        task_id = f"sync_{uuid.uuid4().hex[:10]}"
        start_t = time.perf_counter()

        from promptgreen.optimizer.pipeline import PromptGreenPipeline, PipelineConfig
        pipeline = PromptGreenPipeline(PipelineConfig())
        items = []
        total_saved = 0

        for idx, prompt_text in enumerate(prompts):
            t0 = time.perf_counter()
            res = pipeline.optimize(prompt_text, mode=mode)
            lat = (time.perf_counter() - t0) * 1000.0
            saved = max(0, res.original_token_count - res.final_token_count)
            total_saved += saved
            items.append({
                "index": idx,
                "original_tokens": res.original_token_count,
                "optimized_tokens": res.final_token_count,
                "tokens_saved": saved,
                "latency_ms": round(lat, 2)
            })

        total_lat = (time.perf_counter() - start_t) * 1000.0
        result_payload = {
            "task_id": task_id,
            "status": "COMPLETED",
            "mode": "synchronous_fallback",
            "total_prompts": len(prompts),
            "total_tokens_saved": total_saved,
            "elapsed_ms": round(total_lat, 2),
            "items": items
        }
        self._sync_task_store[task_id] = result_payload
        return result_payload

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Queries status of either a Celery task or a locally-stored synchronous task."""
        if task_id in self._sync_task_store:
            return self._sync_task_store[task_id]

        try:
            from celery.result import AsyncResult
            res = AsyncResult(task_id, app=celery_app)
            status_dict = {
                "task_id": task_id,
                "status": res.status,
                "mode": "celery_async",
                "ready": res.ready(),
                "successful": res.successful() if res.ready() else False,
            }
            if res.ready() and res.successful():
                status_dict["result"] = res.result
            return status_dict
        except Exception as e:
            return {"task_id": task_id, "status": "UNKNOWN", "error": str(e)}
