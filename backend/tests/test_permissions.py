import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import (
    PERM_MANAGE_AI_CONFIG,
    PERM_MANAGE_CASES,
    PERM_MANAGE_IMAGES,
    PERM_MANAGE_RAG,
    PERM_MANAGE_USERS,
    get_current_user,
    user_has_permission,
)
from app.db import Base, get_db
from app.models import User
from app.routers import admin, cases, medical_images, sct


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


@pytest.fixture
def permission_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(cases.router)
    app.include_router(sct.router)
    app.include_router(admin.router)
    app.include_router(medical_images.router)

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


def test_role_permission_matrix_is_consistent():
    student = _user(1, "estudiante")
    teacher = _user(2, "docente")
    admin_user = _user(3, "administrador")

    assert not user_has_permission(student, PERM_MANAGE_CASES)
    assert not user_has_permission(student, PERM_MANAGE_IMAGES)
    assert user_has_permission(teacher, PERM_MANAGE_CASES)
    assert user_has_permission(teacher, PERM_MANAGE_RAG)
    assert user_has_permission(admin_user, PERM_MANAGE_USERS)
    assert user_has_permission(admin_user, PERM_MANAGE_AI_CONFIG)


def test_private_routes_require_jwt_without_override(permission_client):
    _, app, _ = permission_client
    app.dependency_overrides.pop(get_current_user)

    with TestClient(app) as anonymous_client:
        responses = [
            anonymous_client.get("/api/sct/example"),
            anonymous_client.get("/api/medical-images/view/1"),
            anonymous_client.get("/api/medical-images/dzi/1.dzi"),
            anonymous_client.post("/api/cases", json={"title": "Caso", "description": "Desc", "body": "Body"}),
        ]

    assert [response.status_code for response in responses] == [401, 401, 401, 401]


def test_student_is_blocked_from_sensitive_routes(permission_client):
    client, _, current = permission_client
    current["user"] = _user(1, "estudiante")

    responses = [
        client.post("/api/cases", json={"title": "Caso", "description": "Desc", "body": "Body"}),
        client.delete("/api/sct/1"),
        client.post(
            "/api/medical-images/upload",
            data={"title": "Carga no autorizada"},
            files={"file": ("slide.png", b"not-an-image", "image/png")},
        ),
        client.post(
            "/api/medical-images/import-local/camelyon17",
            data={"filename": "patient_001_node_1.tif"},
        ),
        client.delete("/api/medical-images/1"),
        client.get("/api/medical-images/local/camelyon17"),
        client.get("/api/admin/users"),
        client.get("/api/admin/ai-config"),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 403, 403, 403, 403]


def test_teacher_can_manage_educational_content_but_not_admin_users(permission_client):
    client, _, current = permission_client
    current["user"] = _user(2, "docente")

    create_case = client.post(
        "/api/cases",
        json={"title": "Caso docente", "description": "Desc", "body": "Body"},
    )
    admin_users = client.get("/api/admin/users")

    assert create_case.status_code in (200, 201)
    assert admin_users.status_code == 403


def test_admin_can_reach_admin_config(permission_client):
    client, _, current = permission_client
    current["user"] = _user(3, "administrador")

    response = client.get("/api/admin/ai-config")

    assert response.status_code == 200
    assert "items" in response.json()
