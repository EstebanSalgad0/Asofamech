"""Encuestas de percepción de aprendizaje.

Diseño anónimo:
  - `survey_responses` NO contiene user_id.
  - `survey_participation` liga user_id ↔ survey_id sólo para bloquear
    duplicados; no comparte clave con las respuestas, por lo que es imposible
    correlacionar una respuesta con su autor a nivel de datos.

Reglas de negocio:
  - Estudiante puede responder cada encuesta una única vez y NO puede editar.
  - Las encuestas están disponibles mientras `status == "open"`. El docente/admin
    puede archivarlas (`status == "archived"`), lo que las oculta al estudiante
    y bloquea nuevas respuestas, sin borrar datos.
  - Solo docente/admin pueden ver métricas y textos libres.
"""
import csv
import io
from collections import Counter, defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from ..auth import (
    PERM_MANAGE_SURVEYS,
    PERM_VIEW_SURVEYS,
    get_current_user,
    require_permission,
    user_role,
)
from ..db import get_db
from ..models import (
    Survey,
    SurveyAnswer,
    SurveyItem,
    SurveyParticipation,
    SurveyResponse,
    User,
)
from ..text_analysis import word_frequencies
from ..schemas import (
    ItemStat,
    OpenAnswerOut,
    WordCloudOut,
    SectionStat,
    SurveyDetailOut,
    SurveyItemOut,
    SurveyOut,
    SurveyResponseCreate,
    SurveyStatusUpdate,
    SurveySummary,
)

router = APIRouter(prefix="/api/surveys", tags=["surveys"])

_LIKERT_VALID = set(range(1, 6))
_MIN_ROLE_COUNT = 3  # umbral para no re-identificar en desgloses por rol


# ---------- helpers ----------

def _serialize_survey(s: Survey) -> dict:
    return {
        "id": s.id,
        "code": s.code,
        "title": s.title,
        "description": s.description,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _serialize_item(item: SurveyItem) -> dict:
    return {
        "id": item.id,
        "section": item.section,
        "section_order": item.section_order,
        "item_order": item.item_order,
        "text": item.text,
        "item_type": item.item_type,
        "required": item.required,
    }


def _get_survey_or_404(db: Session, code: str) -> Survey:
    survey = (
        db.query(Survey)
        .options(joinedload(Survey.items))
        .filter(Survey.code == code)
        .first()
    )
    if not survey:
        raise HTTPException(status_code=404, detail="Encuesta no encontrada")
    return survey


def _user_already_participated(db: Session, survey_id: int, user_id: int) -> bool:
    return (
        db.query(SurveyParticipation.id)
        .filter(
            SurveyParticipation.survey_id == survey_id,
            SurveyParticipation.user_id == user_id,
        )
        .first()
        is not None
    )


# ---------- endpoints de estudiante ----------

@router.get("", response_model=list[SurveyOut])
def list_surveys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista las encuestas abiertas visibles al estudiante.

    Docentes/admin ven también las archivadas (pero eso se maneja en el panel
    de análisis).
    """
    surveys = db.query(Survey).filter(Survey.status == "open").order_by(Survey.id.asc()).all()
    return [_serialize_survey(s) for s in surveys]


@router.get("/{code}", response_model=SurveyDetailOut)
def get_survey(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalle con ítems + flag `already_answered` para el usuario actual.

    Se permite consultar aunque esté archivada (para no romper enlaces
    guardados), pero el frontend debe mostrarla en modo solo-lectura.
    """
    survey = _get_survey_or_404(db, code)
    payload = _serialize_survey(survey)
    payload["items"] = [_serialize_item(i) for i in survey.items]
    payload["already_answered"] = _user_already_participated(db, survey.id, current_user.id)
    return payload


@router.post("/{code}/responses", status_code=201)
def submit_response(
    code: str,
    payload: SurveyResponseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registra una respuesta anónima.

    La transacción hace dos inserciones que NO comparten clave:
      1) `SurveyResponse` + `SurveyAnswer` (sin user_id).
      2) `SurveyParticipation` (con user_id, sin datos de respuesta).
    Un `UniqueConstraint(survey_id, user_id)` en la segunda tabla garantiza
    que un mismo usuario no pueda responder dos veces.
    """
    survey = _get_survey_or_404(db, code)
    if survey.status != "open":
        raise HTTPException(status_code=409, detail="Esta encuesta está archivada")

    if _user_already_participated(db, survey.id, current_user.id):
        raise HTTPException(status_code=409, detail="Ya respondiste esta encuesta")

    items_by_id = {i.id: i for i in survey.items}

    # Validar todas las respuestas antes de escribir nada
    seen_items = set()
    for ans in payload.answers:
        item = items_by_id.get(ans.item_id)
        if item is None:
            raise HTTPException(
                status_code=422,
                detail=f"Ítem {ans.item_id} no pertenece a esta encuesta",
            )
        if ans.item_id in seen_items:
            raise HTTPException(status_code=422, detail=f"Ítem {ans.item_id} respondido más de una vez")
        seen_items.add(ans.item_id)

        if item.item_type == "likert_1_5":
            if ans.value_int not in _LIKERT_VALID:
                raise HTTPException(
                    status_code=422,
                    detail=f"Ítem {ans.item_id} requiere valor entero 1-5",
                )
        elif item.item_type == "open_text":
            if item.required and not (ans.value_text and ans.value_text.strip()):
                raise HTTPException(
                    status_code=422,
                    detail=f"Ítem {ans.item_id} (abierto) es obligatorio",
                )
        else:
            raise HTTPException(status_code=500, detail=f"Tipo de ítem no soportado: {item.item_type}")

    # Validar ítems obligatorios sin responder
    required_ids = {i.id for i in survey.items if i.required}
    missing = required_ids - seen_items
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Faltan {len(missing)} ítem(s) obligatorio(s) por responder",
        )

    role_at = user_role(current_user)

    # Insertar. Escribimos primero la participación (con UNIQUE) para que un
    # doble envío concurrente no cree respuestas duplicadas.
    participation = SurveyParticipation(survey_id=survey.id, user_id=current_user.id)
    db.add(participation)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya respondiste esta encuesta")

    response = SurveyResponse(survey_id=survey.id, role_at_submission=role_at)
    db.add(response)
    db.flush()

    for ans in payload.answers:
        item = items_by_id[ans.item_id]
        db.add(
            SurveyAnswer(
                response_id=response.id,
                item_id=item.id,
                value_int=ans.value_int if item.item_type == "likert_1_5" else None,
                value_text=(ans.value_text or "").strip() if item.item_type == "open_text" else None,
            )
        )

    db.commit()
    return {"ok": True}


# ---------- endpoints de docente / admin ----------

@router.get("/admin/all", response_model=list[SurveyOut])
def list_all_surveys_admin(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_VIEW_SURVEYS)),
):
    surveys = db.query(Survey).order_by(Survey.id.asc()).all()
    return [_serialize_survey(s) for s in surveys]


@router.patch("/{code}/status")
def update_status(
    code: str,
    payload: SurveyStatusUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_MANAGE_SURVEYS)),
):
    if payload.status not in ("open", "archived"):
        raise HTTPException(status_code=422, detail="status debe ser 'open' o 'archived'")
    survey = _get_survey_or_404(db, code)
    survey.status = payload.status
    survey.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": survey.status}


@router.get("/{code}/summary", response_model=SurveySummary)
def get_summary(
    code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_VIEW_SURVEYS)),
):
    survey = _get_survey_or_404(db, code)

    total_responses = (
        db.query(SurveyResponse.id).filter(SurveyResponse.survey_id == survey.id).count()
    )

    # Traer todas las respuestas Likert de esta encuesta
    rows = (
        db.query(SurveyAnswer.item_id, SurveyAnswer.value_int)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
        .filter(
            SurveyResponse.survey_id == survey.id,
            SurveyAnswer.value_int.isnot(None),
        )
        .all()
    )

    by_item_values: dict[int, list[int]] = defaultdict(list)
    for item_id, val in rows:
        by_item_values[item_id].append(int(val))

    item_stats: list[dict] = []
    section_buckets: dict[str, list[float]] = defaultdict(list)

    for item in survey.items:
        vals = by_item_values.get(item.id, [])
        n = len(vals)
        if item.item_type == "likert_1_5" and n > 0:
            avg = round(sum(vals) / n, 2)
            distribution = {str(k): v for k, v in sorted(Counter(vals).items())}
            section_buckets[item.section].append(avg)
        else:
            avg = None
            distribution = {}
        item_stats.append(
            {
                "item_id": item.id,
                "section": item.section,
                "text": item.text,
                "item_type": item.item_type,
                "average": avg,
                "n": n,
                "distribution": distribution,
            }
        )

    section_averages: list[dict] = []
    global_values: list[float] = []
    seen_sections = []
    for item in survey.items:
        if item.section in seen_sections:
            continue
        seen_sections.append(item.section)
        bucket = section_buckets.get(item.section, [])
        if bucket:
            sec_avg = round(sum(bucket) / len(bucket), 2)
            global_values.append(sec_avg)
        else:
            sec_avg = None
        section_averages.append(
            {
                "section": item.section,
                "average": sec_avg,
                "n_items": sum(1 for i in survey.items if i.section == item.section and i.item_type == "likert_1_5"),
            }
        )

    global_avg = round(sum(global_values) / len(global_values), 2) if global_values else None

    return {
        "survey_code": survey.code,
        "survey_title": survey.title,
        "total_responses": total_responses,
        "global_average": global_avg,
        "section_averages": section_averages,
        "item_stats": item_stats,
    }


@router.get("/{code}/open-answers", response_model=list[OpenAnswerOut])
def get_open_answers(
    code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_VIEW_SURVEYS)),
):
    """Textos libres agrupados por ítem, sin identificar autores."""
    survey = _get_survey_or_404(db, code)
    open_items = [i for i in survey.items if i.item_type == "open_text"]
    if not open_items:
        return []

    ids = [i.id for i in open_items]
    rows = (
        db.query(SurveyAnswer.item_id, SurveyAnswer.value_text)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
        .filter(
            SurveyResponse.survey_id == survey.id,
            SurveyAnswer.item_id.in_(ids),
            SurveyAnswer.value_text.isnot(None),
        )
        .all()
    )
    by_item: dict[int, list[str]] = defaultdict(list)
    for item_id, text in rows:
        if text and text.strip():
            by_item[item_id].append(text.strip())

    return [
        {
            "item_id": i.id,
            "item_text": i.text,
            "section": i.section,
            "answers": by_item.get(i.id, []),
        }
        for i in open_items
    ]


@router.get("/{code}/word-cloud", response_model=list[WordCloudOut])
def get_word_cloud(
    code: str,
    limit: int = 60,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_VIEW_SURVEYS)),
):
    """Terminos mas frecuentes por pregunta abierta.

    Mismo origen que `/open-answers` y las mismas garantias: agrega sobre
    respuestas anonimas y no expone quien escribio que. Se calcula en el
    servidor para que el navegador no tenga que descargar todas las respuestas
    solo para contarlas.
    """
    limit = max(10, min(limit, 200))
    survey = _get_survey_or_404(db, code)
    open_items = [i for i in survey.items if i.item_type == "open_text"]
    if not open_items:
        return []

    ids = [i.id for i in open_items]
    rows = (
        db.query(SurveyAnswer.item_id, SurveyAnswer.value_text)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
        .filter(
            SurveyResponse.survey_id == survey.id,
            SurveyAnswer.item_id.in_(ids),
            SurveyAnswer.value_text.isnot(None),
        )
        .all()
    )

    by_item: dict[int, list[str]] = defaultdict(list)
    for item_id, text in rows:
        if text and text.strip():
            by_item[item_id].append(text)

    return [
        {
            "item_id": item.id,
            "item_text": item.text,
            "section": item.section,
            "total_answers": len(by_item.get(item.id, [])),
            "words": word_frequencies(by_item.get(item.id, []), limit=limit),
        }
        for item in open_items
    ]


@router.get("/{code}/export.csv")
def export_csv(
    code: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_VIEW_SURVEYS)),
):
    """CSV tidy: una fila por respuesta × ítem. No incluye user_id."""
    survey = _get_survey_or_404(db, code)
    items_by_id = {i.id: i for i in survey.items}

    responses = (
        db.query(SurveyResponse)
        .options(joinedload(SurveyResponse.answers))
        .filter(SurveyResponse.survey_id == survey.id)
        .order_by(SurveyResponse.submitted_at.asc())
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["response_id", "submitted_at", "role", "section", "item_id", "item_text", "item_type", "value_int", "value_text"]
    )
    for r in responses:
        for a in r.answers:
            item = items_by_id.get(a.item_id)
            if item is None:
                continue
            writer.writerow(
                [
                    r.id,
                    r.submitted_at.isoformat() if r.submitted_at else "",
                    r.role_at_submission or "",
                    item.section,
                    item.id,
                    item.text,
                    item.item_type,
                    a.value_int if a.value_int is not None else "",
                    (a.value_text or "").replace("\r", " ").replace("\n", " "),
                ]
            )

    filename = f"encuesta_{survey.code}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
