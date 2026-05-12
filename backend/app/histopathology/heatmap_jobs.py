import threading
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


_JOBS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
