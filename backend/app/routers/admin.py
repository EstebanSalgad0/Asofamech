import csv
import io
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..auth_security import display_role, hash_password, normalize_email, normalize_role_for_storage
from ..auth import require_admin
from ..audit import audit_log_to_payload, record_audit_log
from ..db import get_db
from ..email_service import send_template_email
from ..llm_service import (
    GROQ_BASE_URL,
    SECRET_PLACEHOLDER,
    VALID_PROVIDERS,
    build_llm_settings,
    probe_provider,
)
from ..models import AIConfiguration, AuditLog, Document, DocumentChunk, EmailTemplate, LlmUsageLog, User
from ..rag_utils import EMBEDDING_DIMENSIONS


router = APIRouter(prefix="/api/admin", tags=["admin"])

_integrations_cache: dict = {"data": None, "ts": 0.0}
_INTEGRATIONS_TTL = 45.0  # segundos


DEFAULT_AI_CONFIG = {
    # El valor inicial sigue siendo ollama a proposito: es el unico proveedor
    # que funciona sin credenciales, y un despliegue nuevo apuntando a Groq sin
    # API key deja el chatbot muerto desde el primer arranque. El proveedor
    # real se elige desde el panel y se guarda en base de datos.
    "llm_provider": {
        "value": os.getenv("LLM_PROVIDER", "ollama"),
        "value_type": "string",
        "description": (
            "Proveedor del modelo generativo: ollama (local) o una API externa "
            "compatible con OpenAI, como Groq. El RAG sigue calculandose en el "
            "backend en cualquiera de los dos casos."
        ),
    },
    "llm_api_base_url": {
        "value": os.getenv("LLM_API_BASE_URL", GROQ_BASE_URL),
        "value_type": "string",
        "description": (
            "URL base del proveedor externo, sin /chat/completions. "
            f"Para Groq: {GROQ_BASE_URL}"
        ),
    },
    "llm_api_key": {
        "value": os.getenv("LLM_API_KEY", ""),
        "value_type": "password",
        "description": "Clave de API del proveedor externo. Se guarda cifrada en transito y nunca se devuelve en claro.",
    },
    "llm_api_model": {
        "value": os.getenv("LLM_API_MODEL", "openai/gpt-oss-20b"),
        "value_type": "string",
        "description": (
            "Modelo del proveedor externo. En Groq el identificador lleva el prefijo del "
            "proveedor original (ej. openai/gpt-oss-20b)."
        ),
    },
    "llm_request_timeout": {
        "value": os.getenv("LLM_REQUEST_TIMEOUT", "120"),
        "value_type": "integer",
        "description": "Segundos de espera maxima por respuesta del proveedor generativo.",
    },
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
        "value": "1600",
        "value_type": "integer",
        "description": (
            "Tokens maximos por respuesta del chatbot (num_predict). Los modelos de "
            "razonamiento como gpt-oss gastan parte de este presupuesto en razonar antes "
            "de responder, asi que un valor bajo trunca la respuesta a media frase."
        ),
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
    "llm_price_input_per_million": {
        "value": os.getenv("LLM_PRICE_INPUT_PER_MILLION", "0.05"),
        "value_type": "float",
        "description": (
            "Precio en USD por cada 1 000 000 de tokens de entrada (prompt). "
            "Actualizalo cuando el proveedor cambie sus tarifas. Solo se usa "
            "para estimar el costo del consumo mostrado en el panel."
        ),
    },
    "llm_price_output_per_million": {
        "value": os.getenv("LLM_PRICE_OUTPUT_PER_MILLION", "0.08"),
        "value_type": "float",
        "description": (
            "Precio en USD por cada 1 000 000 de tokens de salida (completion). "
            "Actualizalo cuando el proveedor cambie sus tarifas."
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


def _validate_ai_config_value(item: "AIConfigItem") -> None:
    """Rechaza valores que dejarian la integracion generativa inutilizable."""
    value = (item.value or "").strip()

    if item.key == "llm_provider" and value.lower() not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Proveedor no soportado: {value}. Usa {', '.join(sorted(VALID_PROVIDERS))}.",
        )

    if item.key in {"llm_api_base_url", "ollama_url"} and value:
        if not value.lower().startswith(("http://", "https://")):
            raise HTTPException(
                status_code=422,
                detail=f"{item.key} debe empezar por http:// o https://",
            )

    if item.key == "llm_request_timeout" and value:
        try:
            timeout = float(value)
        except ValueError:
            raise HTTPException(status_code=422, detail="El timeout debe ser numerico")
        if not 5 <= timeout <= 600:
            raise HTTPException(status_code=422, detail="El timeout debe estar entre 5 y 600 segundos")


def _is_secret_key(key: str, defaults: dict) -> bool:
    return (defaults.get(key) or {}).get("value_type") == "password"


def _mask_secret(value: str) -> str:
    """Nunca se devuelve un secreto en claro: el panel solo necesita saber si esta puesto."""
    return SECRET_PLACEHOLDER if value else ""


def _is_unchanged_secret(value: str) -> bool:
    return value == SECRET_PLACEHOLDER


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
        raw_value = str(item.value if item else meta["value"])
        is_secret = meta["value_type"] == "password"
        items.append(
            {
                "key": key,
                "value": _mask_secret(raw_value) if is_secret else raw_value,
                "value_type": item.value_type if item else meta["value_type"],
                # La descripcion canonica vive en el codigo: si se toma la
                # almacenada, un guardado antiguo congela el texto de ayuda.
                "description": meta["description"],
                "source": "database" if item else "default",
                "is_set": bool(raw_value) if is_secret else None,
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
        # El formulario reenvia el placeholder cuando el admin no toco el
        # secreto; sobrescribirlo con la mascara borraria la credencial real.
        if _is_secret_key(item.key, DEFAULT_AI_CONFIG) and _is_unchanged_secret(item.value):
            continue
        _validate_ai_config_value(item)
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
    # Cualquier cambio en la config invalida el snapshot del panel de estado
    # de integracion; si no, el admin ve datos viejos hasta 45 s despues.
    _integrations_cache["data"] = None
    _integrations_cache["ts"] = 0.0
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
    llm_settings = build_llm_settings(config)
    from ..embedding_service import embedding_status_for_rag
    from ..pgvector_store import pgvector_available

    documents_count = db.query(Document).count()
    chunks_count = db.query(DocumentChunk).count()
    embedding_status = embedding_status_for_rag(
        model_name=config.get("embedding_model"),
        neural_enabled=parse_bool(config.get("neural_embeddings_enabled"), True),
    )
    pgvector_ok = pgvector_available(db)

    # Un proveedor externo puede tardar mas que Ollama local en el primer
    # contacto (TLS + latencia de red), asi que la sonda no comparte timeout.
    llm = await probe_provider(llm_settings, timeout=1.0 if llm_settings.provider == "ollama" else 6.0)

    result = {
        # Se conserva la clave llama3 por compatibilidad con el panel y los
        # tests existentes; ahora describe el proveedor activo, sea cual sea.
        "llama3": llm,
        "llm": llm,
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


@router.post("/llm/test")
async def test_llm_provider(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Genera una respuesta minima con el proveedor guardado y mide la latencia.

    Sirve para distinguir "la clave es invalida" de "el modelo no existe" antes
    de que un estudiante se encuentre el error en medio de una consulta.
    """
    import httpx

    from ..llm_service import chat_completion

    settings = build_llm_settings(get_ai_config_map(db))
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=min(settings.timeout, 30.0)) as client:
            answer = await chat_completion(
                client,
                settings,
                [
                    {"role": "system", "content": "Responde con una sola palabra."},
                    {"role": "user", "content": "Di 'listo'."},
                ],
                temperature=0.0,
                max_tokens=16,
                num_ctx=512,
                purpose="prueba de conexion",
                db=db,
                feature="llm_probe",
            )
    except HTTPException as exc:
        return {
            "ok": False,
            "provider": settings.provider,
            "label": settings.label,
            "model": settings.model,
            "detail": exc.detail,
        }
    except Exception as exc:  # noqa: BLE001 - el panel necesita el motivo, no un 500
        return {
            "ok": False,
            "provider": settings.provider,
            "label": settings.label,
            "model": settings.model,
            "detail": f"No se pudo contactar al proveedor: {type(exc).__name__}",
        }

    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "ok": bool(answer),
        "provider": settings.provider,
        "label": settings.label,
        "model": settings.model,
        "latency_ms": elapsed_ms,
        "sample": answer[:120],
    }


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
        value = str(item.value if item else meta["value"])
        is_secret = meta["value_type"] == "password"
        items.append({
            "key": key,
            "value": _mask_secret(value) if is_secret else value,
            "value_type": meta["value_type"],
            "description": meta["description"],
            "is_set": bool(value) if is_secret else None,
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
        if _is_secret_key(item.key, DEFAULT_EMAIL_CONFIG) and _is_unchanged_secret(item.value):
            continue
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


# ============ Consumo del LLM (tokens y costo) ============

_WINDOW_TO_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": None}


def _price_from_config(db: Session) -> tuple[float, float]:
    """Lee los precios/1M tokens actuales del panel. 0 si están mal formateados."""
    config = get_ai_config_map(db)
    try:
        p_in = float(config.get("llm_price_input_per_million") or 0.0)
    except (TypeError, ValueError):
        p_in = 0.0
    try:
        p_out = float(config.get("llm_price_output_per_million") or 0.0)
    except (TypeError, ValueError):
        p_out = 0.0
    return max(0.0, p_in), max(0.0, p_out)


def _cost_usd(prompt_tokens: int, completion_tokens: int, price_in: float, price_out: float) -> float:
    return round((prompt_tokens / 1_000_000.0) * price_in + (completion_tokens / 1_000_000.0) * price_out, 6)


@router.get("/llm/usage/summary")
def llm_usage_summary(
    window: str = Query(default="30d"),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Agregados de consumo para el panel: totales, breakdown por proveedor,
    modelo, feature y serie diaria de tokens/costo."""
    if window not in _WINDOW_TO_DAYS:
        raise HTTPException(status_code=422, detail="window debe ser 7d, 30d, 90d o all")

    days = _WINDOW_TO_DAYS[window]
    q = db.query(LlmUsageLog)
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(LlmUsageLog.occurred_at >= cutoff)

    price_in, price_out = _price_from_config(db)

    # Totales globales
    totals_row = q.with_entities(
        func.coalesce(func.sum(LlmUsageLog.prompt_tokens), 0),
        func.coalesce(func.sum(LlmUsageLog.completion_tokens), 0),
        func.count(LlmUsageLog.id),
        func.coalesce(func.sum(case((LlmUsageLog.success == True, 1), else_=0)), 0),  # noqa: E712
    ).one()
    prompt_total, completion_total, calls_total, calls_success = totals_row
    total_tokens = int(prompt_total) + int(completion_total)

    def _breakdown(column):
        rows = (
            q.with_entities(
                column,
                func.coalesce(func.sum(LlmUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(LlmUsageLog.completion_tokens), 0),
                func.count(LlmUsageLog.id),
            )
            .group_by(column)
            .all()
        )
        result = []
        for key, pt, ct, n in rows:
            pt, ct, n = int(pt), int(ct), int(n)
            result.append({
                "key": key or "(sin dato)",
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": pt + ct,
                "calls": n,
                "cost_usd": _cost_usd(pt, ct, price_in, price_out),
            })
        result.sort(key=lambda r: r["total_tokens"], reverse=True)
        return result

    # Serie diaria: agregación en Python (compatible con SQLite en tests).
    rows_daily = q.with_entities(
        LlmUsageLog.occurred_at,
        LlmUsageLog.prompt_tokens,
        LlmUsageLog.completion_tokens,
    ).all()
    daily: dict[str, dict] = defaultdict(lambda: {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0})
    for occurred_at, pt, ct in rows_daily:
        day_key = (occurred_at or datetime.utcnow()).strftime("%Y-%m-%d")
        bucket = daily[day_key]
        bucket["prompt_tokens"] += int(pt or 0)
        bucket["completion_tokens"] += int(ct or 0)
        bucket["calls"] += 1
    series = []
    for day_key in sorted(daily.keys()):
        b = daily[day_key]
        total = b["prompt_tokens"] + b["completion_tokens"]
        series.append({
            "date": day_key,
            "prompt_tokens": b["prompt_tokens"],
            "completion_tokens": b["completion_tokens"],
            "total_tokens": total,
            "calls": b["calls"],
            "cost_usd": _cost_usd(b["prompt_tokens"], b["completion_tokens"], price_in, price_out),
        })

    return {
        "window": window,
        "generated_at": datetime.utcnow().isoformat(),
        "pricing": {
            "input_per_million_usd": price_in,
            "output_per_million_usd": price_out,
        },
        "totals": {
            "prompt_tokens": int(prompt_total),
            "completion_tokens": int(completion_total),
            "total_tokens": total_tokens,
            "calls": int(calls_total),
            "successful_calls": int(calls_success),
            "failed_calls": int(calls_total) - int(calls_success),
            "cost_usd": _cost_usd(int(prompt_total), int(completion_total), price_in, price_out),
        },
        "by_provider": _breakdown(LlmUsageLog.provider),
        "by_model": _breakdown(LlmUsageLog.model),
        "by_feature": _breakdown(LlmUsageLog.feature),
        "daily": series,
    }


@router.get("/llm/usage/recent")
def llm_usage_recent(
    limit: int = Query(default=50, ge=1, le=500),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Últimas N llamadas al LLM, útil para debug. Sin user_id."""
    price_in, price_out = _price_from_config(db)
    rows = (
        db.query(LlmUsageLog)
        .order_by(LlmUsageLog.occurred_at.desc(), LlmUsageLog.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "provider": r.provider,
                "model": r.model,
                "feature": r.feature,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "latency_ms": r.latency_ms,
                "success": r.success,
                "error_kind": r.error_kind,
                "estimated": r.estimated,
                "cost_usd": _cost_usd(r.prompt_tokens, r.completion_tokens, price_in, price_out),
            }
            for r in rows
        ],
    }


@router.get("/llm/usage/export.csv")
def llm_usage_export(
    window: str = Query(default="30d"),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if window not in _WINDOW_TO_DAYS:
        raise HTTPException(status_code=422, detail="window debe ser 7d, 30d, 90d o all")
    days = _WINDOW_TO_DAYS[window]
    q = db.query(LlmUsageLog)
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        q = q.filter(LlmUsageLog.occurred_at >= cutoff)
    q = q.order_by(LlmUsageLog.occurred_at.asc())

    price_in, price_out = _price_from_config(db)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "occurred_at", "provider", "model", "feature",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "latency_ms", "success", "error_kind", "estimated", "cost_usd",
    ])
    for r in q.all():
        writer.writerow([
            r.occurred_at.isoformat() if r.occurred_at else "",
            r.provider,
            r.model,
            r.feature or "",
            r.prompt_tokens,
            r.completion_tokens,
            r.total_tokens,
            r.latency_ms if r.latency_ms is not None else "",
            "true" if r.success else "false",
            r.error_kind or "",
            "true" if r.estimated else "false",
            _cost_usd(r.prompt_tokens, r.completion_tokens, price_in, price_out),
        ])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="llm_usage_{window}.csv"'},
    )
