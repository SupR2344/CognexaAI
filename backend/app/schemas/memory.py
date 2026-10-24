"""Pydantic Schemas for Cognitive Memory Management."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MemoryTypeEnum(str, enum.Enum):
    """Supported categories of memories stored by Cognexa."""

    user_preference = "user_preference"
    project = "project"
    decision = "decision"
    episodic = "episodic"
    error = "error"
    task = "task"
    verified_knowledge = "verified_knowledge"


class MemoryCreate(BaseModel):
    """Payload to record a new memory."""

    memory_type: MemoryTypeEnum = Field(..., description="Category of the memory")
    content: str = Field(..., min_length=1, description="Memory text content")
    metadata_: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        alias="metadata_",
        description="Optional metadata such as confidence score, source file, or tags",
    )

    model_config = ConfigDict(populate_by_name=True)


class MemoryUpdate(BaseModel):
    """Payload to modify an existing memory."""

    content: Optional[str] = Field(default=None, description="Updated memory text")
    memory_type: Optional[MemoryTypeEnum] = Field(default=None, description="Updated memory type")
    metadata_: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="metadata_",
        description="Updated metadata dictionary",
    )

    model_config = ConfigDict(populate_by_name=True)


class MemoryResponse(BaseModel):
    """Schema representing a stored memory."""

    id: uuid.UUID
    memory_type: MemoryTypeEnum
    content: str
    metadata_: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    similarity: Optional[float] = Field(
        default=None,
        description="Cosine similarity score for search responses (0.0 - 1.0)",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MemorySearchRequest(BaseModel):
    """Query payload for semantic vector search over memories."""

    query: str = Field(..., min_length=1, description="Natural language search query")
    memory_type: Optional[MemoryTypeEnum] = Field(
        default=None,
        description="Filter by memory type (optional)",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of nearest memories to return",
    )


class MemorySearchResponse(BaseModel):
    """Results from semantic vector memory search."""

    query: str
    memories: List[MemoryResponse] = Field(default_factory=list)
    total: int = 0
