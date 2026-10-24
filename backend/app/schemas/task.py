"""Pydantic Schemas for Tasks, Steps, and Execution Plans."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class TaskStepResponse(BaseModel):
    """Schema representing an individual step in a planned task."""

    id: uuid.UUID
    step_number: int
    description: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tool_output: Optional[Dict[str, Any]] = Field(default_factory=dict)
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    """Schema representing a complete autonomous task and its execution status."""

    id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    status: str
    plan: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    results: Optional[Dict[str, Any]] = Field(default_factory=dict)
    steps: List[TaskStepResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(BaseModel):
    """Payload to initiate a new autonomous task."""

    title: str = Field(..., min_length=1, max_length=255, description="Short task objective")
    description: Optional[str] = Field(default=None, description="Detailed instructions or goal")
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Linked conversation UUID",
    )
    plan: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="Optional pre-determined list of steps",
    )


class TaskStepApproveRequest(BaseModel):
    """Payload for human-in-the-loop task step approval or parameter override."""

    feedback: Optional[str] = Field(
        default=None,
        description="Optional human feedback or modification instructions for the step",
    )
    approved: bool = Field(
        default=True,
        description="Whether to proceed with execution or reject step",
    )
