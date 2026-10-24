"""Unit tests for Cognexa AI Vector Embedding and Memory Engine."""

import pytest
from app.services.embedding import cosine_similarity, get_embedding


def test_embedding_dimensions():
    """Ensure embedding generator returns 384-dimensional dense vectors."""
    text = "Autonomous AI agents with persistent vector memory"
    vec = get_embedding(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    for val in vec:
        assert isinstance(val, float)


def test_cosine_similarity_identical():
    """Identical vectors should yield a cosine similarity of approximately 1.0."""
    vec1 = [0.1, 0.2, 0.3, 0.4]
    sim = cosine_similarity(vec1, vec1)
    assert pytest.approx(sim, abs=1e-4) == 1.0


def test_cosine_similarity_orthogonal():
    """Orthogonal vectors should yield a cosine similarity of 0.0."""
    vec1 = [1.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0]
    sim = cosine_similarity(vec1, vec2)
    assert pytest.approx(sim, abs=1e-4) == 0.0


def test_semantic_ranking():
    """Verify that semantically related texts have higher cosine similarity than unrelated texts."""
    query = "FastAPI backend architecture with PostgreSQL"
    related = "Python asynchronous API service using postgres database"
    unrelated = "Baking chocolate chip cookies with organic butter"

    q_vec = get_embedding(query)
    rel_vec = get_embedding(related)
    unrel_vec = get_embedding(unrelated)

    rel_score = cosine_similarity(q_vec, rel_vec)
    unrel_score = cosine_similarity(q_vec, unrel_vec)

    assert rel_score > unrel_score
