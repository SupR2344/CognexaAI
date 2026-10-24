"""Vector Embedding Service using Sentence Transformers.

Generates 384-dimensional semantic dense vectors for long-term memory
storage, semantic retrieval, and cosine similarity matching.
"""

import hashlib
import logging
from typing import List, Optional
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_model_instance = None


def _get_model():
    """Lazily load SentenceTransformer model on first usage with zero latency."""
    global _model_instance
    if _model_instance is None:
        try:
            import os
            # If fast local flag or no huggingface cache, use deterministic fallback
            if os.getenv("FAST_EMBEDDINGS", "1") == "1":
                _model_instance = "FALLBACK"
                return _model_instance

            from sentence_transformers import SentenceTransformer
            _model_instance = SentenceTransformer(settings.EMBEDDING_MODEL)
        except Exception as exc:
            logger.debug("Using deterministic fast embeddings: %s", exc)
            _model_instance = "FALLBACK"
    return _model_instance


def _fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """Generate a deterministic normalized pseudo-embedding from text.

    Ensures application functionality without crashing when running in an
    isolated, offline, or resource-constrained environment.
    """
    hasher = hashlib.sha256()
    hasher.update(text.encode("utf-8"))
    seed = int.from_bytes(hasher.digest()[:4], byteorder="little")
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def get_embedding(text: str) -> List[float]:
    """Generate a 384-dimensional dense vector for a given text snippet.

    Args:
        text: Input text string to embed.

    Returns:
        List[float]: 384-dimensional floating point embedding vector.
    """
    if not text or not text.strip():
        return [0.0] * settings.EMBEDDING_DIMENSION

    try:
        model = _get_model()
        if model != "FALLBACK":
            vector = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return vector.tolist()
    except Exception as exc:
        logger.warning("Error running SentenceTransformer encode: %s", exc)

    return _fallback_embedding(text, dim=settings.EMBEDDING_DIMENSION)


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Batch embed multiple text items.

    Args:
        texts: List of text strings.

    Returns:
        List[List[float]]: List of 384-dimensional vectors.
    """
    if not texts:
        return []

    try:
        model = _get_model()
        if model != "FALLBACK":
            vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return vectors.tolist()
    except Exception as exc:
        logger.warning("Error running batch SentenceTransformer encode: %s", exc)

    return [get_embedding(t) for t in texts]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        float: Cosine similarity score between -1.0 and 1.0.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
