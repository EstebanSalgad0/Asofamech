from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import datetime

from ..db import get_db
from ..auth import (
    PERM_MANAGE_CASES,
    get_current_user,
    require_permission,
    user_has_permission,
    ROLE_STUDENT,
    user_role,
)
from ..models import Case, User
from ..schemas import CaseOut, CaseCreate, CaseUpdate, CaseStatusUpdate

router = APIRouter(prefix="/api", tags=["cases"])

_VALID_STATUSES = {"draft", "published", "archived"}


def _serialize(case: Case) -> dict:
    return {
        "id": case.id,
        "title": case.title,
        "description": case.description,
        "body": case.body,
        "clinical_context": case.clinical_context,
        "learning_objectives": case.learning_objectives,
        "difficulty": case.difficulty,
        "topic": case.topic,
        "image_id": case.image_id,
        "sct_test_id": case.sct_test_id,
        "created_by": case.created_by,
        "status": case.status,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


@router.get("/cases", response_model=list[CaseOut])
def list_cases(
    topic: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_manager = user_has_permission(current_user, PERM_MANAGE_CASES)
    query = db.query(Case).filter(Case.is_active == True)

    if not is_manager:
        query = query.filter(Case.status == "published")
    elif status_filter and status_filter in _VALID_STATUSES:
        query = query.filter(Case.status == status_filter)

    if topic:
        query = query.filter(Case.topic.ilike(f"%{topic}%"))
    if difficulty:
        query = query.filter(Case.difficulty == difficulty)

    cases = query.order_by(Case.created_at.desc()).all()
    return [_serialize(c) for c in cases]


@router.get("/cases/search", response_model=list[CaseOut])
def search_cases(
    q: Optional[str] = Query(None, description="Palabras clave"),
    topic: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_manager = user_has_permission(current_user, PERM_MANAGE_CASES)
    query = db.query(Case).filter(Case.is_active == True)

    if not is_manager:
        query = query.filter(Case.status == "published")

    if q:
        term = f"%{q}%"
        query = query.filter(
            or_(
                Case.title.ilike(term),
                Case.description.ilike(term),
                Case.body.ilike(term),
                Case.topic.ilike(term),
                Case.clinical_context.ilike(term),
                Case.learning_objectives.ilike(term),
            )
        )
    if topic:
        query = query.filter(Case.topic.ilike(f"%{topic}%"))
    if difficulty:
        query = query.filter(Case.difficulty == difficulty)

    cases = query.order_by(Case.created_at.desc()).limit(limit).all()
    return [_serialize(c) for c in cases]


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id, Case.is_active == True).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    is_manager = user_has_permission(current_user, PERM_MANAGE_CASES)
    if not is_manager and case.status != "published":
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    return _serialize(case)


@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    case_data: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    if case_data.status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {case_data.status}")

    new_case = Case(
        title=case_data.title,
        description=case_data.description,
        body=case_data.body,
        clinical_context=case_data.clinical_context,
        learning_objectives=case_data.learning_objectives,
        difficulty=case_data.difficulty,
        topic=case_data.topic,
        image_id=case_data.image_id,
        sct_test_id=case_data.sct_test_id,
        created_by=current_user.id,
        status=case_data.status,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return _serialize(new_case)


@router.put("/cases/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    case_data: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    case = db.query(Case).filter(Case.id == case_id, Case.is_active == True).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    for field, value in case_data.dict(exclude_unset=True).items():
        setattr(case, field, value)
    case.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(case)
    return _serialize(case)


@router.patch("/cases/{case_id}/status", response_model=CaseOut)
def update_case_status(
    case_id: int,
    payload: CaseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Estado inválido: {payload.status}")

    case = db.query(Case).filter(Case.id == case_id, Case.is_active == True).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    case.status = payload.status
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    return _serialize(case)


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    case = db.query(Case).filter(Case.id == case_id, Case.is_active == True).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")

    case.is_active = False
    case.updated_at = datetime.utcnow()
    db.commit()
