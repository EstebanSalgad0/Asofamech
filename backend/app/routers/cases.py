from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from ..db import get_db
from ..models import Case
from ..schemas import CaseOut, CaseCreate

router = APIRouter(prefix="/api", tags=["cases"])

@router.get("/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).filter(Case.is_active == True).all()
    return cases


@router.post("/cases", response_model=CaseOut)
def create_case(case_data: CaseCreate, db: Session = Depends(get_db)):
    """
    Crea un nuevo caso clínico
    """
    new_case = Case(
        title=case_data.title,
        description=case_data.description,
        body=case_data.body,
        is_active=True
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case


@router.get("/cases/search", response_model=list[CaseOut])
def search_cases(
    q: Optional[str] = Query(None, description="Búsqueda por palabras clave"),
    limit: int = Query(5, description="Número máximo de resultados"),
    db: Session = Depends(get_db)
):
    """
    Busca casos clínicos por palabras clave en título, descripción, 
    síntomas, diagnóstico, etc.
    """
    query = db.query(Case).filter(Case.is_active == True)
    
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Case.title.ilike(search_term),
                Case.description.ilike(search_term),
                Case.body.ilike(search_term)
            )
        )
    
    cases = query.limit(limit).all()
    return cases
