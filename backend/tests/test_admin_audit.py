import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import AuditLog, User
from app.routers import admin


def _admin_user() -> User:
    return User(
        id=1,
        email="admin@example.com",
        name="Admin",
        password_hash="hash",
        role="administrador",
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def admin_audit_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_admin_user())
        db.commit()

    app = FastAPI()
    app.include_router(admin.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _admin_user

    with TestClient(app) as client:
        yield client, SessionLocal

    Base.metadata.drop_all(bind=engine)


def test_admin_user_creation_writes_audit_log(admin_audit_client):
    client, SessionLocal = admin_audit_client

    response = client.post(
        "/api/admin/users",
        json={
            "name": "Estudiante Nuevo",
            "email": "nuevo@example.com",
            "password": "clave123",
            "role": "estudiante",
            "account_status": "approved",
            "notify_email": False,
        },
    )

    assert response.status_code == 200
    with SessionLocal() as db:
        log = db.query(AuditLog).filter(AuditLog.action == "admin.user.create").one()

    assert log.actor_email == "admin@example.com"
    assert log.target_type == "user"
    assert log.details["user"]["email"] == "nuevo@example.com"
    assert "password" not in log.details


def test_admin_can_list_audit_logs(admin_audit_client):
    client, _ = admin_audit_client
    client.post(
        "/api/admin/users",
        json={
            "name": "Docente Nuevo",
            "email": "docente@example.com",
            "password": "clave123",
            "role": "docente",
            "account_status": "pending",
            "notify_email": False,
        },
    )

    response = client.get("/api/admin/audit-logs?target_type=user")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"][0]["action"] == "admin.user.create"
    assert payload["items"][0]["actor_email"] == "admin@example.com"


def test_deleting_user_preserves_prior_audit_logs(admin_audit_client):
    client, SessionLocal = admin_audit_client
    with SessionLocal() as db:
        user = User(
            id=2,
            email="docente@example.com",
            name="Docente",
            password_hash="hash",
            role="docente",
            is_active=True,
            account_status="approved",
        )
        db.add(user)
        db.flush()
        db.add(
            AuditLog(
                actor_user_id=user.id,
                actor_email=user.email,
                actor_role=user.role,
                action="admin.user.update",
                target_type="user",
                target_id=str(user.id),
                summary="Evento previo",
                details={},
            )
        )
        db.commit()

    response = client.delete("/api/admin/users/2")

    assert response.status_code == 200
    with SessionLocal() as db:
        previous_log = db.query(AuditLog).filter(AuditLog.action == "admin.user.update").one()
        delete_log = db.query(AuditLog).filter(AuditLog.action == "admin.user.delete").one()

    assert previous_log.actor_user_id is None
    assert previous_log.actor_email == "docente@example.com"
    assert delete_log.target_id == "2"
