"""Cognexa AI Service Layer."""

from typing import Any

from app.services.embedding import get_embedding, get_embeddings

__all__ = [
    "get_embedding",
    "get_embeddings",
    "agent_service",
]


def __getattr__(name: str) -> Any:
    if name == "agent_service":
        from app.services.agent import agent_service

        return agent_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
