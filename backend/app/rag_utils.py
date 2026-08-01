import re
import unicodedata
from dataclasses import dataclass
from hashlib import blake2b
from math import sqrt


STOPWORDS = {
    "para", "como", "cuando", "donde", "desde", "sobre", "entre", "esta",
    "este", "estos", "estas", "porque", "cual", "cuales", "que", "con",
    "sin", "los", "las", "una", "uno", "del", "por", "mas", "menos",
    "medico", "medica", "salud", "paciente",
}
EMBEDDING_DIMENSIONS = 384
CHUNK_MAX_TOKENS = 180
CHUNK_OVERLAP_TOKENS = 40


@dataclass(frozen=True)
class RagHit:
    id: int
    title: str
    tags: str
    score: float
    snippet: str
    chunk_id: int | None = None
    chunk_index: int | None = None
    provider: str = "local-hashing"
    source: str = ""
    document_type: str = "text"


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def tokenize(value: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", normalize_text(value))
    return [word for word in words if word not in STOPWORDS]


def _hash_feature(feature: str, dimensions: int = EMBEDDING_DIMENSIONS) -> tuple[int, float]:
    digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
    raw = int.from_bytes(digest, "big", signed=False)
    index = raw % dimensions
    sign = 1.0 if ((raw >> 8) & 1) == 0 else -1.0
    return index, sign


def embed_text(value: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Embedding local deterministico por hashing, normalizado para coseno."""
    tokens = tokenize(value)
    vector = [0.0] * dimensions
    if not tokens:
        return vector

    features: list[str] = []
    features.extend(tokens)
    features.extend(f"{tokens[idx]}_{tokens[idx + 1]}" for idx in range(len(tokens) - 1))

    for feature in features:
        index, sign = _hash_feature(feature, dimensions)
        vector[index] += sign

    norm = sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def chunk_text(
    content: str,
    max_tokens: int = CHUNK_MAX_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[str]:
    clean = re.sub(r"\s+", " ", content or "").strip()
    if not clean:
        return []

    words = clean.split()
    if len(words) <= max_tokens:
        return [clean]

    chunks = []
    step = max(1, max_tokens - overlap_tokens)
    for start in range(0, len(words), step):
        window = words[start:start + max_tokens]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + max_tokens >= len(words):
            break
    return chunks


_ANSWER_KEY_RE = re.compile(r"respuesta\s+correcta", re.IGNORECASE)
_OPTION_LINE_RE = re.compile(r"^\s*[a-eA-E][\)\.]\s+\S")
_QUIZ_HEADING_RE = re.compile(r"^\s*preguntas\b", re.IGNORECASE)


def _looks_like_evaluation_block(paragraph: str) -> bool:
    normalized = normalize_text(paragraph)
    if _ANSWER_KEY_RE.search(normalized):
        return True

    lines = paragraph.splitlines()
    options = {
        line.strip()[0].lower()
        for line in lines
        if _OPTION_LINE_RE.match(line)
    }
    # Tres o mas alternativas distintas (A, B, C...) delatan un item de seleccion
    # multiple; con menos se corre el riesgo de borrar una lista legitima.
    if len(options) >= 3:
        return True

    return bool(_QUIZ_HEADING_RE.match(paragraph.strip())) and len(paragraph.strip()) < 120


def strip_evaluation_items(content: str) -> str:
    """Quita items de autoevaluacion del texto que se indexa para RAG.

    El material docente suele traer preguntas de alternativas con su clave de
    respuesta. Esos bloques compiten con el texto explicativo en la busqueda
    vectorial y, cuando ganan, el estudiante recibe como fuente citada la
    respuesta de un test. El documento original no se modifica: esto solo
    afecta al texto que se convierte en chunks.
    """
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", text)
    kept = [p for p in paragraphs if p.strip() and not _looks_like_evaluation_block(p)]
    return "\n\n".join(kept).strip()


def score_document(query: str, title: str, content: str, tags: str = "") -> float:
    query_terms = tokenize(query)
    if not query_terms:
        return 0.0

    title_terms = set(tokenize(title))
    tag_terms = set(tokenize(tags))
    body_terms = tokenize(content)
    body_set = set(body_terms)
    if not body_set and not title_terms and not tag_terms:
        return 0.0

    score = 0.0
    for term in query_terms:
        if term in title_terms:
            score += 3.0
        if term in tag_terms:
            score += 2.0
        if term in body_set:
            score += 1.0 + min(body_terms.count(term), 4) * 0.15

    coverage = len({term for term in query_terms if term in title_terms or term in tag_terms or term in body_set})
    return score + coverage * 0.4


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|[-| :]+\|$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def make_snippet(content: str, query: str, max_chars: int = 520) -> str:
    clean = re.sub(r"\s+", " ", _strip_markdown(content or "")).strip()
    if len(clean) <= max_chars:
        return clean

    normalized = normalize_text(clean)
    first_pos = None
    for term in tokenize(query):
        pos = normalized.find(term)
        if pos >= 0:
            first_pos = pos if first_pos is None else min(first_pos, pos)

    if first_pos is None:
        return clean[:max_chars].rstrip() + "..."

    start = max(0, first_pos - max_chars // 4)
    end = min(len(clean), start + max_chars)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return prefix + clean[start:end].strip() + suffix
