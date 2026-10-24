"""Task and TaskStep SQLAlchemy Models for Agent Execution."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class TaskStatus(str, enum.Enum):
    """Execution status states for an autonomous agent task."""

    pending = "pending"
    planning = "planning"
    executing = "executing"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class StepStatus(str, enum.Enum):
    """Execution states for individual steps in a plan."""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class Task(Base):
    """Task model representing an agentic workflow goal, plan, and outcome."""

    __tablename__ = "tasks"

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
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status_enum", create_type=True),
        default=TaskStatus.pending,
        nullable=False,
        index=True,
    )
    plan: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Sequential list of planned steps",
    )
    results: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Structured artifacts and final outcomes",
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
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks",
    )
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
        back_populates="tasks",
    )
    steps: Mapped[List["TaskStep"]] = relationship(
        "TaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.step_number.asc()",
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} title={self.title} status={self.status}>"


class TaskStep(Base):
    """TaskStep model representing a distinct tool invocation or action step."""

    __tablename__ = "task_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    tool_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    tool_input: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    tool_output: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )
    status: Mapped[StepStatus] = mapped_column(
        SQLEnum(StepStatus, name="step_status_enum", create_type=True),
        default=StepStatus.pending,
        nullable=False,
        index=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=datetime.utcnow,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="steps",
    )

    def __repr__(self) -> str:
        return f"<TaskStep id={self.id} step={self.step_number} status={self.status}>"
