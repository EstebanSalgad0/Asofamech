from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from pydantic import BaseModel

from ..auth import get_current_user
from ..db import get_db
from ..models import ChatLog, HistopathologySession, SCTAttempt, StudySession, User


class _StudySessionPayload(BaseModel):
    duration_ms: int


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _daily_counts(db, query_fn, days=7):
    now = datetime.utcnow()
    result = []
    for i in range(days - 1, -1, -1):
        d_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        d_end = d_start + timedelta(days=1)
        result.append(query_fn(d_start, d_end))
    return result


@router.post("/study-session", status_code=204)
def record_study_session(
    payload: _StudySessionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.duration_ms < 500:
        return
    db.add(StudySession(user_id=current_user.id, duration_ms=payload.duration_ms))
    db.commit()


@router.get("/stats")
def get_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    uid_str = str(current_user.id)

    chat_total = db.query(func.count(ChatLog.id)).filter(ChatLog.user_id == uid_str).scalar() or 0
    chat_week  = db.query(func.count(ChatLog.id)).filter(
        ChatLog.user_id == uid_str, ChatLog.created_at >= week_ago
    ).scalar() or 0

    histo_q = db.query(HistopathologySession).filter(
        HistopathologySession.user_id == current_user.id,
        HistopathologySession.is_active == True,
    )
    histo_total = histo_q.count()
    histo_week  = histo_q.filter(HistopathologySession.analyzed_at >= week_ago).count()

    sct_q = db.query(SCTAttempt).filter(SCTAttempt.user_id == current_user.id)
    sct_total = sct_q.count()
    sct_week = sct_q.filter(SCTAttempt.completed_at >= week_ago).count()
    latest_sct = sct_q.order_by(SCTAttempt.completed_at.desc()).first()

    chat_daily = _daily_counts(db, lambda s, e: (
        db.query(func.count(ChatLog.id))
        .filter(ChatLog.user_id == uid_str, ChatLog.created_at >= s, ChatLog.created_at < e)
        .scalar() or 0
    ))
    histo_daily = _daily_counts(db, lambda s, e: (
        db.query(func.count(HistopathologySession.id))
        .filter(
            HistopathologySession.user_id == current_user.id,
            HistopathologySession.is_active == True,
            HistopathologySession.analyzed_at >= s,
            HistopathologySession.analyzed_at < e,
        ).scalar() or 0
    ))
    sct_daily = _daily_counts(db, lambda s, e: (
        db.query(func.count(SCTAttempt.id))
        .filter(SCTAttempt.user_id == current_user.id, SCTAttempt.completed_at >= s, SCTAttempt.completed_at < e)
        .scalar() or 0
    ))

    study_total_ms = db.query(func.sum(StudySession.duration_ms)).filter(
        StudySession.user_id == current_user.id
    ).scalar() or 0
    study_week_ms = db.query(func.sum(StudySession.duration_ms)).filter(
        StudySession.user_id == current_user.id,
        StudySession.recorded_at >= week_ago,
    ).scalar() or 0

    return {
        "chat":  {"total": chat_total,  "week": chat_week,  "daily": chat_daily},
        "histo": {"total": histo_total, "week": histo_week, "daily": histo_daily},
        "study": {"total_ms": study_total_ms, "week_ms": study_week_ms},
        "sct": {
            "total": sct_total,
            "week": sct_week,
            "daily": sct_daily,
            "latest": {
                "score": latest_sct.score,
                "correct_count": latest_sct.correct_count,
                "total_items": latest_sct.total_items,
                "completed_at": latest_sct.completed_at.isoformat(),
            } if latest_sct else None,
        },
    }


@router.get("/ranking")
def get_ranking(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    week_ago = datetime.utcnow() - timedelta(days=7)

    active_users = db.query(User).filter(
        User.is_active == True, User.account_status == "approved"
    ).all()

    entries = []
    for u in active_users:
        uid_str = str(u.id)
        chat_n = db.query(func.count(ChatLog.id)).filter(
            ChatLog.user_id == uid_str, ChatLog.created_at >= week_ago
        ).scalar() or 0

        sessions = db.query(HistopathologySession).filter(
            HistopathologySession.user_id == u.id,
            HistopathologySession.is_active == True,
            HistopathologySession.analyzed_at >= week_ago,
        ).all()
        histo_n = len(sessions)
        conf_vals = []
        for s in sessions:
            if s.status == "clasificado" and s.confidence is not None:
                try:
                    conf_vals.append(float(s.confidence))
                except (TypeError, ValueError):
                    pass
        avg_conf = sum(conf_vals) / len(conf_vals) if conf_vals else 0.0

        raw = chat_n * 3 + histo_n * 10 + avg_conf * 40

        parts = (u.name or "Usuario").split()
        display = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")

        entries.append({"user_id": u.id, "name": display, "is_you": u.id == current_user.id, "raw": raw})

    entries.sort(key=lambda x: x["raw"], reverse=True)
    max_raw = entries[0]["raw"] if entries and entries[0]["raw"] > 0 else 1

    ranking = [
        {"name": e["name"], "is_you": e["is_you"], "score": round(e["raw"] / max_raw * 100)}
        for e in entries
    ]

    you_pos = next((i for i, r in enumerate(ranking) if r["is_you"]), None)
    total = len(ranking)
    percentile = round((1 - you_pos / total) * 100) if you_pos is not None and total > 1 else 100

    return {
        "ranking": ranking[:5],
        "your_position": (you_pos + 1) if you_pos is not None else None,
        "percentile": percentile,
        "total_users": total,
    }
