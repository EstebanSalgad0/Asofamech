import os

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..db import get_db
from ..embedding_service import embed_text_for_rag
from ..models import Document, DocumentChunk, User
from ..pgvector_store import (
    delete_pgvector_embeddings_for_document,
    ensure_pgvector_schema,
    search_pgvector,
    upsert_pgvector_embedding,
)
from ..rag_utils import (
    RagHit,
    chunk_text,
    cosine_similarity,
    make_snippet,
    score_document,
)
from .admin import get_ai_config_map, parse_bool


router = APIRouter(prefix="/api/rag", tags=["rag"])
DEFAULT_NEURAL_MIN_SCORE = 0.45
DEFAULT_LOCAL_MIN_SCORE = 0.12


class DocumentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20)
    tags: str = ""


class DocumentOut(BaseModel):
    id: int
    title: str
    content: str
    tags: str | None = None
    chunk_count: int = 0

    class Config:
        orm_mode = True


class RagSearchResponse(BaseModel):
    query: str
    hits: list[dict]
    context: str


def _document_to_out(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "content": document.content,
        "tags": document.tags,
        "chunk_count": len(document.chunks or []),
    }


def sync_document_chunks(db: Session, document: Document) -> int:
    config = get_ai_config_map(db)
    model_name = config.get("embedding_model")
    neural_enabled = parse_bool(config.get("neural_embeddings_enabled"), True)
    pgvector_enabled = parse_bool(config.get("pgvector_enabled"), True)
    pgvector_ready = pgvector_enabled and ensure_pgvector_schema(db)

    if pgvector_ready:
        delete_pgvector_embeddings_for_document(db, document.id)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    source = "\n".join(
        part
        for part in [document.title or "", document.tags or "", document.content or ""]
        if part
    )
    chunks = chunk_text(source)
    for index, chunk in enumerate(chunks):
        embedding = embed_text_for_rag(
            chunk,
            model_name=model_name,
            neural_enabled=neural_enabled,
        )
        chunk_row = DocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk,
            embedding=embedding.vector,
            token_count=len(chunk.split()),
        )
        db.add(chunk_row)
        db.flush()
        if pgvector_ready:
            upsert_pgvector_embedding(
                db,
                chunk_id=chunk_row.id,
                document_id=document.id,
                vector=embedding.vector,
                provider=embedding.provider,
            )
    return len(chunks)


def ensure_vector_index(db: Session) -> None:
    missing = (
        db.query(Document)
        .outerjoin(DocumentChunk)
        .filter(DocumentChunk.id == None)
        .all()
    )
    if not missing:
        return
    for document in missing:
        sync_document_chunks(db, document)
    db.commit()


def _relevance_threshold(provider: str | None) -> float:
    is_neural = (provider or "").startswith("sentence-transformers:")
    env_key = "RAG_MIN_NEURAL_SCORE" if is_neural else "RAG_MIN_LOCAL_SCORE"
    default = DEFAULT_NEURAL_MIN_SCORE if is_neural else DEFAULT_LOCAL_MIN_SCORE
    try:
        return float(os.getenv(env_key, default))
    except (TypeError, ValueError):
        return default


def _is_relevant_score(score: float, provider: str | None) -> bool:
    return score >= _relevance_threshold(provider)


def retrieve_rag_hits(db: Session, query: str, limit: int = 4) -> list[RagHit]:
    ensure_vector_index(db)
    config = get_ai_config_map(db)
    embedding = embed_text_for_rag(
        query,
        model_name=config.get("embedding_model"),
        neural_enabled=parse_bool(config.get("neural_embeddings_enabled"), True),
    )
    query_embedding = embedding.vector
    if not any(query_embedding):
        return []

    if parse_bool(config.get("pgvector_enabled"), True) and ensure_pgvector_schema(db):
        vector_rows = search_pgvector(db, query_embedding, limit=max(8, limit * 4))
        if vector_rows:
            hits: list[RagHit] = []
            seen_documents: set[int] = set()
            for row in vector_rows:
                provider = row.get("provider") or embedding.provider
                score = round(float(row["score"] or 0.0), 6)
                if not _is_relevant_score(score, provider):
                    continue
                document_id = int(row["document_id"])
                if document_id in seen_documents:
                    continue
                seen_documents.add(document_id)
                hits.append(
                    RagHit(
                        id=document_id,
                        title=row["title"],
                        tags=row["tags"] or "",
                        score=score,
                        snippet=make_snippet(row["chunk_content"], query),
                        chunk_id=int(row["chunk_id"]),
                        chunk_index=int(row["chunk_index"]),
                        provider=provider,
                    )
                )
                if len(hits) >= max(1, min(limit, 8)):
                    break
            return hits

    chunk_hits: list[tuple[DocumentChunk, float]] = []
    for chunk in db.query(DocumentChunk).join(Document).all():
        vector_score = cosine_similarity(query_embedding, chunk.embedding or [])
        if vector_score <= 0:
            continue
        lexical_boost = score_document(
            query,
            chunk.document.title,
            chunk.content,
            chunk.document.tags or "",
        ) * 0.03
        combined_score = vector_score + lexical_boost
        if not _is_relevant_score(combined_score, embedding.provider):
            continue
        chunk_hits.append((chunk, combined_score))

    chunk_hits.sort(key=lambda item: item[1], reverse=True)

    hits: list[RagHit] = []
    seen_documents: set[int] = set()
    for chunk, score in chunk_hits:
        if chunk.document_id in seen_documents:
            continue
        seen_documents.add(chunk.document_id)
        hits.append(
            RagHit(
                id=chunk.document_id,
                title=chunk.document.title,
                tags=chunk.document.tags or "",
                score=round(float(score), 6),
                snippet=make_snippet(chunk.content, query),
                chunk_id=chunk.id,
                chunk_index=chunk.chunk_index,
                provider=embedding.provider,
            )
        )
        if len(hits) >= max(1, min(limit, 8)):
            break
    return hits


def build_rag_context(hits: list[RagHit]) -> str:
    if not hits:
        return ""
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        tags = f" | Tags: {hit.tags}" if hit.tags else ""
        blocks.append(
            f"Fuente {idx}: {hit.title}{tags}\n"
            f"Extracto: {hit.snippet}"
        )
    return "\n\n".join(blocks)


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    return [
        _document_to_out(document)
        for document in db.query(Document).order_by(Document.id.desc()).all()
    ]


@router.post("/documents", response_model=DocumentOut)
def create_document(
    payload: DocumentIn,
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    document = Document(
        title=payload.title.strip(),
        content=payload.content.strip(),
        tags=payload.tags.strip() or None,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    sync_document_chunks(db, document)
    db.commit()
    db.refresh(document)
    return _document_to_out(document)


@router.put("/documents/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int,
    payload: DocumentIn,
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    document.title = payload.title.strip()
    document.content = payload.content.strip()
    document.tags = payload.tags.strip() or None
    sync_document_chunks(db, document)
    db.commit()
    db.refresh(document)
    return _document_to_out(document)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    db.delete(document)
    db.commit()
    return {"ok": True}


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(
    document_id: int,
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    sync_document_chunks(db, document)
    db.commit()
    db.refresh(document)
    return _document_to_out(document)


@router.post("/reindex")
def reindex_all_documents(
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    total = 0
    for document in db.query(Document).all():
        total += sync_document_chunks(db, document)
    db.commit()
    return {"ok": True, "chunks_indexed": total}


@router.get("/search", response_model=RagSearchResponse)
def search_documents(
    q: str = Query(min_length=3),
    limit: int = Query(default=4, ge=1, le=8),
    current_user: User = Depends(require_roles("estudiante", "docente", "administrador")),
    db: Session = Depends(get_db),
):
    hits = retrieve_rag_hits(db, q, limit)
    return {
        "query": q,
        "hits": [hit.__dict__ for hit in hits],
        "context": build_rag_context(hits),
    }
