from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..auth import PERM_MANAGE_IMAGES, get_current_user, require_permission
from ..db import get_db
from ..models import DiseaseCategory, User
from ..schemas import DiseaseCategoryCreate, DiseaseCategoryOut, DiseaseCategoryUpdate

router = APIRouter(prefix="/api/disease-categories", tags=["disease-categories"])


def _to_out(category: DiseaseCategory) -> DiseaseCategoryOut:
    return DiseaseCategoryOut(
        id=category.id,
        key=category.key,
        label=category.label,
        icon=category.icon,
        description=category.description,
        keywords=category.keywords or [],
        sort_order=category.sort_order,
        is_active=category.is_active,
        created_at=category.created_at.isoformat() if category.created_at else None,
    )


@router.get("", response_model=List[DiseaseCategoryOut])
async def list_disease_categories(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    Lista las categorias del catalogo de enfermedades de Imagenes IA. Todos
    los usuarios autenticados pueden leerlas (estudiantes las necesitan para
    ver la biblioteca agrupada); solo docentes/administradores las editan.
    """
    categories = (
        db.query(DiseaseCategory)
        .filter(DiseaseCategory.is_active == True)
        .order_by(DiseaseCategory.sort_order, DiseaseCategory.label)
        .all()
    )
    return [_to_out(c) for c in categories]


@router.post("", response_model=DiseaseCategoryOut)
async def create_disease_category(
    payload: DiseaseCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES)),
):
    key = payload.key.strip().lower().replace(" ", "-")
    if not key:
        raise HTTPException(status_code=422, detail="La clave de la categoría no puede quedar vacía")

    existing = db.query(DiseaseCategory).filter(DiseaseCategory.key == key).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Ya existe una categoría con la clave '{key}'")

    category = DiseaseCategory(
        key=key,
        label=payload.label.strip(),
        icon=payload.icon.strip() or "🧫",
        description=(payload.description or "").strip() or None,
        keywords=[k.strip().lower() for k in payload.keywords if k.strip()],
        sort_order=payload.sort_order,
        created_by=current_user.id,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.patch("/{category_id}", response_model=DiseaseCategoryOut)
async def update_disease_category(
    category_id: int,
    payload: DiseaseCategoryUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES)),
):
    category = db.query(DiseaseCategory).filter(DiseaseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if payload.label is not None:
        category.label = payload.label.strip()
    if payload.icon is not None:
        category.icon = payload.icon.strip() or category.icon
    if payload.description is not None:
        category.description = payload.description.strip() or None
    if payload.keywords is not None:
        category.keywords = [k.strip().lower() for k in payload.keywords if k.strip()]
    if payload.sort_order is not None:
        category.sort_order = payload.sort_order
    if payload.is_active is not None:
        category.is_active = payload.is_active

    db.commit()
    db.refresh(category)
    return _to_out(category)


@router.delete("/{category_id}")
async def delete_disease_category(
    category_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_IMAGES)),
):
    """Baja logica: las imagenes que ya tenian esta patologia no se tocan,
    solo dejan de tener una categoria visual dedicada en Imagenes IA."""
    category = db.query(DiseaseCategory).filter(DiseaseCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    category.is_active = False
    db.commit()
    return {"message": f"Categoría '{category.label}' eliminada", "id": category_id}
