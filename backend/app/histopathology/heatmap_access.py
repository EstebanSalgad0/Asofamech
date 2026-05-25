import os
import threading
import time
from typing import Dict, List, Tuple


_RATE_LOCK = threading.Lock()
_RATE_BUCKETS: Dict[str, List[float]] = {}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def normalize_role(role: str | None) -> str:
    value = (role or "").strip().lower()
    aliases = {
        "admin": "administrador",
        "administrator": "administrador",
        "administrador": "administrador",
        "profesor": "profesor",
        "profesora": "profesor",
        "docente": "profesor",
        "teacher": "profesor",
        "estudiante": "estudiante",
        "student": "estudiante",
    }
    return aliases.get(value, "estudiante")


def is_privileged_role(role: str | None) -> bool:
    return normalize_role(role) in {"administrador", "profesor"}


def max_tiles_for_role(role: str | None) -> int:
    if is_privileged_role(role):
        return _env_int("HISTO_PRIVILEGED_MAX_HEATMAP_TILES", 256, minimum=1)
    return _env_int("HISTO_STUDENT_MAX_HEATMAP_TILES", 16, minimum=1)


def max_tile_size_for_role(role: str | None) -> int:
    if is_privileged_role(role):
        return _env_int("HISTO_PRIVILEGED_MAX_HEATMAP_TILE_SIZE", 2048, minimum=64)
    return _env_int("HISTO_STUDENT_MAX_HEATMAP_TILE_SIZE", 1024, minimum=64)


def rate_limit_for_role(role: str | None) -> Tuple[int, int]:
    window_seconds = _env_int("HISTO_HEATMAP_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1)
    if is_privileged_role(role):
        max_requests = _env_int("HISTO_PRIVILEGED_HEATMAP_JOBS_PER_WINDOW", 20, minimum=1)
    else:
        max_requests = _env_int("HISTO_STUDENT_HEATMAP_JOBS_PER_WINDOW", 3, minimum=1)
    return max_requests, window_seconds


def heatmap_rate_limit_key(*, user_id: int | None, role: str, client_id: str | None) -> str:
    client = (client_id or "unknown").strip()[:80] or "unknown"
    return f"{normalize_role(role)}:{user_id or 'anon'}:{client}"


def _count_recent_jobs_for_user(user_id: int, cutoff_timestamp: float) -> Tuple[int, float | None]:
    from datetime import datetime, timezone
    from ..db import SessionLocal
    from ..models import HeatmapJob

    cutoff_dt = datetime.fromtimestamp(cutoff_timestamp, tz=timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        rows = (
            db.query(HeatmapJob.created_at)
            .filter(HeatmapJob.user_id == user_id, HeatmapJob.created_at >= cutoff_dt)
            .order_by(HeatmapJob.created_at.asc())
            .all()
        )
        if rows:
            oldest_dt = rows[0].created_at
            if oldest_dt.tzinfo is None:
                oldest_dt = oldest_dt.replace(tzinfo=timezone.utc)
            oldest = oldest_dt.timestamp()
        else:
            oldest = None
        return len(rows), oldest
    finally:
        db.close()


def check_heatmap_rate_limit(
    key: str, role: str, now: float | None = None, user_id: int | None = None
) -> Tuple[bool, int, int, int]:
    current = time.time() if now is None else now
    max_requests, window_seconds = rate_limit_for_role(role)
    cutoff = current - window_seconds

    if user_id is not None:
        try:
            count, oldest = _count_recent_jobs_for_user(user_id, cutoff)
        except Exception:
            pass  # DB unavailable; fall through to in-memory
        else:
            if count >= max_requests:
                retry_after = max(1, int(window_seconds - (current - oldest))) if oldest else window_seconds
                return False, retry_after, max_requests, window_seconds
            return True, 0, max_requests, window_seconds

    with _RATE_LOCK:
        recent = [stamp for stamp in _RATE_BUCKETS.get(key, []) if stamp > cutoff]
        if len(recent) >= max_requests:
            retry_after = max(1, int(window_seconds - (current - recent[0])))
            _RATE_BUCKETS[key] = recent
            return False, retry_after, max_requests, window_seconds

        recent.append(current)
        _RATE_BUCKETS[key] = recent
        return True, 0, max_requests, window_seconds


def reset_heatmap_rate_limits() -> None:
    with _RATE_LOCK:
        _RATE_BUCKETS.clear()
