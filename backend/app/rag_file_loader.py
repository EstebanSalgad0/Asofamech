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


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_paragraph_text(paragraph) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{W_NS}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{W_NS}tab":
            parts.append(" ")
        elif node.tag == f"{W_NS}br":
            parts.append("\n")
    return "".join(parts).strip()


def _docx_cell_text(cell) -> str:
    """Texto de una celda, en una sola linea.

    Los saltos internos se colapsan porque el destino es una fila de tabla
    markdown, donde un salto de linea rompe la fila.
    """
    lines = [_docx_paragraph_text(p) for p in cell.findall(f"{W_NS}p")]
    joined = " ".join(line for line in lines if line)
    # La barra vertical delimita celdas: dentro del texto se sustituye.
    return joined.replace("|", "/")


def _docx_table_to_markdown(table) -> str:
    """Convierte una tabla de Word en una tabla markdown.

    Sin esto, cada celda sale como un parrafo suelto y se pierde a que fila y
    columna pertenece. Eso da igual en un texto corrido, pero no en una tabla
    como el Practical Script o una rubrica, donde el significado esta
    precisamente en el cruce entre fila y columna.
    """
    rows: list[list[str]] = []
    for row in table.findall(f"{W_NS}tr"):
        cells = [_docx_cell_text(cell) for cell in row.findall(f"{W_NS}tc")]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]

    lines = ["| " + " | ".join(padded[0]) + " |"]
    lines.append("|" + "|".join([" --- "] * width) + "|")
    for row in padded[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _extract_docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(data)) as docx:
            xml = docx.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise HTTPException(status_code=422, detail="DOCX invalido o corrupto") from exc

    root = ElementTree.fromstring(xml)
    body = root.find(f"{W_NS}body")
    if body is None:
        return ""

    # Se recorren los hijos directos del cuerpo en orden, en vez de iterar
    # sobre todos los parrafos del arbol: asi las tablas se procesan como
    # unidad y sus celdas no aparecen ademas sueltas.
    blocks: list[str] = []
    for child in body:
        if child.tag == f"{W_NS}p":
            text = _docx_paragraph_text(child)
            if text:
                blocks.append(text)
        elif child.tag == f"{W_NS}tbl":
            table = _docx_table_to_markdown(child)
            if table:
                blocks.append(table)
    return "\n\n".join(blocks)


A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

# Formatos de imagen que la plataforma sabe mostrar. Word tambien incrusta
# .emf/.wmf (metarchivos de Windows) que ningun navegador renderiza.
DOCX_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DOCX_IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def extract_docx_images(data: bytes, max_images: int = 12) -> list[dict]:
    """Imagenes incrustadas en un .docx, en su orden de aparicion en el texto.

    El orden importa: en un caso clinico la primera imagen suele ser la
    radiografia y la segunda el TAC, y el docente espera verlas en ese mismo
    orden. Por eso se recorren las referencias `<a:blip>` del documento en vez
    de listar `word/media/`, que viene ordenado por nombre de archivo.

    Devuelve `[{filename, content_type, data}]`; nunca lanza, porque un
    documento sin imagenes o con relaciones rotas debe poder importarse igual.
    """
    images: list[dict] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as docx:
            try:
                rels_xml = docx.read("word/_rels/document.xml.rels")
                document_xml = docx.read("word/document.xml")
            except KeyError:
                return []

            targets: dict[str, str] = {}
            for rel in ElementTree.fromstring(rels_xml):
                rel_id = rel.get("Id")
                target = rel.get("Target") or ""
                if rel_id and "image" in (rel.get("Type") or ""):
                    targets[rel_id] = target.lstrip("/")

            seen: set[str] = set()
            for blip in ElementTree.fromstring(document_xml).iter(f"{A_NS}blip"):
                rel_id = blip.get(f"{R_NS}embed")
                target = targets.get(rel_id or "")
                if not target or target in seen:
                    continue
                seen.add(target)

                extension = Path(target).suffix.lower()
                if extension not in DOCX_IMAGE_EXTENSIONS:
                    continue

                path = target if target.startswith("word/") else f"word/{target}"
                try:
                    payload = docx.read(path)
                except KeyError:
                    continue

                images.append(
                    {
                        "filename": Path(target).name,
                        "content_type": DOCX_IMAGE_CONTENT_TYPES[extension],
                        "data": payload,
                    }
                )
                if len(images) >= max_images:
                    break
    except (zipfile.BadZipFile, ElementTree.ParseError):
        return []
    return images


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
