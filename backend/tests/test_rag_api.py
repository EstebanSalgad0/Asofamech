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


def test_lexical_support_requires_shared_term():
    """El filtro descarta documentos de otro tema clinico sin vocabulario comun."""
    assert rag._has_lexical_support(
        "cuando se debe abstener el modelo de clasificar un ROI",
        "Interpretacion de regiones de interes",
        "El modelo se abstiene cuando la confianza no supera el umbral.",
        "ROI, abstencion",
    )
    assert not rag._has_lexical_support(
        "como se diagnostica una infeccion urinaria",
        "Estadificacion TNM del cancer de mama",
        "El componente ganglionar pN describe el compromiso axilar.",
        "TNM, pN",
    )


def test_lexical_support_is_permissive_without_usable_terms():
    """Sin terminos utiles tras quitar conectores, decide solo el score vectorial."""
    assert rag._has_lexical_support("que es una", "Titulo", "Contenido cualquiera", "")


def test_strip_evaluation_items_removes_quiz_and_keeps_explanation():
    from app.rag_utils import strip_evaluation_items

    content = (
        "La NAC resulta de la proliferacion de microorganismos a nivel alveolar.\n\n"
        "Preguntas faciles\n\n"
        "Cual es el mecanismo mas comun de llegada de los patogenos?\n"
        "A) Contacto con la piel\n"
        "B) Microaspiracion de flora orofaringea\n"
        "C) Transmision sanguinea\n"
        "D) Exposicion a radiacion\n\n"
        "Respuesta correcta: B\nJustificacion: llegan por microaspiracion.\n\n"
        "El edema alveolar deteriora el intercambio gaseoso."
    )

    result = strip_evaluation_items(content)

    assert "proliferacion de microorganismos" in result
    assert "edema alveolar deteriora" in result
    assert "Respuesta correcta" not in result
    assert "Microaspiracion de flora" not in result
    assert "Preguntas faciles" not in result


def test_strip_evaluation_items_keeps_short_lettered_lists():
    """Una lista con dos vinetas no es un item de seleccion multiple."""
    from app.rag_utils import strip_evaluation_items

    content = "Clasificacion de la resistencia:\na) Primaria\nb) Adquirida"

    assert "Primaria" in strip_evaluation_items(content)


def test_document_budget_allows_several_chunks_from_same_document():
    per_document: dict[int, int] = {}

    assert rag._document_budget(7, per_document, max_documents=2, max_chunks_per_document=3)
    per_document[7] = 3
    # Alcanzo su tope de fragmentos.
    assert not rag._document_budget(7, per_document, max_documents=2, max_chunks_per_document=3)
    # Otro documento todavia cabe.
    assert rag._document_budget(9, per_document, max_documents=2, max_chunks_per_document=3)
    per_document[9] = 1
    # Con dos documentos distintos ya no entra un tercero.
    assert not rag._document_budget(11, per_document, max_documents=2, max_chunks_per_document=3)


def test_relative_margin_drops_sources_far_below_the_best_hit():
    hits = [
        rag.RagHit(id=1, title="Tuberculosis", tags="", score=0.8834, snippet="a"),
        rag.RagHit(id=2, title="Resistencia", tags="", score=0.7473, snippet="b"),
        rag.RagHit(id=3, title="Neumonia", tags="", score=0.5158, snippet="c"),
    ]

    kept = rag._apply_relative_margin(hits)

    # 0.5158 < 0.8834 * 0.70: otro tema clinico colandose por el umbral absoluto.
    assert [hit.id for hit in kept] == [1, 2]


def test_relative_margin_keeps_close_scores():
    hits = [
        rag.RagHit(id=1, title="Neumonia", tags="", score=0.6832, snippet="a"),
        rag.RagHit(id=1, title="Neumonia", tags="", score=0.5593, snippet="b"),
        rag.RagHit(id=1, title="Neumonia", tags="", score=0.5085, snippet="c"),
    ]

    assert len(rag._apply_relative_margin(hits)) == 3


def test_relative_margin_keeps_a_single_hit():
    hits = [rag.RagHit(id=1, title="ROI", tags="", score=0.4368, snippet="a")]

    assert rag._apply_relative_margin(hits) == hits


def test_build_rag_context_marks_chunks_of_the_same_document():
    hits = [
        rag.RagHit(id=1, title="Neumonia", tags="", score=0.8, snippet="uno", chunk_index=0),
        rag.RagHit(id=1, title="Neumonia", tags="", score=0.7, snippet="dos", chunk_index=2),
        rag.RagHit(id=2, title="Fiebre", tags="", score=0.6, snippet="tres", chunk_index=0),
    ]

    context = rag.build_rag_context(hits)

    assert "Fragmento 1 del mismo documento" in context
    assert "Fragmento 3 del mismo documento" in context
    # El documento que aparece una sola vez no se etiqueta como fragmento.
    assert context.count("del mismo documento") == 2
