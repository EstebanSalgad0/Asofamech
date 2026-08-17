"""Carga idempotente de las rubricas base del revisor de informes.

El "Script de evaluacion para informe clinico de alumno" es la pauta que la
coordinacion academica entrego junto al caso PAC-ASO-001. Se siembra publicada
para que el revisor funcione desde el primer arranque, sin obligar al docente a
transcribir la rubrica a mano.

Como el resto de los seeds: si ya existe una rubrica con el mismo titulo no se
toca, para no pisar los ajustes del docente.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ..models import Rubric
from ..rubric_review import normalize_bands, normalize_criteria, rubric_max_score

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).parent / "rubrics"
SEED_FILES = ["informe_clinico.json"]


def _sync_rubric(db: Session, data: dict) -> None:
    title = data["title"]
    if db.query(Rubric.id).filter(Rubric.title == title).first():
        return

    criteria = normalize_criteria(data.get("criteria"))
    if not criteria:
        logger.warning("[rubrics_seed] '%s' no define criterios validos.", title)
        return

    db.add(
        Rubric(
            title=title,
            description=data.get("description"),
            source_filename=data.get("source_filename"),
            criteria_json=criteria,
            bands_json=normalize_bands(data.get("bands")),
            max_score=rubric_max_score(criteria),
            guidance=data.get("guidance"),
            status=data.get("status", "published"),
            is_active=True,
        )
    )
    logger.info("[rubrics_seed] Rubrica '%s' sembrada.", title)


def seed_rubrics(db: Session) -> None:
    """Idempotente: seguro llamar en cada arranque."""
    for filename in SEED_FILES:
        path = SEEDS_DIR / filename
        if not path.exists():
            logger.warning("[rubrics_seed] Falta el seed: %s", path)
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                _sync_rubric(db, json.load(fh))
        except Exception as exc:
            logger.exception("[rubrics_seed] Error cargando %s: %s", filename, exc)
            db.rollback()
            continue
    db.commit()
