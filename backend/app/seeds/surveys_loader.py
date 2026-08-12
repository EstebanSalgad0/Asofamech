"""Carga idempotente de los instrumentos de encuestas desde JSON.

Se ejecuta en el arranque del backend. Si una encuesta con el mismo `code` ya
existe:
  - No se modifican título/descripción/estado (para no pisar cambios del docente).
  - Los ítems se sincronizan de forma no-destructiva: si aparece un ítem nuevo
    en el JSON se agrega al final; los ítems existentes no se tocan ni se
    borran (así se preservan las respuestas anteriores).

Para reemplazar por completo un instrumento, el docente debe archivar el
existente y publicar uno nuevo con otro `code`.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from ..models import Survey, SurveyItem

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).parent / "surveys"
SEED_FILES = ["razonamiento.json", "fpa.json", "pap.json"]


def _normalize_items(section_name: str, raw_items: list) -> Iterable[dict]:
    """Un ítem puede ser un string (Likert requerido por defecto) o un objeto
    {text, type, required}."""
    for entry in raw_items:
        if isinstance(entry, str):
            yield {"text": entry, "type": "likert_1_5", "required": True}
        elif isinstance(entry, dict):
            yield {
                "text": entry["text"],
                "type": entry.get("type", "likert_1_5"),
                "required": bool(entry.get("required", True)),
            }
        else:
            raise ValueError(f"Ítem inválido en sección '{section_name}': {entry!r}")


def _load_seed_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _sync_survey(db: Session, data: dict) -> None:
    code = data["code"]
    survey = db.query(Survey).filter(Survey.code == code).first()
    created = False
    if survey is None:
        survey = Survey(
            code=code,
            title=data["title"],
            description=data.get("description"),
            status="open",
        )
        db.add(survey)
        db.flush()
        created = True

    existing_texts = {(it.section, it.text) for it in survey.items}

    section_order = 0
    max_item_order = max((it.item_order for it in survey.items), default=-1)

    for section in data["sections"]:
        section_order += 1
        section_name = section["name"]
        for item in _normalize_items(section_name, section["items"]):
            key = (section_name, item["text"])
            if key in existing_texts:
                continue
            max_item_order += 1
            db.add(
                SurveyItem(
                    survey_id=survey.id,
                    section=section_name,
                    section_order=section_order,
                    item_order=max_item_order,
                    text=item["text"],
                    item_type=item["type"],
                    required=item["required"],
                )
            )

    if created:
        logger.info("[surveys_seed] Encuesta '%s' creada con sus ítems.", code)


def seed_surveys(db: Session) -> None:
    """Idempotente: seguro llamar en cada arranque."""
    for filename in SEED_FILES:
        path = SEEDS_DIR / filename
        if not path.exists():
            logger.warning("[surveys_seed] Falta el seed: %s", path)
            continue
        try:
            data = _load_seed_file(path)
            _sync_survey(db, data)
        except Exception as exc:
            logger.exception("[surveys_seed] Error cargando %s: %s", filename, exc)
            db.rollback()
            continue
    db.commit()
