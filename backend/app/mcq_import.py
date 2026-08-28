"""Importacion de bancos de preguntas de alternativa desde un documento.

Los docentes ya tienen guias de estudio en Word/PDF con el formato clasico:
pregunta numerada, alternativas a/b/c/d, la correcta marcada y una
explicacion. Este modulo le pide al LLM que las convierta a la forma que usa
el modulo de Test de alternativas. Al igual que la importacion de casos
clinicos (ver app/case_import.py), esto es una PROPUESTA: no se guarda nada
hasta que el docente la revisa en el constructor manual.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .llm_service import chat_completion, resolve_llm_settings
from .rubric_review import _loads, _text

logger = logging.getLogger(__name__)

MAX_DOCUMENT_CHARS = 40000
MAX_ITEMS = 100
VALID_DIFFICULTIES = {"pregrado", "internado", "residente"}

MCQ_IMPORT_PROMPT = """Eres un asistente académico de una facultad de medicina chilena.
Recibes el texto de un documento con preguntas de alternativa (opción múltiple) que un
docente ya redactó -típicamente pregunta numerada, alternativas a/b/c/d, la correcta
marcada de alguna forma ("Correcta: B", en negrita, etc.) y a veces una explicación- y lo
conviertes al formato estructurado de la plataforma.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:

{
  "topic": "tema principal de todas las preguntas (ej: Patogénesis de la tuberculosis)",
  "difficulty": "pregrado" | "internado" | "residente" | null,
  "items": [
    {
      "question": "enunciado completo de la pregunta, incluida la viñeta clínica si la trae",
      "options": ["texto de la alternativa a", "texto de la alternativa b", "..."],
      "correct_index": 0,
      "explanation": "explicación de por qué esa es la respuesta correcta, si el documento la trae"
    }
  ]
}

Reglas obligatorias:
- "correct_index" es la posición (empezando en 0) de la alternativa correcta dentro de "options",
  en el MISMO ORDEN en que aparecen en el documento. Si el documento marca "Correcta: B" y las
  alternativas son a/b/c/d, "b" corresponde al índice 1.
- Conserva el texto de las alternativas tal como aparece, sin resumir ni corregir redacción.
- Si una pregunta no trae explicación, usa "" (no la inventes).
- Si el documento no deja clara cuál es la alternativa correcta para una pregunta, OMITE esa
  pregunta completa del array "items" en vez de adivinar.
- No inventes preguntas que no estén en el documento.
- "topic" es un resumen breve común a las preguntas; si no es evidente, usa el título del documento.
- Responde en español y sin texto fuera del JSON."""


def _difficulty(value) -> str | None:
    candidate = _text(value, 40).lower()
    return candidate if candidate in VALID_DIFFICULTIES else None


def _normalize_items(raw_items) -> list[dict]:
    items: list[dict] = []
    if not isinstance(raw_items, list):
        return items
    for entry in raw_items[:MAX_ITEMS]:
        if not isinstance(entry, dict):
            continue
        question = _text(entry.get("question"), 4000)
        options = entry.get("options")
        if not question or not isinstance(options, list):
            continue
        options = [_text(opt, 1000) for opt in options if _text(opt, 1000)]
        if len(options) < 2:
            continue
        try:
            correct_index = int(entry.get("correct_index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= correct_index < len(options)):
            continue
        items.append({
            "id": len(items) + 1,
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "explanation": _text(entry.get("explanation"), 2000),
        })
    return items


async def import_mcq_from_text(db: Session, text: str) -> dict:
    """Convierte el texto de un documento en una propuesta de banco de preguntas.

    No persiste nada: devuelve los ítems para que el docente los revise (y
    edite si hace falta) en el constructor antes de guardarlos.
    """
    document = (text or "").strip()
    if len(document) < 100:
        raise HTTPException(
            status_code=422,
            detail="El documento es demasiado corto para contener preguntas de alternativa.",
        )

    settings = resolve_llm_settings(db)
    async with httpx.AsyncClient(timeout=max(settings.timeout, 300.0)) as client:
        raw = await chat_completion(
            client,
            settings,
            [
                {"role": "system", "content": MCQ_IMPORT_PROMPT},
                {"role": "user", "content": document[:MAX_DOCUMENT_CHARS]},
            ],
            temperature=0.1,
            max_tokens=6000,
            num_ctx=16384,
            json_mode=True,
            purpose="importacion de banco de preguntas",
            db=db,
            feature="mcq_import",
        )

    data = _loads(raw)
    items = _normalize_items(data.get("items"))
    if not items:
        raise HTTPException(
            status_code=422,
            detail=(
                "No se reconocieron preguntas de alternativa en el documento. "
                "Revisa el archivo o agrégalas manualmente."
            ),
        )

    warnings: list[str] = []
    raw_count = len(data.get("items") or [])
    if raw_count > len(items):
        warnings.append(
            f"{raw_count - len(items)} pregunta(s) del documento no se pudieron interpretar "
            "con claridad y se omitieron; revísalas manualmente si faltan."
        )

    return {
        "items": items,
        "total": len(items),
        "topic": _text(data.get("topic"), 200) or None,
        "difficulty": _difficulty(data.get("difficulty")),
        "warnings": warnings,
    }
