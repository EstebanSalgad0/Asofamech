from app.rag_utils import (
    chunk_text,
    cosine_similarity,
    embed_text,
    make_snippet,
    score_document,
    tokenize,
)


def test_tokenize_normalizes_accents_and_stopwords():
    assert tokenize("Metástasis en tejido linfático y salud") == [
        "metastasis",
        "tejido",
        "linfatico",
    ]


def test_score_document_prioritizes_title_and_tags():
    title_score = score_document(
        "metastasis ganglio",
        "Metastasis ganglionar",
        "Texto general",
        "",
    )
    body_score = score_document(
        "metastasis ganglio",
        "Texto general",
        "La metastasis aparece en ganglio linfatico.",
        "",
    )
    tag_score = score_document(
        "metastasis ganglio",
        "Texto general",
        "Sin coincidencia directa",
        "metastasis, ganglio",
    )

    assert title_score > body_score
    assert tag_score > body_score


def test_score_document_ignores_unrelated_content():
    assert score_document("diabetes", "Histologia", "Ganglio linfatico") == 0


def test_make_snippet_centers_relevant_content():
    content = "A" * 300 + " metastasis ganglionar confirmada " + "B" * 300
    snippet = make_snippet(content, "metastasis", max_chars=120)

    assert "metastasis ganglionar" in snippet
    assert len(snippet) <= 126


def test_embed_text_returns_normalized_deterministic_vector():
    first = embed_text("metastasis ganglionar")
    second = embed_text("metástasis ganglionar")

    assert first == second
    assert cosine_similarity(first, second) > 0.99
    assert cosine_similarity(first, embed_text("finanzas economia")) < 0.5


def test_chunk_text_splits_with_overlap():
    content = " ".join(f"palabra{i}" for i in range(260))
    chunks = chunk_text(content, max_tokens=100, overlap_tokens=20)

    assert len(chunks) == 3
    assert "palabra80" in chunks[1]
    assert "palabra180" in chunks[2]
