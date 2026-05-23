import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from .rag_utils import EMBEDDING_DIMENSIONS


logger = logging.getLogger(__name__)


def vector_literal(vector: list[float]) -> str:
    values = ",".join(f"{float(value):.8f}" for value in vector[:EMBEDDING_DIMENSIONS])
    return f"[{values}]"


def ensure_pgvector_schema(db: Session) -> bool:
    try:
        db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        db.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS document_vector_embeddings (
                    id SERIAL PRIMARY KEY,
                    chunk_id INTEGER UNIQUE REFERENCES document_chunks(id) ON DELETE CASCADE,
                    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
                    embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
                    provider VARCHAR(160) NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
        )
        db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_document_vector_embeddings_document_id
                ON document_vector_embeddings(document_id)
                """
            )
        )
        return True
    except Exception as exc:
        db.rollback()
        logger.warning("pgvector no esta disponible: %s", exc)
        return False


def pgvector_available(db: Session) -> bool:
    try:
        result = db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        ).scalar()
        return bool(result)
    except Exception:
        db.rollback()
        return False


def upsert_pgvector_embedding(
    db: Session,
    chunk_id: int,
    document_id: int,
    vector: list[float],
    provider: str,
) -> None:
    if not pgvector_available(db):
        return
    db.execute(
        text(
            """
            INSERT INTO document_vector_embeddings (chunk_id, document_id, embedding, provider, updated_at)
            VALUES (:chunk_id, :document_id, CAST(:embedding AS vector), :provider, NOW())
            ON CONFLICT (chunk_id)
            DO UPDATE SET
                embedding = EXCLUDED.embedding,
                provider = EXCLUDED.provider,
                updated_at = NOW()
            """
        ),
        {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "embedding": vector_literal(vector),
            "provider": provider,
        },
    )


def delete_pgvector_embeddings_for_document(db: Session, document_id: int) -> None:
    if not pgvector_available(db):
        return
    db.execute(
        text("DELETE FROM document_vector_embeddings WHERE document_id = :document_id"),
        {"document_id": document_id},
    )


def search_pgvector(db: Session, query_vector: list[float], limit: int = 8) -> list[dict]:
    if not pgvector_available(db):
        return []
    rows = db.execute(
        text(
            """
            SELECT
                c.id AS chunk_id,
                c.chunk_index AS chunk_index,
                c.content AS chunk_content,
                d.id AS document_id,
                d.title AS title,
                COALESCE(d.source, '') AS source,
                COALESCE(d.document_type, 'text') AS document_type,
                COALESCE(d.tags, '') AS tags,
                e.provider AS provider,
                1 - (e.embedding <=> CAST(:query_embedding AS vector)) AS score
            FROM document_vector_embeddings e
            JOIN document_chunks c ON c.id = e.chunk_id
            JOIN documents d ON d.id = e.document_id
            WHERE d.indexing_status = 'indexed'
            ORDER BY e.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        ),
        {
            "query_embedding": vector_literal(query_vector),
            "limit": max(1, min(limit, 32)),
        },
    ).mappings().all()
    return [dict(row) for row in rows]
