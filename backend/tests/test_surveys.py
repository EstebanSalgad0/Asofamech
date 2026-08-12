import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import (
    Survey,
    SurveyItem,
    SurveyParticipation,
    SurveyResponse,
    User,
)
from app.routers import surveys


def _make_user(user_id: int = 1, role: str = "estudiante") -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        name=f"Usuario {user_id}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def surveys_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    # Sembrar una encuesta mínima con 2 Likert obligatorios + 1 abierto opcional
    with SessionLocal() as db:
        db.add(_make_user(1, "estudiante"))
        db.add(_make_user(2, "docente"))
        db.add(_make_user(3, "estudiante"))
        survey = Survey(code="demo", title="Demo", status="open")
        db.add(survey)
        db.flush()
        db.add(SurveyItem(survey_id=survey.id, section="I", section_order=1, item_order=0, text="Q1", item_type="likert_1_5", required=True))
        db.add(SurveyItem(survey_id=survey.id, section="I", section_order=1, item_order=1, text="Q2", item_type="likert_1_5", required=True))
        db.add(SurveyItem(survey_id=survey.id, section="II", section_order=2, item_order=2, text="Comentario", item_type="open_text", required=False))
        db.commit()

    app = FastAPI()
    app.include_router(surveys.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    current = {"user_id": 1, "role": "estudiante"}

    def override_current_user():
        return _make_user(current["user_id"], current["role"])

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    with TestClient(app) as client:
        yield client, SessionLocal, current

    Base.metadata.drop_all(bind=engine)


def _item_ids(SessionLocal, survey_code="demo"):
    with SessionLocal() as db:
        survey = db.query(Survey).filter(Survey.code == survey_code).first()
        items = sorted(survey.items, key=lambda i: i.item_order)
        return [i.id for i in items]


def test_student_can_list_open_surveys(surveys_client):
    client, _, _ = surveys_client
    resp = client.get("/api/surveys")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "demo"


def test_get_survey_returns_items_and_answered_flag(surveys_client):
    client, _, _ = surveys_client
    resp = client.get("/api/surveys/demo")
    assert resp.status_code == 200
    data = resp.json()
    assert data["already_answered"] is False
    assert len(data["items"]) == 3


def test_submit_valid_response_persists_anonymously(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)

    resp = client.post(
        "/api/surveys/demo/responses",
        json={
            "answers": [
                {"item_id": ids[0], "value_int": 4},
                {"item_id": ids[1], "value_int": 5},
                {"item_id": ids[2], "value_text": "Muy útil"},
            ]
        },
    )
    assert resp.status_code == 201, resp.text

    with SessionLocal() as db:
        # Se registró la respuesta y las 3 answers
        responses = db.query(SurveyResponse).all()
        assert len(responses) == 1
        assert len(responses[0].answers) == 3
        # La respuesta NO contiene user_id (comprobación estructural)
        assert not hasattr(responses[0], "user_id") or getattr(responses[0], "user_id", None) is None
        # Participación registrada por separado
        parts = db.query(SurveyParticipation).all()
        assert len(parts) == 1
        assert parts[0].user_id == 1


def test_cannot_submit_twice(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)
    body = {
        "answers": [
            {"item_id": ids[0], "value_int": 3},
            {"item_id": ids[1], "value_int": 3},
        ]
    }
    r1 = client.post("/api/surveys/demo/responses", json=body)
    assert r1.status_code == 201
    r2 = client.post("/api/surveys/demo/responses", json=body)
    assert r2.status_code == 409
    assert "respondiste" in r2.json()["detail"].lower()


def test_get_survey_flags_answered_after_submission(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)
    client.post(
        "/api/surveys/demo/responses",
        json={"answers": [{"item_id": ids[0], "value_int": 4}, {"item_id": ids[1], "value_int": 4}]},
    )
    resp = client.get("/api/surveys/demo")
    assert resp.status_code == 200
    assert resp.json()["already_answered"] is True


def test_rejects_missing_required_likert(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)
    resp = client.post(
        "/api/surveys/demo/responses",
        json={"answers": [{"item_id": ids[0], "value_int": 4}]},
    )
    assert resp.status_code == 422


def test_rejects_out_of_range_likert(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)
    resp = client.post(
        "/api/surveys/demo/responses",
        json={"answers": [{"item_id": ids[0], "value_int": 9}, {"item_id": ids[1], "value_int": 3}]},
    )
    assert resp.status_code == 422


def test_rejects_submission_to_archived_survey(surveys_client):
    client, SessionLocal, _ = surveys_client
    ids = _item_ids(SessionLocal)
    with SessionLocal() as db:
        s = db.query(Survey).filter(Survey.code == "demo").first()
        s.status = "archived"
        db.commit()
    resp = client.post(
        "/api/surveys/demo/responses",
        json={"answers": [{"item_id": ids[0], "value_int": 3}, {"item_id": ids[1], "value_int": 3}]},
    )
    assert resp.status_code == 409


def test_student_cannot_view_summary(surveys_client):
    client, _, current = surveys_client
    current["user_id"] = 1
    current["role"] = "estudiante"
    resp = client.get("/api/surveys/demo/summary")
    assert resp.status_code == 403


def test_teacher_can_view_summary_and_open_answers(surveys_client):
    client, SessionLocal, current = surveys_client
    ids = _item_ids(SessionLocal)

    # Dos estudiantes responden
    for uid, vals in [(1, (5, 4, "Excelente")), (3, (3, 3, "Regular"))]:
        current["user_id"] = uid
        current["role"] = "estudiante"
        client.post(
            "/api/surveys/demo/responses",
            json={
                "answers": [
                    {"item_id": ids[0], "value_int": vals[0]},
                    {"item_id": ids[1], "value_int": vals[1]},
                    {"item_id": ids[2], "value_text": vals[2]},
                ]
            },
        )

    current["user_id"] = 2
    current["role"] = "docente"
    resp = client.get("/api/surveys/demo/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_responses"] == 2
    assert data["global_average"] is not None
    # Los 2 items Likert deben tener n=2
    likert = [i for i in data["item_stats"] if i["item_type"] == "likert_1_5"]
    assert all(i["n"] == 2 for i in likert)

    resp2 = client.get("/api/surveys/demo/open-answers")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert set(data2[0]["answers"]) == {"Excelente", "Regular"}


def test_teacher_can_archive_and_reopen(surveys_client):
    client, _, current = surveys_client
    current["user_id"] = 2
    current["role"] = "docente"
    resp = client.patch("/api/surveys/demo/status", json={"status": "archived"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"

    resp2 = client.patch("/api/surveys/demo/status", json={"status": "open"})
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "open"


def test_csv_export_excludes_user_id(surveys_client):
    client, SessionLocal, current = surveys_client
    ids = _item_ids(SessionLocal)
    client.post(
        "/api/surveys/demo/responses",
        json={
            "answers": [
                {"item_id": ids[0], "value_int": 5},
                {"item_id": ids[1], "value_int": 4},
                {"item_id": ids[2], "value_text": "Muy bueno"},
            ]
        },
    )
    current["user_id"] = 2
    current["role"] = "docente"
    resp = client.get("/api/surveys/demo/export.csv")
    assert resp.status_code == 200
    body = resp.text
    assert "user_id" not in body.lower().splitlines()[0]
    assert "Muy bueno" in body
