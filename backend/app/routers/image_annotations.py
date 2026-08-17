"""Anotaciones docentes sobre una region de una imagen del visor.

No tiene relacion alguna con el pipeline de clasificacion (CONCH/CAMELYON):
una anotacion es un rectangulo con texto que el docente deja sobre la imagen
para que el estudiante vea "esto es un linfocito" o "aqui hay necrosis
caseosa", sin que en ningun momento se invoque al modelo de IA. Existe
precisamente para las imagenes que la coordinacion academica pidio no
analizar, y para complementar las que si se analizan con contexto que el
clasificador no puede dar.

Lectura: cualquier usuario autenticado (igual que el resto del visor).
Escritura: solo quien gestiona contenido educativo (docente/administrador),
y cualquiera de ellos puede editar o borrar la anotacion de otro colega -
es contenido institucional del curso, no propiedad personal de quien la creo.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from ..auth import (
    PERM_MANAGE_EDUCATIONAL_CONTENT,
    get_current_user,
    require_permission,
)
from ..db import get_db
from ..models import ImageAnnotation, MedicalImage, User
from ..schemas import ImageAnnotationCreate, ImageAnnotationOut, ImageAnnotationUpdate

router = APIRouter(prefix="/api/medical-images", tags=["image-annotations"])

VALID_SHAPES = {"rect", "ellipse"}


def _serialize(annotation: ImageAnnotation) -> dict:
    return {
        "id": annotation.id,
        "image_id": annotation.image_id,
        "roi": annotation.roi,
        "shape": annotation.shape,
        "label": annotation.label,
        "note": annotation.note,
        "created_by": annotation.created_by,
        "creator_name": annotation.creator.name if annotation.creator else None,
        "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
        "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None,
    }


def _get_image_or_404(image_id: int, db: Session) -> MedicalImage:
    image = (
        db.query(MedicalImage)
        .filter(MedicalImage.id == image_id, MedicalImage.is_active == True)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return image


def _get_annotation_or_404(annotation_id: int, db: Session) -> ImageAnnotation:
    annotation = (
        db.query(ImageAnnotation)
        .options(joinedload(ImageAnnotation.creator))
        .filter(ImageAnnotation.id == annotation_id)
        .first()
    )
    if not annotation:
        raise HTTPException(status_code=404, detail="Anotación no encontrada")
    return annotation


@router.get("/{image_id}/annotations", response_model=list[ImageAnnotationOut])
def list_annotations(
    image_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    _get_image_or_404(image_id, db)
    annotations = (
        db.query(ImageAnnotation)
        .options(joinedload(ImageAnnotation.creator))
        .filter(ImageAnnotation.image_id == image_id)
        .order_by(ImageAnnotation.created_at.asc())
        .all()
    )
    return [_serialize(a) for a in annotations]


@router.post(
    "/{image_id}/annotations",
    response_model=ImageAnnotationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation(
    image_id: int,
    payload: ImageAnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_EDUCATIONAL_CONTENT)),
):
    _get_image_or_404(image_id, db)

    shape = (payload.shape or "rect").strip().lower()
    if shape not in VALID_SHAPES:
        raise HTTPException(status_code=422, detail=f"Forma no valida: {shape}")

    annotation = ImageAnnotation(
        image_id=image_id,
        roi=payload.roi.model_dump() if hasattr(payload.roi, "model_dump") else payload.roi.dict(),
        shape=shape,
        label=payload.label.strip(),
        note=(payload.note or "").strip() or None,
        created_by=current_user.id,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return _serialize(annotation)


@router.put("/annotations/{annotation_id}", response_model=ImageAnnotationOut)
def update_annotation(
    annotation_id: int,
    payload: ImageAnnotationUpdate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_EDUCATIONAL_CONTENT)),
):
    annotation = _get_annotation_or_404(annotation_id, db)

    if payload.roi is not None:
        annotation.roi = payload.roi.model_dump() if hasattr(payload.roi, "model_dump") else payload.roi.dict()
    if payload.shape is not None:
        shape = payload.shape.strip().lower()
        if shape not in VALID_SHAPES:
            raise HTTPException(status_code=422, detail=f"Forma no valida: {shape}")
        annotation.shape = shape
    if payload.label is not None:
        annotation.label = payload.label.strip()
    if payload.note is not None:
        annotation.note = payload.note.strip() or None

    annotation.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(annotation)
    return _serialize(annotation)


@router.delete("/annotations/{annotation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_annotation(
    annotation_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_permission(PERM_MANAGE_EDUCATIONAL_CONTENT)),
):
    annotation = _get_annotation_or_404(annotation_id, db)
    db.delete(annotation)
    db.commit()
