"""Anotaciones sobre una region de una imagen.

Dos requisitos clave del pedido docente:
- estas anotaciones deben poder existir sobre cualquier imagen del visor SIN
  que eso implique correr el clasificador de IA. Se verifica explícitamente
  que crear/leer/editar no toca `HistopathologySession`.
- el estudiante puede dejar sus propias anotaciones (para su ejercicio de
  identificación) y sólo gestiona las suyas; docente/administrador siguen
  pudiendo curar todo.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.db import Base, get_db
from app.models import HistopathologySession, ImageAnnotation, MedicalImage, User
from app.routers import image_annotations


def _make_user(role: str, user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"{role}{user_id}@example.com",
        name=f"Usuario {role}",
        password_hash="hash",
        role=role,
        is_active=True,
        account_status="approved",
    )


@pytest.fixture
def annotations_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        db.add(_make_user("docente", 1))
        db.add(_make_user("estudiante", 2))
        db.add(
            MedicalImage(
                id=1,
                filename="lamina.svs",
                original_filename="lamina.svs",
                title="Lámina de prueba",
                file_type="svs",
                file_path="/tmp/lamina.svs",
                uploaded_by=1,
                is_active=True,
            )
        )
        db.commit()

    current = {"role": "docente", "id": 1}

    app = FastAPI()
    app.include_router(image_annotations.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _make_user(current["role"], current["id"])

    with TestClient(app) as client:
        yield client, SessionLocal, current

    Base.metadata.drop_all(bind=engine)


def _create(client, **overrides):
    payload = {
        "roi": {"x": 100, "y": 200, "width": 300, "height": 250},
        "label": "Linfocito",
        "note": "Célula redonda con núcleo denso, característica de infiltrado linfocitario.",
    }
    payload.update(overrides)
    return client.post("/api/medical-images/1/annotations", json=payload)


def test_teacher_can_create_an_annotation(annotations_client):
    client, _, _ = annotations_client
    response = _create(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["label"] == "Linfocito"
    assert body["roi"] == {"x": 100, "y": 200, "width": 300, "height": 250}
    assert body["creator_name"] == "Usuario docente"
    # El rol viaja en el payload para que el visor pinte distinto docente vs estudiante.
    assert body["creator_role"] == "docente"
    assert body["shape"] == "rect"  # valor por defecto cuando no se envia


def test_annotation_can_be_an_ellipse(annotations_client):
    client, _, _ = annotations_client
    response = _create(client, shape="ellipse")
    assert response.status_code == 201, response.text
    assert response.json()["shape"] == "ellipse"


def test_invalid_shape_is_rejected(annotations_client):
    client, _, _ = annotations_client
    response = _create(client, shape="triangle")
    assert response.status_code == 422


def test_shape_can_be_changed_on_update(annotations_client):
    client, _, _ = annotations_client
    annotation_id = _create(client).json()["id"]

    updated = client.put(
        f"/api/medical-images/annotations/{annotation_id}",
        json={"shape": "ellipse"},
    )
    assert updated.status_code == 200
    assert updated.json()["shape"] == "ellipse"
    # Lo demas no se toco porque no vino en el payload.
    assert updated.json()["label"] == "Linfocito"


def test_student_can_read_and_create_annotations(annotations_client):
    """El estudiante deja sus propias marcas de estudio ("aquí creo que hay
    necrosis") y las ve junto con las del docente."""
    client, _, current = annotations_client
    _create(client)  # anotacion del docente

    current["role"] = "estudiante"
    current["id"] = 2

    listed = client.get("/api/medical-images/1/annotations")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    created = _create(client, label="Mi hipótesis: necrosis")
    assert created.status_code == 201, created.text
    assert created.json()["creator_role"] == "estudiante"
    assert created.json()["created_by"] == 2


def test_student_cannot_edit_or_delete_a_teacher_annotation(annotations_client):
    client, _, current = annotations_client
    teacher_annotation_id = _create(client).json()["id"]

    current["role"] = "estudiante"
    current["id"] = 2

    forbidden_edit = client.put(
        f"/api/medical-images/annotations/{teacher_annotation_id}",
        json={"label": "no debería poder"},
    )
    assert forbidden_edit.status_code == 403

    forbidden_delete = client.delete(f"/api/medical-images/annotations/{teacher_annotation_id}")
    assert forbidden_delete.status_code == 403


def test_student_can_edit_and_delete_own_annotation(annotations_client):
    client, _, current = annotations_client

    current["role"] = "estudiante"
    current["id"] = 2

    own_id = _create(client, label="Mi marca").json()["id"]

    updated = client.put(
        f"/api/medical-images/annotations/{own_id}",
        json={"label": "Mi marca (corregida)"},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Mi marca (corregida)"

    deleted = client.delete(f"/api/medical-images/annotations/{own_id}")
    assert deleted.status_code == 204


def test_teacher_can_curate_a_students_annotation(annotations_client):
    """Docente/admin siguen pudiendo editar/borrar lo que sea, incluida una
    anotación de un estudiante (para corregir errores didácticos)."""
    client, _, current = annotations_client

    current["role"] = "estudiante"
    current["id"] = 2
    student_annotation_id = _create(client, label="Creo que es necrosis").json()["id"]

    current["role"] = "docente"
    current["id"] = 1

    updated = client.put(
        f"/api/medical-images/annotations/{student_annotation_id}",
        json={"label": "Necrosis coagulativa (confirmada)"},
    )
    assert updated.status_code == 200

    deleted = client.delete(f"/api/medical-images/annotations/{student_annotation_id}")
    assert deleted.status_code == 204


def test_teacher_can_edit_and_delete(annotations_client):
    client, _, _ = annotations_client
    annotation_id = _create(client).json()["id"]

    updated = client.put(
        f"/api/medical-images/annotations/{annotation_id}",
        json={"label": "Linfocito maduro", "note": "Ajustado tras revisión de pares."},
    )
    assert updated.status_code == 200
    assert updated.json()["label"] == "Linfocito maduro"
    # El ROI no se tocó porque no vino en el payload.
    assert updated.json()["roi"] == {"x": 100, "y": 200, "width": 300, "height": 250}

    deleted = client.delete(f"/api/medical-images/annotations/{annotation_id}")
    assert deleted.status_code == 204
    assert client.get("/api/medical-images/1/annotations").json() == []


def test_any_teacher_can_edit_a_colleagues_annotation(annotations_client):
    """Es contenido del curso, no propiedad personal de quien lo creó."""
    client, SessionLocal, current = annotations_client
    with SessionLocal() as db:
        db.add(_make_user("docente", 3))
        db.commit()

    annotation_id = _create(client).json()["id"]

    current["id"] = 3
    response = client.put(
        f"/api/medical-images/annotations/{annotation_id}",
        json={"label": "Editado por otro docente"},
    )
    assert response.status_code == 200


def test_annotation_never_touches_the_classifier_pipeline(annotations_client):
    """El requisito central: nada de esto debe crear ni tocar una sesión de IA."""
    client, SessionLocal, _ = annotations_client
    _create(client)

    with SessionLocal() as db:
        assert db.query(HistopathologySession).count() == 0
        assert db.query(ImageAnnotation).count() == 1


def test_annotation_on_image_never_analyzed_is_allowed(annotations_client):
    """El caso de uso explícito: imágenes que la coordinación no quiere analizar."""
    client, _, _ = annotations_client
    # No se llamó a /analyze-roi ni se creó ninguna HistopathologySession antes
    # de anotar; la anotación no lo requiere.
    response = _create(client)
    assert response.status_code == 201


def test_annotation_requires_a_label(annotations_client):
    client, _, _ = annotations_client
    response = _create(client, label="")
    assert response.status_code == 422


def test_annotation_on_missing_image_is_404(annotations_client):
    client, _, _ = annotations_client
    response = client.post(
        "/api/medical-images/999/annotations",
        json={"roi": {"x": 0, "y": 0, "width": 10, "height": 10}, "label": "x"},
    )
    assert response.status_code == 404


def test_deleting_the_image_cascades_to_its_annotations(annotations_client):
    client, SessionLocal, _ = annotations_client
    _create(client)

    with SessionLocal() as db:
        image = db.query(MedicalImage).filter(MedicalImage.id == 1).first()
        db.delete(image)
        db.commit()

    with SessionLocal() as db:
        assert db.query(ImageAnnotation).count() == 0


def test_negative_roi_is_rejected(annotations_client):
    client, _, _ = annotations_client
    response = _create(client, roi={"x": -5, "y": 0, "width": 10, "height": 10})
    assert response.status_code == 422
