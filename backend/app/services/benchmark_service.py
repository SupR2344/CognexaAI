"""Benchmark and operational metrics for the Cognexa AI architecture."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.conversation import Conversation
from app.models.memory import Memory
from app.models.task import Task, TaskStatus
from app.models.user import User

logger = logging.getLogger(__name__)


class BenchmarkService:
    """Compute structured health and readiness metrics for the running system."""

    async def build_user_benchmark(self, db: AsyncSession, user_id: Any) -> Dict[str, Any]:
        """Create a benchmark snapshot for a user across tasks, chat, and memory."""
        total_conversations = (await db.execute(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user_id,
                Conversation.is_active == True,  # noqa: E712
            )
        )).scalar() or 0

        total_memories = (await db.execute(
            select(func.count(Memory.id)).where(
                Memory.user_id == user_id,
                Memory.is_active == True,  # noqa: E712
            )
        )).scalar() or 0

        total_tasks = (await db.execute(
            select(func.count(Task.id)).where(Task.user_id == user_id)
        )).scalar() or 0

        completed_tasks = (await db.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.completed,
            )
        )).scalar() or 0

        failed_tasks = (await db.execute(
            select(func.count(Task.id)).where(
                Task.user_id == user_id,
                Task.status == TaskStatus.failed,
            )
        )).scalar() or 0

        success_rate = 100.0
        if (completed_tasks + failed_tasks) > 0:
            success_rate = round((completed_tasks / (completed_tasks + failed_tasks)) * 100, 1)

        readiness_score = min(
            100.0,
            round(
                (
                    (total_conversations * 8)
                    + (total_memories * 5)
                    + (completed_tasks * 20)
                    + (failed_tasks * -10)
                ) / max(1, (total_tasks or 1) * 2 + 10),
                1,
            ) * 100,
        )

        benchmark = {
            "name": "cognexa-user-readiness",
            "status": "ok" if total_tasks > 0 or total_memories > 0 else "bootstrap",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scores": {
                "workflow_success_rate": success_rate,
                "workflow_readiness": readiness_score,
            },
            "summary": (
                "The user workspace is active and benchmark data is available. "
                if total_tasks or total_memories or total_conversations
                else "No benchmarkable activity has been recorded yet."
            ),
            "details": {
                "total_conversations": total_conversations,
                "total_memories": total_memories,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
            },
        }
        return benchmark

    async def build_system_snapshot(self, db: AsyncSession) -> Dict[str, Any]:
        """Build a system-level snapshot including database and LLM health."""
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
        total_tasks = (await db.execute(select(func.count(Task.id)))).scalar() or 0
        total_memories = (await db.execute(select(func.count(Memory.id)))).scalar() or 0

        completed_tasks = (await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.completed)
        )).scalar() or 0
        failed_tasks = (await db.execute(
            select(func.count(Task.id)).where(Task.status == TaskStatus.failed)
        )).scalar() or 0

        denominator = completed_tasks + failed_tasks
        success_rate = 100.0 if denominator == 0 else round((completed_tasks / denominator) * 100, 1)

        ollama_status = "unknown"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags")
                ollama_status = "healthy" if response.status_code == 200 else "degraded"
        except Exception as exc:  # pragma: no cover - runtime-dependent
            logger.warning("Ollama benchmark probe failed: %s", exc)
            ollama_status = "unreachable"

        snapshot = {
            "status": "healthy" if total_users > 0 else "bootstrapping",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system": {
                "database": "connected",
                "ollama": ollama_status,
                "users": total_users,
                "tasks": total_tasks,
                "memories": total_memories,
            },
            "benchmark": {
                "name": "cognexa-system-benchmark",
                "status": "ok" if total_tasks > 0 or total_memories > 0 else "bootstrap",
                "scores": {
                    "task_success_rate": success_rate,
                    "task_completion_volume": completed_tasks,
                    "task_failure_volume": failed_tasks,
                },
                "summary": "Operational benchmark snapshot generated for the active system state.",
            },
        }
        return snapshot
