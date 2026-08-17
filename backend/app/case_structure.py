"""Estructura canonica de un caso clinico ASOFAMECH.

El formato lo fija el caso PA-ASO-001 (Tuberculosis miliar en paciente VIH+),
que la coordinacion academica definio como plantilla para el resto de los
casos. Este modulo es la unica fuente de verdad sobre esa forma: el router, el
seed y el editor del frontend derivan de aqui.

Se guarda como un unico JSON (`Case.structured_json`) en vez de repartirlo en
columnas porque la plantilla tiene ~13 secciones con listas y tablas anidadas:
normalizarla en tablas relacionales obligaria a una decena de modelos que solo
se leen y escriben en bloque. A cambio, `normalize_structure` hace de esquema:
recorta, tipa y ordena todo lo que entra, de modo que la base nunca guarda una
forma que la vista no sepa renderizar.

`structure_to_markdown` mantiene sincronizado el campo `body` heredado, del que
dependen la busqueda de texto y el contexto que recibe el chatbot.
"""
from __future__ import annotations

from typing import Any

CASE_STRUCTURE_VERSION = 1

# Escala del Practical Script / test de concordancia (SCT).
SCT_SCALE = [-2, -1, 0, 1, 2]
SCT_SCALE_LABELS = {
    -2: "Mucho menos apropiada",
    -1: "Menos apropiada",
    0: "Sin cambios",
    1: "Mas apropiada",
    2: "Mucho mas apropiada",
}

# Limites defensivos: el editor es libre y el JSON viaja completo en cada PUT.
MAX_LIST_ITEMS = 60
MAX_SHORT_TEXT = 400
MAX_LONG_TEXT = 20000


# --------------------------------------------------------------- normalizacion

def _text(value: Any, limit: int = MAX_LONG_TEXT) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _short(value: Any) -> str:
    return _text(value, MAX_SHORT_TEXT)


def _text_list(value: Any) -> list[str]:
    """Acepta lista o texto con saltos de linea / punto y coma."""
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part for chunk in value.split("\n") for part in chunk.split(";")]
    elif isinstance(value, list):
        raw = value
    else:
        return []
    items = [_short(item) for item in raw]
    return [item for item in items if item][:MAX_LIST_ITEMS]


def _rows(value: Any, fields: dict[str, str]) -> list[dict]:
    """Normaliza una lista de filas segun `fields` = {clave: tipo}.

    Tipos: "short", "long", "list", "int", "ratings".
    Descarta filas totalmente vacias para que el editor pueda dejar lineas en
    blanco sin ensuciar el caso publicado.
    """
    if not isinstance(value, list):
        return []

    normalized: list[dict] = []
    for entry in value[:MAX_LIST_ITEMS]:
        if not isinstance(entry, dict):
            continue
        row: dict[str, Any] = {}
        for key, kind in fields.items():
            raw = entry.get(key)
            if kind == "short":
                row[key] = _short(raw)
            elif kind == "long":
                row[key] = _text(raw)
            elif kind == "list":
                row[key] = _text_list(raw)
            elif kind == "int":
                row[key] = _optional_int(raw)
            elif kind == "ratings":
                row[key] = _ratings(raw)
        if _row_has_content(row):
            normalized.append(row)
    return normalized


def _row_has_content(row: dict) -> bool:
    return any(value not in ("", [], None) for value in row.values())


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _ratings(value: Any) -> list[dict]:
    """Celdas de una fila del Practical Script: un juicio por diagnostico."""
    if not isinstance(value, list):
        return []
    cells: list[dict] = []
    for entry in value[:MAX_LIST_ITEMS]:
        if not isinstance(entry, dict):
            continue
        score = _optional_int(entry.get("value"))
        if score is not None and score not in SCT_SCALE:
            score = max(-2, min(2, score))
        cells.append({"value": score, "rationale": _short(entry.get("rationale"))})
    return cells


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def empty_structure() -> dict:
    """Plantilla vacia con todas las secciones del formato PA-ASO-001."""
    return normalize_structure({})


def normalize_structure(raw: Any) -> dict:
    """Devuelve la estructura completa, con todas las claves presentes.

    Nunca lanza: lo que no encaja se descarta. El caso clinico es contenido
    editorial escrito a mano por docentes, y rechazar el guardado entero por un
    campo mal tipado perderia el trabajo de toda la sesion de edicion.
    """
    data = _dict(raw)

    identification = _dict(data.get("identification"))
    narratives = _dict(data.get("narratives"))
    semantics = _dict(data.get("semantics"))
    qualifiers = _dict(semantics.get("qualifiers"))
    clinical = _dict(data.get("clinical"))
    profile = _dict(clinical.get("patient_profile"))
    exam = _dict(data.get("physical_exam"))
    vitals = _dict(exam.get("vital_signs"))
    workup = _dict(data.get("workup"))
    course = _dict(data.get("course"))
    diagnoses = _dict(data.get("diagnoses"))
    primary = _dict(diagnoses.get("primary"))
    script = _dict(data.get("practical_script"))
    pathology = _dict(data.get("pathology"))
    pedagogy = _dict(data.get("pedagogy"))
    assessment = _dict(data.get("assessment"))

    return {
        "version": CASE_STRUCTURE_VERSION,
        "identification": {
            "case_code": _short(identification.get("case_code")),
            "summary": _text(identification.get("summary")),
            "keywords": _text_list(identification.get("keywords")),
        },
        "narratives": {
            "patient_first_person": _text(narratives.get("patient_first_person")),
            "clinical_presentation": _text(narratives.get("clinical_presentation")),
        },
        "semantics": {
            "pivot_symptom": _short(semantics.get("pivot_symptom")),
            "key_terms": _text_list(semantics.get("key_terms")),
            "qualifiers": {
                "temporality": _text_list(qualifiers.get("temporality")),
                "evolution": _text_list(qualifiers.get("evolution")),
                "intensity": _text_list(qualifiers.get("intensity")),
                "features": _text_list(qualifiers.get("features")),
            },
        },
        "clinical": {
            "patient_profile": {
                "age": _short(profile.get("age")),
                "sex": _short(profile.get("sex")),
                "background": _text(profile.get("background")),
            },
            "chief_complaint": _text(clinical.get("chief_complaint")),
            "anamnesis": _text(clinical.get("anamnesis")),
            "medications": _text_list(clinical.get("medications")),
            "habits": _text(clinical.get("habits")),
            "occupation": _short(clinical.get("occupation")),
        },
        "physical_exam": {
            "vital_signs": {
                "blood_pressure": _short(vitals.get("blood_pressure")),
                "heart_rate": _short(vitals.get("heart_rate")),
                "respiratory_rate": _short(vitals.get("respiratory_rate")),
                "temperature": _short(vitals.get("temperature")),
                "oxygen_saturation": _short(vitals.get("oxygen_saturation")),
                "weight": _short(vitals.get("weight")),
                "height": _short(vitals.get("height")),
                "bmi": _short(vitals.get("bmi")),
            },
            "general_state": _text(exam.get("general_state")),
            "systems": _rows(exam.get("systems"), {"name": "short", "findings": "long"}),
        },
        "workup": {
            "lab_panels": _lab_panels(workup.get("lab_panels")),
            "microbiology": _rows(
                workup.get("microbiology"),
                {"test": "short", "result": "short", "note": "long"},
            ),
            "imaging": _rows(
                workup.get("imaging"),
                {"study": "short", "source": "short", "report": "long"},
            ),
        },
        "course": {
            "timeline": _rows(course.get("timeline"), {"moment": "short", "event": "long"}),
            "treatment_plan": _text(course.get("treatment_plan")),
        },
        "diagnoses": {
            "primary": {"name": _short(primary.get("name")), "sctid": _short(primary.get("sctid"))},
            "differentials": _rows(
                diagnoses.get("differentials"), {"name": "short", "sctid": "short"}
            ),
            "justification": _text(diagnoses.get("justification")),
        },
        "practical_script": {
            "instructions": _text(script.get("instructions")),
            "columns": _text_list(script.get("columns")),
            "rows": _rows(script.get("rows"), {"finding": "short", "ratings": "ratings"}),
        },
        "pathology": {
            "specimen": _short(pathology.get("specimen")),
            "macroscopic": _text(pathology.get("macroscopic")),
            "microscopic": _text(pathology.get("microscopic")),
            "diagnosis": _text(pathology.get("diagnosis")),
            "coding": _short(pathology.get("coding")),
            "concordance": _rows(
                pathology.get("concordance"),
                {
                    "diagnosis": "short",
                    "new_data": "long",
                    "shift": "int",
                    "rationale": "long",
                },
            ),
        },
        "pedagogy": {
            "objectives": _rows(pedagogy.get("objectives"), {"area": "short", "text": "long"}),
            "level": _short(pedagogy.get("level")),
            "prerequisites": _text(pedagogy.get("prerequisites")),
            "curricular_placement": _text(pedagogy.get("curricular_placement")),
            # Con el caso aun abierto, la clave de correccion se oculta al
            # estudiante. El docente la libera cuando el caso ya se discutio.
            "reveal_key": bool(pedagogy.get("reveal_key")),
        },
        "assessment": {
            "multiple_choice": _mcq(assessment.get("multiple_choice")),
            "open_questions": _rows(
                assessment.get("open_questions"), {"question": "long", "rubric": "long"}
            ),
        },
    }


def _lab_panels(value: Any) -> list[dict]:
    """Panel de laboratorio: cabecera + filas parametro/resultado/referencia."""
    if not isinstance(value, list):
        return []
    panels: list[dict] = []
    for entry in value[:MAX_LIST_ITEMS]:
        if not isinstance(entry, dict):
            continue
        panel = {
            "name": _short(entry.get("name")),
            "comment": _text(entry.get("comment")),
            "rows": _rows(
                entry.get("rows"),
                {
                    "parameter": "short",
                    "result": "short",
                    "reference": "short",
                    "interpretation": "short",
                },
            ),
        }
        if panel["name"] or panel["rows"] or panel["comment"]:
            panels.append(panel)
    return panels


def _mcq(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    questions: list[dict] = []
    for entry in value[:MAX_LIST_ITEMS]:
        if not isinstance(entry, dict):
            continue
        options = _text_list(entry.get("options"))
        correct = _optional_int(entry.get("correct_index"))
        if correct is not None and not (0 <= correct < len(options)):
            correct = None
        question = {
            "question": _text(entry.get("question")),
            "options": options,
            "correct_index": correct,
            "rationale": _text(entry.get("rationale")),
        }
        if question["question"] or options:
            questions.append(question)
    return questions


def structure_is_empty(structure: dict | None) -> bool:
    """True si no hay ningun contenido util (solo claves vacias)."""
    if not structure:
        return True
    return _is_blank(structure, skip_keys={"version"})


def _is_blank(value: Any, skip_keys: set[str] | None = None) -> bool:
    if isinstance(value, dict):
        return all(
            _is_blank(v)
            for k, v in value.items()
            if not (skip_keys and k in skip_keys)
        )
    if isinstance(value, list):
        return all(_is_blank(v) for v in value)
    # Un booleano apagado es la ausencia de una marca, no contenido: si
    # `reveal_key=False` contara, ninguna estructura seria vacia jamas.
    if isinstance(value, bool):
        return value is False
    return value in ("", None)


# ------------------------------------------------------------------- markdown

def _md_section(lines: list[str], title: str) -> None:
    lines.append(f"## {title}")


def _md_sub(lines: list[str], title: str) -> None:
    lines.append(f"### {title}")


def _md_table(lines: list[str], headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        return
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join([" --- "] * len(headers)) + "|")
    for row in rows:
        cells = [(cell or "").replace("|", "/").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")


def _md_bullets(lines: list[str], items: list[str]) -> None:
    for item in items:
        lines.append(f"- {item}")
    if items:
        lines.append("")


def _md_paragraph(lines: list[str], text: str) -> None:
    if text:
        lines.append(text)
        lines.append("")


def structure_to_markdown(structure: dict | None) -> str:
    """Renderiza la estructura al markdown ligero que entiende `CaseBody`.

    Es lo que ve el estudiante y lo que indexa la busqueda, asi que incluye
    todo salvo las secciones que son material del docente: el Practical Script
    con sus puntajes, la justificacion diagnostica, el banco de evaluacion y
    los metadatos pedagogicos viajan aparte para no revelar las respuestas.
    """
    if not structure:
        return ""

    data = normalize_structure(structure)
    lines: list[str] = []

    ident = data["identification"]
    if ident["summary"]:
        _md_paragraph(lines, ident["summary"])
    if ident["keywords"]:
        _md_paragraph(lines, "**Palabras clave:** " + ", ".join(ident["keywords"]))

    narratives = data["narratives"]
    if narratives["patient_first_person"]:
        _md_section(lines, "Relato del paciente")
        _md_paragraph(lines, narratives["patient_first_person"])
    if narratives["clinical_presentation"]:
        _md_section(lines, "Presentacion clinica")
        _md_paragraph(lines, narratives["clinical_presentation"])

    semantics = data["semantics"]
    qualifiers = semantics["qualifiers"]
    has_qualifiers = any(qualifiers.values())
    if semantics["pivot_symptom"] or semantics["key_terms"] or has_qualifiers:
        _md_section(lines, "Analisis semantico")
        if semantics["pivot_symptom"]:
            _md_paragraph(lines, f"**Sintoma pivote:** {semantics['pivot_symptom']}")
        if semantics["key_terms"]:
            _md_sub(lines, "Terminos medicos relevantes")
            _md_bullets(lines, semantics["key_terms"])
        if has_qualifiers:
            _md_sub(lines, "Calificadores semanticos")
            for label, key in (
                ("Temporalidad", "temporality"),
                ("Evolucion", "evolution"),
                ("Intensidad / cantidad", "intensity"),
                ("Caracteristicas", "features"),
            ):
                if qualifiers[key]:
                    _md_paragraph(lines, f"**{label}:** " + ", ".join(qualifiers[key]))

    clinical = data["clinical"]
    profile = clinical["patient_profile"]
    profile_bits = [bit for bit in (profile["age"], profile["sex"]) if bit]
    if profile_bits or profile["background"] or clinical["chief_complaint"] or clinical["anamnesis"]:
        _md_section(lines, "Informacion clinica")
        if profile_bits or profile["background"]:
            header = ", ".join(profile_bits)
            _md_paragraph(
                lines,
                "**Perfil del paciente:** " + " — ".join(p for p in (header, profile["background"]) if p),
            )
        if clinical["occupation"]:
            _md_paragraph(lines, f"**Ocupacion:** {clinical['occupation']}")
        if clinical["chief_complaint"]:
            _md_sub(lines, "Motivo de consulta")
            _md_paragraph(lines, clinical["chief_complaint"])
        if clinical["anamnesis"]:
            _md_sub(lines, "Anamnesis y evolucion")
            _md_paragraph(lines, clinical["anamnesis"])
        if clinical["medications"]:
            _md_sub(lines, "Farmacos")
            _md_bullets(lines, clinical["medications"])
        if clinical["habits"]:
            _md_sub(lines, "Habitos")
            _md_paragraph(lines, clinical["habits"])

    exam = data["physical_exam"]
    vitals = exam["vital_signs"]
    vital_rows = [
        (label, vitals[key])
        for label, key in (
            ("Presion arterial", "blood_pressure"),
            ("Frecuencia cardiaca", "heart_rate"),
            ("Frecuencia respiratoria", "respiratory_rate"),
            ("Temperatura", "temperature"),
            ("Saturacion O2", "oxygen_saturation"),
            ("Peso", "weight"),
            ("Talla", "height"),
            ("IMC", "bmi"),
        )
        if vitals[key]
    ]
    if vital_rows or exam["general_state"] or exam["systems"]:
        _md_section(lines, "Examen fisico")
        if vital_rows:
            _md_sub(lines, "Signos vitales")
            _md_table(lines, ["Parametro", "Valor"], [[label, value] for label, value in vital_rows])
        if exam["general_state"]:
            _md_sub(lines, "Estado general")
            _md_paragraph(lines, exam["general_state"])
        for system in exam["systems"]:
            _md_sub(lines, system["name"] or "Hallazgos")
            _md_paragraph(lines, system["findings"])

    workup = data["workup"]
    if workup["lab_panels"] or workup["microbiology"]:
        _md_section(lines, "Laboratorio")
        for panel in workup["lab_panels"]:
            if panel["name"]:
                _md_sub(lines, panel["name"])
            _md_table(
                lines,
                ["Parametro", "Resultado", "Referencia", "Interpretacion"],
                [
                    [row["parameter"], row["result"], row["reference"], row["interpretation"]]
                    for row in panel["rows"]
                ],
            )
            _md_paragraph(lines, panel["comment"])
        if workup["microbiology"]:
            _md_sub(lines, "Microbiologia")
            _md_table(
                lines,
                ["Examen", "Resultado", "Observacion"],
                [[row["test"], row["result"], row["note"]] for row in workup["microbiology"]],
            )

    if workup["imaging"]:
        _md_section(lines, "Imagenologia")
        for study in workup["imaging"]:
            _md_sub(lines, study["study"] or "Estudio")
            if study["source"]:
                _md_paragraph(lines, f"Fuente: {study['source']}")
            _md_paragraph(lines, study["report"])

    course = data["course"]
    if course["timeline"] or course["treatment_plan"]:
        _md_section(lines, "Evolucion temporal")
        _md_table(
            lines,
            ["Momento", "Hecho clinico"],
            [[row["moment"], row["event"]] for row in course["timeline"]],
        )
        if course["treatment_plan"]:
            _md_sub(lines, "Plan de tratamiento")
            _md_paragraph(lines, course["treatment_plan"])

    pathology = data["pathology"]
    if any(pathology[key] for key in ("specimen", "macroscopic", "microscopic", "diagnosis")):
        _md_section(lines, "Informe anatomopatologico")
        if pathology["specimen"]:
            _md_paragraph(lines, f"**Muestra recibida:** {pathology['specimen']}")
        if pathology["macroscopic"]:
            _md_sub(lines, "Descripcion macroscopica")
            _md_paragraph(lines, pathology["macroscopic"])
        if pathology["microscopic"]:
            _md_sub(lines, "Descripcion microscopica")
            _md_paragraph(lines, pathology["microscopic"])
        if pathology["diagnosis"]:
            _md_sub(lines, "Diagnostico anatomopatologico")
            _md_paragraph(lines, pathology["diagnosis"])
        if pathology["coding"]:
            _md_paragraph(lines, f"**Codificacion:** {pathology['coding']}")

    return "\n".join(lines).strip()


def strip_answer_key(structure: dict | None) -> dict:
    """Version de la estructura apta para el estudiante.

    Quita lo que constituye la clave de correccion: los puntajes del Practical
    Script, la justificacion diagnostica, el test de concordancia y el banco de
    evaluacion. Entregarlos junto al enunciado convertiria el ejercicio de
    razonamiento en un ejercicio de lectura.

    Si el docente marco `pedagogy.reveal_key` —tipicamente despues de discutir
    el caso en clase— la estructura se devuelve completa.
    """
    data = normalize_structure(structure or {})
    if data["pedagogy"]["reveal_key"]:
        return data

    data["practical_script"] = {"instructions": "", "columns": [], "rows": []}
    data["diagnoses"]["justification"] = ""
    data["pathology"]["concordance"] = []
    data["assessment"] = {"multiple_choice": [], "open_questions": []}
    return data
