import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


_WORKER_SEMAPHORE: threading.Semaphore | None = None
_WORKER_LIMIT: int | None = None
_SEM_LOCK = threading.Lock()


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
    with _SEM_LOCK:
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _job_to_dict(job) -> Dict[str, Any]:
    def _iso(dt):
        return dt.isoformat() if dt else None

    return {
        "job_id": job.job_id,
        "trace_id": job.trace_id,
        "status": job.status,
        "progress": job.progress,
        "processed_tiles": job.processed_tiles,
        "total_tiles": job.total_tiles,
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "completed_at": _iso(job.completed_at),
        "failed_at": _iso(job.failed_at),
        "error": job.error,
        "request": job.request_json,
        "result": job.result_json,
        "worker_limit": job.worker_limit,
    }


def create_heatmap_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    from ..db import SessionLocal
    from ..models import HeatmapJob

    job_id = str(uuid4())
    db = SessionLocal()
    try:
        job = HeatmapJob(
            job_id=job_id,
            trace_id=payload["trace_id"],
            status="queued",
            progress=0.0,
            processed_tiles=0,
            total_tiles=0,
            created_at=_utc_now(),
            request_json=payload["request"],
            worker_limit=heatmap_worker_limit(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return _job_to_dict(job)
    finally:
        db.close()


def update_heatmap_job(job_id: str, **updates) -> Optional[Dict[str, Any]]:
    from ..db import SessionLocal
    from ..models import HeatmapJob

    db = SessionLocal()
    try:
        job = db.query(HeatmapJob).filter(HeatmapJob.job_id == job_id).first()
        if not job:
            return None
        field_map = {
            "status": "status",
            "progress": "progress",
            "processed_tiles": "processed_tiles",
            "total_tiles": "total_tiles",
            "started_at": "started_at",
            "completed_at": "completed_at",
            "failed_at": "failed_at",
            "error": "error",
            "result": "result_json",
        }
        for key, value in updates.items():
            col = field_map.get(key, key)
            if hasattr(job, col):
                setattr(job, col, value)
        db.commit()
        db.refresh(job)
        return _job_to_dict(job)
    finally:
        db.close()


def get_heatmap_job(job_id: str) -> Optional[Dict[str, Any]]:
    from ..db import SessionLocal
    from ..models import HeatmapJob

    db = SessionLocal()
    try:
        job = db.query(HeatmapJob).filter(HeatmapJob.job_id == job_id).first()
        return _job_to_dict(job) if job else None
    finally:
        db.close()
