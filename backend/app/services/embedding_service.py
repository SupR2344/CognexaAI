"""Embedding Service for Cognexa AI.

Uses sentence-transformers to generate dense vector embeddings for semantic search
and context retrieval, implementing a singleton pattern to ensure the model is loaded once.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

# Fallback config resolution
try:
    from app.core.config import settings  # type: ignore

    DEFAULT_EMBEDDING_MODEL = getattr(
        settings, "EMBEDDING_MODEL", getattr(settings, "embedding_model", "all-MiniLM-L6-v2")
    )
except Exception:
    DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")


class EmbeddingService:
    """Singleton service for generating vector embeddings via sentence-transformers."""

    _instance: Optional[EmbeddingService] = None
    _lock: threading.Lock = threading.Lock()
    _model_name: Optional[str] = None
    _model_instance = None

    def __new__(cls, model_name: Optional[str] = None) -> EmbeddingService:
        """Ensure singleton pattern so model is only instantiated once."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingService, cls).__new__(cls)
                cls._instance._initialized = False  # type: ignore[attr-defined]
            return cls._instance

    def __init__(self, model_name: Optional[str] = None) -> None:
        """Initialize embedding model if not already initialized.

        Args:
            model_name: Optional sentence-transformer model name or path.
                        Defaults to config / EMBEDDING_MODEL ("all-MiniLM-L6-v2").
        """
        if getattr(self, "_initialized", False):
            return

        with self._lock:
            if getattr(self, "_initialized", False):
                return

            chosen_model = model_name or DEFAULT_EMBEDDING_MODEL or "all-MiniLM-L6-v2"
            self._model_name = chosen_model
            logger.info("Initializing EmbeddingService with model: %s", chosen_model)

            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._model_instance = SentenceTransformer(chosen_model)
                logger.info("SentenceTransformer model '%s' loaded successfully.", chosen_model)
            except Exception as err:
                logger.error(
                    "Failed to load SentenceTransformer model '%s': %s",
                    chosen_model,
                    err,
                    exc_info=True,
                )
                raise RuntimeError(
                    f"Could not load embedding model '{chosen_model}': {err}"
                ) from err

            self._initialized = True

    @property
    def model_name(self) -> str:
        """Return the active model name."""
        return self._model_name or "all-MiniLM-L6-v2"

    def embed(self, text: str) -> List[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Text string to embed.

        Returns:
            List of float values representing the dense embedding vector.
        """
        if not text or not text.strip():
            # Return zero vector with matching dimension if empty
            if self._model_instance is not None:
                dim = self._model_instance.get_sentence_embedding_dimension()
                return [0.0] * dim
            return [0.0] * 384

        try:
            embedding = self._model_instance.encode(text, convert_to_numpy=True)
            return [float(x) for x in embedding.tolist()]
        except Exception as err:
            logger.error("Failed to generate embedding for text: %s", err, exc_info=True)
            raise RuntimeError(f"Embedding error: {err}") from err

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (list of float lists).
        """
        if not texts:
            return []

        # Replace empty strings with whitespace to preserve vector alignment
        cleaned = [t if t and t.strip() else " " for t in texts]

        try:
            embeddings = self._model_instance.encode(
                cleaned,
                convert_to_numpy=True,
                batch_size=32,
                show_progress_bar=False,
            )
            return [[float(x) for x in emb.tolist()] for emb in embeddings]
        except Exception as err:
            logger.error("Failed to generate batch embeddings: %s", err, exc_info=True)
            raise RuntimeError(f"Batch embedding error: {err}") from err


def get_embedding_service(model_name: Optional[str] = None) -> EmbeddingService:
    """Dependency provider function for EmbeddingService.

    Args:
        model_name: Optional model name override.

    Returns:
        Singleton EmbeddingService instance.
    """
    return EmbeddingService(model_name=model_name)
