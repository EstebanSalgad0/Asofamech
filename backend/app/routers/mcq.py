from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from typing import List

from ..rag_file_loader import extract_text_from_bytes
from ..mcq_import import import_mcq_from_text
from ..schemas import (
    MCQImportResponse, MCQItem, MCQSaveRequest, MCQTestOut, MCQTestDetail,
    MCQTestUpdate, MCQAnswerItem, MCQAttemptCreate, MCQAttemptOut,
    MCQAttemptWithTest, MCQAttemptDetail, MCQAttemptAdminOut,
)
from ..models import MCQTest, MCQAttempt, User
from ..db import get_db
from ..auth import (
    PERM_MANAGE_MCQ, PERM_REVIEW_STUDENTS,
    get_current_user, require_permission, user_has_permission,
)

router = APIRouter(prefix="/api/mcq", tags=["MCQ"])

VALID_STATUSES = {"draft", "published", "archived"}


def calculate_mcq_attempt_score(items_json: list[dict], answers: list[MCQAnswerItem]) -> tuple[int, int, float]:
    correct_map = {}
    for item in items_json or []:
        try:
            correct_map[int(item["id"])] = int(item["correct_index"])
        except (KeyError, TypeError, ValueError):
            continue

    correct_count = 0
    for answer in answers:
        item_id = int(answer.item_id)
        if item_id in correct_map and correct_map[item_id] == int(answer.selected_index):
            correct_count += 1

    total = len(items_json or [])
    score = round(correct_count / total, 4) if total > 0 else 0.0
    return correct_count, total, score


def _test_to_out(test: MCQTest) -> MCQTestOut:
    return MCQTestOut(
        id=test.id,
        name=test.name,
        topic=test.topic,
        difficulty=test.difficulty,
        num_items=test.num_items,
        created_at=test.created_at.isoformat(),
        status=test.status,
        created_by=test.created_by,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Importacion desde archivo (IA) — no guarda nada
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/import", response_model=MCQImportResponse)
async def import_mcq_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_MCQ)),
):
    """Propone un banco de preguntas a partir de un documento. No guarda nada:
    el docente revisa y edita el resultado en el constructor antes de guardar."""
    data = await file.read()
    text, _document_type = extract_text_from_bytes(data, file.filename, file.content_type)
    draft = await import_mcq_from_text(db, text)
    return MCQImportResponse(**draft)


# ──────────────────────────────────────────────────────────────────────────────
# Gestion del banco de actividades (PERM_MANAGE_MCQ)
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/save", response_model=MCQTestOut)
async def save_mcq_test(
    request: MCQSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_MCQ)),
):
    """Guarda un test de alternativas en el banco de actividades (creado a
    mano o revisado desde una importacion)."""
    if request.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido. Use: {VALID_STATUSES}")
    try:
        items_dict = [item.dict() for item in request.items]
        mcq_test = MCQTest(
            name=request.name,
            topic=request.topic,
            difficulty=request.difficulty,
            num_items=request.num_items,
            items_json=items_dict,
            status=request.status,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(mcq_test)
        db.commit()
        db.refresh(mcq_test)
        return _test_to_out(mcq_test)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar test de alternativas: {e}")


@router.get("/list", response_model=List[MCQTestOut])
async def list_mcq_tests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista tests de alternativas del banco de actividades.
    - Estudiantes: solo tests publicados (status='published').
    - Docentes / Administradores: todos los tests activos (draft, published, archived).
    """
    query = db.query(MCQTest).filter(MCQTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_MCQ):
        query = query.filter(MCQTest.status == "published")
    tests = query.order_by(MCQTest.created_at.desc()).all()
    return [_test_to_out(t) for t in tests]


@router.get("/admin/attempts", response_model=List[MCQAttemptAdminOut])
async def list_all_attempts(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_REVIEW_STUDENTS)),
):
    """Lista todos los intentos de todos los estudiantes. Solo docentes y administradores."""
    attempts = (
        db.query(MCQAttempt)
        .options(joinedload(MCQAttempt.test), joinedload(MCQAttempt.user))
        .order_by(MCQAttempt.completed_at.desc())
        .limit(300)
        .all()
    )
    result = []
    for a in attempts:
        result.append(MCQAttemptAdminOut(
            id=a.id,
            test_id=a.test_id,
            user_id=a.user_id,
            score=a.score,
            correct_count=a.correct_count,
            total_items=a.total_items,
            completed_at=a.completed_at.isoformat(),
            test_name=a.test.name if a.test else "",
            test_topic=a.test.topic if a.test else "",
            test_difficulty=a.test.difficulty if a.test else "",
            user_email=a.user.email if a.user else "",
            user_name=a.user.name if a.user else "",
        ))
    return result


@router.get("/my-attempts", response_model=List[MCQAttemptWithTest])
async def list_my_attempts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Historial de intentos del usuario autenticado, enriquecido con datos del test."""
    attempts = (
        db.query(MCQAttempt)
        .options(joinedload(MCQAttempt.test))
        .filter(MCQAttempt.user_id == current_user.id)
        .order_by(MCQAttempt.completed_at.desc())
        .all()
    )
    return [
        MCQAttemptWithTest(
            id=a.id,
            test_id=a.test_id,
            user_id=a.user_id,
            score=a.score,
            correct_count=a.correct_count,
            total_items=a.total_items,
            completed_at=a.completed_at.isoformat(),
            test_name=a.test.name if a.test else "",
            test_topic=a.test.topic if a.test else "",
            test_difficulty=a.test.difficulty if a.test else "",
        )
        for a in attempts
    ]


@router.get("/attempts/{attempt_id}", response_model=MCQAttemptDetail)
async def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Detalle de un intento. El propietario o un docente/admin pueden verlo."""
    attempt = db.query(MCQAttempt).filter(MCQAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Intento no encontrado")
    if attempt.user_id != current_user.id and not user_has_permission(current_user, PERM_REVIEW_STUDENTS):
        raise HTTPException(status_code=403, detail="Sin acceso a este intento")
    test = db.query(MCQTest).filter(MCQTest.id == attempt.test_id).first()
    return MCQAttemptDetail(
        id=attempt.id,
        test_id=attempt.test_id,
        user_id=attempt.user_id,
        score=attempt.score,
        correct_count=attempt.correct_count,
        total_items=attempt.total_items,
        completed_at=attempt.completed_at.isoformat(),
        answers_json=attempt.answers_json,
        test_name=test.name if test else "",
        test_topic=test.topic if test else "",
        test_difficulty=test.difficulty if test else "",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Resolucion por estudiante
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/{test_id}/attempt", response_model=MCQAttemptOut)
async def submit_mcq_attempt(
    test_id: int,
    request: MCQAttemptCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Registra un intento de resolución. El orden en que el estudiante vio las
    preguntas y alternativas se baraja solo en el frontend; aquí se califica
    siempre contra el `id`/`correct_index` originales, así que el orden no
    afecta el puntaje.
    """
    query = db.query(MCQTest).filter(MCQTest.id == test_id, MCQTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_MCQ):
        query = query.filter(MCQTest.status == "published")
    test = query.first()
    if not test:
        raise HTTPException(status_code=404, detail="Test de alternativas no encontrado o no publicado")

    correct_count, total, score = calculate_mcq_attempt_score(test.items_json, request.answers)

    started_at = None
    if request.started_at:
        try:
            started_at = datetime.fromisoformat(request.started_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass

    attempt = MCQAttempt(
        test_id=test_id,
        user_id=current_user.id,
        answers_json=[a.dict() for a in request.answers],
        score=score,
        correct_count=correct_count,
        total_items=total,
        started_at=started_at,
        completed_at=datetime.utcnow(),
    )
    try:
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al guardar intento: {e}")

    return MCQAttemptOut(
        id=attempt.id,
        test_id=attempt.test_id,
        user_id=attempt.user_id,
        score=attempt.score,
        correct_count=attempt.correct_count,
        total_items=attempt.total_items,
        completed_at=attempt.completed_at.isoformat(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Edicion y acceso individual (PERM_MANAGE_MCQ)
# ──────────────────────────────────────────────────────────────────────────────

@router.patch("/{test_id}", response_model=MCQTestOut)
async def update_mcq_test(
    test_id: int,
    request: MCQTestUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_MCQ)),
):
    """Actualiza nombre, estado o tema de un test de alternativas."""
    test = db.query(MCQTest).filter(MCQTest.id == test_id, MCQTest.is_active == True).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test de alternativas no encontrado")
    if request.name is not None:
        test.name = request.name.strip()
    if request.status is not None:
        if request.status not in VALID_STATUSES:
            raise HTTPException(status_code=422, detail=f"Estado inválido. Use: {VALID_STATUSES}")
        test.status = request.status
    if request.topic is not None:
        test.topic = request.topic.strip()
    try:
        db.commit()
        db.refresh(test)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al actualizar test: {e}")
    return _test_to_out(test)


@router.delete("/{test_id}")
async def delete_mcq_test(
    test_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_MCQ)),
):
    """Soft-delete de un test de alternativas. Requiere PERM_MANAGE_MCQ."""
    test = db.query(MCQTest).filter(MCQTest.id == test_id, MCQTest.is_active == True).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test de alternativas no encontrado")
    test.is_active = False
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al eliminar test: {e}")
    return {"message": f"Test '{test.name}' eliminado", "id": test_id}


@router.get("/{test_id}", response_model=MCQTestDetail)
async def get_mcq_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Obtiene un test de alternativas por ID. Estudiantes solo pueden ver tests publicados."""
    query = db.query(MCQTest).filter(MCQTest.id == test_id, MCQTest.is_active == True)
    if not user_has_permission(current_user, PERM_MANAGE_MCQ):
        query = query.filter(MCQTest.status == "published")
    test = query.first()
    if not test:
        raise HTTPException(status_code=404, detail="Test de alternativas no encontrado o no publicado")
    items = [MCQItem(**item) for item in test.items_json]
    return MCQTestDetail(
        id=test.id,
        name=test.name,
        topic=test.topic,
        difficulty=test.difficulty,
        num_items=test.num_items,
        items=items,
        created_at=test.created_at.isoformat(),
        status=test.status,
    )
