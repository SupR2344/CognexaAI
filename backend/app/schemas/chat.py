"""Pydantic Schemas for Chat Conversations and Messages."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Schema for sending a new message to the AI agent."""

    message: str = Field(..., min_length=1, description="User prompt or instruction")
    use_memory: bool = Field(
        default=True,
        description="Whether to retrieve relevant long-term memories for this message",
    )
    conversation_id: Optional[Union[uuid.UUID, str]] = Field(
        default=None,
        description="Optional existing conversation UUID or ID string. If None or non-UUID, a new conversation is initiated.",
    )
    model: Optional[str] = Field(
        default="Cognexa 2.0 Pro",
        description="Active model or mode selected by user (Cognexa 2.0 Pro, Qwen 2.5 7B Core, Deep Research Mode, Multi-Agent Swarm)",
    )


class ChatResponse(BaseModel):
    """Response returned after processing a user message."""

    response: str = Field(..., description="Agent text response")
    reply: Optional[str] = Field(default=None, description="Alias for response")
    conversation_id: uuid.UUID = Field(..., description="Active conversation UUID")
    task_created: bool = Field(
        default=False,
        description="Whether an autonomous background task/plan was generated",
    )
    task_id: Optional[uuid.UUID] = Field(
        default=None,
        description="UUID of created task, if applicable",
    )
    memories_used: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of relevant episodic and knowledge memories used for context",
    )

    def model_post_init(self, __context: Any) -> None:
        if not self.reply:
            self.reply = self.response


class MessageResponse(BaseModel):
    """Schema for individual message items."""

    id: uuid.UUID
    role: str
    content: str
    metadata_: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ConversationResponse(BaseModel):
    """Full conversation details including historical messages."""

    id: uuid.UUID
    title: str
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    """Summarized conversation entry for listings."""

    id: uuid.UUID
    title: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)
