"""Recovery of task steps interrupted by a backend restart."""

from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import StepStatus, Task, TaskStatus

logger = logging.getLogger(__name__)


async def recover_interrupted_tasks(db: AsyncSession) -> int:
    """Fail in-flight steps after restart without retrying potentially completed side effects."""
    result = await db.execute(
        select(Task)
        .join(Task.steps)
        .options(selectinload(Task.steps))
        .where(Task.steps.any(status=StepStatus.running))
    )
    tasks = result.unique().scalars().all()
    if not tasks:
        return 0

    recovered_at = datetime.now(timezone.utc).isoformat()
    for task in tasks:
        interrupted_steps = []
        for step in task.steps:
            if step.status == StepStatus.running:
                step.status = StepStatus.failed
                step.completed_at = datetime.now(timezone.utc)
                step.error_message = (
                    "Backend restarted while this step was running; its outcome is unknown. "
                    "The step was not retried automatically."
                )
                step.tool_output = {
                    "status": "interrupted",
                    "tool": step.tool_name,
                    "verification": {
                        "status": "failed",
                        "summary": step.error_message,
                    },
                    "execution_timestamp": recovered_at,
                }
                interrupted_steps.append(step.step_number)
            elif step.status == StepStatus.pending:
                step.status = StepStatus.skipped
                step.error_message = "Not run because an earlier step was interrupted."

        task.status = TaskStatus.failed
        task.results = {
            **(task.results or {}),
            "summary": "Task interrupted by backend restart; execution outcome is unknown.",
            "interrupted_steps": interrupted_steps,
            "completed_steps_count": sum(
                step.status == StepStatus.completed for step in task.steps
            ),
            "failed_steps_count": sum(
                step.status == StepStatus.failed for step in task.steps
            ),
            "skipped_steps_count": sum(
                step.status == StepStatus.skipped for step in task.steps
            ),
            "recovered_at": recovered_at,
        }
        logger.warning(
            "Marked task %s failed after restart; interrupted steps: %s",
            task.id,
            interrupted_steps,
        )

    await db.commit()
    return len(tasks)
