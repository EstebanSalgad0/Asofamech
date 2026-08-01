import os
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth_security import display_role, hash_password, normalize_email, normalize_role_for_storage
from ..auth import require_admin
from ..audit import audit_log_to_payload, record_audit_log
from ..db import get_db
from ..email_service import send_template_email
from ..models import AIConfiguration, AuditLog, Document, DocumentChunk, EmailTemplate, User
from ..rag_utils import EMBEDDING_DIMENSIONS


router = APIRouter(prefix="/api/admin", tags=["admin"])

_integrations_cache: dict = {"data": None, "ts": 0.0}
_INTEGRATIONS_TTL = 45.0  # segundos


DEFAULT_AI_CONFIG = {
    "llm_model": {
        "value": os.getenv("LLM_MODEL", "llama3.1:8b"),
        "value_type": "string",
        "description": "Modelo generativo usado por Ollama para el chatbot y SCT.",
    },
    "ollama_url": {
        "value": os.getenv("OLLAMA_URL", os.getenv("OLLAMA_HOST", "http://ollama:11434")),
        "value_type": "string",
        "description": "URL interna del servicio Ollama.",
    },
    "rag_enabled": {
        "value": "true",
        "value_type": "boolean",
        "description": "Activa recuperacion documental para contextualizar respuestas.",
    },
    "scope_filter_enabled": {
        "value": "true",
        "value_type": "boolean",
        "description": "Clasifica si la consulta pertenece al ambito medico antes de responder.",
    },
    "temperature": {
        "value": "0.4",
        "value_type": "float",
        "description": (
            "Creatividad del modelo generativo. Valores bajos reducen la invencion "
            "de datos y mejoran la fidelidad a las fuentes RAG."
        ),
    },
    "top_p": {
        "value": "0.9",
        "value_type": "float",
        "description": "Muestreo nucleus del modelo generativo.",
    },
    "max_context_documents": {
        "value": "4",
        "value_type": "integer",
        "description": "Cantidad maxima de documentos RAG enviados al prompt.",
    },
    "chat_max_tokens": {
        "value": "800",
        "value_type": "integer",
        "description": "Tokens maximos por respuesta del chatbot (num_predict). Menos tokens = respuesta mas rapida.",
    },
    "chat_num_ctx": {
        "value": "4096",
        "value_type": "integer",
        "description": "Ventana de contexto del chatbot (num_ctx). Valores altos recuerdan mas historial pero son mas lentos.",
    },
    "feedback_max_tokens": {
        "value": "400",
        "value_type": "integer",
        "description": "Tokens maximos para la retroalimentacion educativa de histopatologia. Menos tokens = feedback mas rapido.",
    },
    "feedback_num_ctx": {
        "value": "2048",
        "value_type": "integer",
        "description": "Ventana de contexto de la retroalimentacion educativa (num_ctx). 2048 es suficiente para prompts cortos.",
    },
    "neural_embeddings_enabled": {
        "value": os.getenv("RAG_NEURAL_EMBEDDINGS_ENABLED", "true"),
        "value_type": "boolean",
        "description": "Usa sentence-transformers para embeddings RAG cuando esta disponible.",
    },
    "embedding_model": {
        "value": os.getenv(
            "RAG_EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        "value_type": "string",
        "description": (
            "Modelo sentence-transformers usado para vectorizar documentos. "
            "Debe ser multilingue: el corpus y las consultas estan en espanol. "
            "Al cambiarlo hay que reindexar el corpus completo."
        ),
    },
    "pgvector_enabled": {
        "value": os.getenv("RAG_PGVECTOR_ENABLED", "true"),
        "value_type": "boolean",
        "description": "Usa pgvector como indice de busqueda vectorial si PostgreSQL lo soporta.",
    },
    "rag_chunk_max_tokens": {
        "value": os.getenv("RAG_CHUNK_MAX_TOKENS", "400"),
        "value_type": "integer",
        "description": (
            "Tamano maximo de cada fragmento documental RAG. 400 tokens conserva "
            "el parrafo completo en material medico educativo."
        ),
    },
    "rag_max_chunks_per_document": {
        "value": os.getenv("RAG_MAX_CHUNKS_PER_DOCUMENT", "3"),
        "value_type": "integer",
        "description": (
            "Fragmentos que puede aportar un mismo documento al contexto. Con 1 "
            "un documento que concentra la respuesta la entrega incompleta."
        ),
    },
    "rag_exclude_evaluation_items": {
        "value": os.getenv("RAG_EXCLUDE_EVALUATION_ITEMS", "true"),
        "value_type": "boolean",
        "description": (
            "Excluye del indice las preguntas de alternativas y sus claves de "
            "respuesta, para que no se citen como fuente al estudiante."
        ),
    },
    "rag_chunk_overlap_tokens": {
        "value": os.getenv("RAG_CHUNK_OVERLAP_TOKENS", "80"),
        "value_type": "integer",
        "description": (
            "Solapamiento entre fragmentos documentales RAG. 80 tokens evita "
            "cortar definiciones o listas a la mitad."
        ),
    },
}


DEFAULT_EMAIL_CONFIG = {
    "email_smtp_host": {
        "value": os.getenv("SMTP_HOST", ""),
        "value_type": "string",
        "description": "Hostname del servidor SMTP (ej. smtp.gmail.com).",
    },
    "email_smtp_port": {
        "value": os.getenv("SMTP_PORT", "587"),
        "value_type": "integer",
        "description": "Puerto SMTP (587 para STARTTLS, 465 para SSL).",
    },
    "email_smtp_user": {
        "value": os.getenv("SMTP_USER", ""),
        "value_type": "string",
        "description": "Usuario o correo de autenticacion SMTP.",
    },
    "email_smtp_password": {
        "value": os.getenv("SMTP_PASSWORD", ""),
        "value_type": "password",
        "description": "Contrasena de autenticacion SMTP.",
    },
    "email_smtp_from": {
        "value": os.getenv("SMTP_FROM", ""),
        "value_type": "string",
        "description": "Direccion de correo mostrada como remitente (From).",
    },
    "email_smtp_tls": {
        "value": "true",
        "value_type": "boolean",
        "description": "Usar STARTTLS para cifrar la conexion SMTP.",
    },
}

DEFAULT_EMAIL_TEMPLATES: dict[str, dict] = {
    "account_approved": {
        "label": "Cuenta aprobada",
        "subject": "Tu cuenta ASOFAMECH ha sido habilitada",
        "body": (
            "Hola {nombre},\n\n"
            "Tu cuenta fue revisada y habilitada por el administrador.\n"
            "Ya puedes ingresar a la plataforma desde:\n{url_plataforma}\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_rejected": {
        "label": "Cuenta rechazada",
        "subject": "Tu solicitud de cuenta ASOFAMECH no fue aprobada",
        "body": (
            "Hola {nombre},\n\n"
            "Lamentablemente tu solicitud de acceso a la plataforma ASOFAMECH no fue aprobada.\n"
            "Si crees que esto es un error, contacta al administrador.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_suspended": {
        "label": "Cuenta suspendida",
        "subject": "Tu cuenta ASOFAMECH ha sido suspendida",
        "body": (
            "Hola {nombre},\n\n"
            "Tu cuenta en la plataforma ASOFAMECH ha sido suspendida temporalmente.\n"
            "Contacta al administrador para mas informacion.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
    "account_pending": {
        "label": "Registro recibido",
        "subject": "Solicitud de cuenta ASOFAMECH recibida",
        "body": (
            "Hola {nombre},\n\n"
            "Hemos recibido tu solicitud de acceso a la plataforma ASOFAMECH.\n"
            "Un administrador revisara tu cuenta en breve y te notificaremos por este medio.\n\n"
            "Este es un correo automatico del prototipo educativo ASOFAMECH."
        ),
    },
}


class AIConfigItem(BaseModel):
    key: str
    value: str
    value_type: str = "string"
    description: str | None = None


class AIConfigUpdate(BaseModel):
    items: list[AIConfigItem]


class EmailTemplateUpdate(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)


class AdminUserUpdate(BaseModel):
    role: str | None = None
    account_status: str | None = None
    is_active: bool | None = None
    notify_email: bool = False


class AdminApproveUserRequest(BaseModel):
    role: str | None = None
    notify_email: bool = True


class AdminCreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=200)
    password: str = Field(min_length=8, max_length=200)
    role: str = "estudiante"
    account_status: str = "approved"
    notify_email: bool = True


def parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}


def get_ai_config_map(db: Session) -> dict[str, str]:
    config = {key: str(meta["value"]) for key, meta in DEFAULT_AI_CONFIG.items()}
    for item in db.query(AIConfiguration).all():
        config[item.key] = item.value
    return config


def _upsert_config_item(db: Session, payload: AIConfigItem) -> AIConfiguration:
    item = db.query(AIConfiguration).filter(AIConfiguration.key == payload.key).first()
    if not item:
        item = AIConfiguration(key=payload.key)
        db.add(item)
    item.value = str(payload.value)
    item.value_type = payload.value_type or "string"
    item.description = payload.description
    return item


def _safe_status(value: str | None) -> str:
    status = (value or "pending").strip().lower()
    if status not in {"pending", "approved", "rejected", "suspended"}:
        raise HTTPException(status_code=422, detail="Estado de cuenta no permitido")
    return status


def _validate_admin_email(email: str) -> str:
    normalized = normalize_email(email)
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise HTTPException(status_code=422, detail="Correo electronico invalido")
    return normalized


def _validate_admin_password(password: str) -> None:
    if len(password or "") < 8:
        raise HTTPException(status_code=422, detail="La contrasena debe tener al menos 8 caracteres")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise HTTPException(status_code=422, detail="La contrasena debe incluir letras y numeros")


def _user_to_admin_payload(user: User, db: Session) -> dict:
    approver = db.query(User).filter(User.id == user.approved_by).first() if user.approved_by else None
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "role_label": display_role(user.role),
        "is_active": bool(user.is_active),
        "account_status": user.account_status or "pending",
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "approved_at": user.approved_at.isoformat() if user.approved_at else None,
        "approved_by": user.approved_by,
        "approved_by_name": approver.name if approver else None,
    }


def _user_audit_snapshot(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "account_status": user.account_status or "pending",
    }


def _apply_user_status(user: User, status: str, current_user: User) -> None:
    user.account_status = status
    if status == "approved":
        user.is_active = True
        user.approved_at = datetime.utcnow()
        user.approved_by = current_user.id
    elif status in {"pending", "rejected", "suspended"}:
        user.is_active = False


@router.get("/ai-config")
def get_ai_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stored = {item.key: item for item in db.query(AIConfiguration).all()}
    items = []
    for key, meta in DEFAULT_AI_CONFIG.items():
        item = stored.get(key)
        items.append(
            {
                "key": key,
                "value": item.value if item else meta["value"],
                "value_type": item.value_type if item else meta["value_type"],
                "description": item.description if item else meta["description"],
                "source": "database" if item else "default",
            }
        )
    return {"items": items}


@router.put("/ai-config")
def update_ai_config(
    payload: AIConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    allowed = set(DEFAULT_AI_CONFIG.keys())
    changed_keys = []
    for item in payload.items:
        if item.key not in allowed:
            raise HTTPException(status_code=422, detail=f"Clave de configuracion no permitida: {item.key}")
        _upsert_config_item(db, item)
        changed_keys.append(item.key)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.ai_config.update",
        target_type="ai_configuration",
        summary=f"Actualiza {len(changed_keys)} clave(s) de configuracion IA",
        details={"keys": changed_keys},
    )
    db.commit()
    return get_ai_config(current_user, db)


@router.get("/users")
def list_users(
    status_filter: str | None = Query(default=None, alias="status"),
    role_filter: str | None = Query(default=None, alias="role"),
    q: str | None = Query(default=None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)
    if status_filter:
        query = query.filter(User.account_status == _safe_status(status_filter))
    if role_filter:
        query = query.filter(User.role == normalize_role_for_storage(role_filter))
    if q:
        needle = f"%{normalize_email(q)}%"
        query = query.filter((User.email.ilike(needle)) | (User.name.ilike(needle)))
    users = query.order_by(User.created_at.desc(), User.id.desc()).all()
    return {"users": [_user_to_admin_payload(user, db) for user in users]}


@router.get("/audit-logs")
def list_audit_logs(
    actor_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)
    if actor_id is not None:
        query = query.filter(AuditLog.actor_user_id == actor_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if target_id:
        query = query.filter(AuditLog.target_id == str(target_id))
    logs = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    return {"count": len(logs), "items": [audit_log_to_payload(log) for log in logs]}


@router.post("/users")
def create_user(
    payload: AdminCreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email = _validate_admin_email(payload.email)
    _validate_admin_password(payload.password)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")

    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role=normalize_role_for_storage(payload.role),
    )
    db.add(user)
    db.flush()
    _apply_user_status(user, _safe_status(payload.account_status), current_user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.create",
        target_type="user",
        target_id=user.id,
        summary=f"Crea usuario {user.email}",
        details={"user": _user_audit_snapshot(user), "notify_email": bool(payload.notify_email)},
    )
    db.commit()
    db.refresh(user)

    email_result = None
    if payload.notify_email and (user.account_status or "pending") == "approved" and user.is_active:
        email_result = send_template_email(user, "account_approved", db)
    return {"user": _user_to_admin_payload(user, db), "email": email_result}


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_user.id and payload.account_status in {"pending", "rejected", "suspended"}:
        raise HTTPException(status_code=422, detail="No puedes deshabilitar tu propia cuenta")

    before = _user_audit_snapshot(user)
    if payload.role is not None:
        user.role = normalize_role_for_storage(payload.role)
    if payload.account_status is not None:
        _apply_user_status(user, _safe_status(payload.account_status), current_user)
    if payload.is_active is not None:
        if user.id == current_user.id and not payload.is_active:
            raise HTTPException(status_code=422, detail="No puedes desactivar tu propia cuenta")
        user.is_active = bool(payload.is_active)
        if user.is_active and (user.account_status or "pending") != "approved":
            _apply_user_status(user, "approved", current_user)
        if not user.is_active and (user.account_status or "pending") == "approved":
            user.account_status = "suspended"

    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.update",
        target_type="user",
        target_id=user.id,
        summary=f"Actualiza usuario {user.email}",
        details={"before": before, "after": _user_audit_snapshot(user), "notify_email": bool(payload.notify_email)},
    )
    db.commit()
    db.refresh(user)
    email_result = None
    new_status = user.account_status or "pending"
    if new_status == "approved" and user.is_active:
        email_result = send_template_email(user, "account_approved", db)
    elif new_status == "suspended" or not user.is_active:
        email_result = send_template_email(user, "account_suspended", db)
    elif new_status == "rejected":
        email_result = send_template_email(user, "account_rejected", db)
    return {"user": _user_to_admin_payload(user, db), "email": email_result}


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: int,
    payload: AdminApproveUserRequest | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    before = _user_audit_snapshot(user)
    if payload and payload.role:
        user.role = normalize_role_for_storage(payload.role)
    _apply_user_status(user, "approved", current_user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.approve",
        target_type="user",
        target_id=user.id,
        summary=f"Aprueba usuario {user.email}",
        details={"before": before, "after": _user_audit_snapshot(user), "notify_email": payload.notify_email if payload else True},
    )
    db.commit()
    db.refresh(user)
    email_result = send_template_email(user, "account_approved", db) if (payload is None or payload.notify_email) else None
    return {"user": _user_to_admin_payload(user, db), "email": email_result}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from sqlalchemy.exc import IntegrityError
    from ..models import HistopathologyCorrection, HistopathologySession, MedicalImage

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_user.id:
        raise HTTPException(status_code=422, detail="No puedes eliminar tu propia cuenta")

    deleted_user_snapshot = _user_audit_snapshot(user)

    # 1. Correcciones hechas por este docente
    db.query(HistopathologyCorrection).filter(
        HistopathologyCorrection.docente_user_id == user_id
    ).delete(synchronize_session=False)

    # 2. Correcciones sobre sesiones propias del usuario, luego las sesiones
    session_ids = [
        r.id for r in db.query(HistopathologySession.id)
        .filter(HistopathologySession.user_id == user_id).all()
    ]
    if session_ids:
        db.query(HistopathologyCorrection).filter(
            HistopathologyCorrection.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
    db.query(HistopathologySession).filter(
        HistopathologySession.user_id == user_id
    ).delete(synchronize_session=False)

    # 3. Imágenes subidas: desasociar (uploaded_by es nullable)
    db.query(MedicalImage).filter(
        MedicalImage.uploaded_by == user_id
    ).update({"uploaded_by": None}, synchronize_session=False)

    # 4. Otros usuarios que fueron aprobados por este admin
    db.query(User).filter(
        User.approved_by == user_id
    ).update({"approved_by": None}, synchronize_session=False)

    # Mantener la trazabilidad historica sin bloquear la eliminacion del usuario.
    db.query(AuditLog).filter(
        AuditLog.actor_user_id == user_id
    ).update({"actor_user_id": None}, synchronize_session=False)

    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.delete",
        target_type="user",
        target_id=user.id,
        summary=f"Elimina usuario {user.email}",
        details={"deleted_user": deleted_user_snapshot},
    )

    try:
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar el usuario: tiene datos asociados que no pueden desvincularse.",
        )

    return {"ok": True, "deleted_id": user_id}


@router.post("/users/{user_id}/reject")
def reject_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == current_user.id:
        raise HTTPException(status_code=422, detail="No puedes rechazar tu propia cuenta")
    before = _user_audit_snapshot(user)
    _apply_user_status(user, "rejected", current_user)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.user.reject",
        target_type="user",
        target_id=user.id,
        summary=f"Rechaza usuario {user.email}",
        details={"before": before, "after": _user_audit_snapshot(user)},
    )
    db.commit()
    db.refresh(user)
    send_template_email(user, "account_rejected", db)
    return {"user": _user_to_admin_payload(user, db)}


@router.get("/integrations/status")
async def integrations_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
    refresh: bool = False,
):
    now = time.monotonic()
    if not refresh and _integrations_cache["data"] is not None and now - _integrations_cache["ts"] < _INTEGRATIONS_TTL:
        return _integrations_cache["data"]

    config = get_ai_config_map(db)
    ollama_url = config.get("ollama_url", DEFAULT_AI_CONFIG["ollama_url"]["value"])
    from ..embedding_service import embedding_status_for_rag
    from ..pgvector_store import pgvector_available

    documents_count = db.query(Document).count()
    chunks_count = db.query(DocumentChunk).count()
    embedding_status = embedding_status_for_rag(
        model_name=config.get("embedding_model"),
        neural_enabled=parse_bool(config.get("neural_embeddings_enabled"), True),
    )
    pgvector_ok = pgvector_available(db)

    ollama = {"configured": bool(ollama_url), "url": ollama_url, "reachable": False, "models": []}
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            if response.status_code == 200:
                ollama["reachable"] = True
                ollama["models"] = [m["name"] for m in response.json().get("models", [])]
    except httpx.HTTPError:
        ollama["reachable"] = False

    result = {
        "llama3": ollama,
        "rag": {
            "enabled": parse_bool(config.get("rag_enabled"), True),
            "documents_count": documents_count,
            "chunks_count": chunks_count,
            "retriever": "pgvector_cosine" if pgvector_ok and parse_bool(config.get("pgvector_enabled"), True) else "json_cosine",
            "pgvector_available": pgvector_ok,
            "embedding_provider": embedding_status.provider,
            "neural_embeddings": embedding_status.neural,
            "vector_backend": "pgvector" if pgvector_ok and parse_bool(config.get("pgvector_enabled"), True) else "json",
            "metric": "cosine",
            "dimensions": EMBEDDING_DIMENSIONS,
        },
        "email": {
            "smtp_configured": _is_smtp_configured(db),
            "outbox_path": os.getenv("ASOFAMECH_EMAIL_OUTBOX_PATH", "artifacts/email_outbox.jsonl"),
        },
        "cached_at": now,
    }
    _integrations_cache["data"] = result
    _integrations_cache["ts"] = now
    return result


# ─── Email config helpers ────────────────────────────────────────────────────

def _get_email_smtp_dict(db: Session) -> dict:
    keys = set(DEFAULT_EMAIL_CONFIG.keys())
    stored = {item.key: item.value for item in db.query(AIConfiguration).filter(AIConfiguration.key.in_(keys)).all()}
    return {k: stored.get(k, str(meta["value"])) for k, meta in DEFAULT_EMAIL_CONFIG.items()}


def _is_smtp_configured(db: Session) -> bool:
    cfg = _get_email_smtp_dict(db)
    return bool(cfg.get("email_smtp_host") and (cfg.get("email_smtp_from") or cfg.get("email_smtp_user")))


# ─── Email config endpoints ──────────────────────────────────────────────────

@router.get("/email-config")
def get_email_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    keys = set(DEFAULT_EMAIL_CONFIG.keys())
    stored = {item.key: item for item in db.query(AIConfiguration).filter(AIConfiguration.key.in_(keys)).all()}
    items = []
    for key, meta in DEFAULT_EMAIL_CONFIG.items():
        item = stored.get(key)
        value = item.value if item else str(meta["value"])
        items.append({
            "key": key,
            "value": value,
            "value_type": meta["value_type"],
            "description": meta["description"],
        })
    return {"items": items}


@router.put("/email-config")
def update_email_config(
    payload: AIConfigUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    allowed = set(DEFAULT_EMAIL_CONFIG.keys())
    changed_keys = []
    for item in payload.items:
        if item.key not in allowed:
            raise HTTPException(status_code=422, detail=f"Clave no permitida: {item.key}")
        _upsert_config_item(db, item)
        changed_keys.append(item.key)
    record_audit_log(
        db,
        actor=current_user,
        action="admin.email_config.update",
        target_type="email_configuration",
        summary=f"Actualiza {len(changed_keys)} clave(s) SMTP",
        details={"keys": changed_keys},
    )
    db.commit()
    return get_email_config(current_user, db)


@router.post("/email-config/test")
async def test_email_config(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from ..email_service import send_test_email
    cfg = _get_email_smtp_dict(db)
    return send_test_email(current_user, cfg)


# ─── Email template endpoints ────────────────────────────────────────────────

@router.get("/email-templates")
def get_email_templates(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stored = {t.key: t for t in db.query(EmailTemplate).all()}
    templates = []
    for key, defaults in DEFAULT_EMAIL_TEMPLATES.items():
        t = stored.get(key)
        templates.append({
            "key": key,
            "label": defaults["label"],
            "subject": t.subject if t else defaults["subject"],
            "body": t.body if t else defaults["body"],
            "updated_at": t.updated_at.isoformat() if t and t.updated_at else None,
            "source": "database" if t else "default",
        })
    return {"templates": templates}


@router.put("/email-templates/{key}")
def update_email_template(
    key: str,
    payload: EmailTemplateUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if key not in DEFAULT_EMAIL_TEMPLATES:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    t = db.query(EmailTemplate).filter(EmailTemplate.key == key).first()
    if not t:
        defaults = DEFAULT_EMAIL_TEMPLATES[key]
        t = EmailTemplate(key=key, label=defaults["label"], subject=payload.subject, body=payload.body)
        db.add(t)
    else:
        t.subject = payload.subject
        t.body = payload.body
    record_audit_log(
        db,
        actor=current_user,
        action="admin.email_template.update",
        target_type="email_template",
        target_id=key,
        summary=f"Actualiza plantilla de correo {key}",
        details={"key": key, "subject": payload.subject},
    )
    db.commit()
    db.refresh(t)
    return {
        "template": {
            "key": t.key,
            "label": t.label,
            "subject": t.subject,
            "body": t.body,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
    }
