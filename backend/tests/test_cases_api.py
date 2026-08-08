import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import Case, CaseLink, MedicalImage, SCTTest, User
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


# ── recursos externos (bibliografia, guias, Wooclap) ─────────────────────────

def _base_case_payload(**extra) -> dict:
    payload = {"title": "Caso", "description": "Resumen", "body": "Cuerpo"}
    payload.update(extra)
    return payload


def test_create_case_stores_external_links_in_order(cases_client):
    client, SessionLocal = cases_client

    response = client.post(
        "/api/cases",
        json=_base_case_payload(
            links=[
                {
                    "kind": "wooclap",
                    "label": "Actividad interactiva",
                    "url": "https://app.wooclap.com/EVENTO",
                    "description": "Responde en vivo durante la clase",
                },
                {
                    "kind": "bibliografia",
                    "label": "Harrison, capitulo 121",
                    "url": "https://biblioteca.example.cl/harrison",
                },
            ]
        ),
    )

    assert response.status_code == 201
    links = response.json()["links"]
    assert [link["kind"] for link in links] == ["wooclap", "bibliografia"]
    assert [link["position"] for link in links] == [0, 1]
    assert links[0]["description"] == "Responde en vivo durante la clase"
    assert links[1]["description"] is None


def test_create_case_rejects_non_http_link_scheme(cases_client):
    client, SessionLocal = cases_client

    response = client.post(
        "/api/cases",
        json=_base_case_payload(
            links=[{"kind": "otro", "label": "Malicioso", "url": "javascript:alert(1)"}]
        ),
    )

    assert response.status_code == 422
    assert "http://" in response.json()["detail"]
    with SessionLocal() as db:
        assert db.query(Case).count() == 0


def test_create_case_rejects_unknown_link_kind(cases_client):
    client, _ = cases_client

    response = client.post(
        "/api/cases",
        json=_base_case_payload(
            links=[{"kind": "torrent", "label": "X", "url": "https://example.cl"}]
        ),
    )

    assert response.status_code == 422
    assert "Tipo de recurso no permitido" in response.json()["detail"]


def test_create_case_rejects_link_without_label(cases_client):
    client, _ = cases_client

    response = client.post(
        "/api/cases",
        json=_base_case_payload(links=[{"kind": "guia", "label": "  ", "url": "https://example.cl"}]),
    )

    assert response.status_code == 422
    assert "titulo visible" in response.json()["detail"]


def test_update_replaces_links_when_sent_and_keeps_them_when_omitted(cases_client):
    client, SessionLocal = cases_client

    created = client.post(
        "/api/cases",
        json=_base_case_payload(
            links=[{"kind": "guia", "label": "Guia MINSAL", "url": "https://minsal.example.cl/guia"}]
        ),
    ).json()
    case_id = created["id"]

    # Sin la clave links, los recursos existentes no se tocan.
    untouched = client.put(f"/api/cases/{case_id}", json={"title": "Caso renombrado"}).json()
    assert untouched["title"] == "Caso renombrado"
    assert [link["label"] for link in untouched["links"]] == ["Guia MINSAL"]

    # Con la clave presente, se reemplaza el conjunto completo.
    replaced = client.put(
        f"/api/cases/{case_id}",
        json={"links": [{"kind": "video", "label": "Semiologia pulmonar", "url": "https://video.example.cl/1"}]},
    ).json()
    assert [link["label"] for link in replaced["links"]] == ["Semiologia pulmonar"]

    # Una lista vacia limpia los recursos sin dejar filas huerfanas.
    emptied = client.put(f"/api/cases/{case_id}", json={"links": []}).json()
    assert emptied["links"] == []
    with SessionLocal() as db:
        assert db.query(CaseLink).count() == 0


def test_deleting_case_links_does_not_leak_between_cases(cases_client):
    client, SessionLocal = cases_client

    first = client.post(
        "/api/cases",
        json=_base_case_payload(
            title="Primero",
            links=[{"kind": "otro", "label": "A", "url": "https://a.example.cl"}],
        ),
    ).json()
    second = client.post(
        "/api/cases",
        json=_base_case_payload(
            title="Segundo",
            links=[{"kind": "otro", "label": "B", "url": "https://b.example.cl"}],
        ),
    ).json()

    client.put(f"/api/cases/{first['id']}", json={"links": []})

    remaining = client.get(f"/api/cases/{second['id']}").json()
    assert [link["label"] for link in remaining["links"]] == ["B"]
    with SessionLocal() as db:
        assert db.query(CaseLink).count() == 1
