import os
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..db import get_db
from ..models import AIConfiguration, Document, User


router = APIRouter(prefix="/api/admin", tags=["admin"])


DEFAULT_AI_CONFIG = {
    "llm_model": {
        "value": os.getenv("LLM_MODEL", "llama3:8b"),
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
        "value": "0.7",
        "value_type": "float",
        "description": "Creatividad del modelo generativo.",
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
}


class AIConfigItem(BaseModel):
    key: str
    value: str
    value_type: str = "string"
    description: str | None = None


class AIConfigUpdate(BaseModel):
    items: list[AIConfigItem]


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
    for item in payload.items:
        if item.key not in allowed:
            raise HTTPException(status_code=422, detail=f"Clave de configuracion no permitida: {item.key}")
        _upsert_config_item(db, item)
    db.commit()
    return get_ai_config(current_user, db)


@router.get("/integrations/status")
async def integrations_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    config = get_ai_config_map(db)
    ollama_url = config.get("ollama_url", DEFAULT_AI_CONFIG["ollama_url"]["value"])
    documents_count = db.query(Document).count()

    ollama = {"configured": bool(ollama_url), "url": ollama_url, "reachable": False}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            ollama["reachable"] = response.status_code == 200
    except httpx.HTTPError:
        ollama["reachable"] = False

    return {
        "llama3": ollama,
        "rag": {
            "enabled": parse_bool(config.get("rag_enabled"), True),
            "documents_count": documents_count,
            "retriever": "vector_hashing_cosine_local",
        },
    }
