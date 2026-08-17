"""Revision automatica de informes clinicos contra una rubrica.

Dos operaciones, ambas apoyadas en el proveedor LLM configurado:

  1. `extract_rubric_from_text`: convierte el documento de rubrica que sube el
     docente (el .docx de la coordinacion, por ejemplo) en criterios y niveles
     estructurados, que el docente revisa antes de guardar.
  2. `evaluate_report`: puntua el informe del estudiante criterio por criterio.

Las dos normalizan agresivamente la salida del modelo. Un LLM puede inventarse
un puntaje fuera de escala, omitir un criterio o devolver el JSON envuelto en
markdown; aqui se recorta y se recalcula el total en Python, de modo que la
nota que se guarda siempre es aritmeticamente consistente con la rubrica,
aunque el modelo sume mal.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .llm_service import chat_completion, resolve_llm_settings

logger = logging.getLogger(__name__)

MAX_REPORT_CHARS = 24000
MAX_CRITERIA = 20
MAX_LEVELS = 8

EXTRACTION_PROMPT = """Eres un asistente académico de una facultad de medicina.
Recibes el texto de una pauta o rúbrica de evaluación y debes convertirlo en JSON estructurado.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:
{
  "title": "título de la rúbrica",
  "description": "objetivo de la evaluación en una o dos frases",
  "criteria": [
    {
      "name": "nombre del criterio",
      "description": "qué se observa en este criterio",
      "levels": [
        {"label": "Adecuado", "score": 3, "descriptor": "descripción del desempeño"},
        {"label": "Parcial", "score": 2, "descriptor": "..."},
        {"label": "Insuficiente", "score": 1, "descriptor": "..."}
      ]
    }
  ],
  "bands": [
    {"label": "Adecuado", "min": 18, "max": 21},
    {"label": "Parcial", "min": 12, "max": 17},
    {"label": "Insuficiente", "min": 7, "max": 11}
  ]
}

Reglas:
- Respeta los criterios, niveles y puntajes que aparecen en el documento; no inventes ninguno.
- Si el documento no define puntajes numéricos, asigna una escala descendente empezando en el número de niveles.
- Si no hay bandas de interpretación, devuelve "bands": [].
- Responde en español y sin texto fuera del JSON."""

EVALUATION_PROMPT = """Eres un docente de medicina corrigiendo el informe clínico de un estudiante.
Evalúas ÚNICAMENTE con los criterios de la rúbrica entregada. No agregues criterios propios.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:
{
  "criteria": [
    {
      "name": "nombre exacto del criterio de la rúbrica",
      "score": 2,
      "level": "etiqueta del nivel elegido",
      "justification": "por qué ese nivel, en una o dos frases",
      "evidence": "cita breve y literal del informe que sustenta el juicio, o cadena vacía"
    }
  ],
  "summary": "dictamen global en dos o tres frases",
  "strengths": ["fortaleza concreta", "..."],
  "improvements": ["qué debe corregir el estudiante", "..."]
}

Reglas:
- Un objeto por cada criterio de la rúbrica, en el mismo orden y con el mismo nombre.
- "score" debe ser uno de los puntajes definidos para ese criterio.
- Sé exigente y específico: cita el informe en "evidence" en lugar de generalizar.
- Si el informe no aporta evidencia para un criterio, asigna el nivel más bajo y dilo.
- Responde en español y sin texto fuera del JSON."""


# ------------------------------------------------------------------ utilidades

def _loads(raw: str) -> dict:
    """Parsea la respuesta del modelo tolerando envoltorios de markdown."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Algunos modelos anteponen una frase antes del objeto.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise HTTPException(
                status_code=502,
                detail="El modelo no devolvió un JSON interpretable.",
            )
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=502,
                detail="El modelo no devolvió un JSON interpretable.",
            ) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="El modelo no devolvió un objeto JSON.")
    return data


def _text(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any, limit: int = 10) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    items = [_text(item, 400) for item in value]
    return [item for item in items if item][:limit]


# ------------------------------------------------------------------- rubricas

def normalize_criteria(raw: Any) -> list[dict]:
    """Normaliza la lista de criterios de una rubrica.

    Cada criterio conserva sus niveles con puntaje; el maximo del criterio es el
    puntaje mas alto entre sus niveles, no un campo aparte, para que no puedan
    contradecirse.
    """
    if not isinstance(raw, list):
        return []

    criteria: list[dict] = []
    for entry in raw[:MAX_CRITERIA]:
        if not isinstance(entry, dict):
            continue
        name = _text(entry.get("name"), 200)
        if not name:
            continue

        levels: list[dict] = []
        for level in (entry.get("levels") or [])[:MAX_LEVELS]:
            if not isinstance(level, dict):
                continue
            score = _number(level.get("score"))
            if score is None:
                continue
            levels.append(
                {
                    "label": _text(level.get("label"), 80) or f"{score:g} puntos",
                    "score": score,
                    "descriptor": _text(level.get("descriptor"), 600),
                }
            )
        levels.sort(key=lambda item: item["score"], reverse=True)
        if not levels:
            continue

        criteria.append(
            {
                "name": name,
                "description": _text(entry.get("description"), 600),
                "levels": levels,
                "max_score": levels[0]["score"],
            }
        )
    return criteria


def normalize_bands(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    bands: list[dict] = []
    for entry in raw[:10]:
        if not isinstance(entry, dict):
            continue
        label = _text(entry.get("label"), 80)
        minimum = _number(entry.get("min"))
        maximum = _number(entry.get("max"))
        if not label or minimum is None or maximum is None:
            continue
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        bands.append({"label": label, "min": minimum, "max": maximum})
    bands.sort(key=lambda item: item["min"], reverse=True)
    return bands


def rubric_max_score(criteria: list[dict]) -> float:
    return round(sum(criterion["max_score"] for criterion in criteria), 2)


def band_for_score(bands: list[dict] | None, score: float) -> str | None:
    for band in bands or []:
        if band["min"] <= score <= band["max"]:
            return band["label"]
    return None


async def extract_rubric_from_text(db: Session, text: str) -> dict:
    """Propone una rubrica estructurada a partir del texto del documento.

    Devuelve un borrador para que el docente lo revise: no persiste nada, porque
    una extraccion automatica puede confundir columnas de una tabla y nadie
    deberia corregir con una rubrica que no valido antes.
    """
    settings = resolve_llm_settings(db)
    async with httpx.AsyncClient(timeout=max(settings.timeout, 180.0)) as client:
        raw = await chat_completion(
            client,
            settings,
            [
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": text[:MAX_REPORT_CHARS]},
            ],
            temperature=0.1,
            max_tokens=3000,
            num_ctx=8192,
            json_mode=True,
            purpose="extraccion de rubrica",
            db=db,
            feature="rubric_extract",
        )

    data = _loads(raw)
    criteria = normalize_criteria(data.get("criteria"))
    if not criteria:
        raise HTTPException(
            status_code=422,
            detail="No se reconocieron criterios en el documento. Revisa el archivo o carga la rúbrica a mano.",
        )
    bands = normalize_bands(data.get("bands"))
    return {
        "title": _text(data.get("title"), 200) or "Rúbrica sin título",
        "description": _text(data.get("description"), 1000),
        "criteria": criteria,
        "bands": bands,
        "max_score": rubric_max_score(criteria),
    }


# ----------------------------------------------------------------- evaluacion

def _rubric_for_prompt(rubric_title: str, criteria: list[dict], guidance: str | None) -> str:
    lines = [f"RÚBRICA: {rubric_title}", ""]
    for index, criterion in enumerate(criteria, 1):
        lines.append(f"{index}. {criterion['name']} (máximo {criterion['max_score']:g} puntos)")
        if criterion.get("description"):
            lines.append(f"   Qué se observa: {criterion['description']}")
        for level in criterion["levels"]:
            descriptor = f" — {level['descriptor']}" if level.get("descriptor") else ""
            lines.append(f"   · {level['score']:g} puntos, {level['label']}{descriptor}")
        lines.append("")
    if guidance:
        lines.append("INDICACIONES ADICIONALES DEL DOCENTE:")
        lines.append(guidance)
    return "\n".join(lines)


def _match_criterion(name: str, criteria: list[dict]) -> dict | None:
    """Empareja el criterio devuelto por el modelo con el de la rubrica.

    Primero por nombre exacto sin distinguir mayusculas; si el modelo lo
    reescribio, por coincidencia de prefijo. Lo que no encaje se descarta: es
    preferible perder un criterio inventado a sumarlo al puntaje.
    """
    normalized = name.strip().lower()
    for criterion in criteria:
        if criterion["name"].strip().lower() == normalized:
            return criterion
    for criterion in criteria:
        actual = criterion["name"].strip().lower()
        if normalized.startswith(actual[:12]) or actual.startswith(normalized[:12]):
            return criterion
    return None


def normalize_evaluation(data: dict, criteria: list[dict], bands: list[dict] | None) -> dict:
    """Convierte la respuesta del modelo en una evaluacion consistente.

    El puntaje de cada criterio se ajusta al nivel valido mas cercano y el total
    se recalcula sumando en Python: nunca se confia en la aritmetica del modelo.
    Un criterio que el modelo no evaluo se registra con puntaje 0 y se marca
    como no evaluado, para que el docente lo vea en lugar de que desaparezca.
    """
    # Los criterios se renormalizan (operacion idempotente) porque pueden venir
    # de `rubric.criteria_json`, escrito por una version anterior del formato o
    # importado a mano: sin `max_score` calculado, la suma fallaria.
    criteria = normalize_criteria(criteria)

    by_name: dict[str, dict] = {}
    for entry in data.get("criteria") or []:
        if not isinstance(entry, dict):
            continue
        match = _match_criterion(_text(entry.get("name"), 200), criteria)
        if match and match["name"] not in by_name:
            by_name[match["name"]] = entry

    results: list[dict] = []
    total = 0.0
    for criterion in criteria:
        entry = by_name.get(criterion["name"])
        allowed = [level["score"] for level in criterion["levels"]]
        if entry is None:
            results.append(
                {
                    "criterion": criterion["name"],
                    "score": 0.0,
                    "max_score": criterion["max_score"],
                    "level": None,
                    "justification": "El modelo no entregó una valoración para este criterio.",
                    "evidence": "",
                    "evaluated": False,
                }
            )
            continue

        raw_score = _number(entry.get("score"))
        if raw_score is None:
            score = min(allowed)
        else:
            # Se ancla al nivel valido mas cercano: la rubrica es discreta.
            score = min(allowed, key=lambda option: abs(option - raw_score))

        level_label = _text(entry.get("level"), 80)
        if not level_label:
            level_label = next(
                (level["label"] for level in criterion["levels"] if level["score"] == score),
                None,
            )

        total += score
        results.append(
            {
                "criterion": criterion["name"],
                "score": score,
                "max_score": criterion["max_score"],
                "level": level_label,
                "justification": _text(entry.get("justification"), 1200),
                "evidence": _text(entry.get("evidence"), 600),
                "evaluated": True,
            }
        )

    total = round(total, 2)
    max_score = rubric_max_score(criteria)
    return {
        "criteria": results,
        "total_score": total,
        "max_score": max_score,
        "band": band_for_score(bands, total),
        "summary": _text(data.get("summary"), 2000),
        "strengths": _string_list(data.get("strengths")),
        "improvements": _string_list(data.get("improvements")),
    }


async def evaluate_report(
    db: Session,
    *,
    rubric_title: str,
    criteria: list[dict],
    bands: list[dict] | None,
    guidance: str | None,
    report_text: str,
) -> dict:
    """Puntua un informe contra la rubrica y devuelve el resultado normalizado."""
    criteria = normalize_criteria(criteria)
    if not criteria:
        raise HTTPException(status_code=422, detail="La rúbrica no tiene criterios definidos.")

    settings = resolve_llm_settings(db)
    user_message = (
        f"{_rubric_for_prompt(rubric_title, criteria, guidance)}\n\n"
        "INFORME DEL ESTUDIANTE:\n"
        f"{report_text[:MAX_REPORT_CHARS]}"
    )

    async with httpx.AsyncClient(timeout=max(settings.timeout, 240.0)) as client:
        raw = await chat_completion(
            client,
            settings,
            [
                {"role": "system", "content": EVALUATION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=3000,
            num_ctx=8192,
            json_mode=True,
            purpose="revision de informe con rubrica",
            db=db,
            feature="rubric_review",
        )

    result = normalize_evaluation(_loads(raw), criteria, bands)
    result["provider"] = settings.provider
    result["model"] = settings.model
    return result
