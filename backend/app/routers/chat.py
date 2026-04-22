from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
import os
import logging
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Case

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["chat"])

OLLAMA_URL = os.getenv("OLLAMA_URL", os.getenv("OLLAMA_HOST", "http://ollama:11434"))
LLM_MODEL = os.getenv("LLM_MODEL", "llama3:8b")
MAX_CONTEXT_CASES = 3


class ChatRequest(BaseModel):
    text: str


def _build_cases_context(question: str, db: Session) -> str:
    """
    Busca casos clínicos relacionados para enriquecer la respuesta educativa.
    """
    tokens = [
        word.strip(".,;:!?()[]{}\"' ").lower()
        for word in question.split()
        if len(word.strip(".,;:!?()[]{}\"' ")) >= 4
    ]

    if not tokens:
        return ""

    clauses = []
    for token in tokens[:6]:
        term = f"%{token}%"
        clauses.extend([
            Case.title.ilike(term),
            Case.description.ilike(term),
            Case.body.ilike(term),
        ])

    if not clauses:
        return ""

    cases = (
        db.query(Case)
        .filter(Case.is_active == True)
        .filter(or_(*clauses))
        .limit(MAX_CONTEXT_CASES)
        .all()
    )

    if not cases:
        return ""

    context_blocks = []
    for idx, case in enumerate(cases, start=1):
        body = (case.body or "").replace("\n", " ").strip()
        if len(body) > 420:
            body = body[:420].rstrip() + "..."
        context_blocks.append(
            f"Caso {idx}: {case.title}\n"
            f"Resumen: {case.description}\n"
            f"Detalle: {body}"
        )

    return "\n\n".join(context_blocks)


@router.post("/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    user_text = req.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío.")

    cases_context = _build_cases_context(user_text, db)

    system_prompt = (
        "Eres un asistente médico educativo. Responde en español de forma clara, "
        "estructurada y basada en evidencia actual. Incluye un aviso de que la "
        "información es educativa y no reemplaza la consulta clínica presencial."
    )

    if cases_context:
        system_prompt += (
            "\n\nUsa este contexto de casos clínicos del sistema para enriquecer "
            "la explicación cuando sea pertinente:\n"
            f"{cases_context}"
        )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "top_p": 0.9,
            "num_ctx": 8192,
        },
    }

    logger.info(f"Enviando mensaje a Ollama URL: {OLLAMA_URL}/api/chat")

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            logger.info(f"Ollama respondió con status: {resp.status_code}")
            logger.info(f"Respuesta: {resp.text[:200]}")
            
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"Ollama devolvió un error HTTP {resp.status_code}: {resp.text}",
                )

            try:
                ollama_data = resp.json()
            except ValueError as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"No se pudo parsear la respuesta de Ollama como JSON: {e}",
                )

            assistant_text = ollama_data.get("message", {}).get("content", "").strip()
            if not assistant_text:
                assistant_text = (
                    "No pude generar una respuesta en este momento. "
                    "Intenta reformular tu pregunta."
                )

            # Mantener contrato esperado por frontend: lista de mensajes con clave text.
            return {"messages": [{"text": assistant_text}]}
            
    except httpx.HTTPError as e:
        logger.error(f"Excepción al conectar con Ollama: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Error al contactar al servidor Ollama: {e}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excepción inesperada: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Error inesperado: {e}",
        )
