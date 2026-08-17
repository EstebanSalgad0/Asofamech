"""Carga idempotente de los casos clinicos plantilla.

PAC-ASO-001 (tuberculosis miliar en VIH) es el caso que la coordinacion
academica definio como modelo del formato. Se siembra al arranque para que la
plataforma nunca este vacia y para que un docente pueda abrirlo, duplicarlo y
usarlo como molde.

Idempotente y no destructivo: si el caso ya existe (mismo `case_code`) no se
toca. Un docente puede editarlo libremente sin que el proximo arranque le pise
los cambios; para volver al original basta con borrarlo y reiniciar.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..case_structure import normalize_structure, structure_to_markdown
from ..models import Case, CaseLink

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).parent / "cases"
SEED_FILES = ["pac_aso_001.json"]


def _sync_case(db: Session, data: dict) -> None:
    code = data["case_code"]
    if db.query(Case.id).filter(Case.case_code == code).first():
        return

    structure = normalize_structure(data.get("structured"))
    body = structure_to_markdown(structure) or data.get("body") or ""

    case = Case(
        title=data["title"],
        description=data["description"],
        body=body,
        case_code=code,
        structured_json=structure,
        clinical_context=data.get("clinical_context"),
        learning_objectives=data.get("learning_objectives"),
        difficulty=data.get("difficulty"),
        topic=data.get("topic"),
        status=data.get("status", "published"),
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    for position, link in enumerate(data.get("links") or []):
        case.links.append(
            CaseLink(
                kind=link.get("kind", "otro"),
                label=link["label"][:200],
                url=link["url"][:1000],
                description=(link.get("description") or None),
                position=position,
            )
        )
    db.add(case)
    logger.info("[cases_seed] Caso '%s' sembrado.", code)


def seed_cases(db: Session) -> None:
    """Idempotente: seguro llamar en cada arranque."""
    for filename in SEED_FILES:
        path = SEEDS_DIR / filename
        if not path.exists():
            logger.warning("[cases_seed] Falta el seed: %s", path)
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                _sync_case(db, json.load(fh))
        except Exception as exc:
            logger.exception("[cases_seed] Error cargando %s: %s", filename, exc)
            db.rollback()
            continue
    db.commit()
