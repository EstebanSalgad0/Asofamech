"""Importación de un caso clínico desde un documento Word.

Se prueban dos cosas distintas:
  - Que el documento llegue al modelo con sus tablas intactas: si el Practical
    Script se aplana, la importación produce un caso con la matriz destruida y
    nadie lo nota hasta que un estudiante lo abre.
  - Que la propuesta se normalice y NUNCA se guarde sola.

La respuesta del modelo se simula: aquí se verifica la tubería, no la calidad
de la generación.
"""
import io
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Case, User
from app.rag_file_loader import extract_docx_images, extract_text_from_bytes
from app.routers import cases

# Documento real entregado por la coordinación académica. Los tests que lo
# necesitan se saltan si no está disponible, para que la suite siga corriendo
# en una máquina limpia.
SAMPLE_DOCX = Path(r"C:\Users\salga\OneDrive\Escritorio\ASOFAMECH 23\caso 2.docx")
requires_sample = pytest.mark.skipif(
    not SAMPLE_DOCX.exists(), reason="El .docx de ejemplo no está disponible"
)

MODEL_RESPONSE = json.dumps(
    {
        "title": "Neumonía adquirida en la comunidad en paciente adulta mayor",
        "description": "Mujer de 64 años con fiebre, tos productiva y disnea progresiva de 3 días.",
        "topic": "Neumonía adquirida en la comunidad",
        "difficulty": "pregrado",
        "inferred": ["semantics.pivot_symptom", "semantics.qualifiers.temporality"],
        "notes": "El documento no trae informe anatomopatológico ni banco de evaluación.",
        "structured": {
            "identification": {"summary": "Neumonía lobar derecha en adulta mayor diabética."},
            "narratives": {
                "patient_first_person": "Recuerdo que hace unos días comencé a sentirme más cansada.",
                "clinical_presentation": "Paciente de 64 años con cuadro de 3 días de fiebre y tos.",
            },
            "semantics": {
                "pivot_symptom": "Disnea progresiva",
                "key_terms": ["Fiebre", "Tos productiva", "Disnea progresiva"],
                "qualifiers": {"temporality": ["3 días de evolución"], "evolution": ["progresiva"]},
            },
            "clinical": {
                "patient_profile": {"age": "64 años", "sex": "Femenino", "background": "Diabetes, HTA, obesidad"},
                "chief_complaint": "Fiebre y dificultad respiratoria.",
                "medications": ["Losartán 50 mg/día"],
            },
            "physical_exam": {
                "vital_signs": {"temperature": "38.7 °C", "heart_rate": "105 lpm", "oxygen_saturation": "90%"},
                "systems": [
                    {"name": "Sistema respiratorio", "findings": "Matidez basal derecha, soplo tubario."}
                ],
            },
            "workup": {
                "lab_panels": [
                    {
                        "name": "Hemograma",
                        "rows": [{"parameter": "Leucocitos", "result": "15.800 /mm³", "reference": "", "interpretation": ""}],
                    }
                ],
                "imaging": [{"study": "Radiografía de tórax", "report": "Opacidad alveolar en lóbulo inferior derecho."}],
            },
            "course": {"treatment_plan": "Ceftriaxona + Azitromicina IV."},
            "diagnoses": {
                "primary": {"name": "Neumonía adquirida en la comunidad", "sctid": ""},
                "differentials": [
                    {"name": "Exacerbación de EPOC", "sctid": ""},
                    {"name": "Insuficiencia cardíaca congestiva", "sctid": ""},
                ],
            },
            "practical_script": {
                "columns": ["Neumonía bacteriana lobar derecha", "Exacerbación de EPOC"],
                "rows": [
                    {
                        "finding": "Síntomas",
                        "ratings": [
                            {"value": 2, "rationale": "Síntomas típicos de neumonía lobar"},
                            {"value": -1, "rationale": "No explican totalmente nueva disnea"},
                        ],
                    }
                ],
            },
            "pedagogy": {"objectives": [{"area": "", "text": "Signos del síndrome de consolidación."}]},
        },
    }
)


def _make_user(role: str = "docente") -> User:
    return User(
        id=1,
        email=f"{role}@example.com",
        name=f"Usuario {role}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def import_client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_make_user("docente"))
        db.add(User(id=2, email="e@example.com", name="Est", password_hash="h",
                    role="estudiante", is_active=True, account_status="approved"))
        db.commit()

    captured: dict = {}

    async def fake_chat_completion(client, settings, messages, **kwargs):
        # Se guarda lo que ve el modelo para poder afirmar que las tablas
        # llegaron con su rejilla.
        captured["prompt"] = messages[-1]["content"]
        return MODEL_RESPONSE

    class FakeSettings:
        provider = "groq"
        model = "llama-3.3-70b"
        timeout = 60.0

    monkeypatch.setattr("app.case_import.chat_completion", fake_chat_completion)
    monkeypatch.setattr("app.case_import.resolve_llm_settings", lambda db: FakeSettings())

    current = {"role": "docente"}

    app = FastAPI()
    app.include_router(cases.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user(current["role"])

    with TestClient(app) as client:
        yield client, SessionLocal, captured, current

    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------- extracción

@requires_sample
def test_word_tables_reach_the_model_as_tables():
    """La tabla SCT debe conservar filas y columnas, no aplanarse."""
    text, _ = extract_text_from_bytes(SAMPLE_DOCX.read_bytes(), "caso 2.docx")

    assert "| --- |" in text, "las tablas se están aplanando"
    header = "| Dato clínico | Hallazgos en la paciente | Neumonía bacteriana lobar derecha |"
    assert header in text
    # Una fila completa se mantiene en una sola línea, con su valor por columna.
    fila = next(line for line in text.splitlines() if line.startswith("| Síntomas |"))
    assert fila.count("|") == 8  # 7 columnas
    assert "+2: Síntomas típicos de neumonía lobar" in fila
    assert "-1: No explican totalmente nueva disnea" in fila


@requires_sample
def test_embedded_images_keep_document_order():
    images = extract_docx_images(SAMPLE_DOCX.read_bytes())
    assert [i["filename"] for i in images] == ["image1.png", "image2.jpeg", "image3.png"]
    assert images[1]["content_type"] == "image/jpeg"
    assert all(i["data"] for i in images)


def test_metafile_images_are_skipped():
    """Word incrusta .emf/.wmf que ningún navegador puede mostrar."""
    from app.rag_file_loader import DOCX_IMAGE_EXTENSIONS

    assert ".emf" not in DOCX_IMAGE_EXTENSIONS
    assert ".wmf" not in DOCX_IMAGE_EXTENSIONS


def test_corrupt_file_does_not_break_image_extraction():
    assert extract_docx_images(b"esto no es un zip") == []


# ---------------------------------------------------------------- importación

@requires_sample
def test_import_returns_a_draft_without_saving(import_client):
    client, SessionLocal, captured, _ = import_client

    response = client.post(
        "/api/cases/import",
        files={"file": ("caso 2.docx", SAMPLE_DOCX.read_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200, response.text
    draft = response.json()

    assert draft["title"].startswith("Neumonía adquirida")
    assert draft["difficulty"] == "pregrado"
    assert draft["structured"]["semantics"]["pivot_symptom"] == "Disnea progresiva"
    assert len(draft["structured"]["practical_script"]["columns"]) == 2

    # La tabla llegó al modelo con su rejilla intacta.
    assert "| --- |" in captured["prompt"]

    # Nada se persistió: el docente todavía no ha revisado la propuesta.
    with SessionLocal() as db:
        assert db.query(Case).count() == 0


@requires_sample
def test_import_carries_the_document_images(import_client):
    client, _, _, _ = import_client
    response = client.post(
        "/api/cases/import",
        files={"file": ("caso 2.docx", SAMPLE_DOCX.read_bytes(), "application/octet-stream")},
    )
    images = response.json()["images"]
    assert [i["filename"] for i in images] == ["image1.png", "image2.jpeg", "image3.png"]
    assert all(i["data_base64"] for i in images)


@requires_sample
def test_import_flags_what_the_document_lacked(import_client):
    client, _, _, _ = import_client
    draft = client.post(
        "/api/cases/import",
        files={"file": ("caso 2.docx", SAMPLE_DOCX.read_bytes(), "application/octet-stream")},
    ).json()

    # Lo deducido se marca como tal, no se presenta como transcripción.
    assert "semantics.pivot_symptom" in draft["inferred"]

    avisos = " ".join(draft["warnings"])
    assert "anatomopatológico" in avisos
    assert "banco de evaluación" in avisos
    assert "SNOMED" in avisos
    # Lo que sí venía en el documento no debe aparecer como faltante.
    assert "signos vitales" not in avisos.lower()
    assert "laboratorio" not in avisos.lower()


def test_sctid_is_never_invented(import_client):
    """Un código SNOMED plausible pero falso es indistinguible de uno correcto."""
    client, _, _, _ = import_client
    draft = client.post(
        "/api/cases/import",
        files={"file": ("caso.txt", io.BytesIO(b"Caso clinico. " * 40), "text/plain")},
    ).json()

    assert draft["structured"]["diagnoses"]["primary"]["sctid"] == ""
    assert all(d["sctid"] == "" for d in draft["structured"]["diagnoses"]["differentials"])


def test_short_document_is_rejected(import_client):
    client, _, _, _ = import_client
    response = client.post(
        "/api/cases/import",
        files={"file": ("nota.txt", io.BytesIO(b"Apunte suelto sin caso clinico dentro."), "text/plain")},
    )
    assert response.status_code == 422


def test_student_cannot_import_cases(import_client):
    client, _, _, current = import_client
    current["role"] = "estudiante"
    response = client.post(
        "/api/cases/import",
        files={"file": ("caso.txt", io.BytesIO(b"Caso clinico. " * 40), "text/plain")},
    )
    assert response.status_code == 403


def test_unreadable_model_output_is_reported(import_client, monkeypatch):
    client, _, _, _ = import_client

    async def chatty(*args, **kwargs):
        return "Claro, aquí tienes el caso: (no es JSON)"

    monkeypatch.setattr("app.case_import.chat_completion", chatty)
    response = client.post(
        "/api/cases/import",
        files={"file": ("caso.txt", io.BytesIO(b"Caso clinico. " * 40), "text/plain")},
    )
    assert response.status_code == 502


def test_empty_structure_from_model_is_rejected(import_client, monkeypatch):
    """Si el modelo no reconoció un caso, no se abre un editor vacío."""
    client, _, _, _ = import_client

    async def empty(*args, **kwargs):
        return json.dumps({"title": "Algo", "structured": {}})

    monkeypatch.setattr("app.case_import.chat_completion", empty)
    response = client.post(
        "/api/cases/import",
        files={"file": ("caso.txt", io.BytesIO(b"Caso clinico. " * 40), "text/plain")},
    )
    assert response.status_code == 422
    assert "No se reconoció un caso" in response.json()["detail"]
