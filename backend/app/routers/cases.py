import os
import shutil
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
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
from ..models import Case, CaseImage, CaseLink, MedicalImage, SCTTest, User
from ..schemas import CaseOut, CaseCreate, CaseUpdate, CaseStatusUpdate

router = APIRouter(prefix="/api", tags=["cases"])

_VALID_STATUSES = {"draft", "published", "archived"}

CASE_IMAGE_DIR = "uploads/case_images"
os.makedirs(CASE_IMAGE_DIR, exist_ok=True)
# Solo formatos de imagen plana: las laminas WSI (.svs/.tiff) pertenecen a la
# piscina histopatologica, que tiene su propio visor y su propio pipeline.
CASE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_CASE_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGES_PER_CASE = 12
_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ------------------------------------------------------------- recursos externos
# Tipos de recurso que puede adjuntar el docente. Wooclap se distingue del resto
# porque es la via de retroalimentacion interactiva: el estudiante sale de la
# plataforma a responder en vivo, no a leer.
CASE_LINK_KINDS = {
    "wooclap",
    "bibliografia",
    "guia",
    "articulo",
    "video",
    "otro",
}
MAX_LINKS_PER_CASE = 15
MAX_LINK_URL_LENGTH = 1000
# Solo http/https: esquemas como javascript:, data: o file: convertirian un
# enlace publicado por un docente en un vector de ejecucion en el navegador del
# estudiante, o en una lectura del sistema de archivos local.
ALLOWED_LINK_SCHEMES = {"http", "https"}


def _validate_link_url(raw_url: str, label: str) -> str:
    url = (raw_url or "").strip()
    if not url:
        raise HTTPException(status_code=422, detail=f"El recurso '{label}' no tiene URL.")
    if len(url) > MAX_LINK_URL_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"La URL del recurso '{label}' supera los {MAX_LINK_URL_LENGTH} caracteres.",
        )

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_LINK_SCHEMES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"La URL del recurso '{label}' debe empezar por http:// o https:// "
                f"(recibido: '{parsed.scheme or 'sin esquema'}')."
            ),
        )
    if not parsed.netloc:
        raise HTTPException(
            status_code=422,
            detail=f"La URL del recurso '{label}' no tiene un dominio valido.",
        )
    return url


def _normalize_link_payload(links: list, current_user: User) -> list[dict]:
    if len(links) > MAX_LINKS_PER_CASE:
        raise HTTPException(
            status_code=422,
            detail=f"Un caso admite hasta {MAX_LINKS_PER_CASE} recursos externos.",
        )

    normalized: list[dict] = []
    for position, link in enumerate(links):
        values = link if isinstance(link, dict) else _schema_values(link)
        label = (values.get("label") or "").strip()
        if not label:
            raise HTTPException(
                status_code=422,
                detail="Cada recurso externo necesita un titulo visible.",
            )

        kind = (values.get("kind") or "otro").strip().lower()
        if kind not in CASE_LINK_KINDS:
            raise HTTPException(
                status_code=422,
                detail=f"Tipo de recurso no permitido: {kind}",
            )

        description = (values.get("description") or "").strip() or None
        normalized.append({
            "kind": kind,
            "label": label[:200],
            "url": _validate_link_url(values.get("url"), label),
            "description": description[:400] if description else None,
            "position": position,
            "created_by": current_user.id,
        })
    return normalized


def _replace_case_links(case: Case, links: list, current_user: User, db: Session) -> None:
    """Sustituye el conjunto completo de recursos del caso.

    El formulario del docente edita la lista entera, asi que reemplazarla es mas
    simple y menos propenso a divergencias que sincronizar altas y bajas una a una.
    """
    normalized = _normalize_link_payload(links, current_user)
    case.links.clear()
    db.flush()
    for values in normalized:
        case.links.append(CaseLink(**values))


def _serialize_case_link(link: CaseLink) -> dict:
    return {
        "id": link.id,
        "case_id": link.case_id,
        "kind": link.kind,
        "label": link.label,
        "url": link.url,
        "description": link.description,
        "position": link.position,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


def _schema_values(schema, **kwargs) -> dict:
    if hasattr(schema, "model_dump"):
        return schema.model_dump(**kwargs)
    return schema.dict(**kwargs)


def _validate_linked_resources(values: dict, db: Session) -> None:
    image_id = values.get("image_id")
    if image_id is not None:
        image = (
            db.query(MedicalImage.id)
            .filter(MedicalImage.id == image_id, MedicalImage.is_active == True)
            .first()
        )
        if not image:
            raise HTTPException(
                status_code=422,
                detail=f"Imagen histopatológica no encontrada: ID {image_id}",
            )

    sct_test_id = values.get("sct_test_id")
    if sct_test_id is not None:
        sct_test = (
            db.query(SCTTest.id)
            .filter(SCTTest.id == sct_test_id, SCTTest.is_active == True)
            .first()
        )
        if not sct_test:
            raise HTTPException(
                status_code=422,
                detail=f"Test SCT no encontrado: ID {sct_test_id}",
            )


def _serialize_case_image(image: CaseImage) -> dict:
    return {
        "id": image.id,
        "case_id": image.case_id,
        "caption": image.caption,
        "modality": image.modality,
        "file_type": image.file_type,
        "file_size": image.file_size,
        "position": image.position,
        "original_filename": image.original_filename,
        "url": f"/api/cases/images/{image.id}/file",
        "created_at": image.created_at.isoformat() if image.created_at else None,
    }


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
        "images": [_serialize_case_image(img) for img in (case.images or [])],
        "links": [_serialize_case_link(link) for link in (case.links or [])],
        "created_by": case.created_by,
        "status": case.status,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
    }


def _get_case_or_404(case_id: int, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id, Case.is_active == True).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return case


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

    values = _schema_values(case_data)
    _validate_linked_resources(values, db)

    new_case = Case(
        title=values["title"],
        description=values["description"],
        body=values["body"],
        clinical_context=values.get("clinical_context"),
        learning_objectives=values.get("learning_objectives"),
        difficulty=values.get("difficulty"),
        topic=values.get("topic"),
        image_id=values.get("image_id"),
        sct_test_id=values.get("sct_test_id"),
        created_by=current_user.id,
        status=values["status"],
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(new_case)

    for link_values in _normalize_link_payload(values.get("links") or [], current_user):
        new_case.links.append(CaseLink(**link_values))

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

    values = _schema_values(case_data, exclude_unset=True)
    _validate_linked_resources(values, db)

    # links es una relacion, no una columna: setattr con dicts crudos la rompe.
    links_payload = values.pop("links", None)

    for field, value in values.items():
        setattr(case, field, value)
    if links_payload is not None:
        _replace_case_links(case, links_payload, current_user, db)
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


# ---------------------------------------------------------------- case images
# Imagenes ilustrativas del caso (radiografia, TAC, fotografia clinica). No se
# mezclan con medical_images: esas son laminas histopatologicas que el
# clasificador puede analizar, y una radiografia no pertenece a ese dominio.


@router.get("/cases/{case_id}/images")
def list_case_images(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = _get_case_or_404(case_id, db)
    if case.status != "published" and not user_has_permission(current_user, PERM_MANAGE_CASES):
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    return [_serialize_case_image(img) for img in case.images]


@router.post("/cases/{case_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_case_images(
    case_id: int,
    files: list[UploadFile] = File(...),
    captions: Optional[str] = Form(default=None),
    modality: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    """Sube una o varias imagenes al caso.

    `captions` acepta leyendas separadas por '|' en el mismo orden que los
    archivos; si faltan, se usa el nombre original del archivo.
    """
    case = _get_case_or_404(case_id, db)

    caption_list = [c.strip() for c in (captions or "").split("|")] if captions else []
    existing = len(case.images)
    if existing + len(files) > MAX_IMAGES_PER_CASE:
        raise HTTPException(
            status_code=422,
            detail=f"Un caso admite hasta {MAX_IMAGES_PER_CASE} imagenes (ya tiene {existing}).",
        )

    created: list[CaseImage] = []
    for index, upload in enumerate(files):
        extension = os.path.splitext(upload.filename or "")[1].lower()
        if extension not in CASE_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Formato no permitido en '{upload.filename}'. "
                    f"Usa: {', '.join(sorted(CASE_IMAGE_EXTENSIONS))}"
                ),
            )

        unique_name = f"{uuid.uuid4()}{extension}"
        destination = os.path.join(CASE_IMAGE_DIR, unique_name)
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)

        size = os.path.getsize(destination)
        if size > MAX_CASE_IMAGE_BYTES:
            os.remove(destination)
            raise HTTPException(
                status_code=413,
                detail=f"'{upload.filename}' supera el limite de 20 MB.",
            )

        caption = caption_list[index] if index < len(caption_list) and caption_list[index] else None
        row = CaseImage(
            case_id=case.id,
            filename=unique_name,
            original_filename=(upload.filename or unique_name)[:200],
            caption=(caption or upload.filename or "")[:300] or None,
            modality=(modality or None),
            file_type=extension.lstrip("."),
            file_size=size,
            file_path=destination,
            position=existing + index,
            uploaded_by=current_user.id,
        )
        db.add(row)
        created.append(row)

    case.updated_at = datetime.utcnow()
    db.commit()
    for row in created:
        db.refresh(row)
    return [_serialize_case_image(row) for row in created]


@router.get("/cases/images/{image_id}/file")
def get_case_image_file(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = db.query(CaseImage).filter(CaseImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    case = db.query(Case).filter(Case.id == image.case_id, Case.is_active == True).first()
    if not case or (
        case.status != "published" and not user_has_permission(current_user, PERM_MANAGE_CASES)
    ):
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    if not os.path.exists(image.file_path):
        raise HTTPException(status_code=404, detail="Archivo de imagen no disponible")

    return FileResponse(
        image.file_path,
        media_type=_CONTENT_TYPES.get(f".{image.file_type}", "application/octet-stream"),
        filename=image.original_filename,
    )


@router.delete("/cases/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case_image(
    image_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PERM_MANAGE_CASES)),
):
    image = db.query(CaseImage).filter(CaseImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    stored_path = image.file_path
    db.delete(image)
    db.commit()

    if stored_path and os.path.exists(stored_path):
        try:
            os.remove(stored_path)
        except OSError:
            # El registro ya se elimino; un archivo huerfano no debe romper la
            # respuesta al usuario.
            pass
