import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.llm_service import SECRET_PLACEHOLDER
from app.models import AIConfiguration, User
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
def admin_client():
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


def _item(payload: dict, key: str) -> dict:
    return next(entry for entry in payload["items"] if entry["key"] == key)


def _put(client, key: str, value: str, value_type: str = "string"):
    return client.put(
        "/api/admin/ai-config",
        json={"items": [{"key": key, "value": value, "value_type": value_type}]},
    )


def _stored(SessionLocal, key: str):
    with SessionLocal() as db:
        row = db.query(AIConfiguration).filter(AIConfiguration.key == key).first()
        return row.value if row else None


# ── secretos ─────────────────────────────────────────────────────────────────

def test_api_key_is_never_returned_in_clear(admin_client):
    client, SessionLocal = admin_client

    assert _put(client, "llm_api_key", "gsk_secreto_real", "password").status_code == 200

    payload = client.get("/api/admin/ai-config").json()
    item = _item(payload, "llm_api_key")
    assert item["value"] == SECRET_PLACEHOLDER
    assert item["is_set"] is True
    assert "gsk_secreto_real" not in client.get("/api/admin/ai-config").text
    # El valor real sigue guardado y disponible para el backend.
    assert _stored(SessionLocal, "llm_api_key") == "gsk_secreto_real"


def test_resending_the_placeholder_does_not_erase_the_stored_key(admin_client):
    client, SessionLocal = admin_client
    _put(client, "llm_api_key", "gsk_secreto_real", "password")

    # El formulario reenvia la mascara cuando el admin no toca el campo.
    assert _put(client, "llm_api_key", SECRET_PLACEHOLDER, "password").status_code == 200

    assert _stored(SessionLocal, "llm_api_key") == "gsk_secreto_real"


def test_empty_value_clears_the_key_deliberately(admin_client):
    client, SessionLocal = admin_client
    _put(client, "llm_api_key", "gsk_secreto_real", "password")

    assert _put(client, "llm_api_key", "", "password").status_code == 200

    assert _stored(SessionLocal, "llm_api_key") == ""
    assert _item(client.get("/api/admin/ai-config").json(), "llm_api_key")["is_set"] is False


def test_smtp_password_is_masked_the_same_way(admin_client):
    client, SessionLocal = admin_client

    client.put(
        "/api/admin/email-config",
        json={"items": [{"key": "email_smtp_password", "value": "clave-smtp", "value_type": "password"}]},
    )

    payload = client.get("/api/admin/email-config").json()
    assert _item(payload, "email_smtp_password")["value"] == SECRET_PLACEHOLDER

    client.put(
        "/api/admin/email-config",
        json={"items": [{"key": "email_smtp_password", "value": SECRET_PLACEHOLDER, "value_type": "password"}]},
    )
    assert _stored(SessionLocal, "email_smtp_password") == "clave-smtp"


# ── validacion ───────────────────────────────────────────────────────────────

def test_unknown_provider_is_rejected(admin_client):
    client, SessionLocal = admin_client

    response = _put(client, "llm_provider", "gemini")

    assert response.status_code == 422
    assert "Proveedor no soportado" in response.json()["detail"]
    assert _stored(SessionLocal, "llm_provider") is None


def test_base_url_without_scheme_is_rejected(admin_client):
    client, _ = admin_client

    response = _put(client, "llm_api_base_url", "api.groq.com/openai/v1")

    assert response.status_code == 422
    assert "http://" in response.json()["detail"]


def test_timeout_outside_range_is_rejected(admin_client):
    client, _ = admin_client

    assert _put(client, "llm_request_timeout", "0", "integer").status_code == 422
    assert _put(client, "llm_request_timeout", "120", "integer").status_code == 200


def test_provider_keys_are_exposed_with_their_defaults(admin_client):
    client, _ = admin_client

    payload = client.get("/api/admin/ai-config").json()
    keys = {entry["key"] for entry in payload["items"]}

    assert {"llm_provider", "llm_api_base_url", "llm_api_key", "llm_api_model"} <= keys
    assert _item(payload, "llm_provider")["value"] == "ollama"
    assert _item(payload, "llm_api_base_url")["value"].startswith("https://api.groq.com")
