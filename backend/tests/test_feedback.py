"""Pruebas para el módulo de feedback de usabilidad."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import PERM_VIEW_FEEDBACK, get_current_user, user_has_permission
from app.db import Base, get_db
from app.models import User
from app.routers import feedback


def _user(user_id: int, role: str) -> User:
    return User(
        id=user_id,
        email=f"{role}-{user_id}@example.com",
        name=f"Usuario {role}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


VALID_PAYLOAD = {
    "nav_clarity": 4,
    "viewer_ease": 3,
    "roi_ease": 3,
    "ai_clarity": 5,
    "chatbot_utility": 4,
    "sct_utility": 4,
    "observations": "La navegación es bastante intuitiva.",
}


@pytest.fixture
def feedback_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(feedback.router)

    current = {"user": _user(1, "estudiante")}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    with TestClient(app) as client:
        yield client, app, current

    Base.metadata.drop_all(bind=engine)


# ── Permisos RBAC ──────────────────────────────────────────────────────────

def test_student_does_not_have_view_feedback_permission():
    student = _user(1, "estudiante")
    assert not user_has_permission(student, PERM_VIEW_FEEDBACK)


def test_teacher_has_view_feedback_permission():
    teacher = _user(2, "docente")
    assert user_has_permission(teacher, PERM_VIEW_FEEDBACK)


def test_admin_has_view_feedback_permission():
    admin = _user(3, "administrador")
    assert user_has_permission(admin, PERM_VIEW_FEEDBACK)


# ── Envío de feedback ──────────────────────────────────────────────────────

def test_submit_feedback_creates_record(feedback_client):
    client, _, _ = feedback_client

    response = client.post("/api/feedback", json=VALID_PAYLOAD)

    assert response.status_code == 200
    data = response.json()
    assert data["nav_clarity"] == 4
    assert data["ai_clarity"] == 5
    assert data["observations"] == "La navegación es bastante intuitiva."
    assert data["role_at_submission"] == "estudiante"


def test_submit_feedback_upserts_existing(feedback_client):
    client, _, _ = feedback_client

    client.post("/api/feedback", json=VALID_PAYLOAD)
    updated = {**VALID_PAYLOAD, "nav_clarity": 2, "observations": "Actualizado"}
    response = client.post("/api/feedback", json=updated)

    assert response.status_code == 200
    data = response.json()
    assert data["nav_clarity"] == 2
    assert data["observations"] == "Actualizado"


def test_submit_feedback_requires_auth(feedback_client):
    _, app, _ = feedback_client
    app.dependency_overrides.pop(get_current_user)

    with TestClient(app) as anon:
        response = anon.post("/api/feedback", json=VALID_PAYLOAD)

    assert response.status_code == 401


def test_submit_feedback_rejects_invalid_rating(feedback_client):
    client, _, _ = feedback_client
    bad_payload = {**VALID_PAYLOAD, "nav_clarity": 6}

    response = client.post("/api/feedback", json=bad_payload)

    assert response.status_code == 422


def test_submit_feedback_rejects_zero_rating(feedback_client):
    client, _, _ = feedback_client
    bad_payload = {**VALID_PAYLOAD, "sct_utility": 0}

    response = client.post("/api/feedback", json=bad_payload)

    assert response.status_code == 422


# ── Consulta propia ────────────────────────────────────────────────────────

def test_get_my_feedback_returns_null_before_submission(feedback_client):
    client, _, _ = feedback_client

    response = client.get("/api/feedback/my")

    assert response.status_code == 200
    assert response.json() is None


def test_get_my_feedback_returns_submission(feedback_client):
    client, _, _ = feedback_client

    client.post("/api/feedback", json=VALID_PAYLOAD)
    response = client.get("/api/feedback/my")

    assert response.status_code == 200
    data = response.json()
    assert data["nav_clarity"] == 4


# ── Resumen para docente/admin ─────────────────────────────────────────────

def test_student_cannot_access_summary(feedback_client):
    client, _, _ = feedback_client

    response = client.get("/api/feedback/summary")

    assert response.status_code == 403


def test_teacher_can_access_summary(feedback_client):
    client, _, current = feedback_client
    current["user"] = _user(2, "docente")

    response = client.get("/api/feedback/summary")

    assert response.status_code == 200
    data = response.json()
    assert "total_responses" in data
    assert "averages" in data
    assert "by_role" in data
    assert "recent_observations" in data


def test_summary_aggregates_feedback_correctly(feedback_client):
    client, _, current = feedback_client

    # Estudiante envía feedback
    current["user"] = _user(1, "estudiante")
    client.post("/api/feedback", json=VALID_PAYLOAD)

    # Docente consulta resumen
    current["user"] = _user(2, "docente")
    response = client.get("/api/feedback/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_responses"] == 1
    assert data["averages"]["nav_clarity"] == 4.0
    assert "estudiante" in data["by_role"]
    assert data["recent_observations"] == ["La navegación es bastante intuitiva."]


def test_responses_endpoint_anonymizes_user(feedback_client):
    client, _, current = feedback_client

    current["user"] = _user(1, "estudiante")
    client.post("/api/feedback", json=VALID_PAYLOAD)

    current["user"] = _user(2, "docente")
    response = client.get("/api/feedback/responses")

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    item = items[0]
    # Solo tiene rol, no nombre ni email
    assert "role" in item
    assert "user_id" not in item
    assert "email" not in item
    assert "name" not in item


def test_student_cannot_access_responses(feedback_client):
    client, _, _ = feedback_client

    response = client.get("/api/feedback/responses")

    assert response.status_code == 403
