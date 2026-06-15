"""Sube documentos RAG de histopatología directamente a la base de datos."""
import sys
import os
sys.path.insert(0, "/app")

from datetime import datetime
from app.db import SessionLocal
from app.models import Document, User
from app.routers.rag import sync_document_chunks

# Chunking óptimo para texto médico educativo:
#  - 400 tokens: párrafo completo con contexto suficiente para embedding semántico
#  - 80 tokens de overlap: evita cortar definiciones o listas a mitad
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80

DOCUMENTS = [
    {
        "filename": "01_ganglio_linfatico_histologia_normal.md",
        "title": "Ganglio linfático: histología normal y anatomía microscópica",
        "tags": "histopatología, ganglio linfático, anatomía microscópica, senos, folículos, corteza",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "02_metastasis_ganglio_linfatico_cancer_mama.md",
        "title": "Metástasis de cáncer de mama en ganglio linfático",
        "tags": "metástasis, ganglio linfático, cáncer de mama, macrometástasis, micrometástasis, ITC",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "03_carcinoma_ductal_invasivo_morfologia.md",
        "title": "Carcinoma ductal invasivo de mama: morfología y clasificación histológica",
        "tags": "carcinoma ductal invasivo, CDI, grado Nottingham, HER2, luminal, triple negativo, morfología",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "04_estadificacion_TNM_cancer_mama.md",
        "title": "Estadificación TNM del cáncer de mama: componente ganglionar (pN)",
        "tags": "TNM, estadificación, pN, ganglio centinela, metástasis, AJCC, pronóstico",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "05_interpretacion_roi_histopatologia.md",
        "title": "Interpretación de regiones de interés (ROI) en histopatología de ganglio linfático",
        "tags": "ROI, parche, patch, CAMELYON, abstención, artefactos, clasificación IA",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "06_cancer_mama_diseminacion_linfatica.md",
        "title": "Cáncer de mama: diseminación linfática y cadenas ganglionares",
        "tags": "diseminación linfática, axila, mamaria interna, ganglio centinela, VEGF-C, ELV",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "07_camelyon_dataset_ia_histopatologia.md",
        "title": "Dataset CAMELYON y modelos de IA en histopatología de ganglio linfático",
        "tags": "CAMELYON, PCam, IA, inteligencia artificial, CONCH, AUC, tri-head, WSI",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
    {
        "filename": "08_tecnicas_histologia_hematoxilina_eosina.md",
        "title": "Técnica de hematoxilina y eosina (H&E): fundamentos e interpretación",
        "tags": "H&E, hematoxilina, eosina, tinción, núcleo, citoplasma, IHQ, citoqueratinas",
        "source": "Material educativo ASOFAMECH – Histopatología",
    },
]

DOCS_DIR = "/app/rag_seed_docs"


def main():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "administrador").first()
        if not admin:
            print("ERROR: No se encontró usuario administrador.")
            sys.exit(1)

        print(f"Subiendo documentos como: {admin.name} ({admin.email})\n")

        for meta in DOCUMENTS:
            path = os.path.join(DOCS_DIR, meta["filename"])
            if not os.path.exists(path):
                print(f"  [SKIP] Archivo no encontrado: {path}")
                continue

            with open(path, encoding="utf-8") as f:
                content = f.read()

            # Evitar duplicados por título
            existing = db.query(Document).filter(Document.title == meta["title"]).first()
            if existing:
                print(f"  [EXISTE] {meta['title'][:60]}...")
                continue

            doc = Document(
                title=meta["title"],
                content=content,
                tags=meta["tags"],
                source=meta["source"],
                document_type="text",
                created_by=admin.id,
                uploaded_at=datetime.utcnow(),
                indexing_status="pending",
                chunk_size=CHUNK_SIZE,
                chunk_overlap=CHUNK_OVERLAP,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            n_chunks = sync_document_chunks(db, doc)
            db.commit()

            print(f"  [OK] {meta['title'][:60]}... → {n_chunks} chunks")

        print("\nListo.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
