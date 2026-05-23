import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
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
from ..rag_file_loader import clean_document_text, extract_text_from_upload
from ..rag_utils import (
    CHUNK_MAX_TOKENS,
    CHUNK_OVERLAP_TOKENS,
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
MIN_CHUNK_TOKENS = 80
MAX_CHUNK_TOKENS = 500
MIN_CHUNK_OVERLAP = 0
MAX_CHUNK_OVERLAP = 120


class DocumentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20)
    tags: str = ""
    source: str = Field(default="", max_length=500)
    document_type: str = Field(default="text", max_length=50)
    chunk_size: int | None = Field(default=None, ge=MIN_CHUNK_TOKENS, le=MAX_CHUNK_TOKENS)
    chunk_overlap: int | None = Field(default=None, ge=MIN_CHUNK_OVERLAP, le=MAX_CHUNK_OVERLAP)


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    tags: str | None = None
    source: str | None = None
    document_type: str = "text"
    uploaded_at: datetime | None = None
    created_by: int | None = None
    creator_name: str | None = None
    indexing_status: str = "pending"
    indexing_error: str | None = None
    chunk_size: int = CHUNK_MAX_TOKENS
    chunk_overlap: int = CHUNK_OVERLAP_TOKENS
    chunk_count: int = 0


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
        "source": document.source,
        "document_type": document.document_type or "text",
        "uploaded_at": document.uploaded_at,
        "created_by": document.created_by,
        "creator_name": document.creator.name if document.creator else None,
        "indexing_status": document.indexing_status or "pending",
        "indexing_error": document.indexing_error,
        "chunk_size": document.chunk_size or CHUNK_MAX_TOKENS,
        "chunk_overlap": document.chunk_overlap if document.chunk_overlap is not None else CHUNK_OVERLAP_TOKENS,
        "chunk_count": len(document.chunks or []),
    }


def _config_int(config: dict[str, str], key: str, default: int) -> int:
    try:
        return int(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _bounded_chunk_settings(
    chunk_size: int | None,
    chunk_overlap: int | None,
    config: dict[str, str] | None = None,
) -> tuple[int, int]:
    config = config or {}
    size = chunk_size or _config_int(config, "rag_chunk_max_tokens", CHUNK_MAX_TOKENS)
    overlap = (
        chunk_overlap
        if chunk_overlap is not None
        else _config_int(config, "rag_chunk_overlap_tokens", CHUNK_OVERLAP_TOKENS)
    )
    size = max(MIN_CHUNK_TOKENS, min(MAX_CHUNK_TOKENS, int(size)))
    overlap = max(MIN_CHUNK_OVERLAP, min(MAX_CHUNK_OVERLAP, int(overlap)))
    overlap = min(overlap, max(0, size - 1))
    return size, overlap


def sync_document_chunks(db: Session, document: Document) -> int:
    config = get_ai_config_map(db)
    model_name = config.get("embedding_model")
    neural_enabled = parse_bool(config.get("neural_embeddings_enabled"), True)
    pgvector_enabled = parse_bool(config.get("pgvector_enabled"), True)
    pgvector_ready = pgvector_enabled and ensure_pgvector_schema(db)
    chunk_size, chunk_overlap = _bounded_chunk_settings(
        document.chunk_size,
        document.chunk_overlap,
        config,
    )
    document.chunk_size = chunk_size
    document.chunk_overlap = chunk_overlap
    document.indexing_status = "indexing"
    document.indexing_error = None

    if pgvector_ready:
        delete_pgvector_embeddings_for_document(db, document.id)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    source = "\n".join(
        part
        for part in [document.title or "", document.tags or "", document.content or ""]
        if part
    )
    chunks = chunk_text(clean_document_text(source), max_tokens=chunk_size, overlap_tokens=chunk_overlap)
    if not chunks:
        document.indexing_status = "failed"
        document.indexing_error = "No se generaron chunks a partir del contenido"
        return 0
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
            embedding_provider=embedding.provider,
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
    document.indexing_status = "indexed"
    document.indexing_error = None
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
                        source=row.get("source") or "",
                        document_type=row.get("document_type") or "text",
                    )
                )
                if len(hits) >= max(1, min(limit, 8)):
                    break
            return hits

    chunk_hits: list[tuple[DocumentChunk, float]] = []
    for chunk in (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.indexing_status == "indexed")
        .all()
    ):
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
                provider=chunk.embedding_provider or embedding.provider,
                source=chunk.document.source or "",
                document_type=chunk.document.document_type or "text",
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
        source = f" | Fuente: {hit.source}" if hit.source else ""
        blocks.append(
            f"Fuente {idx}: {hit.title}{tags}{source}\n"
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
    config = get_ai_config_map(db)
    chunk_size, chunk_overlap = _bounded_chunk_settings(payload.chunk_size, payload.chunk_overlap, config)
    document = Document(
        title=payload.title.strip(),
        content=clean_document_text(payload.content),
        tags=payload.tags.strip() or None,
        source=payload.source.strip() or None,
        document_type=(payload.document_type or "text").strip().lower(),
        created_by=current_user.id,
        uploaded_at=datetime.utcnow(),
        indexing_status="pending",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    sync_document_chunks(db, document)
    db.commit()
    db.refresh(document)
    return _document_to_out(document)


@router.post("/documents/upload", response_model=DocumentOut)
async def upload_document(
    title: str | None = Form(default=None),
    tags: str = Form(default=""),
    source: str | None = Form(default=None),
    chunk_size: int | None = Form(default=None),
    chunk_overlap: int | None = Form(default=None),
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles("docente", "administrador")),
    db: Session = Depends(get_db),
):
    content, detected_type = await extract_text_from_upload(file)
    config = get_ai_config_map(db)
    bounded_chunk_size, bounded_chunk_overlap = _bounded_chunk_settings(
        chunk_size,
        chunk_overlap,
        config,
    )
    filename = file.filename or "documento"
    resolved_title = (title or "").strip() or filename
    document = Document(
        title=resolved_title[:200],
        content=content,
        tags=tags.strip() or None,
        source=(source or filename).strip() or None,
        document_type=detected_type,
        created_by=current_user.id,
        uploaded_at=datetime.utcnow(),
        indexing_status="pending",
        chunk_size=bounded_chunk_size,
        chunk_overlap=bounded_chunk_overlap,
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
    config = get_ai_config_map(db)
    chunk_size, chunk_overlap = _bounded_chunk_settings(payload.chunk_size, payload.chunk_overlap, config)
    document.title = payload.title.strip()
    document.content = clean_document_text(payload.content)
    document.tags = payload.tags.strip() or None
    document.source = payload.source.strip() or None
    document.document_type = (payload.document_type or document.document_type or "text").strip().lower()
    document.chunk_size = chunk_size
    document.chunk_overlap = chunk_overlap
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
    delete_pgvector_embeddings_for_document(db, document.id)
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
