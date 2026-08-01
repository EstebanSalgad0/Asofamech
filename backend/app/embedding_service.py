import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib.util import find_spec

from .rag_utils import EMBEDDING_DIMENSIONS, embed_text as hash_embed_text


logger = logging.getLogger(__name__)
# Modelo multilingue: el corpus y las consultas del chatbot estan en espanol.
# all-MiniLM-L6-v2 solo esta entrenado en ingles y hunde los scores de similitud.
# paraphrase-multilingual-MiniLM-L12-v2 mantiene 384 dimensiones, por lo que es
# reemplazo directo sin cambios en el esquema de pgvector.
DEFAULT_SENTENCE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    provider: str
    neural: bool


def _truthy(value: str | bool | None, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}


@lru_cache(maxsize=2)
def _load_sentence_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _fit_dimensions(vector: list[float], dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    if len(vector) == dimensions:
        return vector
    if len(vector) > dimensions:
        return vector[:dimensions]
    return vector + [0.0] * (dimensions - len(vector))


def embedding_status_for_rag(
    model_name: str | None = None,
    neural_enabled: bool | str | None = None,
) -> EmbeddingResult:
    enabled = _truthy(
        neural_enabled if neural_enabled is not None else os.getenv("RAG_NEURAL_EMBEDDINGS_ENABLED"),
        True,
    )
    selected_model = model_name or os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_SENTENCE_MODEL)
    if enabled and find_spec("sentence_transformers") is not None:
        return EmbeddingResult(
            vector=[],
            provider=f"sentence-transformers:{selected_model}",
            neural=True,
        )
    return EmbeddingResult(vector=[], provider="local-hashing", neural=False)


def embed_text_for_rag(
    text: str,
    model_name: str | None = None,
    neural_enabled: bool | str | None = None,
) -> EmbeddingResult:
    enabled = _truthy(
        neural_enabled if neural_enabled is not None else os.getenv("RAG_NEURAL_EMBEDDINGS_ENABLED"),
        True,
    )
    selected_model = model_name or os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_SENTENCE_MODEL)

    if enabled:
        try:
            model = _load_sentence_model(selected_model)
            encoded = model.encode(text or "", normalize_embeddings=True)
            vector = [float(value) for value in encoded.tolist()]
            return EmbeddingResult(
                vector=_fit_dimensions(vector),
                provider=f"sentence-transformers:{selected_model}",
                neural=True,
            )
        except Exception as exc:  # pragma: no cover - depends on optional model files
            logger.warning(
                "No se pudo usar sentence-transformers (%s). Se usara embedding local por hashing.",
                exc,
            )

    return EmbeddingResult(
        vector=hash_embed_text(text),
        provider="local-hashing",
        neural=False,
    )
