"""Revisor de informes clinicos por rubrica.

Flujo:
  1. El docente carga la rubrica: sube el documento y el LLM propone criterios y
     niveles (`POST /rubrics/extract`), los revisa y guarda (`POST /rubrics`).
  2. Publica la rubrica; solo entonces el estudiante la ve.
  3. El estudiante sube su informe (.docx, .pdf o texto) y elige una o varias
     rubricas publicadas contra las que quiere que se evalue. El archivo se lee
     una sola vez; cada rubrica produce su propia entrega y su propia
     evaluacion, agrupadas por `batch_id`.
  4. Cada resultado nace privado. Docente y administrador lo revisan, pueden
     corregir el puntaje y anotar un comentario, y deciden cuando liberarlo -
     rubrica por rubrica, no todo el envio junto.

La visibilidad se decide en el serializador, no en el frontend: un estudiante
que consulte la API directamente tampoco obtiene la nota sin liberar.
"""
from __future__ import annotations

import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..audit import record_audit_log
from ..auth import (
    PERM_MANAGE_RUBRICS,
    PERM_REVIEW_REPORTS,
    PERM_SUBMIT_REPORTS,
    get_current_user,
    require_permission,
    user_has_permission,
)
from ..db import get_db
from ..models import Case, ReportEvaluation, ReportSubmission, Rubric, User
from ..rag_file_loader import extract_text_from_upload
from ..rubric_review import (
    band_for_score,
    evaluate_report,
    extract_rubric_from_text,
    normalize_bands,
    normalize_criteria,
    rubric_max_score,
)
from ..schemas import (
    EvaluationRelease,
    ReportSubmissionOut,
    RubricCreate,
    RubricDraftOut,
    RubricOut,
    RubricStatusUpdate,
    RubricStudentProgress,
    RubricUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

REPORT_DIR = "uploads/reports"
os.makedirs(REPORT_DIR, exist_ok=True)

VALID_RUBRIC_STATUSES = {"draft", "published", "archived"}
# Mismos formatos que acepta el cargador de RAG: el informe del estudiante llega
# como Word en la practica, pero PDF y texto plano no cuestan nada mas.
REPORT_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}
MAX_REPORT_BYTES = 15 * 1024 * 1024
MAX_OPEN_SUBMISSIONS_PER_RUBRIC = 3
# Un mismo envio puede evaluar el archivo contra varias rubricas a la vez; el
# tope evita que un envio arrastre decenas de evaluaciones en paralelo por error.
MAX_RUBRICS_PER_SUBMISSION = 10

_CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


def _schema_values(schema, **kwargs) -> dict:
    if hasattr(schema, "model_dump"):
        return schema.model_dump(**kwargs)
    return schema.dict(**kwargs)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


# ------------------------------------------------------------------- rubricas

def _serialize_rubric(rubric: Rubric) -> dict:
    return {
        "id": rubric.id,
        "title": rubric.title,
        "description": rubric.description,
        "criteria": rubric.criteria_json or [],
        "bands": rubric.bands_json or [],
        "guidance": rubric.guidance,
        "max_score": rubric.max_score or 0.0,
        "case_id": rubric.case_id,
        "source_filename": rubric.source_filename,
        "due_at": _iso(rubric.due_at),
        "status": rubric.status,
        "created_by": rubric.created_by,
        "created_at": _iso(rubric.created_at),
        "updated_at": _iso(rubric.updated_at),
    }


def _get_rubric_or_404(rubric_id: int, db: Session) -> Rubric:
    rubric = (
        db.query(Rubric)
        .filter(Rubric.id == rubric_id, Rubric.is_active == True)
        .first()
    )
    if not rubric:
        raise HTTPException(status_code=404, detail="Rúbrica no encontrada")
    return rubric


def _validate_case(case_id: Optional[int], db: Session) -> None:
    if case_id is None:
        return
    exists = db.query(Case.id).filter(Case.id == case_id, Case.is_active == True).first()
    if not exists:
        raise HTTPException(status_code=422, detail=f"Caso clínico no encontrado: ID {case_id}")


@router.post("/rubrics/extract", response_model=RubricDraftOut)
async def extract_rubric(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_MANAGE_RUBRICS)),
):
    """Propone una rúbrica a partir de un documento. No guarda nada."""
    text, _document_type = await extract_text_from_upload(file)
    draft = await extract_rubric_from_text(db, text)
    draft["source_filename"] = (file.filename or "")[:200] or None
    return draft


@router.get("/rubrics", response_model=list[RubricOut])
def list_rubrics(
    status_filter: Optional[str] = Query(None, alias="status"),
    case_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rúbricas visibles: el estudiante solo ve las publicadas."""
    is_manager = user_has_permission(current_user, PERM_MANAGE_RUBRICS)
    query = db.query(Rubric).filter(Rubric.is_active == True)

    if not is_manager:
        query = query.filter(Rubric.status == "published")
    elif status_filter and status_filter in VALID_RUBRIC_STATUSES:
        query = query.filter(Rubric.status == status_filter)

    if case_id is not None:
        query = query.filter(Rubric.case_id == case_id)

    return [_serialize_rubric(r) for r in query.order_by(Rubric.created_at.desc()).all()]


@router.get("/rubrics/{rubric_id}", response_model=RubricOut)
def get_rubric(
    rubric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rubric = _get_rubric_or_404(rubric_id, db)
    if rubric.status != "published" and not user_has_permission(current_user, PERM_MANAGE_RUBRICS):
        raise HTTPException(status_code=404, detail="Rúbrica no encontrada")
    return _serialize_rubric(rubric)


@router.post("/rubrics", response_model=RubricOut, status_code=status.HTTP_201_CREATED)
def create_rubric(
    payload: RubricCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_RUBRICS)),
):
    if payload.status not in VALID_RUBRIC_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {payload.status}")

    values = _schema_values(payload)
    criteria = normalize_criteria(values.get("criteria"))
    if not criteria:
        raise HTTPException(status_code=422, detail="La rúbrica necesita al menos un criterio con niveles.")
    _validate_case(values.get("case_id"), db)

    rubric = Rubric(
        title=values["title"].strip()[:200],
        description=(values.get("description") or "").strip() or None,
        criteria_json=criteria,
        bands_json=normalize_bands(values.get("bands")),
        guidance=(values.get("guidance") or "").strip() or None,
        max_score=rubric_max_score(criteria),
        case_id=values.get("case_id"),
        source_filename=(values.get("source_filename") or "")[:200] or None,
        due_at=values.get("due_at"),
        status=values["status"],
        created_by=current_user.id,
        is_active=True,
    )
    db.add(rubric)
    db.commit()
    db.refresh(rubric)

    record_audit_log(
        db,
        actor=current_user,
        action="rubric.create",
        target_type="rubric",
        target_id=rubric.id,
        summary=f"Rúbrica creada: {rubric.title}",
    )
    db.commit()
    return _serialize_rubric(rubric)


@router.put("/rubrics/{rubric_id}", response_model=RubricOut)
def update_rubric(
    rubric_id: int,
    payload: RubricUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_RUBRICS)),
):
    rubric = _get_rubric_or_404(rubric_id, db)
    values = _schema_values(payload, exclude_unset=True)

    if "status" in values:
        if values["status"] not in VALID_RUBRIC_STATUSES:
            raise HTTPException(status_code=422, detail=f"Estado inválido: {values['status']}")
        rubric.status = values["status"]
    if "title" in values and values["title"]:
        rubric.title = values["title"].strip()[:200]
    if "description" in values:
        rubric.description = (values["description"] or "").strip() or None
    if "guidance" in values:
        rubric.guidance = (values["guidance"] or "").strip() or None
    if "case_id" in values:
        _validate_case(values["case_id"], db)
        rubric.case_id = values["case_id"]
    if "due_at" in values:
        rubric.due_at = values["due_at"]
    if "bands" in values:
        rubric.bands_json = normalize_bands(values["bands"])
    if "criteria" in values:
        criteria = normalize_criteria(values["criteria"])
        if not criteria:
            raise HTTPException(status_code=422, detail="La rúbrica necesita al menos un criterio con niveles.")
        rubric.criteria_json = criteria
        rubric.max_score = rubric_max_score(criteria)

    rubric.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rubric)

    record_audit_log(
        db,
        actor=current_user,
        action="rubric.update",
        target_type="rubric",
        target_id=rubric.id,
        summary=f"Rúbrica actualizada: {rubric.title}",
    )
    db.commit()
    return _serialize_rubric(rubric)


@router.patch("/rubrics/{rubric_id}/status", response_model=RubricOut)
def update_rubric_status(
    rubric_id: int,
    payload: RubricStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_RUBRICS)),
):
    if payload.status not in VALID_RUBRIC_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {payload.status}")
    rubric = _get_rubric_or_404(rubric_id, db)
    rubric.status = payload.status
    rubric.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(rubric)
    return _serialize_rubric(rubric)


@router.get("/rubrics/{rubric_id}/progress", response_model=list[RubricStudentProgress])
def get_rubric_progress(
    rubric_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_REVIEW_REPORTS)),
):
    """Por cada estudiante que ya entregó: cuantos de sus intentos gasto y su
    ultima nota. Solo lista a quien ya subio algo -no hay concepto de "curso" o
    "seccion" en la plataforma para poder listar tambien a quien no ha entregado
    nada todavia."""
    rubric = _get_rubric_or_404(rubric_id, db)

    submissions = (
        db.query(ReportSubmission)
        .options(joinedload(ReportSubmission.evaluation), joinedload(ReportSubmission.student))
        .filter(ReportSubmission.rubric_id == rubric_id)
        .order_by(ReportSubmission.user_id, ReportSubmission.created_at.desc())
        .all()
    )

    by_student: dict[int, list[ReportSubmission]] = defaultdict(list)
    for submission in submissions:
        # El order_by compuesto (user_id, created_at desc) deja, dentro de cada
        # estudiante, la entrega mas reciente primero.
        by_student[submission.user_id].append(submission)

    progress: list[dict] = []
    for user_id, items in by_student.items():
        latest = items[0]
        evaluation = latest.evaluation
        # Puntaje tal cual lo define la rubrica (ej. 18 de 21), no convertido a
        # otra escala: mezclar "18" con "de 100" es lo que confunde a la hora de
        # leer una nota. Se toma del snapshot de la evaluacion, no del
        # max_score actual de la rubrica, por si esta se edito despues.
        latest_score = _effective_score(evaluation) if evaluation else None

        progress.append(
            {
                "user_id": user_id,
                "student_name": latest.student.name if latest.student else None,
                "student_email": latest.student.email if latest.student else None,
                "attempts": len(items),
                "attempts_max": MAX_OPEN_SUBMISSIONS_PER_RUBRIC,
                "latest_submission_id": latest.id,
                "latest_status": latest.status,
                "latest_score": latest_score,
                "latest_max_score": evaluation.max_score if evaluation else None,
                "latest_released": bool(evaluation and evaluation.released),
            }
        )

    progress.sort(key=lambda item: (item["student_name"] or "").lower())
    return progress


@router.delete("/rubrics/{rubric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    rubric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_RUBRICS)),
):
    """Baja logica: las entregas ya evaluadas siguen apuntando a la rubrica."""
    rubric = _get_rubric_or_404(rubric_id, db)
    rubric.is_active = False
    rubric.updated_at = datetime.utcnow()
    record_audit_log(
        db,
        actor=current_user,
        action="rubric.delete",
        target_type="rubric",
        target_id=rubric.id,
        summary=f"Rúbrica eliminada: {rubric.title}",
    )
    db.commit()


# ------------------------------------------------------------------- entregas

def _effective_score(evaluation: ReportEvaluation) -> float:
    return (
        evaluation.teacher_score
        if evaluation.teacher_score is not None
        else evaluation.total_score
    )


def _serialize_evaluation(evaluation: ReportEvaluation, rubric: Optional[Rubric]) -> dict:
    score = _effective_score(evaluation)
    # Si el docente corrigio el puntaje, el dictamen se recalcula con las bandas
    # de la rubrica: dejar el del modelo diria "Insuficiente" junto a una nota
    # que el docente subio a "Adecuado".
    band = evaluation.band
    if evaluation.teacher_score is not None and rubric is not None:
        band = band_for_score(rubric.bands_json or [], score) or band

    return {
        "total_score": evaluation.total_score,
        "max_score": evaluation.max_score,
        "band": band,
        "criteria": evaluation.criteria_json or [],
        "summary": evaluation.summary,
        "strengths": evaluation.strengths or [],
        "improvements": evaluation.improvements or [],
        "provider": evaluation.provider,
        "model": evaluation.model,
        "evaluated_at": _iso(evaluation.evaluated_at),
        "released": evaluation.released,
        "released_at": _iso(evaluation.released_at),
        "teacher_note": evaluation.teacher_note,
        "teacher_score": evaluation.teacher_score,
        "effective_score": score,
    }


def _serialize_submission(submission: ReportSubmission, *, is_reviewer: bool) -> dict:
    evaluation = submission.evaluation
    # El estudiante solo recibe la evaluacion cuando el docente la libera; hasta
    # entonces se le informa que existe, sin revelar el puntaje.
    show_evaluation = bool(evaluation) and (is_reviewer or evaluation.released)

    return {
        "id": submission.id,
        "batch_id": submission.batch_id,
        "rubric_id": submission.rubric_id,
        "rubric_title": submission.rubric.title if submission.rubric else None,
        "case_id": submission.case_id,
        "case_title": submission.case.title if submission.case else None,
        # La identidad del estudiante solo viaja hacia quien corrige.
        "user_id": submission.user_id if is_reviewer else None,
        "student_name": submission.student.name if (is_reviewer and submission.student) else None,
        "student_email": submission.student.email if (is_reviewer and submission.student) else None,
        "original_filename": submission.original_filename,
        "file_type": submission.file_type,
        "file_size": submission.file_size,
        "status": submission.status,
        "error": submission.error if is_reviewer else None,
        "created_at": _iso(submission.created_at),
        "evaluation": _serialize_evaluation(evaluation, submission.rubric) if show_evaluation else None,
        "evaluation_pending_release": bool(evaluation) and not evaluation.released and not is_reviewer,
    }


def _submission_query(db: Session):
    return db.query(ReportSubmission).options(
        joinedload(ReportSubmission.rubric),
        joinedload(ReportSubmission.case),
        joinedload(ReportSubmission.student),
        joinedload(ReportSubmission.evaluation),
    )


def _get_submission_or_404(submission_id: int, db: Session) -> ReportSubmission:
    submission = _submission_query(db).filter(ReportSubmission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    return submission


async def _run_evaluation(db: Session, submission: ReportSubmission) -> None:
    """Evalua la entrega y guarda (o reemplaza) su resultado.

    Un fallo del proveedor deja la entrega en `failed` con el motivo, en vez de
    perderla: el archivo y el texto ya estan guardados y el docente puede
    reintentar sin pedirle al estudiante que vuelva a subir nada.
    """
    rubric = submission.rubric
    try:
        result = await evaluate_report(
            db,
            rubric_title=rubric.title,
            criteria=rubric.criteria_json or [],
            bands=rubric.bands_json or [],
            guidance=rubric.guidance,
            report_text=submission.extracted_text,
        )
    except HTTPException as exc:
        submission.status = "failed"
        submission.error = str(exc.detail)[:2000]
        submission.updated_at = datetime.utcnow()
        db.commit()
        raise

    evaluation = submission.evaluation
    if evaluation is None:
        evaluation = ReportEvaluation(submission_id=submission.id)
        db.add(evaluation)

    evaluation.total_score = result["total_score"]
    evaluation.max_score = result["max_score"]
    evaluation.band = result["band"]
    evaluation.criteria_json = result["criteria"]
    evaluation.summary = result["summary"]
    evaluation.strengths = result["strengths"]
    evaluation.improvements = result["improvements"]
    evaluation.provider = result["provider"]
    evaluation.model = result["model"]
    evaluation.evaluated_at = datetime.utcnow()
    # Reevaluar no republica: si el docente ya habia liberado la nota anterior,
    # debe volver a decidir sobre la nueva.
    evaluation.released = False
    evaluation.released_at = None
    evaluation.released_by = None

    submission.status = "evaluated"
    submission.error = None
    submission.updated_at = datetime.utcnow()
    db.commit()


def _parse_rubric_ids(raw: str) -> list[int]:
    """CSV de IDs -> lista de enteros unicos, en el orden en que llegaron."""
    seen: dict[int, None] = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            rubric_id = int(chunk)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"ID de rúbrica inválido: '{chunk}'")
        seen[rubric_id] = None
    return list(seen.keys())


@router.post("/submissions", response_model=list[ReportSubmissionOut], status_code=status.HTTP_201_CREATED)
async def create_submission(
    file: UploadFile = File(...),
    rubric_ids: str = Form(..., description="IDs de rúbrica separados por coma"),
    case_id: Optional[int] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SUBMIT_REPORTS)),
):
    """Sube un informe y lo evalúa contra una o varias rúbricas a la vez.

    El archivo se lee y se guarda una sola vez; cada rúbrica seleccionada
    produce su propia entrega y su propia evaluación, agrupadas bajo el mismo
    `batch_id` para que la interfaz las muestre como un solo informe con
    varios resultados. Es todo o nada: si alguna rúbrica no es válida o algún
    tope ya se alcanzó, no se crea ninguna entrega.
    """
    rubric_id_list = _parse_rubric_ids(rubric_ids)
    if not rubric_id_list:
        raise HTTPException(status_code=422, detail="Selecciona al menos una rúbrica.")
    if len(rubric_id_list) > MAX_RUBRICS_PER_SUBMISSION:
        raise HTTPException(
            status_code=422,
            detail=f"Puedes evaluar un informe contra hasta {MAX_RUBRICS_PER_SUBMISSION} rúbricas a la vez.",
        )

    is_reviewer = user_has_permission(current_user, PERM_REVIEW_REPORTS)

    now = datetime.utcnow()
    rubrics: list[Rubric] = []
    for rubric_id in rubric_id_list:
        rubric = _get_rubric_or_404(rubric_id, db)
        if rubric.status != "published" and not is_reviewer:
            raise HTTPException(status_code=404, detail=f"Rúbrica no encontrada: ID {rubric_id}")
        # El docente/administrador puede seguir probando la rubrica despues de
        # la fecha; para el estudiante, la entrega queda cerrada.
        if rubric.due_at and now > rubric.due_at and not is_reviewer:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"La rúbrica '{rubric.title}' cerró sus entregas el "
                    f"{rubric.due_at.strftime('%d-%m-%Y %H:%M')}."
                ),
            )
        rubrics.append(rubric)

    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in REPORT_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Formato no permitido. Usa: {', '.join(sorted(REPORT_EXTENSIONS))}",
        )

    _validate_case(case_id, db)

    if not is_reviewer:
        # Se valida el tope de CADA rúbrica antes de crear ninguna entrega: es
        # todo o nada, para no dejar el envio a medias si la tercera rubrica
        # de cinco resulta estar copada.
        for rubric in rubrics:
            pending = (
                db.query(ReportSubmission.id)
                .filter(
                    ReportSubmission.user_id == current_user.id,
                    ReportSubmission.rubric_id == rubric.id,
                )
                .count()
            )
            if pending >= MAX_OPEN_SUBMISSIONS_PER_RUBRIC:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Ya enviaste {pending} informes para la rúbrica '{rubric.title}'. "
                        "Elimina alguno antes de subir otro."
                    ),
                )

    # `extract_text_from_upload` lee el archivo entero, valida el tamaño y
    # devuelve el texto plano; se hace antes de escribir en disco para no dejar
    # basura si el documento resulta ilegible. Se hace una sola vez para todas
    # las rubricas seleccionadas.
    text, _document_type = await extract_text_from_upload(file)

    await file.seek(0)
    data = await file.read()
    if len(data) > MAX_REPORT_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 15 MB.")

    stored_filename = f"{uuid.uuid4()}{extension}"
    destination = os.path.join(REPORT_DIR, stored_filename)
    with open(destination, "wb") as buffer:
        buffer.write(data)

    batch_id = str(uuid.uuid4())
    submissions: list[ReportSubmission] = []
    for rubric in rubrics:
        submission = ReportSubmission(
            batch_id=batch_id,
            rubric_id=rubric.id,
            case_id=case_id if case_id is not None else rubric.case_id,
            user_id=current_user.id,
            original_filename=(file.filename or stored_filename)[:200],
            # Las filas del mismo batch comparten el archivo fisico: no tiene
            # sentido guardar N copias identicas en disco solo porque se
            # evaluan contra N rubricas distintas.
            stored_filename=stored_filename,
            file_path=destination,
            file_type=extension.lstrip("."),
            file_size=len(data),
            extracted_text=text,
            status="pending",
        )
        db.add(submission)
        submissions.append(submission)
    db.commit()
    for submission in submissions:
        db.refresh(submission)

    # Secuencial, no en paralelo: todas las evaluaciones comparten esta misma
    # Session de SQLAlchemy (sincrona, inyectada una vez por request), y no es
    # segura para operaciones intercaladas entre corutinas. Cada rubrica falla
    # de forma independiente, sin tumbar a las demas del mismo envio.
    for submission in submissions:
        try:
            await _run_evaluation(db, submission)
        except HTTPException as exc:
            logger.warning(
                "Evaluación fallida para la entrega %s: %s", submission.id, exc.detail
            )

    submission_ids = [s.id for s in submissions]
    ordered = (
        _submission_query(db)
        .filter(ReportSubmission.id.in_(submission_ids))
        .order_by(ReportSubmission.id.asc())
        .all()
    )
    return [_serialize_submission(s, is_reviewer=is_reviewer) for s in ordered]


@router.get("/submissions/mine", response_model=list[ReportSubmissionOut])
def list_my_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_SUBMIT_REPORTS)),
):
    submissions = (
        _submission_query(db)
        .filter(ReportSubmission.user_id == current_user.id)
        .order_by(ReportSubmission.created_at.desc())
        .all()
    )
    return [_serialize_submission(s, is_reviewer=False) for s in submissions]


@router.get("/submissions", response_model=list[ReportSubmissionOut])
def list_submissions(
    rubric_id: Optional[int] = Query(None),
    case_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    released: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_REVIEW_REPORTS)),
):
    """Todas las entregas, con identidad y puntaje. Solo docente/administrador."""
    query = _submission_query(db)
    if rubric_id is not None:
        query = query.filter(ReportSubmission.rubric_id == rubric_id)
    if case_id is not None:
        query = query.filter(ReportSubmission.case_id == case_id)
    if status_filter:
        query = query.filter(ReportSubmission.status == status_filter)
    if released is not None:
        query = query.join(ReportEvaluation).filter(ReportEvaluation.released == released)

    submissions = query.order_by(ReportSubmission.created_at.desc()).limit(limit).all()
    return [_serialize_submission(s, is_reviewer=True) for s in submissions]


@router.get("/submissions/{submission_id}", response_model=ReportSubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(submission_id, db)
    is_reviewer = user_has_permission(current_user, PERM_REVIEW_REPORTS)
    if not is_reviewer and submission.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    return _serialize_submission(submission, is_reviewer=is_reviewer)


@router.post("/submissions/{submission_id}/evaluate", response_model=ReportSubmissionOut)
async def reevaluate_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_REVIEW_REPORTS)),
):
    """Vuelve a pasar el informe por el modelo (tras corregir la rúbrica, por ejemplo)."""
    submission = _get_submission_or_404(submission_id, db)
    await _run_evaluation(db, submission)
    submission = _get_submission_or_404(submission_id, db)

    record_audit_log(
        db,
        actor=current_user,
        action="report.reevaluate",
        target_type="report_submission",
        target_id=submission.id,
        summary=f"Informe reevaluado: {submission.original_filename}",
    )
    db.commit()
    return _serialize_submission(submission, is_reviewer=True)


@router.patch("/submissions/{submission_id}/release", response_model=ReportSubmissionOut)
def release_evaluation(
    submission_id: int,
    payload: EvaluationRelease,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_REVIEW_REPORTS)),
):
    """Publica (o retira) el resultado para el estudiante y guarda la corrección docente."""
    submission = _get_submission_or_404(submission_id, db)
    evaluation = submission.evaluation
    if evaluation is None:
        raise HTTPException(status_code=409, detail="Esta entrega todavía no tiene evaluación.")

    if payload.teacher_score is not None:
        if not (0 <= payload.teacher_score <= evaluation.max_score):
            raise HTTPException(
                status_code=422,
                detail=f"El puntaje corregido debe estar entre 0 y {evaluation.max_score:g}.",
            )
        evaluation.teacher_score = payload.teacher_score
    if payload.teacher_note is not None:
        evaluation.teacher_note = payload.teacher_note.strip() or None

    evaluation.released = payload.released
    evaluation.released_at = datetime.utcnow() if payload.released else None
    evaluation.released_by = current_user.id if payload.released else None
    db.commit()

    submission = _get_submission_or_404(submission_id, db)
    record_audit_log(
        db,
        actor=current_user,
        action="report.release" if payload.released else "report.unrelease",
        target_type="report_submission",
        target_id=submission.id,
        summary=(
            f"Evaluación {'liberada' if payload.released else 'retirada'}: "
            f"{submission.original_filename}"
        ),
    )
    db.commit()
    return _serialize_submission(submission, is_reviewer=True)


@router.get("/submissions/{submission_id}/file")
def download_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = _get_submission_or_404(submission_id, db)
    if (
        not user_has_permission(current_user, PERM_REVIEW_REPORTS)
        and submission.user_id != current_user.id
    ):
        raise HTTPException(status_code=404, detail="Entrega no encontrada")

    if not os.path.exists(submission.file_path):
        raise HTTPException(status_code=404, detail="El archivo ya no está disponible")

    return FileResponse(
        submission.file_path,
        media_type=_CONTENT_TYPES.get(submission.file_type, "application/octet-stream"),
        filename=submission.original_filename,
    )


@router.get("/submissions/{submission_id}/text")
def get_submission_text(
    submission_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission(PERM_REVIEW_REPORTS)),
):
    """Texto plano tal como lo leyó el modelo. Sirve para auditar una nota rara."""
    submission = _get_submission_or_404(submission_id, db)
    return {"id": submission.id, "text": submission.extracted_text}


@router.delete("/submissions/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """El estudiante puede retirar su entrega; el docente puede eliminar cualquiera."""
    submission = _get_submission_or_404(submission_id, db)
    is_reviewer = user_has_permission(current_user, PERM_REVIEW_REPORTS)
    if not is_reviewer and submission.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entrega no encontrada")
    # Una nota ya publicada es parte del registro academico del estudiante: solo
    # el docente puede retirarla.
    if not is_reviewer and submission.evaluation and submission.evaluation.released:
        raise HTTPException(
            status_code=409,
            detail="No puedes eliminar una entrega cuya evaluación ya fue publicada.",
        )

    stored_path = submission.file_path
    db.delete(submission)
    db.commit()

    # Otras filas del mismo envio (evaluadas contra otras rubricas) pueden
    # seguir apuntando al mismo archivo fisico: solo se borra si esta era la
    # ultima referencia.
    still_referenced = (
        db.query(ReportSubmission.id).filter(ReportSubmission.file_path == stored_path).first()
        is not None
    )
    if stored_path and not still_referenced and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError:
            # El registro ya no existe; un archivo huerfano no debe romper la
            # respuesta al usuario.
            pass
