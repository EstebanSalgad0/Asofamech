from app.embedding_service import embedding_status_for_rag, embed_text_for_rag
from app.pgvector_store import vector_literal
from app.rag_utils import EMBEDDING_DIMENSIONS


def test_embed_text_for_rag_can_disable_neural_provider():
    result = embed_text_for_rag("metastasis ganglionar", neural_enabled=False)

    assert result.provider == "local-hashing"
    assert result.neural is False
    assert len(result.vector) == EMBEDDING_DIMENSIONS


def test_embedding_status_does_not_load_model_when_neural_disabled():
    result = embedding_status_for_rag(neural_enabled=False)

    assert result.provider == "local-hashing"
    assert result.neural is False
    assert result.vector == []


def test_vector_literal_matches_pgvector_syntax():
    literal = vector_literal([0.1, -0.2, 0.3])

    assert literal.startswith("[")
    assert literal.endswith("]")
    assert "0.10000000" in literal
    assert "-0.20000000" in literal
