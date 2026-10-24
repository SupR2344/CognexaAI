"""Agent Task and Step Execution Management Routes.

Provides APIs to list tasks, inspect execution plans, approve pending
actions (Human-in-the-Loop), and abort workflows.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.auth.security import get_current_user
from app.agent.graph import generate_approved_task_plan
from app.database import get_db
from app.agent.tools import TOOL_MAP, _validate_path
from app.services.sandbox import sandbox
from app.services.task_events import (
    publish_step_event,
    subscribe_to_step,
    unsubscribe_from_step,
)
from app.models.memory import Memory, MemoryType
from app.models.task import StepStatus, Task, TaskStep, TaskStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse, TaskStepApproveRequest
from app.services.embedding import get_embedding
from app.services.verification_service import VerificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])
verification_service = VerificationService()


def _tool_result_succeeded(output: Any) -> bool:
    """Interpret a registered tool's result without treating arbitrary output as success."""
    if isinstance(output, dict):
        if "success" in output:
            return bool(output["success"])
        if "passed" in output:
            return bool(output["passed"])
        if "exit_code" in output:
            return output["exit_code"] == 0
        return False

    if not isinstance(output, str) or not output.strip():
        return False

    normalized = output.lstrip().lower()
    return not normalized.startswith(
        ("error:", "security error:", "search error:", "execution error:")
    )


def _skip_pending_steps(task: Task, reason: str) -> None:
    for step in task.steps:
        if step.status == StepStatus.pending:
            step.status = StepStatus.skipped
            step.error_message = reason


def _finalize_task(task: Task) -> None:
    """Set terminal task status only when its persisted step statuses justify it."""
    steps = task.steps
    failed_steps = [step for step in steps if step.status == StepStatus.failed]
    if failed_steps:
        task.status = TaskStatus.failed
        _skip_pending_steps(task, "Not run because an earlier task step failed.")
        summary = f"Task failed at step {failed_steps[0].step_number}."

    skipped_count = sum(step.status == StepStatus.skipped for step in steps)
    completed_count = sum(step.status == StepStatus.completed for step in steps)

    if not failed_steps and skipped_count:
        task.status = TaskStatus.cancelled
        _skip_pending_steps(task, "Not run because the task was cancelled.")
        summary = "Task cancelled before all steps were completed."
    elif not failed_steps and steps and completed_count == len(steps):
        task.status = TaskStatus.completed
        summary = "All task steps completed successfully."
    elif not failed_steps and not steps:
        task.status = TaskStatus.failed
        summary = "Task has no executable steps."
    elif not failed_steps:
        task.status = TaskStatus.executing
        summary = "Task is in progress."

    skipped_count = sum(step.status == StepStatus.skipped for step in steps)
    task.results = {
        "summary": summary,
        "completed_steps_count": completed_count,
        "failed_steps_count": len(failed_steps),
        "skipped_steps_count": skipped_count,
        "finalized_at": datetime.now(timezone.utc).isoformat(),
    }


def _verify_tool_output(
    tool_name: str,
    tool_input: Dict[str, Any],
    output: Any,
) -> Dict[str, Any]:
    """Verify tool output against execution evidence and approved write inputs."""
    if tool_name == "run_tests":
        return verification_service.verify_test_results(output)

    if tool_name in {"execute_command", "run_python_code"}:
        if not isinstance(output, dict):
            return {
                "status": "failed",
                "summary": "Sandbox returned an unexpected result type.",
            }
        stdout_key = "stdout" if tool_name == "execute_command" else "output"
        stderr_key = "stderr" if tool_name == "execute_command" else "errors"
        exit_code = output.get("exit_code")
        if not isinstance(exit_code, int):
            return {
                "status": "failed",
                "summary": "Sandbox did not report an exit code.",
            }
        return verification_service.verify_command_result(
            expected=tool_input.get("expected_output"),
            actual_stdout=str(output.get(stdout_key, "")),
            actual_stderr=str(output.get(stderr_key, "")),
            exit_code=exit_code,
        )

    if tool_name == "write_file":
        if not _tool_result_succeeded(output):
            return {
                "status": "failed",
                "summary": str(output)[:500],
            }
        try:
            target = _validate_path(str(tool_input["file_path"]))
            actual = target.read_text(encoding="utf-8")
        except (KeyError, OSError, UnicodeError, PermissionError) as exc:
            return {
                "status": "failed",
                "summary": f"Unable to verify written file: {exc}",
            }
        return verification_service.verify_file_write(
            expected=str(tool_input["content"]),
            actual=actual,
        )

    return verification_service.verify_observation(output)


async def _store_terminal_task_memory(db: AsyncSession, task: Task) -> None:
    """Persist a compact, evidence-based completion or failure for future retrieval."""
    if task.status not in (TaskStatus.completed, TaskStatus.failed):
        return

    completed = task.status == TaskStatus.completed
    if completed:
        verified_steps = [
            step.description
            for step in task.steps
            if step.status == StepStatus.completed
        ]
        outcome = (
            f"Task completed successfully. Verified steps: "
            f"{'; '.join(verified_steps[:6]) or 'No step details recorded'}."
        )
        memory_type = MemoryType.episodic
        confidence = 0.9
    else:
        failed_step = next(
            (step for step in task.steps if step.status == StepStatus.failed),
            None,
        )
        failure_description = (
            failed_step.description if failed_step else "No executable step completed"
        )
        error_type = verification_service.classify_error(
            failed_step.error_message or "" if failed_step else ""
        )["error_type"]
        outcome = (
            f"Task failed at step '{failure_description}' with error category "
            f"{error_type}. Review the recorded task execution evidence before retrying."
        )
        memory_type = MemoryType.error
        confidence = 0.6

    content = f"Workspace task '{task.title[:200]}'. {outcome}"
    embedding = await run_in_threadpool(get_embedding, content)
    db.add(
        Memory(
            user_id=task.user_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            metadata_={
                "source": "verified_task_outcome",
                "task_id": str(task.id),
                "verification_status": "verified" if completed else "failed",
                "confidence": confidence,
            },
        )
    )
    task.results = {
        **(task.results or {}),
        "memory_update": {
            "status": "stored",
            "memory_type": memory_type.value,
        },
    }


@router.get(
    "/",
    response_model=List[TaskResponse],
    summary="List all tasks created by the user",
)
async def list_tasks(
    status_filter: Optional[TaskStatus] = Query(
        default=None,
        alias="status",
        description="Filter tasks by status",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TaskResponse]:
    """Retrieve all autonomous workflow tasks with their respective execution steps."""
    stmt = (
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.user_id == current_user.id)
    )

    if status_filter is not None:
        stmt = stmt.where(Task.status == status_filter)

    stmt = stmt.order_by(desc(Task.created_at)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [TaskResponse.model_validate(t) for t in tasks]


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get details and step progress for a specific task",
)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Retrieve full execution metadata and step results for a specific task."""
    stmt = (
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/replan",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a revised approval-gated plan for a failed task",
)
async def replan_failed_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Create a separate task revision; failed actions are never retried implicitly."""
    stmt = (
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    source_task = result.scalar_one_or_none()

    if source_task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    if source_task.status != TaskStatus.failed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed tasks can be replanned.",
        )

    failed_steps = [step for step in source_task.steps if step.status == StepStatus.failed]
    failure_context = "\n".join(
        f"Failed step {step.step_number} ({step.description}): "
        f"{(step.error_message or 'No error details recorded')[:700]}"
        for step in failed_steps[:3]
    )[:2200]
    revised_description = (
        f"{(source_task.description or source_task.title)[:2500]}\n\n"
        "This is a revised plan for a previously failed task. Do not assume the failed "
        "action had no side effects. Inspect the current workspace before proposing "
        "any corrective action. Original failure evidence:\n"
        f"{failure_context or 'The task failed without a recorded failed step.'}"
    )[:6000]

    plan_steps = await generate_approved_task_plan(
        title=source_task.title,
        description=revised_description,
    )
    revised_task = Task(
        user_id=source_task.user_id,
        conversation_id=source_task.conversation_id,
        title=source_task.title[:255],
        description=revised_description,
        status=TaskStatus.pending,
        plan=plan_steps,
        results={
            "summary": "Revised plan created and waiting for user approval.",
            "replanned_from_task_id": str(source_task.id),
        },
    )
    revised_task.steps = [
        TaskStep(
            step_number=step_data["step_number"],
            description=step_data["description"],
            tool_name=step_data["tool_name"],
            tool_input=step_data["tool_input"],
            status=StepStatus.pending,
        )
        for step_data in plan_steps
    ]
    db.add(revised_task)
    await db.commit()
    refreshed_result = await db.execute(
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == revised_task.id)
    )
    refreshed_task = refreshed_result.scalar_one()
    return TaskResponse.model_validate(refreshed_task)


@router.post(
    "/{task_id}/approve",
    response_model=TaskResponse,
    summary="Approve and execute the next pending step in a task",
)
@router.post(
    "/{task_id}/steps/{step_id}/approve",
    response_model=TaskResponse,
    summary="Approve and execute a specific step in a task",
)
async def approve_task_step(
    task_id: uuid.UUID,
    step_id: Optional[uuid.UUID] = None,
    approval_body: Optional[TaskStepApproveRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Human-in-the-loop gatekeeper: approves and executes the next pending plan step."""
    stmt = (
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.user_id == current_user.id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.status in (TaskStatus.completed, TaskStatus.cancelled, TaskStatus.failed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve steps on a task with status: {task.status.value}",
        )
    if any(step.status == StepStatus.running for step in task.steps):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A task step is already running.",
        )

    # Locate target step (by step_id if provided, else next pending)
    if step_id:
        pending_step = next((s for s in task.steps if s.id == step_id), None)
        if pending_step is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task step not found",
            )
        if pending_step.status != StepStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve a task step with status: {pending_step.status.value}",
            )
    else:
        pending_step = next(
            (s for s in sorted(task.steps, key=lambda x: x.step_number) if s.status == StepStatus.pending),
            None,
        )

    if not pending_step:
        _finalize_task(task)
        await _store_terminal_task_memory(db, task)
        await db.commit()
        await db.refresh(task)
        return TaskResponse.model_validate(task)

    next_pending_step = next(
        (s for s in sorted(task.steps, key=lambda x: x.step_number) if s.status == StepStatus.pending),
        None,
    )
    if pending_step is not next_pending_step:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task steps must be approved in order.",
        )

    # If rejection was passed in approval payload
    if approval_body and not approval_body.approved:
        pending_step.status = StepStatus.skipped
        pending_step.error_message = f"Step rejected by user: {approval_body.feedback or 'No reason provided'}"
        _skip_pending_steps(task, "Not run because a task step was rejected.")
        _finalize_task(task)
        await db.commit()
        await db.refresh(task)
        return TaskResponse.model_validate(task)

    claim = await db.execute(
        update(TaskStep)
        .where(
            TaskStep.id == pending_step.id,
            TaskStep.task_id == task.id,
            TaskStep.status == StepStatus.pending,
        )
        .values(status=StepStatus.running)
    )
    if claim.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task step was already claimed for execution.",
        )

    # Execute step action
    pending_step.status = StepStatus.running
    task.status = TaskStatus.executing
    await db.commit()
    publish_step_event(
        task.id,
        pending_step.id,
        {"type": "status", "status": "running"},
    )

    actual_tool_name = pending_step.tool_name or ""
    tool_func = TOOL_MAP.get(actual_tool_name)

    output_raw: Any = None
    verification: Dict[str, Any]
    try:
        if tool_func:
            t_input = pending_step.tool_input or {}
            schema_fields = getattr(tool_func.args_schema, "model_fields", None)
            if schema_fields is None:
                schema_fields = getattr(tool_func.args_schema, "__fields__", {})
            if not isinstance(t_input, dict) or set(t_input) - set(schema_fields):
                raise ValueError("Task contains unsupported tool input fields.")
            tool_func.args_schema(**t_input)
            if isinstance(t_input, dict):
                if hasattr(tool_func, "invoke"):
                    output_raw = await run_in_threadpool(
                        _invoke_approved_tool,
                        tool_func,
                        t_input,
                        task.id,
                        pending_step.id,
                    )
                else:
                    output_raw = await run_in_threadpool(
                        _invoke_approved_tool,
                        tool_func,
                        t_input,
                        task.id,
                        pending_step.id,
                    )
            elif isinstance(t_input, str):
                if hasattr(tool_func, "invoke"):
                    output_raw = await run_in_threadpool(
                        _invoke_approved_tool,
                        tool_func,
                        t_input,
                        task.id,
                        pending_step.id,
                    )
                else:
                    output_raw = await run_in_threadpool(
                        _invoke_approved_tool,
                        tool_func,
                        t_input,
                        task.id,
                        pending_step.id,
                    )
            else:
                output_raw = await run_in_threadpool(
                    _invoke_approved_tool,
                    tool_func,
                    {},
                    task.id,
                    pending_step.id,
                )
            verification = _verify_tool_output(actual_tool_name, t_input, output_raw)
        else:
            output_raw = f"Tool '{actual_tool_name}' is not registered."
            verification = {
                "status": "failed",
                "summary": output_raw,
            }
    except Exception as exc:
        logger.exception("Task %s step %s execution failed.", task.id, pending_step.step_number)
        output_raw = {"error": str(exc)}
        verification = {
            "status": "failed",
            "summary": f"Tool execution failed: {exc}",
        }

    is_success = verification.get("status") == "verified"

    execution_result = {
        "status": "success" if is_success else "warning",
        "tool": actual_tool_name,
        "output": output_raw,
        "verification": verification,
        "approval_feedback": approval_body.feedback if approval_body else None,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    pending_step.tool_output = execution_result
    pending_step.status = StepStatus.completed if is_success else StepStatus.failed
    pending_step.completed_at = datetime.now(timezone.utc)
    if not is_success:
        pending_step.error_message = str(verification.get("summary", "Verification failed"))[:1000]
        _skip_pending_steps(task, "Not run because an earlier task step failed.")

    _finalize_task(task)
    await _store_terminal_task_memory(db, task)

    await db.commit()
    await db.refresh(task)
    publish_step_event(
        task.id,
        pending_step.id,
        {"type": "complete", "status": pending_step.status.value},
    )

    logger.info("Executed step %s for task %s", pending_step.step_number, task.id)
    return TaskResponse.model_validate(task)


def _invoke_approved_tool(
    tool_func: Any,
    tool_input: Any,
    task_id: uuid.UUID,
    step_id: uuid.UUID,
) -> Any:
    """Invoke an approved tool while forwarding sandbox output to live subscribers."""
    callback = lambda stream, chunk: publish_step_event(
        task_id,
        step_id,
        {"type": "output", "stream": stream, "chunk": chunk},
    )
    with sandbox.capture_output(callback):
        if isinstance(tool_input, dict):
            if hasattr(tool_func, "invoke"):
                return tool_func.invoke(tool_input)
            return tool_func(**tool_input)
        if isinstance(tool_input, str):
            if hasattr(tool_func, "invoke"):
                return tool_func.invoke(tool_input)
            return tool_func(tool_input)
        if hasattr(tool_func, "invoke"):
            return tool_func.invoke({})
        return tool_func()


@router.get(
    "/{task_id}/steps/{step_id}/logs",
    summary="Stream live output for an approved task step",
)
async def stream_task_step_logs(
    task_id: uuid.UUID,
    step_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    stmt = (
        select(TaskStep)
        .join(Task, Task.id == TaskStep.task_id)
        .where(
            Task.id == task_id,
            TaskStep.id == step_id,
            Task.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task step not found",
        )

    event_queue = await subscribe_to_step(task_id, step_id)

    async def event_generator():
        started_at = asyncio.get_running_loop().time()
        try:
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            if step.status in (StepStatus.completed, StepStatus.failed, StepStatus.skipped):
                output = step.tool_output or {}
                raw_output = output.get("output")
                if isinstance(raw_output, dict):
                    for stream_name in ("stdout", "stderr", "output", "errors"):
                        text = raw_output.get(stream_name)
                        if isinstance(text, str) and text:
                            yield (
                                "data: "
                                + json.dumps(
                                    {
                                        "type": "output",
                                        "stream": stream_name,
                                        "chunk": text,
                                    }
                                )
                                + "\n\n"
                            )
                yield (
                    "data: "
                    + json.dumps({"type": "complete", "status": step.status.value})
                    + "\n\n"
                )
                return

            while asyncio.get_running_loop().time() - started_at < 300:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "complete":
                    return
        finally:
            unsubscribe_from_step(task_id, step_id, event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/{task_id}/cancel",
    response_model=TaskResponse,
    summary="Cancel a task and halt any pending execution steps",
)
async def cancel_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Abort an in-progress or pending task and mark remaining steps as skipped."""
    stmt = (
        select(Task)
        .options(selectinload(Task.steps))
        .where(Task.id == task_id, Task.user_id == current_user.id)
        .with_for_update()
    )
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if any(step.status == StepStatus.running for step in task.steps):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot cancel while a task step is running.",
        )

    task.status = TaskStatus.cancelled

    for step in task.steps:
        if step.status in (StepStatus.pending, StepStatus.running):
            step.status = StepStatus.skipped
            step.error_message = "Step skipped due to workflow cancellation"

    await db.commit()
    await db.refresh(task)

    logger.info("Cancelled task %s for user %s", task.id, current_user.username)
    return TaskResponse.model_validate(task)
