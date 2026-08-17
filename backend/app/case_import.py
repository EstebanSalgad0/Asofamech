"""Importacion de casos clinicos redactados en Word.

Los docentes ya escriben sus casos en documentos con una estructura muy
parecida a la del formato PA-ASO-001, pero cada uno numera y titula las
secciones a su manera. Este modulo le pide al LLM que haga esa traduccion y
devuelve una PROPUESTA: nada se guarda hasta que el docente la revisa en el
editor. Un mapeo automatico puede confundir una columna del Practical Script o
atribuir un hallazgo al sistema equivocado, y un caso clinico publicado con un
error asi es peor que no tener el caso.

Dos reglas que el prompt insiste en mantener, porque son las que separan una
importacion util de una peligrosa:

  - No inventar datos clinicos. Lo que el documento no diga queda vacio para
    que el docente lo complete; un campo en blanco se ve, un dato inventado no.
  - Los codigos SNOMED (SCTID) nunca se generan. Un codigo plausible pero falso
    es indistinguible de uno correcto para quien lee el caso.

El sintoma pivote y los calificadores semanticos si se infieren del relato
—es justamente el ejercicio que evalua la rubrica de informes— pero se
devuelven listados en `inferred` para que la interfaz los marque como
sugerencia y no como transcripcion.
"""
from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .case_structure import normalize_structure, structure_is_empty
from .llm_service import chat_completion, resolve_llm_settings
from .rubric_review import _loads, _string_list, _text

logger = logging.getLogger(__name__)

MAX_DOCUMENT_CHARS = 40000
VALID_DIFFICULTIES = {"pregrado", "internado", "residente"}

IMPORT_PROMPT = """Eres un asistente académico de una facultad de medicina chilena.
Recibes el texto de un caso clínico redactado por un docente y lo conviertes al formato estructurado de la plataforma.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma:

{
  "title": "título del caso",
  "description": "resumen breve del caso, 1-2 frases",
  "topic": "tema principal (ej: Neumonía adquirida en la comunidad)",
  "difficulty": "pregrado" | "internado" | "residente",
  "inferred": ["rutas de los campos que dedujiste y no estaban literales en el documento"],
  "notes": "qué información pedía el formato y el documento no traía",
  "structured": {
    "identification": {"case_code": "", "summary": "", "keywords": ["palabra clave"]},
    "narratives": {
      "patient_first_person": "relato del paciente en primera persona, tal como aparece",
      "clinical_presentation": "el mismo cuadro en lenguaje médico"
    },
    "semantics": {
      "pivot_symptom": "síntoma central que organiza el caso",
      "key_terms": ["término médico relevante"],
      "qualifiers": {
        "temporality": ["hace 3 días", "..."],
        "evolution": ["progresiva", "..."],
        "intensity": ["38.7 °C", "..."],
        "features": ["productiva", "..."]
      }
    },
    "clinical": {
      "patient_profile": {"age": "64 años", "sex": "Femenino", "background": "antecedentes"},
      "chief_complaint": "motivo de consulta",
      "anamnesis": "historia de la enfermedad actual",
      "medications": ["fármaco y dosis"],
      "habits": "tabaco, alcohol, otros",
      "occupation": ""
    },
    "physical_exam": {
      "vital_signs": {"blood_pressure": "", "heart_rate": "", "respiratory_rate": "",
                      "temperature": "", "oxygen_saturation": "", "weight": "", "height": "", "bmi": ""},
      "general_state": "estado general",
      "systems": [{"name": "Sistema respiratorio", "findings": "hallazgos completos"}]
    },
    "workup": {
      "lab_panels": [{"name": "Hemograma", "comment": "",
                      "rows": [{"parameter": "Leucocitos", "result": "15.800 /mm³", "reference": "", "interpretation": ""}]}],
      "microbiology": [{"test": "", "result": "", "note": ""}],
      "imaging": [{"study": "Radiografía de tórax", "source": "", "report": "hallazgos e interpretación"}]
    },
    "course": {"timeline": [{"moment": "", "event": ""}], "treatment_plan": "tratamiento indicado"},
    "diagnoses": {
      "primary": {"name": "diagnóstico principal", "sctid": ""},
      "differentials": [{"name": "diagnóstico diferencial", "sctid": ""}],
      "justification": ""
    },
    "practical_script": {
      "instructions": "",
      "columns": ["diagnóstico 1", "diagnóstico 2"],
      "rows": [{"finding": "dato clínico",
                "ratings": [{"value": 2, "rationale": "justificación"}, {"value": -1, "rationale": "..."}]}]
    },
    "pathology": {"specimen": "", "macroscopic": "", "microscopic": "", "diagnosis": "", "coding": "",
                  "concordance": [{"diagnosis": "", "new_data": "", "shift": 0, "rationale": ""}]},
    "pedagogy": {"objectives": [{"area": "", "text": "punto de aprendizaje"}],
                 "level": "", "prerequisites": "", "curricular_placement": ""},
    "assessment": {"multiple_choice": [], "open_questions": []}
  }
}

Reglas obligatorias:
- NO inventes datos clínicos. Si el documento no trae una sección, deja sus campos vacíos ("" o []).
- NO generes códigos SNOMED (sctid): déjalos siempre en "" aunque conozcas el código.
- Transcribe los valores tal como aparecen (unidades incluidas); no los conviertas ni los redondees.
- Reparte el examen físico en un objeto por sistema, conservando todos los hallazgos.
- Tabla tipo SCT o Practical Script: las columnas que NO son "dato clínico" ni "hallazgos en el paciente"
  son los diagnósticos; van en "columns" en ese mismo orden, y cada fila lleva un "ratings" por columna.
  Extrae el número (-2 a +2) al campo "value" y el resto del texto a "rationale".
- Esos mismos diagnósticos son los diferenciales: cópialos a "differentials" (el más apoyado por la
  evidencia va en "primary" si el documento no declara otro diagnóstico).
- "pivot_symptom" y "qualifiers" normalmente no vienen escritos: dedúcelos del relato y añade sus rutas
  a "inferred" (por ejemplo "semantics.pivot_symptom").
- Responde en español y sin texto fuera del JSON."""


def _difficulty(value) -> str | None:
    candidate = _text(value, 40).lower()
    return candidate if candidate in VALID_DIFFICULTIES else None


async def import_case_from_text(db: Session, text: str) -> dict:
    """Convierte el texto de un documento en una propuesta de caso clinico.

    No persiste nada: devuelve el borrador para que el docente lo revise.
    """
    document = (text or "").strip()
    if len(document) < 200:
        raise HTTPException(
            status_code=422,
            detail="El documento es demasiado corto para contener un caso clínico.",
        )

    settings = resolve_llm_settings(db)
    async with httpx.AsyncClient(timeout=max(settings.timeout, 300.0)) as client:
        raw = await chat_completion(
            client,
            settings,
            [
                {"role": "system", "content": IMPORT_PROMPT},
                {"role": "user", "content": document[:MAX_DOCUMENT_CHARS]},
            ],
            temperature=0.1,
            max_tokens=6000,
            num_ctx=16384,
            json_mode=True,
            purpose="importacion de caso clinico",
            db=db,
            feature="case_import",
        )

    data = _loads(raw)
    structure = normalize_structure(data.get("structured"))
    if structure_is_empty(structure):
        raise HTTPException(
            status_code=422,
            detail=(
                "No se reconoció un caso clínico en el documento. "
                "Revisa el archivo o carga el caso manualmente."
            ),
        )

    # La plataforma exige título y descripción; si el modelo no los dio, se
    # rellenan desde la estructura antes que dejar al docente con el formulario
    # bloqueado por dos campos.
    title = _text(data.get("title"), 200) or structure["diagnoses"]["primary"]["name"]
    description = (
        _text(data.get("description"), 1000)
        or structure["identification"]["summary"]
        or structure["clinical"]["chief_complaint"]
    )

    return {
        "title": title[:200],
        "description": description[:1000],
        "topic": _text(data.get("topic"), 200) or None,
        "difficulty": _difficulty(data.get("difficulty")),
        "structured": structure,
        "inferred": _string_list(data.get("inferred"), limit=30),
        "notes": _text(data.get("notes"), 1000),
        "warnings": _completeness_warnings(structure),
    }


def _completeness_warnings(structure: dict) -> list[str]:
    """Avisos sobre lo que el documento no traia.

    Se calculan en Python y no se le piden al modelo: si el modelo omitio una
    seccion por descuido, tambien omitiria el aviso correspondiente.
    """
    warnings: list[str] = []

    if not structure["narratives"]["patient_first_person"]:
        warnings.append("El caso no incluye relato del paciente en primera persona.")
    if not structure["semantics"]["pivot_symptom"]:
        warnings.append("No se identificó un síntoma pivote.")
    if not structure["practical_script"]["rows"]:
        warnings.append("El documento no traía una tabla de Practical Script (SCT).")
    if not structure["diagnoses"]["differentials"]:
        warnings.append("No se encontraron diagnósticos diferenciales.")
    if not any(structure["physical_exam"]["vital_signs"].values()):
        warnings.append("No se encontraron signos vitales.")
    if not structure["workup"]["lab_panels"]:
        warnings.append("No se encontraron exámenes de laboratorio.")

    missing_sctid = not structure["diagnoses"]["primary"]["sctid"] and bool(
        structure["diagnoses"]["primary"]["name"]
    )
    if missing_sctid:
        warnings.append(
            "Los códigos SNOMED (SCTID) no se generan automáticamente: complétalos a mano."
        )
    if not structure["pathology"]["microscopic"]:
        warnings.append("El caso no incluye informe anatomopatológico.")
    if not structure["assessment"]["open_questions"] and not structure["assessment"]["multiple_choice"]:
        warnings.append("El caso no incluye banco de evaluación.")

    return warnings
