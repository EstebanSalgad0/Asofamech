import threading
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_WORKER_SEMAPHORE: threading.Semaphore | None = None
_WORKER_LIMIT: int | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configured_worker_limit() -> int:
    value = os.getenv("HISTO_MAX_CONCURRENT_HEATMAP_JOBS", "1")
    try:
        parsed = int(value)
    except ValueError:
        return 1
    return max(1, parsed)


def _worker_semaphore() -> threading.Semaphore:
    global _WORKER_LIMIT, _WORKER_SEMAPHORE
    limit = _configured_worker_limit()
    with _LOCK:
        if _WORKER_SEMAPHORE is None or _WORKER_LIMIT != limit:
            _WORKER_LIMIT = limit
            _WORKER_SEMAPHORE = threading.Semaphore(limit)
        return _WORKER_SEMAPHORE


def heatmap_worker_limit() -> int:
    return _configured_worker_limit()


def acquire_heatmap_worker() -> None:
    _worker_semaphore().acquire()


def release_heatmap_worker() -> None:
    _worker_semaphore().release()


def create_heatmap_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    job_id = str(uuid4())
    job = {
        "job_id": job_id,
        "trace_id": payload["trace_id"],
        "status": "queued",
        "progress": 0.0,
        "processed_tiles": 0,
        "total_tiles": 0,
        "created_at": utc_now(),
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None,
        "request": payload["request"],
        "result": None,
        "worker_limit": heatmap_worker_limit(),
    }
    with _LOCK:
        _JOBS[job_id] = job
    return deepcopy(job)


def update_heatmap_job(job_id: str, **updates) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        job.update(updates)
        return deepcopy(job)


def get_heatmap_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return deepcopy(job) if job else None
