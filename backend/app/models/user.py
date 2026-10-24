"""User SQLAlchemy Model."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.memory import Memory
    from app.models.task import Task


class User(Base):
    """User account model for authentication, ownership, and authorization."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
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

    # Relationships
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Conversation.created_at.desc()",
    )
    memories: Mapped[List["Memory"]] = relationship(
        "Memory",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Memory.created_at.desc()",
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Task.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} email={self.email}>"
