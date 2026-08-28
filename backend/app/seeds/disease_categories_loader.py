"""Carga idempotente del catalogo inicial de enfermedades de Imagenes IA.

Se ejecuta en el arranque del backend. Si la tabla ya tiene alguna fila no
hace nada: el catalogo pasa a ser propiedad del docente desde Configuracion
y este seed solo existe para no perder, en la primera migracion, las
categorias que antes vivian hardcodeadas en el frontend.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import DiseaseCategory

DEFAULT_CATEGORIES = [
    {
        "key": "cancer-mama",
        "label": "Cáncer de mama",
        "icon": "🎗️",
        "description": "Metástasis en ganglio linfático centinela (CAMELYON17 · SLN-Breast)",
        "keywords": ["camelyon", "sln", "breast", "mama", "metastasico", "metastasis", "cancer", "carcinoma", "tumor", "neoplasia", "maligno"],
        "sort_order": 10,
    },
    {
        "key": "necrosis",
        "label": "Necrosis y muerte celular",
        "icon": "🧬",
        "description": "Necrosis coagulativa y licuefactiva, apoptosis e infarto",
        "keywords": ["necrosis", "apoptosis", "infarto", "isquemia", "gangrena"],
        "sort_order": 20,
    },
    {
        "key": "inflamacion",
        "label": "Inflamación aguda y crónica",
        "icon": "🔥",
        "description": "Infiltrado inflamatorio, absceso y granuloma",
        "keywords": ["inflamacion", "absceso", "granuloma", "infiltrado", "itis"],
        "sort_order": 30,
    },
    {
        "key": "tuberculosis",
        "label": "Tuberculosis",
        "icon": "🫁",
        "description": "Granulomas caseificantes y bacilo de Koch en tejido pulmonar y extrapulmonar",
        "keywords": ["tuberculosis", "tb", "bacilo de koch", "baar", "koch"],
        "sort_order": 40,
    },
    {
        "key": "hepatitis",
        "label": "Hepatitis",
        "icon": "🫘",
        "description": "Inflamación hepática de origen viral, autoinmune o tóxico",
        "keywords": ["hepatitis", "higado", "hepatocito", "hepatopatia", "cirrosis"],
        "sort_order": 50,
    },
    {
        "key": "neumonia",
        "label": "Neumonía",
        "icon": "🌬️",
        "description": "Consolidación e infiltrado inflamatorio del parénquima pulmonar",
        "keywords": ["neumonia"],
        "sort_order": 60,
    },
    {
        "key": "infecciosa",
        "label": "Patología infecciosa",
        "icon": "🦠",
        "description": "Agentes bacterianos, micóticos, virales y parasitarios",
        "keywords": ["infeccion", "bacteria", "micosis", "hongo", "viral", "virus", "parasito", "langerhans", "histiocitosis"],
        "sort_order": 70,
    },
    {
        "key": "vascular",
        "label": "Trastornos vasculares",
        "icon": "🩸",
        "description": "Trombosis, hemorragia, congestión y edema",
        "keywords": ["trombosis", "hemorragia", "congestion", "edema", "embolia", "vascular", "aterosclerosis"],
        "sort_order": 80,
    },
    {
        "key": "adaptaciones",
        "label": "Adaptaciones y depósitos celulares",
        "icon": "⚗️",
        "description": "Hiperplasia, hipertrofia, metaplasia, displasia y esteatosis",
        "keywords": ["hiperplasia", "hipertrofia", "metaplasia", "displasia", "atrofia", "esteatosis", "amiloide", "deposito", "acumulacion"],
        "sort_order": 90,
    },
]


def seed_disease_categories(db: Session) -> None:
    if db.query(DiseaseCategory).first() is not None:
        return
    for entry in DEFAULT_CATEGORIES:
        db.add(DiseaseCategory(**entry))
    db.commit()
