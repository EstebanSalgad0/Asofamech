import csv
import io
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import (
    PERM_VIEW_FEEDBACK,
    get_current_user,
    require_permission,
    user_role,
)
from ..db import get_db
from ..models import UsabilityFeedback, User
from ..schemas import FeedbackCreate, FeedbackOut, FeedbackResponseItem, FeedbackSummary

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

_VALID_RATINGS = set(range(1, 6))
_DIMENSIONS = ["nav_clarity", "viewer_ease", "roi_ease", "ai_clarity", "chatbot_utility", "sct_utility"]
_MIN_ROLE_COUNT = 3   # umbral mínimo para mostrar desglose por rol sin riesgo de re-identificación


def _validate_ratings(data: FeedbackCreate) -> None:
    for dim in _DIMENSIONS:
        val = getattr(data, dim)
        if val not in _VALID_RATINGS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{dim}' debe ser un entero entre 1 y 5, recibido: {val}",
            )


def _serialize(fb: UsabilityFeedback) -> dict:
    return {
        "id": fb.id,
        "role_at_submission": fb.role_at_submission,
        "nav_clarity": fb.nav_clarity,
        "viewer_ease": fb.viewer_ease,
        "roi_ease": fb.roi_ease,
        "ai_clarity": fb.ai_clarity,
        "chatbot_utility": fb.chatbot_utility,
        "sct_utility": fb.sct_utility,
        "observations": fb.observations,
        "submitted_at": fb.submitted_at.isoformat() if fb.submitted_at else None,
        "updated_at": fb.updated_at.isoformat() if fb.updated_at else None,
    }


def _compute_averages(rows: list) -> dict:
    n = len(rows)
    if n == 0:
        return {d: 0.0 for d in _DIMENSIONS}
    return {
        d: round(sum(getattr(r, d) for r in rows) / n, 2)
        for d in _DIMENSIONS
    }


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_200_OK)
def submit_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crea o actualiza la evaluación del usuario autenticado (upsert por user_id)."""
    _validate_ratings(data)

    now = datetime.utcnow()
    existing = db.query(UsabilityFeedback).filter(
        UsabilityFeedback.user_id == current_user.id
    ).first()

    if existing:
        for dim in _DIMENSIONS:
            setattr(existing, dim, getattr(data, dim))
        existing.observations = data.observations
        existing.role_at_submission = user_role(current_user)
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return _serialize(existing)

    new_fb = UsabilityFeedback(
        user_id=current_user.id,
        role_at_submission=user_role(current_user),
        nav_clarity=data.nav_clarity,
        viewer_ease=data.viewer_ease,
        roi_ease=data.roi_ease,
        ai_clarity=data.ai_clarity,
        chatbot_utility=data.chatbot_utility,
        sct_utility=data.sct_utility,
        observations=data.observations,
        submitted_at=now,
        updated_at=now,
    )
    db.add(new_fb)
    db.commit()
    db.refresh(new_fb)
    return _serialize(new_fb)


@router.get("/my", response_model=Optional[FeedbackOut])
def get_my_feedback(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Devuelve la evaluación propia, o null si aún no se ha enviado."""
    fb = db.query(UsabilityFeedback).filter(
        UsabilityFeedback.user_id == current_user.id
    ).first()
    return _serialize(fb) if fb else None


@router.get("/summary", response_model=FeedbackSummary)
def get_feedback_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_VIEW_FEEDBACK)),
):
    """Resumen agregado anónimo (docente/admin). El desglose por rol se oculta
    cuando un rol tiene menos de _MIN_ROLE_COUNT respuestas para evitar
    re-identificación en grupos pequeños."""
    all_rows = db.query(UsabilityFeedback).all()
    total = len(all_rows)

    global_avgs = _compute_averages(all_rows)

    roles = {r.role_at_submission for r in all_rows}
    by_role = {}
    for role in roles:
        role_rows = [r for r in all_rows if r.role_at_submission == role]
        count = len(role_rows)
        if count >= _MIN_ROLE_COUNT:
            by_role[role] = {
                "count": count,
                "averages": _compute_averages(role_rows),
                "anonymized": False,
            }
        else:
            # Mostramos la cantidad pero no los promedios para proteger la privacidad
            by_role[role] = {
                "count": count,
                "averages": None,
                "anonymized": True,
            }

    recent_obs = [
        r.observations
        for r in sorted(all_rows, key=lambda x: x.updated_at, reverse=True)
        if r.observations and r.observations.strip()
    ][:20]

    return {
        "total_responses": total,
        "averages": global_avgs,
        "by_role": by_role,
        "recent_observations": recent_obs,
    }


@router.get("/responses", response_model=List[FeedbackResponseItem])
def get_feedback_responses(
    role: Optional[str] = Query(None, description="Filtrar por rol"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_VIEW_FEEDBACK)),
):
    """Lista de respuestas anonimizadas (rol, ratings, observación, fecha — sin nombre ni email)."""
    query = db.query(UsabilityFeedback).order_by(UsabilityFeedback.updated_at.desc())
    if role:
        query = query.filter(UsabilityFeedback.role_at_submission == role)
    rows = query.all()
    return [
        {
            "role": r.role_at_submission,
            "nav_clarity": r.nav_clarity,
            "viewer_ease": r.viewer_ease,
            "roi_ease": r.roi_ease,
            "ai_clarity": r.ai_clarity,
            "chatbot_utility": r.chatbot_utility,
            "sct_utility": r.sct_utility,
            "observations": r.observations,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
        }
        for r in rows
    ]


@router.get("/export.csv")
def export_feedback_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_VIEW_FEEDBACK)),
):
    """Descarga todas las respuestas anonimizadas en formato CSV (docente/admin)."""
    rows = db.query(UsabilityFeedback).order_by(UsabilityFeedback.updated_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "rol",
        "claridad_navegacion", "facilidad_visor", "facilidad_roi",
        "claridad_ia", "utilidad_chatbot", "utilidad_sct",
        "observaciones", "fecha",
    ])
    for r in rows:
        writer.writerow([
            r.role_at_submission,
            r.nav_clarity, r.viewer_ease, r.roi_ease,
            r.ai_clarity, r.chatbot_utility, r.sct_utility,
            r.observations or "",
            r.submitted_at.strftime("%Y-%m-%d") if r.submitted_at else "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=evaluaciones_usabilidad.csv"},
    )
