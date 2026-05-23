from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..db import get_db
from ..histopathology.heatmap_store import load_heatmap_history_for_user
from ..models import (
    ChatLog,
    HeatmapJob,
    HistopathologySession,
    MedicalImage,
    SCTAttempt,
    User,
)


router = APIRouter(prefix="/api/history", tags=["history"])


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _short_text(value: str | None, max_length: int = 220) -> str:
    text = " ".join((value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def _event_date(*values: Any) -> datetime:
    for value in values:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                continue
    return datetime.min


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_summary(user: User | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


def _user_by_id(db: Session, user_id: int | str | None) -> User | None:
    if user_id is None:
        return None
    try:
        normalized = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.query(User).filter(User.id == normalized).first()


def _image_fields(image: MedicalImage | None) -> dict:
    return {
        "image_id": image.id if image else None,
        "image_title": image.title if image else None,
        "image_filename": image.original_filename if image else None,
    }


def _session_payload(session: HistopathologySession, include_user: bool = False) -> dict:
    payload = {
        "id": session.id,
        "trace_id": session.trace_id,
        "analyzed_at": _iso(session.analyzed_at),
        "status": session.status,
        "clase": session.clase,
        "confidence": session.confidence,
        "roi_1": session.roi_1,
        "roi_2": session.roi_2,
        **_image_fields(session.image),
    }
    if include_user:
        payload["user"] = _user_summary(session.user)
    return payload


def _attempt_payload(attempt: SCTAttempt, include_user: bool = False) -> dict:
    test = attempt.test
    payload = {
        "id": attempt.id,
        "test_id": attempt.test_id,
        "test_name": test.name if test else None,
        "test_focus": test.focus if test else None,
        "test_difficulty": test.difficulty if test else None,
        "score": attempt.score,
        "correct_count": attempt.correct_count,
        "total_items": attempt.total_items,
        "started_at": _iso(attempt.started_at),
        "completed_at": _iso(attempt.completed_at),
    }
    if include_user:
        payload["user"] = _user_summary(attempt.user)
    return payload


def _chat_payload(log: ChatLog, db: Session | None = None, include_user: bool = False) -> dict:
    rag_sources = log.rag_sources if isinstance(log.rag_sources, list) else []
    payload = {
        "id": log.id,
        "created_at": _iso(log.created_at),
        "question": _short_text(log.question),
        "answer": _short_text(log.answer),
        "used_rag": bool(rag_sources),
        "source_count": len(rag_sources),
    }
    if include_user and db is not None:
        payload["user"] = _user_summary(_user_by_id(db, log.user_id))
    return payload


def _heatmap_job_payload(job: HeatmapJob, include_user: bool = False) -> dict:
    request = job.request_json if isinstance(job.request_json, dict) else {}
    result = job.result_json if isinstance(job.result_json, dict) else {}
    payload = {
        "job_id": job.job_id,
        "trace_id": job.trace_id,
        "status": job.status,
        "progress": job.progress,
        "processed_tiles": job.processed_tiles,
        "total_tiles": job.total_tiles,
        "image_id": request.get("image_id") or result.get("image_id"),
        "created_at": _iso(job.created_at),
        "started_at": _iso(job.started_at),
        "completed_at": _iso(job.completed_at),
        "failed_at": _iso(job.failed_at),
        "error": _short_text(job.error, 180) if job.error else None,
    }
    if include_user:
        payload["user"] = _user_summary(job.user)
    return payload


def _heatmap_artifact_payload(item: dict) -> dict:
    summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
    decision = summary.get("roi_decision") if isinstance(summary.get("roi_decision"), dict) else {}
    educational = item.get("educational") if isinstance(item.get("educational"), dict) else {}
    return {
        "trace_id": item.get("trace_id"),
        "image_id": item.get("image_id"),
        "analyzed_at": item.get("analyzed_at"),
        "status": "completed",
        "tile_count": item.get("tile_count"),
        "roi_label": decision.get("label") or decision.get("status"),
        "educational_label": educational.get("label"),
    }


def _my_sessions(db: Session, user_id: int, limit: int) -> list[dict]:
    sessions = (
        db.query(HistopathologySession)
        .filter(
            HistopathologySession.user_id == user_id,
            HistopathologySession.is_active == True,
        )
        .order_by(HistopathologySession.analyzed_at.desc())
        .limit(limit)
        .all()
    )
    return [_session_payload(session) for session in sessions]


def _my_sct_attempts(db: Session, user_id: int, limit: int) -> list[dict]:
    attempts = (
        db.query(SCTAttempt)
        .filter(SCTAttempt.user_id == user_id)
        .order_by(SCTAttempt.completed_at.desc())
        .limit(limit)
        .all()
    )
    return [_attempt_payload(attempt) for attempt in attempts]


def _my_conversations(db: Session, user_id: int, limit: int) -> list[dict]:
    logs = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == str(user_id))
        .order_by(ChatLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [_chat_payload(log) for log in logs]


def _my_heatmaps(db: Session, user_id: int, limit: int) -> list[dict]:
    artifacts = [
        {"kind": "heatmap", **_heatmap_artifact_payload(item)}
        for item in load_heatmap_history_for_user(user_id, limit=limit)
    ]
    artifact_traces = {item.get("trace_id") for item in artifacts if item.get("trace_id")}
    jobs = (
        db.query(HeatmapJob)
        .filter(HeatmapJob.user_id == user_id)
        .order_by(HeatmapJob.created_at.desc())
        .limit(limit)
        .all()
    )
    pending_jobs = [
        {"kind": "heatmap_job", **_heatmap_job_payload(job)}
        for job in jobs
        if job.status != "completed" or job.trace_id not in artifact_traces
    ]
    combined = pending_jobs + artifacts
    combined.sort(
        key=lambda item: _event_date(
            item.get("created_at"),
            item.get("analyzed_at"),
            item.get("completed_at"),
            item.get("failed_at"),
        ),
        reverse=True,
    )
    return combined[:limit]


@router.get("/me")
def get_my_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    roi_sessions = _my_sessions(db, current_user.id, limit)
    sct_attempts = _my_sct_attempts(db, current_user.id, limit)
    conversations = _my_conversations(db, current_user.id, limit)
    heatmaps = _my_heatmaps(db, current_user.id, limit)
    return {
        "user_id": current_user.id,
        "generated_at": _utc_now().isoformat(),
        "counts": {
            "roi_sessions": len(roi_sessions),
            "analyses": len(roi_sessions),
            "sct_attempts": len(sct_attempts),
            "conversations": len(conversations),
            "heatmaps": len(heatmaps),
        },
        "roi_sessions": roi_sessions,
        "analyses": roi_sessions,
        "sct_attempts": sct_attempts,
        "conversations": conversations,
        "heatmaps": heatmaps,
    }


@router.get("/roi-sessions")
def list_my_roi_sessions(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _my_sessions(db, current_user.id, limit)
    return {"count": len(items), "items": items}


@router.get("/analyses")
def list_my_analyses(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _my_sessions(db, current_user.id, limit)
    return {"count": len(items), "items": items}


@router.get("/sct-attempts")
def list_my_sct_attempts(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _my_sct_attempts(db, current_user.id, limit)
    return {"count": len(items), "items": items}


@router.get("/conversations")
def list_my_conversations(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _my_conversations(db, current_user.id, limit)
    return {"count": len(items), "items": items}


@router.get("/heatmaps")
def list_my_heatmaps(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = _my_heatmaps(db, current_user.id, limit)
    return {"count": len(items), "items": items}


@router.get("/admin/roi-sessions")
def list_student_roi_sessions(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    query = db.query(HistopathologySession).filter(HistopathologySession.is_active == True)
    if user_id is not None:
        query = query.filter(HistopathologySession.user_id == user_id)
    sessions = query.order_by(HistopathologySession.analyzed_at.desc()).limit(limit).all()
    items = [_session_payload(session, include_user=True) for session in sessions]
    return {"count": len(items), "items": items}


@router.get("/admin/sct-attempts")
def list_student_sct_attempts(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    query = db.query(SCTAttempt)
    if user_id is not None:
        query = query.filter(SCTAttempt.user_id == user_id)
    attempts = query.order_by(SCTAttempt.completed_at.desc()).limit(limit).all()
    items = [_attempt_payload(attempt, include_user=True) for attempt in attempts]
    return {"count": len(items), "items": items}


@router.get("/admin/conversations")
def list_student_conversations(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    query = db.query(ChatLog)
    if user_id is not None:
        query = query.filter(ChatLog.user_id == str(user_id))
    logs = query.order_by(ChatLog.created_at.desc()).limit(limit).all()
    items = [_chat_payload(log, db=db, include_user=True) for log in logs]
    return {"count": len(items), "items": items}


@router.get("/admin/heatmaps")
def list_student_heatmaps(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    query = db.query(HeatmapJob)
    if user_id is not None:
        query = query.filter(HeatmapJob.user_id == user_id)
    jobs = query.order_by(HeatmapJob.created_at.desc()).limit(limit).all()
    items = [_heatmap_job_payload(job, include_user=True) for job in jobs]
    return {"count": len(items), "items": items}


@router.get("/admin/activity")
def list_student_activity(
    user_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    events: list[tuple[datetime, dict]] = []

    histo_query = db.query(HistopathologySession).filter(HistopathologySession.is_active == True)
    if user_id is not None:
        histo_query = histo_query.filter(HistopathologySession.user_id == user_id)
    for session in histo_query.order_by(HistopathologySession.analyzed_at.desc()).limit(limit).all():
        payload = _session_payload(session, include_user=True)
        events.append((_event_date(session.analyzed_at), {"type": "roi_analysis", **payload}))

    attempt_query = db.query(SCTAttempt)
    if user_id is not None:
        attempt_query = attempt_query.filter(SCTAttempt.user_id == user_id)
    for attempt in attempt_query.order_by(SCTAttempt.completed_at.desc()).limit(limit).all():
        payload = _attempt_payload(attempt, include_user=True)
        events.append((_event_date(attempt.completed_at), {"type": "sct_attempt", **payload}))

    chat_query = db.query(ChatLog)
    if user_id is not None:
        chat_query = chat_query.filter(ChatLog.user_id == str(user_id))
    for log in chat_query.order_by(ChatLog.created_at.desc()).limit(limit).all():
        payload = _chat_payload(log, db=db, include_user=True)
        events.append((_event_date(log.created_at), {"type": "conversation", **payload}))

    heatmap_query = db.query(HeatmapJob)
    if user_id is not None:
        heatmap_query = heatmap_query.filter(HeatmapJob.user_id == user_id)
    for job in heatmap_query.order_by(HeatmapJob.created_at.desc()).limit(limit).all():
        payload = _heatmap_job_payload(job, include_user=True)
        events.append((_event_date(job.completed_at, job.failed_at, job.started_at, job.created_at), {"type": "heatmap_job", **payload}))

    events.sort(key=lambda item: item[0], reverse=True)
    items = [payload for _, payload in events[:limit]]
    return {"count": len(items), "items": items}
