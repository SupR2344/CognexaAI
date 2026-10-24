"""Dashboard and Analytics Routes.

Aggregates operational metrics, chronological activity timelines,
and tool execution audit logs.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_current_user
from app.database import get_db
from app.models.conversation import Conversation, Message
from app.models.memory import Memory
from app.models.task import StepStatus, Task, TaskStep, TaskStatus
from app.models.user import User
from app.services.benchmark_service import BenchmarkService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
benchmark_service = BenchmarkService()


@router.get(
    "/benchmark",
    summary="Get a benchmark summary for the authenticated user's workflow state",
)
async def get_user_benchmark(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return a benchmark snapshot capturing workflow readiness and task success trends."""
    return await benchmark_service.build_user_benchmark(db, current_user.id)


@router.get(
    "/stats",
    summary="Get user aggregate metrics and task success rates",
)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate aggregate statistics across conversations, memories, and workflows."""
    # Conversations count
    conv_stmt = select(func.count(Conversation.id)).where(
        Conversation.user_id == current_user.id,
        Conversation.is_active == True,  # noqa: E712
    )
    total_conversations = (await db.execute(conv_stmt)).scalar() or 0

    # Memories count
    mem_stmt = select(func.count(Memory.id)).where(
        Memory.user_id == current_user.id,
        Memory.is_active == True,  # noqa: E712
    )
    total_memories = (await db.execute(mem_stmt)).scalar() or 0

    # Total tasks count
    tasks_stmt = select(func.count(Task.id)).where(Task.user_id == current_user.id)
    total_tasks = (await db.execute(tasks_stmt)).scalar() or 0

    # Completed tasks
    completed_stmt = select(func.count(Task.id)).where(
        Task.user_id == current_user.id,
        Task.status == TaskStatus.completed,
    )
    completed_tasks = (await db.execute(completed_stmt)).scalar() or 0

    # Failed tasks
    failed_stmt = select(func.count(Task.id)).where(
        Task.user_id == current_user.id,
        Task.status == TaskStatus.failed,
    )
    failed_tasks = (await db.execute(failed_stmt)).scalar() or 0

    # Success rate calculation
    decided_tasks = completed_tasks + failed_tasks
    if decided_tasks > 0:
        success_rate = round((completed_tasks / decided_tasks) * 100, 1)
    elif total_tasks > 0:
        success_rate = 100.0
    else:
        success_rate = 100.0

    return {
        "total_conversations": total_conversations,
        "total_memories": total_memories,
        "memories_stored": total_memories,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "tasks_completed": completed_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": success_rate,
    }



@router.get(
    "/activity",
    summary="Get recent activity timeline across all modules",
)
async def get_recent_activity(
    limit: int = Query(default=15, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Synthesize a unified chronological timeline of user agent events."""
    activities: List[Dict[str, Any]] = []

    # 1. Recent Tasks
    t_stmt = (
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(desc(Task.updated_at))
        .limit(limit)
    )
    tasks = (await db.execute(t_stmt)).scalars().all()
    for t in tasks:
        activities.append({
            "id": str(t.id),
            "type": "task",
            "title": f"Task: {t.title}",
            "description": f"Status: {t.status.value}",
            "timestamp": t.updated_at.isoformat() if t.updated_at else t.created_at.isoformat(),
            "status": t.status.value,
        })

    # 2. Recent Memories
    m_stmt = (
        select(Memory)
        .where(
            Memory.user_id == current_user.id,
            Memory.is_active == True,  # noqa: E712
        )
        .order_by(desc(Memory.created_at))
        .limit(limit)
    )
    memories = (await db.execute(m_stmt)).scalars().all()
    for m in memories:
        m_type = m.memory_type.value if hasattr(m.memory_type, "value") else str(m.memory_type)
        activities.append({
            "id": str(m.id),
            "type": "memory",
            "title": f"Memory stored ({m_type})",
            "description": (m.content[:80] + "...") if len(m.content) > 80 else m.content,
            "timestamp": m.created_at.isoformat(),
            "status": "retained",
        })

    # 3. Recent Conversations
    c_stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.is_active == True,  # noqa: E712
        )
        .order_by(desc(Conversation.created_at))
        .limit(limit)
    )
    conversations = (await db.execute(c_stmt)).scalars().all()
    for c in conversations:
        activities.append({
            "id": str(c.id),
            "type": "chat",
            "title": f"Conversation: {c.title}",
            "description": "Chat session active",
            "timestamp": c.created_at.isoformat(),
            "status": "active" if c.is_active else "archived",
        })

    # Sort descending by timestamp
    activities.sort(key=lambda a: a["timestamp"], reverse=True)
    return activities[:limit]


@router.get(
    "/execution-logs",
    summary="Get recent tool and action execution logs",
)
@router.get(
    "/logs",
    summary="Get recent tool and action execution logs (alias)",
)
async def get_execution_logs(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Retrieve audit trail of step executions and tool outputs."""
    stmt = (
        select(TaskStep, Task.title)
        .join(Task, TaskStep.task_id == Task.id)
        .where(Task.user_id == current_user.id)
        .order_by(desc(TaskStep.created_at))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    logs: List[Dict[str, Any]] = []
    for step, task_title in rows:
        status_val = step.status.value if hasattr(step.status, "value") else str(step.status)
        level = "error" if step.error_message or status_val == "failed" else "info"
        iso_time = step.created_at.isoformat() if step.created_at else datetime.utcnow().isoformat()

        logs.append({
            "id": str(step.id),
            "step_id": str(step.id),
            "task_id": str(step.task_id),
            "task_title": task_title,
            "step_number": step.step_number,
            "description": step.description,
            "tool_name": step.tool_name,
            "tool_input": step.tool_input,
            "tool_output": step.tool_output,
            "status": status_val,
            "error_message": step.error_message,
            "created_at": iso_time,
            "timestamp": iso_time,
            "completed_at": step.completed_at.isoformat() if step.completed_at else None,
            "level": level,
            "module": step.tool_name or "agent.orchestrator",
            "message": f"Step {step.step_number}: {step.description}",
            "details": {
                "task": task_title,
                "tool": step.tool_name,
                "input": step.tool_input,
                "output": step.tool_output,
                "error": step.error_message,
            },
        })

    return logs

