"""Memory SQLAlchemy Model for Cognitive Long-Term Storage."""

from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, JSON, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy import JSON as VectorFallback
    Vector = lambda dim: VectorFallback

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class MemoryType(str, enum.Enum):
    """Types of cognitive memories retained by Cognexa AI."""

    user_preference = "user_preference"
    project = "project"
    decision = "decision"
    episodic = "episodic"
    error = "error"
    task = "task"
    verified_knowledge = "verified_knowledge"


class Memory(Base):
    """Cognitive memory entity with vector embeddings for semantic recall."""

    __allow_unmapped__ = True
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_type: Mapped[MemoryType] = mapped_column(
        SQLEnum(MemoryType, name="memory_type_enum", create_type=True),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    embedding: Mapped[Optional[Any]] = mapped_column(
        Vector(384),
        nullable=True,
        comment="384-dimensional vector embedding from sentence-transformers",
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default=dict,
        comment="Includes provenance, confidence, project_association, etc.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=datetime.utcnow,
        default=datetime.utcnow,
        nullable=False,
    )

    # Dynamic attribute for search ranking (not persisted in database)
    similarity: ClassVar[Optional[float]] = None

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="memories",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert memory entity to dictionary."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "memory_type": self.memory_type.value if hasattr(self.memory_type, "value") else str(self.memory_type),
            "content": self.content,
            "metadata": self.metadata_,
            "is_active": self.is_active,
            "similarity": self.similarity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<Memory id={self.id} type={self.memory_type} user_id={self.user_id}>"
