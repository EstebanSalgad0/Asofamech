"""Revisor de informes por rubrica.

El foco de estos tests es la regla que sostiene todo el modulo: la nota que
genera el modelo NO llega al estudiante hasta que un docente la libera. Se
verifica en la API, no en la interfaz, porque es ahi donde tiene que sostenerse.

El proveedor LLM se sustituye por una respuesta fija: lo que se prueba es el
flujo y la normalizacion, no la calidad de la generacion.
"""
import io
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Rubric, User
from app.routers import reports


RUBRIC_CRITERIA = [
    {
        "name": "Lenguaje médico",
        "description": "Terminología clínica precisa.",
        "levels": [
            {"label": "Adecuado", "score": 3, "descriptor": "Preciso y formal."},
            {"label": "Parcial", "score": 2, "descriptor": "Algunas imprecisiones."},
            {"label": "Insuficiente", "score": 1, "descriptor": "Coloquial."},
        ],
    },
    {
        "name": "Síntoma pivote",
        "description": "Identifica el síntoma central.",
        "levels": [
            {"label": "Adecuado", "score": 3, "descriptor": "Claro y pertinente."},
            {"label": "Parcial", "score": 2, "descriptor": "Poco jerarquizado."},
            {"label": "Insuficiente", "score": 1, "descriptor": "Ausente."},
        ],
    },
]

MODEL_RESPONSE = json.dumps(
    {
        "criteria": [
            {
                "name": "Lenguaje médico",
                "score": 3,
                "level": "Adecuado",
                "justification": "Usa terminología precisa.",
                "evidence": "disnea progresiva en reposo",
            },
            {
                "name": "Síntoma pivote",
                "score": 2,
                "level": "Parcial",
                "justification": "Lo menciona pero no lo jerarquiza.",
                "evidence": "",
            },
        ],
        "summary": "Informe correcto con margen de mejora.",
        "strengths": ["Terminología adecuada"],
        "improvements": ["Jerarquizar el síntoma pivote"],
    }
)


def _make_user(role: str, user_id: int) -> User:
    return User(
        id=user_id,
        email=f"{role}{user_id}@example.com",
        name=f"Usuario {role}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def reports_client(monkeypatch, tmp_path):
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
        db.add(_make_user("estudiante", 3))
        db.add(
            Rubric(
                id=1,
                title="Script de evaluación",
                criteria_json=RUBRIC_CRITERIA,
                bands_json=[
                    {"label": "Adecuado", "min": 5, "max": 6},
                    {"label": "Parcial", "min": 3, "max": 4},
                ],
                max_score=6,
                status="published",
                is_active=True,
            )
        )
        db.add(
            Rubric(
                id=2,
                title="Formato y presentación",
                criteria_json=RUBRIC_CRITERIA,
                bands_json=[{"label": "Adecuado", "min": 5, "max": 6}],
                max_score=6,
                status="published",
                is_active=True,
            )
        )
        db.commit()

    # Los archivos de las entregas no deben ensuciar el repo durante los tests.
    monkeypatch.setattr(reports, "REPORT_DIR", str(tmp_path))

    async def fake_chat_completion(*args, **kwargs):
        return MODEL_RESPONSE

    class FakeSettings:
        provider = "groq"
        model = "llama-3.3-70b"
        timeout = 60.0

    monkeypatch.setattr("app.rubric_review.chat_completion", fake_chat_completion)
    monkeypatch.setattr("app.rubric_review.resolve_llm_settings", lambda db: FakeSettings())

    current = {"role": "docente", "id": 1}

    app = FastAPI()
    app.include_router(reports.router)

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


def _upload(client, text=b"Paciente con disnea progresiva en reposo y tos hemoptoica de tres meses.", rubric_ids="1"):
    return client.post(
        "/api/reports/submissions",
        files={"file": ("informe.txt", io.BytesIO(text), "text/plain")},
        data={"rubric_ids": rubric_ids},
    )


def test_submission_is_scored_against_the_rubric(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2

    response = _upload(client)
    assert response.status_code == 201, response.text
    body = response.json()[0]
    assert body["status"] == "evaluated"
    # El estudiante no recibe la nota todavia, pero si sabe que ya fue revisado.
    assert body["evaluation"] is None
    assert body["evaluation_pending_release"] is True


def test_teacher_sees_the_score_before_releasing_it(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    _upload(client)

    current["role"] = "docente"
    current["id"] = 1
    listed = client.get("/api/reports/submissions").json()
    assert len(listed) == 1
    evaluation = listed[0]["evaluation"]
    assert evaluation["total_score"] == 5
    assert evaluation["max_score"] == 6
    assert evaluation["band"] == "Adecuado"
    assert evaluation["released"] is False
    assert listed[0]["student_email"] == "estudiante2@example.com"


def test_submission_against_several_rubrics_at_once(reports_client):
    """El pedido central: un mismo archivo, varias rubricas, evaluaciones independientes."""
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2

    response = _upload(client, rubric_ids="1,2")
    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body) == 2
    assert {item["rubric_id"] for item in body} == {1, 2}
    # Ambas entregas nacen del mismo envio: comparten batch_id.
    assert body[0]["batch_id"] == body[1]["batch_id"]
    assert all(item["status"] == "evaluated" for item in body)


def test_evaluations_from_the_same_batch_are_released_independently(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submissions = _upload(client, rubric_ids="1,2").json()
    first_id, second_id = submissions[0]["id"], submissions[1]["id"]

    current["role"] = "docente"
    current["id"] = 1
    client.patch(f"/api/reports/submissions/{first_id}/release", json={"released": True})

    current["role"] = "estudiante"
    current["id"] = 2
    mine = {item["id"]: item for item in client.get("/api/reports/submissions/mine").json()}
    assert mine[first_id]["evaluation"] is not None
    assert mine[second_id]["evaluation"] is None
    assert mine[second_id]["evaluation_pending_release"] is True


def test_deleting_one_evaluation_of_a_batch_keeps_the_shared_file(reports_client):
    """Las N filas de un envio comparten el archivo fisico: borrar una no debe romper las otras."""
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submissions = _upload(client, rubric_ids="1,2").json()
    first_id, second_id = submissions[0]["id"], submissions[1]["id"]

    assert client.delete(f"/api/reports/submissions/{first_id}").status_code == 204
    # La segunda entrega del mismo batch sigue pudiendo descargar su archivo.
    assert client.get(f"/api/reports/submissions/{second_id}/file").status_code == 200


def test_a_missing_rubric_in_a_multi_submission_blocks_the_whole_upload(reports_client):
    """Todo o nada: si una rubrica del lote no es valida, no se crea ninguna entrega."""
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2

    response = _upload(client, rubric_ids="1,999")
    assert response.status_code == 404
    assert client.get("/api/reports/submissions/mine").json() == []


def test_too_many_rubrics_in_one_submission_is_rejected(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    too_many = ",".join(str(n) for n in range(1, reports.MAX_RUBRICS_PER_SUBMISSION + 2))
    response = _upload(client, rubric_ids=too_many)
    assert response.status_code == 422


def test_student_receives_the_score_only_after_release(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    released = client.patch(
        f"/api/reports/submissions/{submission_id}/release",
        json={"released": True, "teacher_note": "Buen trabajo."},
    )
    assert released.status_code == 200

    current["role"] = "estudiante"
    current["id"] = 2
    mine = client.get("/api/reports/submissions/mine").json()
    assert mine[0]["evaluation"]["total_score"] == 5
    assert mine[0]["evaluation"]["teacher_note"] == "Buen trabajo."
    assert mine[0]["evaluation_pending_release"] is False


def test_teacher_score_overrides_and_rebands(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    result = client.patch(
        f"/api/reports/submissions/{submission_id}/release",
        json={"released": True, "teacher_score": 4},
    ).json()

    evaluation = result["evaluation"]
    assert evaluation["effective_score"] == 4
    # El puntaje del modelo se conserva para que la correccion sea trazable.
    assert evaluation["total_score"] == 5
    assert evaluation["band"] == "Parcial"


def test_teacher_score_outside_the_scale_is_rejected(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    response = client.patch(
        f"/api/reports/submissions/{submission_id}/release",
        json={"released": True, "teacher_score": 99},
    )
    assert response.status_code == 422


def test_reevaluating_withdraws_a_previous_release(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    client.patch(f"/api/reports/submissions/{submission_id}/release", json={"released": True})
    reevaluated = client.post(f"/api/reports/submissions/{submission_id}/evaluate").json()
    assert reevaluated["evaluation"]["released"] is False


def test_student_cannot_read_another_students_submission(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["id"] = 3
    assert client.get(f"/api/reports/submissions/{submission_id}").status_code == 404
    assert client.get(f"/api/reports/submissions/{submission_id}/file").status_code == 404
    assert client.get("/api/reports/submissions/mine").json() == []


def test_student_cannot_list_every_submission(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    assert client.get("/api/reports/submissions").status_code == 403


def test_student_cannot_delete_a_published_evaluation(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    client.patch(f"/api/reports/submissions/{submission_id}/release", json={"released": True})

    current["role"] = "estudiante"
    current["id"] = 2
    assert client.delete(f"/api/reports/submissions/{submission_id}").status_code == 409


def test_unsupported_format_is_rejected(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    response = client.post(
        "/api/reports/submissions",
        files={"file": ("informe.exe", io.BytesIO(b"binario"), "application/octet-stream")},
        data={"rubric_ids": "1"},
    )
    assert response.status_code == 422


def test_student_cannot_manage_rubrics(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2

    assert client.post("/api/reports/rubrics", json={"title": "x", "criteria": []}).status_code == 403
    assert client.delete("/api/reports/rubrics/1").status_code == 403


def test_student_only_sees_published_rubrics(reports_client):
    client, current = reports_client
    client.patch("/api/reports/rubrics/1/status", json={"status": "draft"})
    client.patch("/api/reports/rubrics/2/status", json={"status": "draft"})

    current["role"] = "estudiante"
    current["id"] = 2
    assert client.get("/api/reports/rubrics").json() == []
    assert client.get("/api/reports/rubrics/1").status_code == 404


def test_rubric_max_score_comes_from_its_levels(reports_client):
    client, _ = reports_client
    created = client.post(
        "/api/reports/rubrics",
        json={
            "title": "Nueva rúbrica",
            "criteria": [
                {
                    "name": "Coherencia",
                    "levels": [
                        {"label": "Alto", "score": 4},
                        {"label": "Bajo", "score": 1},
                    ],
                }
            ],
            "status": "published",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["max_score"] == 4


def test_rubric_without_criteria_is_rejected(reports_client):
    client, _ = reports_client
    response = client.post("/api/reports/rubrics", json={"title": "Vacía", "criteria": []})
    assert response.status_code == 422


def test_a_failed_evaluation_keeps_the_submission(reports_client, monkeypatch):
    """Si el proveedor falla, la entrega se conserva para poder reintentarla."""
    client, current = reports_client

    async def broken_chat_completion(*args, **kwargs):
        raise HTTPException(status_code=502, detail="El proveedor no respondió.")

    monkeypatch.setattr("app.rubric_review.chat_completion", broken_chat_completion)

    current["role"] = "estudiante"
    current["id"] = 2
    response = _upload(client)
    assert response.status_code == 201
    body = response.json()[0]
    assert body["status"] == "failed"
    assert body["evaluation"] is None
    # El estudiante no ve el detalle tecnico del fallo del proveedor.
    assert body["error"] is None

    # El docente si lo ve, y puede reintentar cuando el proveedor vuelva.
    current["role"] = "docente"
    current["id"] = 1
    listed = client.get("/api/reports/submissions").json()
    assert "no respondió" in listed[0]["error"]

    async def working(*args, **kwargs):
        return MODEL_RESPONSE

    monkeypatch.setattr("app.rubric_review.chat_completion", working)
    retried = client.post(f"/api/reports/submissions/{body['id']}/evaluate").json()
    assert retried["status"] == "evaluated"
    assert retried["evaluation"]["total_score"] == 5


def test_student_hits_the_submission_cap(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2

    for _ in range(reports.MAX_OPEN_SUBMISSIONS_PER_RUBRIC):
        assert _upload(client).status_code == 201

    blocked = _upload(client)
    assert blocked.status_code == 429


def test_malformed_model_output_is_reported_not_crashed(reports_client, monkeypatch):
    client, current = reports_client

    async def chatty(*args, **kwargs):
        return "Claro, aquí tienes la evaluación: no es JSON."

    monkeypatch.setattr("app.rubric_review.chat_completion", chatty)

    current["role"] = "estudiante"
    current["id"] = 2
    body = _upload(client).json()[0]
    assert body["status"] == "failed"


def test_model_output_wrapped_in_markdown_is_parsed(reports_client, monkeypatch):
    """Varios modelos devuelven el JSON dentro de un bloque ```json."""
    client, current = reports_client

    async def fenced(*args, **kwargs):
        return f"```json\n{MODEL_RESPONSE}\n```"

    monkeypatch.setattr("app.rubric_review.chat_completion", fenced)

    current["role"] = "estudiante"
    current["id"] = 2
    body = _upload(client).json()[0]
    assert body["status"] == "evaluated"


# ---------------------------------------------------------- fecha de entrega

def test_rubric_closes_after_its_due_date(reports_client):
    client, current = reports_client
    past = "2020-01-01T00:00:00"
    client.patch("/api/reports/rubrics/1/status", json={"status": "published"})
    client.put("/api/reports/rubrics/1", json={"due_at": past})

    current["role"] = "estudiante"
    current["id"] = 2
    response = _upload(client)
    assert response.status_code == 409
    assert "cerró sus entregas" in response.json()["detail"]


def test_teacher_can_still_submit_after_the_due_date(reports_client):
    """El docente puede seguir probando la rúbrica aunque ya haya cerrado para estudiantes."""
    client, current = reports_client
    client.put("/api/reports/rubrics/1", json={"due_at": "2020-01-01T00:00:00"})

    response = _upload(client)  # current sigue en rol docente por defecto
    assert response.status_code == 201


def test_rubric_without_due_date_stays_open(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    assert _upload(client).status_code == 201


def test_future_due_date_still_accepts_submissions(reports_client):
    client, current = reports_client
    future = "2099-01-01T00:00:00"
    client.put("/api/reports/rubrics/1", json={"due_at": future})

    current["role"] = "estudiante"
    current["id"] = 2
    assert _upload(client).status_code == 201


def test_due_date_can_be_cleared(reports_client):
    client, current = reports_client
    client.put("/api/reports/rubrics/1", json={"due_at": "2020-01-01T00:00:00"})
    updated = client.put("/api/reports/rubrics/1", json={"due_at": None}).json()
    assert updated["due_at"] is None

    current["role"] = "estudiante"
    current["id"] = 2
    assert _upload(client).status_code == 201


def test_a_multi_rubric_submission_is_blocked_if_any_rubric_is_closed(reports_client):
    """Todo o nada: si una de las rubricas del lote ya cerro, no se crea ninguna entrega."""
    client, current = reports_client
    client.put("/api/reports/rubrics/2", json={"due_at": "2020-01-01T00:00:00"})

    current["role"] = "estudiante"
    current["id"] = 2
    response = _upload(client, rubric_ids="1,2")
    assert response.status_code == 409
    assert client.get("/api/reports/submissions/mine").json() == []


# ------------------------------------------------------------------ progreso

def test_progress_tracks_attempts_used_and_latest_score(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    _upload(client)
    _upload(client)

    current["role"] = "docente"
    current["id"] = 1
    progress = client.get("/api/reports/rubrics/1/progress").json()
    assert len(progress) == 1
    entry = progress[0]
    assert entry["user_id"] == 2
    assert entry["attempts"] == 2
    assert entry["attempts_max"] == reports.MAX_OPEN_SUBMISSIONS_PER_RUBRIC
    assert entry["latest_score"] == 5
    assert entry["latest_max_score"] == 6
    assert entry["latest_released"] is False


def test_progress_reflects_teacher_corrected_score(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    submission_id = _upload(client).json()[0]["id"]

    current["role"] = "docente"
    current["id"] = 1
    client.patch(
        f"/api/reports/submissions/{submission_id}/release",
        json={"released": True, "teacher_score": 3},
    )
    progress = client.get("/api/reports/rubrics/1/progress").json()
    assert progress[0]["latest_score"] == 3
    assert progress[0]["latest_max_score"] == 6
    assert progress[0]["latest_released"] is True


def test_progress_only_lists_students_who_submitted(reports_client):
    client, current = reports_client
    progress = client.get("/api/reports/rubrics/1/progress").json()
    assert progress == []


def test_student_cannot_see_the_progress_panel(reports_client):
    client, current = reports_client
    current["role"] = "estudiante"
    current["id"] = 2
    assert client.get("/api/reports/rubrics/1/progress").status_code == 403
