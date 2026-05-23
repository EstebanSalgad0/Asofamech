import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import AIConfiguration, Document, DocumentChunk, User
from app.routers import rag


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
def rag_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        db.add(_make_user("docente"))
        db.add_all(
            [
                AIConfiguration(
                    key="neural_embeddings_enabled",
                    value="false",
                    value_type="boolean",
                ),
                AIConfiguration(
                    key="pgvector_enabled",
                    value="false",
                    value_type="boolean",
                ),
            ]
        )
        db.commit()

    app = FastAPI()
    app.include_router(rag.router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user("docente")

    with TestClient(app) as client:
        yield client, TestingSessionLocal, app

    Base.metadata.drop_all(bind=engine)


def test_rag_routes_require_authentication(rag_client):
    _, _, app = rag_client
    app.dependency_overrides.pop(get_current_user)

    with TestClient(app) as anonymous_client:
        response = anonymous_client.get("/api/rag/documents")

    assert response.status_code == 401


def test_rag_admin_routes_require_docente_or_admin(rag_client):
    client, _, app = rag_client
    app.dependency_overrides[get_current_user] = lambda: _make_user("estudiante")

    response = client.post(
        "/api/rag/documents",
        json={
            "title": "Guia docente",
            "content": "Contenido academico suficiente sobre metastasis ganglionar.",
        },
    )

    assert response.status_code == 403


def test_rag_document_crud_search_reindex_and_delete(rag_client):
    client, SessionLocal, _ = rag_client
    create_response = client.post(
        "/api/rag/documents",
        json={
            "title": "Guia de metastasis ganglionar",
            "tags": "histopatologia, ganglio",
            "source": "manual docente",
            "content": (
                "La metastasis ganglionar puede identificarse por grupos celulares "
                "tumorales en el parenquima del ganglio linfatico."
            ),
            "chunk_size": 80,
            "chunk_overlap": 10,
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["indexing_status"] == "indexed"
    assert created["chunk_count"] >= 1
    assert created["source"] == "manual docente"

    update_response = client.put(
        f"/api/rag/documents/{created['id']}",
        json={
            "title": "Guia actualizada de metastasis",
            "tags": "histopatologia",
            "source": "manual revisado",
            "content": (
                "La metastasis ganglionar se correlaciona con hallazgos tumorales "
                "en tejido linfatico y requiere correlacion docente."
            ),
            "chunk_size": 80,
            "chunk_overlap": 10,
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["source"] == "manual revisado"

    search_response = client.get("/api/rag/search?q=metastasis%20ganglionar&limit=4")
    assert search_response.status_code == 200
    hits = search_response.json()["hits"]
    assert hits
    assert hits[0]["source"] == "manual revisado"
    assert "metastasis" in hits[0]["snippet"].lower()

    reindex_response = client.post(f"/api/rag/documents/{created['id']}/reindex")
    assert reindex_response.status_code == 200
    assert reindex_response.json()["indexing_status"] == "indexed"

    delete_response = client.delete(f"/api/rag/documents/{created['id']}")
    assert delete_response.status_code == 200
    with SessionLocal() as db:
        assert db.query(Document).count() == 0
        assert db.query(DocumentChunk).count() == 0


def test_rag_upload_txt_extracts_indexes_and_searches(rag_client):
    client, _, _ = rag_client
    content = (
        "## Fiebre prolongada\n\n"
        "La fiebre prolongada requiere anamnesis, examen fisico y busqueda de foco infeccioso."
    ).encode("utf-8")

    response = client.post(
        "/api/rag/documents/upload",
        data={"title": "Apunte fiebre", "tags": "medicina interna", "source": "apunte.md"},
        files={"file": ("apunte.md", content, "text/markdown")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_type"] == "markdown"
    assert payload["indexing_status"] == "indexed"
    assert payload["chunk_count"] >= 1

    search_response = client.get("/api/rag/search?q=fiebre%20prolongada&limit=4")
    assert search_response.status_code == 200
    assert search_response.json()["hits"]
