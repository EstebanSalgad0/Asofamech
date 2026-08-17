"""Casos clinicos en el formato PA-ASO-001.

Verifica que la estructura se guarda normalizada, que el cuerpo markdown se
regenera desde ella (de lo que dependen la busqueda y el chatbot) y —lo mas
importante— que la clave de correccion no viaja al estudiante.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import User
from app.routers import cases


STRUCTURE = {
    "identification": {
        "case_code": "PAC-ASO-777",
        "summary": "Paciente con tos cronica.",
        "keywords": ["Tuberculosis", "VIH"],
    },
    "narratives": {
        "patient_first_person": "Llevo tres meses tosiendo.",
        "clinical_presentation": "Cuadro de tres meses de tos productiva.",
    },
    "semantics": {
        "pivot_symptom": "Tos con hemoptisis",
        "key_terms": ["Hemoptisis", "Disnea progresiva"],
        "qualifiers": {"temporality": ["hace 3 meses"], "evolution": ["progresiva"]},
    },
    "workup": {
        "lab_panels": [
            {
                "name": "Hemograma",
                "rows": [{"parameter": "Hb", "result": "10,2 g/dL", "reference": "13,5-17,5"}],
                "comment": "Anemia moderada.",
            }
        ]
    },
    "diagnoses": {
        "primary": {"name": "Tuberculosis miliar", "sctid": "47604008"},
        "differentials": [{"name": "Sarcoidosis", "sctid": "24369008"}],
        "justification": "La incidencia en Chile es alta y el cultivo confirma.",
    },
    "practical_script": {
        "columns": ["Tuberculosis miliar", "Sarcoidosis"],
        "rows": [
            {
                "finding": "1. Perdida de peso",
                "ratings": [
                    {"value": 2, "rationale": "Muy frecuente."},
                    {"value": 1, "rationale": "Comun."},
                ],
            }
        ],
    },
    "pathology": {
        "specimen": "Ganglio linfatico",
        "microscopic": "Granulomas con necrosis caseosa.",
        "concordance": [
            {"diagnosis": "Sarcoidosis", "new_data": "Necrosis caseosa", "shift": -2, "rationale": "No caseifica."}
        ],
    },
    "assessment": {
        "open_questions": [{"question": "Redacte el resumen.", "rubric": "Script de evaluacion."}]
    },
}


def _make_user(role: str, user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"{role}@example.com",
        name=f"Usuario {role}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def structured_client():
    """Cliente cuyo rol se puede cambiar en caliente para probar la visibilidad."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_make_user("docente", 1))
        db.add(_make_user("estudiante", 2))
        db.commit()

    current = {"role": "docente", "id": 1}

    app = FastAPI()
    app.include_router(cases.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user(current["role"], current["id"])

    with TestClient(app) as client:
        yield client, current

    Base.metadata.drop_all(bind=engine)


def _create_case(client, **overrides):
    payload = {
        "title": "Tuberculosis miliar",
        "description": "Resumen del caso",
        "structured": STRUCTURE,
        "status": "published",
    }
    payload.update(overrides)
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_structured_case_generates_body_and_keeps_structure(structured_client):
    client, _ = structured_client
    created = _create_case(client)

    assert created["case_code"] == "PAC-ASO-777"
    assert created["structured"]["semantics"]["pivot_symptom"] == "Tos con hemoptisis"
    # El cuerpo se genera desde la estructura, no queda vacio.
    assert "Tos con hemoptisis" in created["body"]
    assert "Granulomas con necrosis caseosa" in created["body"]
    # Las tablas de laboratorio llegan como markdown renderizable.
    assert "| Hb |" in created["body"]


def test_body_search_reaches_structured_content(structured_client):
    client, _ = structured_client
    _create_case(client)

    response = client.get("/api/cases/search", params={"q": "hemoptisis"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_case_code_is_searchable(structured_client):
    client, _ = structured_client
    _create_case(client)

    response = client.get("/api/cases/search", params={"q": "PAC-ASO-777"})
    assert [c["case_code"] for c in response.json()] == ["PAC-ASO-777"]


def test_student_never_receives_the_answer_key(structured_client):
    client, current = structured_client
    _create_case(client)

    current["role"] = "estudiante"
    current["id"] = 2
    listed = client.get("/api/cases").json()
    assert len(listed) == 1
    structure = listed[0]["structured"]

    # Lo que resuelve el caso queda fuera.
    assert structure["practical_script"]["rows"] == []
    assert structure["diagnoses"]["justification"] == ""
    assert structure["pathology"]["concordance"] == []
    assert structure["assessment"]["open_questions"] == []
    # El enunciado sigue completo.
    assert structure["narratives"]["patient_first_person"].startswith("Llevo tres meses")
    assert structure["workup"]["lab_panels"][0]["rows"][0]["result"] == "10,2 g/dL"


def test_teacher_can_release_the_answer_key(structured_client):
    client, current = structured_client
    created = _create_case(client)

    revealed = dict(STRUCTURE)
    revealed["pedagogy"] = {"reveal_key": True}
    response = client.put(f"/api/cases/{created['id']}", json={"structured": revealed})
    assert response.status_code == 200

    current["role"] = "estudiante"
    current["id"] = 2
    structure = client.get(f"/api/cases/{created['id']}").json()["structured"]
    assert len(structure["practical_script"]["rows"]) == 1
    assert structure["diagnoses"]["justification"] != ""


def test_detail_endpoint_also_strips_the_key(structured_client):
    client, current = structured_client
    created = _create_case(client)

    current["role"] = "estudiante"
    current["id"] = 2
    detail = client.get(f"/api/cases/{created['id']}").json()
    assert detail["structured"]["practical_script"]["rows"] == []


def test_free_text_case_still_works(structured_client):
    client, _ = structured_client
    created = _create_case(client, structured=None, body="## Caso\n\nTexto libre del docente.")

    assert created["structured"] is None
    assert created["body"] == "## Caso\n\nTexto libre del docente."


def test_case_without_body_or_structure_is_rejected(structured_client):
    client, _ = structured_client
    response = client.post(
        "/api/cases",
        json={"title": "Vacio", "description": "Sin contenido", "structured": {}},
    )
    assert response.status_code == 422


def test_body_cannot_desync_from_structure(structured_client):
    """Editar el markdown a mano en un caso estructurado deberia rechazarse."""
    client, _ = structured_client
    created = _create_case(client)

    response = client.put(f"/api/cases/{created['id']}", json={"body": "otro cuerpo"})
    assert response.status_code == 422


def test_updating_structure_regenerates_body(structured_client):
    client, _ = structured_client
    created = _create_case(client)

    changed = dict(STRUCTURE)
    changed["semantics"] = {**STRUCTURE["semantics"], "pivot_symptom": "Disnea en reposo"}
    updated = client.put(f"/api/cases/{created['id']}", json={"structured": changed}).json()

    assert "Disnea en reposo" in updated["body"]
    assert "Tos con hemoptisis" not in updated["body"]


def test_template_endpoint_returns_every_section(structured_client):
    client, _ = structured_client
    template = client.get("/api/cases/template").json()["structured"]
    assert "practical_script" in template
    assert template["identification"]["case_code"] == ""


def test_student_cannot_read_the_template(structured_client):
    client, current = structured_client
    current["role"] = "estudiante"
    current["id"] = 2
    assert client.get("/api/cases/template").status_code == 403
