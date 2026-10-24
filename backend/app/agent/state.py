"""LangGraph Agent State definition for Cognexa AI."""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict
from langgraph.graph import add_messages


class AgentState(TypedDict):
    """Execution state tracked across the Cognexa LangGraph orchestrator graph."""

    messages: Annotated[Sequence[Any], add_messages]
    user_id: str
    conversation_id: str
    memories: List[Dict[str, Any]]  # Retrieved relevant memories
    task_title: Optional[str]
    task_description: Optional[str]
    current_plan: List[Dict[str, Any]]  # Current execution plan steps
    current_step: int  # Current step index
    task_id: Optional[str]  # Associated task ID
    tool_results: List[Dict[str, Any]]  # Results from tool executions
    verification_status: str  # pending, verified, failed
    retry_count: int
    max_retries: int
    error_log: List[str]
    final_response: str
