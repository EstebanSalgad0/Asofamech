import os
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import (
    ChatLog,
    HeatmapJob,
    HistopathologySession,
    MedicalImage,
    SCTAttempt,
    SCTTest,
    User,
)
from app.routers import history


def _make_user(user_id: int, role: str = "estudiante") -> User:
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
def history_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with SessionLocal() as db:
        student_a = _make_user(1)
        student_b = _make_user(2)
        admin = _make_user(3, role="administrador")
        db.add_all([student_a, student_b, admin])
        db.add_all(
            [
                MedicalImage(
                    id=1,
                    filename="slide-a.svs",
                    original_filename="slide-a.svs",
                    title="Lamina A",
                    file_type="svs",
                    file_path="uploads/slide-a.svs",
                    uploaded_by=1,
                ),
                MedicalImage(
                    id=2,
                    filename="slide-b.svs",
                    original_filename="slide-b.svs",
                    title="Lamina B",
                    file_type="svs",
                    file_path="uploads/slide-b.svs",
                    uploaded_by=2,
                ),
            ]
        )
        db.add(
            SCTTest(
                id=1,
                name="SCT fiebre",
                difficulty="pregrado",
                focus="fiebre",
                num_items=1,
                items_json=[{"id": 1, "correct_answer": 1}],
            )
        )
        db.flush()
        db.add_all(
            [
                HistopathologySession(
                    trace_id="trace-a",
                    user_id=1,
                    image_id=1,
                    analyzed_at=now,
                    roi_1={"x": 0, "y": 0, "width": 100, "height": 100},
                    roi_2={"x": 10, "y": 10, "width": 80, "height": 80},
                    status="clasificado",
                    clase="no_metastasico",
                    confidence=0.9,
                ),
                HistopathologySession(
                    trace_id="trace-b",
                    user_id=2,
                    image_id=2,
                    analyzed_at=now - timedelta(minutes=5),
                    roi_1={"x": 0, "y": 0, "width": 100, "height": 100},
                    roi_2={"x": 10, "y": 10, "width": 80, "height": 80},
                    status="clasificado",
                    clase="metastasico",
                    confidence=0.8,
                ),
                SCTAttempt(
                    test_id=1,
                    user_id=1,
                    answers_json=[{"item_id": 1, "selected_answer": 1}],
                    score=1.0,
                    correct_count=1,
                    total_items=1,
                    completed_at=now,
                ),
                SCTAttempt(
                    test_id=1,
                    user_id=2,
                    answers_json=[{"item_id": 1, "selected_answer": 0}],
                    score=0.0,
                    correct_count=0,
                    total_items=1,
                    completed_at=now - timedelta(minutes=4),
                ),
                ChatLog(
                    user_id="1",
                    question="Pregunta de usuario uno",
                    answer="Respuesta educativa uno",
                    rag_sources=[],
                    created_at=now,
                ),
                ChatLog(
                    user_id="2",
                    question="Pregunta de usuario dos",
                    answer="Respuesta educativa dos",
                    rag_sources=[{"chunk_id": 22}],
                    created_at=now - timedelta(minutes=3),
                ),
                HeatmapJob(
                    job_id="job-a",
                    trace_id="heat-a",
                    user_id=1,
                    status="running",
                    progress=0.5,
                    processed_tiles=2,
                    total_tiles=4,
                    created_at=now,
                    request_json={"image_id": 1},
                    worker_limit=1,
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(history.router)
    current = {"user": _make_user(1)}

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current["user"]

    with TemporaryDirectory() as tmp, patch.dict(os.environ, {"HISTO_HEATMAP_DIR": tmp}):
        with TestClient(app) as client:
            yield client, app, current

    Base.metadata.drop_all(bind=engine)


def test_my_history_is_scoped_to_current_user(history_client):
    client, _, _ = history_client

    response = client.get("/api/history/me")

    assert response.status_code == 200
    payload = response.json()
    assert [item["trace_id"] for item in payload["analyses"]] == ["trace-a"]
    assert [item["question"] for item in payload["conversations"]] == ["Pregunta de usuario uno"]
    assert [item["correct_count"] for item in payload["sct_attempts"]] == [1]
    assert payload["heatmaps"][0]["job_id"] == "job-a"


def test_history_requires_jwt_without_override(history_client):
    _, app, _ = history_client
    app.dependency_overrides.pop(get_current_user)

    with TestClient(app) as anonymous_client:
        response = anonymous_client.get("/api/history/me")

    assert response.status_code == 401


def test_student_cannot_open_admin_activity(history_client):
    client, _, _ = history_client

    response = client.get("/api/history/admin/activity")

    assert response.status_code == 403


def test_admin_activity_can_filter_by_student(history_client):
    client, _, current = history_client
    current["user"] = _make_user(3, role="administrador")

    response = client.get("/api/history/admin/activity?user_id=2")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert {item["user"]["id"] for item in items if item.get("user")} == {2}
    assert {item["type"] for item in items} >= {"roi_analysis", "sct_attempt", "conversation"}
