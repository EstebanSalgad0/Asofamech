import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Case, MedicalImage, SCTTest, User
from app.routers import cases


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
def cases_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_make_user())
        db.commit()

    app = FastAPI()
    app.include_router(cases.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user()

    with TestClient(app) as client:
        yield client, SessionLocal

    Base.metadata.drop_all(bind=engine)


def test_create_case_rejects_missing_image_id(cases_client):
    client, SessionLocal = cases_client

    response = client.post(
        "/api/cases",
        json={
            "title": "Caso con imagen inexistente",
            "description": "Resumen",
            "body": "Cuerpo",
            "image_id": 999,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Imagen histopatológica no encontrada: ID 999"
    with SessionLocal() as db:
        assert db.query(Case).count() == 0


def test_create_case_rejects_missing_sct_test_id(cases_client):
    client, SessionLocal = cases_client

    response = client.post(
        "/api/cases",
        json={
            "title": "Caso con SCT inexistente",
            "description": "Resumen",
            "body": "Cuerpo",
            "sct_test_id": 999,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Test SCT no encontrado: ID 999"
    with SessionLocal() as db:
        assert db.query(Case).count() == 0


def test_create_case_accepts_existing_related_resources(cases_client):
    client, SessionLocal = cases_client

    with SessionLocal() as db:
        image = MedicalImage(
            filename="image.png",
            original_filename="image.png",
            title="Imagen docente",
            file_type="png",
            file_path="uploads/medical_images/image.png",
            uploaded_by=1,
            is_active=True,
        )
        sct_test = SCTTest(
            name="SCT docente",
            difficulty="pregrado",
            focus="medicina interna",
            num_items=0,
            items_json=[],
            is_active=True,
        )
        db.add_all([image, sct_test])
        db.commit()
        db.refresh(image)
        db.refresh(sct_test)
        image_id = image.id
        sct_test_id = sct_test.id

    response = client.post(
        "/api/cases",
        json={
            "title": "Caso valido",
            "description": "Resumen",
            "body": "Cuerpo",
            "image_id": image_id,
            "sct_test_id": sct_test_id,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["image_id"] == image_id
    assert payload["sct_test_id"] == sct_test_id
