from pathlib import Path

from app.db import SessionLocal
from app.models import Document
from app.routers.rag import sync_document_chunks


TITLE = "Fiebre: evaluacion inicial, signos de alarma y manejo educativo"
TAGS = (
    "fiebre, temperatura alta, signos de alarma, pediatria, adultos, triage, "
    "infecciones respiratorias"
)
CONTENT_PATH = Path("/app/data/rag/fiebre_documento_rag.md")


def main() -> None:
    content = CONTENT_PATH.read_text(encoding="utf-8")
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.title == TITLE).first()
        if document is None:
            document = Document(title=TITLE, content=content, tags=TAGS)
            db.add(document)
            db.commit()
            db.refresh(document)
            action = "created"
        else:
            document.content = content
            document.tags = TAGS
            db.commit()
            db.refresh(document)
            action = "updated"

        chunk_count = sync_document_chunks(db, document)
        db.commit()
        print(f"{action}: id={document.id}, chunks={chunk_count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
