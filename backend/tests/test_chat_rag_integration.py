from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import AIConfiguration, ChatLog, Document, User
from app.routers import chat
from app.routers.rag import sync_document_chunks


def _user(role: str = "estudiante") -> User:
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
def chat_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_user())
        db.add_all(
            [
                AIConfiguration(key="neural_embeddings_enabled", value="false", value_type="boolean"),
                AIConfiguration(key="pgvector_enabled", value="false", value_type="boolean"),
                AIConfiguration(key="scope_filter_enabled", value="false", value_type="boolean"),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(chat.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _user()

    with TestClient(app) as client:
        yield client, SessionLocal, app

    Base.metadata.drop_all(bind=engine)


def _ollama_answer(text: str = "Respuesta educativa apoyada en el material cargado."):
    return {"message": {"content": text}}


def test_chat_uses_rag_context_and_returns_source_chunks(chat_client):
    client, SessionLocal, _ = chat_client
    with SessionLocal() as db:
        document = Document(
            title="Guia de metastasis ganglionar",
            content=(
                "La metastasis ganglionar corresponde a infiltracion tumoral en el "
                "ganglio linfatico y debe explicarse con finalidad educativa."
            ),
            tags="histopatologia, ganglio",
            source="manual docente",
            document_type="markdown",
            created_by=1,
            indexing_status="pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        sync_document_chunks(db, document)
        db.commit()

    with patch("app.routers.chat._post_ollama_chat", new=AsyncMock(return_value=_ollama_answer())):
        response = client.post("/api/chat", json={"text": "Explica metastasis ganglionar"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Respuesta educativa apoyada en el material cargado."
    assert payload["used_rag"] is True
    assert payload["source_chunks"]
    assert payload["source_chunks"][0]["chunk_id"] is not None
    assert payload["source_chunks"][0]["source"] == "manual docente"
    assert "diagnostico" in payload["warning"].lower()

    with SessionLocal() as db:
        log = db.query(ChatLog).one()
        assert log.rag_sources
        assert log.rag_sources[0]["chunk_id"] == payload["source_chunks"][0]["chunk_id"]


def test_chat_falls_back_when_no_rag_context(chat_client):
    client, SessionLocal, _ = chat_client

    with patch("app.routers.chat._post_ollama_chat", new=AsyncMock(return_value=_ollama_answer("Respuesta educativa general."))):
        response = client.post("/api/chat", json={"text": "Explica fiebre prolongada en pediatria"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_rag"] is False
    assert payload["source_chunks"] == []
    assert "No se recupero contexto documental suficiente" in payload["warning"]

    with SessionLocal() as db:
        log = db.query(ChatLog).one()
        assert log.rag_sources == []


def test_chat_blocks_out_of_scope_before_rag(chat_client):
    client, SessionLocal, _ = chat_client
    with SessionLocal() as db:
        item = db.query(AIConfiguration).filter(AIConfiguration.key == "scope_filter_enabled").one()
        item.value = "true"
        db.commit()

    with patch("app.routers.chat._classify_medical_scope", new=AsyncMock(return_value=chat.SCOPE_NON_MEDICAL)):
        with patch("app.routers.chat._post_ollama_chat", new=AsyncMock()) as ollama_mock:
            response = client.post("/api/chat", json={"text": "Calcula una inversion financiera"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["message_type"] == "out_of_scope"
    assert payload["used_rag"] is False
    assert payload["source_chunks"] == []
    ollama_mock.assert_not_called()


def test_chat_requires_jwt_without_override(chat_client):
    _, _, app = chat_client
    app.dependency_overrides.pop(get_current_user)

    with TestClient(app) as anonymous_client:
        response = anonymous_client.post("/api/chat", json={"text": "Que es la fiebre"})

    assert response.status_code == 401


def test_chat_rejects_overlong_input(chat_client):
    client, _, _ = chat_client

    response = client.post("/api/chat", json={"text": "a" * 4001})

    assert response.status_code == 422
