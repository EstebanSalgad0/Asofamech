from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_roles
from ..db import get_db
from ..models import Document, DocumentChunk, User
from ..rag_utils import (
    RagHit,
    chunk_text,
    cosine_similarity,
    embed_text,
    make_snippet,
    score_document,
)


router = APIRouter(prefix="/api/rag", tags=["rag"])


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
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    source = "\n".join(
        part
        for part in [document.title or "", document.tags or "", document.content or ""]
        if part
    )
    chunks = chunk_text(source)
    for index, chunk in enumerate(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embed_text(chunk),
                token_count=len(chunk.split()),
            )
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


def retrieve_rag_hits(db: Session, query: str, limit: int = 4) -> list[RagHit]:
    ensure_vector_index(db)
    query_embedding = embed_text(query)
    if not any(query_embedding):
        return []

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
        chunk_hits.append((chunk, vector_score + lexical_boost))

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
