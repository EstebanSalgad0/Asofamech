from __future__ import annotations

import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile


SUPPORTED_RAG_EXTENSIONS = {".txt", ".md", ".markdown", ".docx", ".pdf"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
MAX_RAG_UPLOAD_BYTES = 15 * 1024 * 1024


def clean_document_text(value: str) -> str:
    text = (value or "").replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_document_type(filename: str | None, content_type: str | None = None) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension in {".md", ".markdown"}:
        return "markdown"
    if extension == ".txt":
        return "txt"
    if extension == ".docx":
        return "docx"
    if extension == ".pdf":
        return "pdf"
    if content_type == "application/pdf":
        return "pdf"
    return "text"


def validate_supported_extension(filename: str | None) -> str:
    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_RAG_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_RAG_EXTENSIONS))
        raise HTTPException(
            status_code=422,
            detail=f"Formato no soportado. Usa uno de estos archivos: {allowed}",
        )
    return extension


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as docx:
            xml = docx.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=422, detail="DOCX invalido o corrupto") from exc

    root = ElementTree.fromstring(xml)
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        parts: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{namespace}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{namespace}tab":
                parts.append(" ")
            elif node.tag == f"{namespace}br":
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _extract_pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(
            status_code=422,
            detail="La lectura de PDF requiere instalar la dependencia pypdf.",
        ) from exc

    try:
        reader = PdfReader(BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise HTTPException(status_code=422, detail="No se pudo extraer texto del PDF") from exc
    return "\n\n".join(page for page in pages if page.strip())


def extract_text_from_bytes(data: bytes, filename: str | None, content_type: str | None = None) -> tuple[str, str]:
    if len(data) > MAX_RAG_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el limite de 15 MB")

    extension = validate_supported_extension(filename)
    document_type = detect_document_type(filename, content_type)
    if extension in TEXT_EXTENSIONS:
        text = _decode_text(data)
    elif extension == ".docx":
        text = _extract_docx_text(data)
    elif extension == ".pdf":
        text = _extract_pdf_text(data)
    else:
        text = ""

    cleaned = clean_document_text(text)
    if len(cleaned) < 20:
        raise HTTPException(status_code=422, detail="No se extrajo texto suficiente del documento")
    return cleaned, document_type


async def extract_text_from_upload(file: UploadFile) -> tuple[str, str]:
    data = await file.read()
    return extract_text_from_bytes(data, file.filename, file.content_type)
