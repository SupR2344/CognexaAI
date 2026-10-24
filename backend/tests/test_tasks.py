"""Tests for task planning and persisted execution outcomes."""

import asyncio
import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import Base
from app.services import agent as agent_module
from app.services.agent import agent_service
from app.services.task_recovery import recover_interrupted_tasks
from app.services.task_events import (
    publish_step_event,
    subscribe_to_step,
    unsubscribe_from_step,
)
from app.agent.graph import generate_approved_task_plan
from app.agent.tools import TOOL_MAP
from app.models.task import StepStatus, Task, TaskStatus, TaskStep
from app.models.user import User
from app.routes.tasks import (
    _finalize_task,
    replan_failed_task,
    _tool_result_succeeded,
    _store_terminal_task_memory,
    stream_task_step_logs,
    _verify_tool_output,
)


def _task_with_steps(*statuses: StepStatus) -> Task:
    task = Task(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Test task",
        status=TaskStatus.planning,
    )
    task.steps = [
        TaskStep(
            id=uuid.uuid4(),
            task_id=task.id,
            step_number=index,
            description=f"Step {index}",
            status=step_status,
        )
        for index, step_status in enumerate(statuses, start=1)
    ]
    return task


def test_task_plan_uses_registered_tools_and_valid_inputs():
    plan = agent_service.plan_task("Verify the project")

    assert len(plan) == 2
    for step in plan:
        tool = TOOL_MAP[step["tool_name"]]
        tool.args_schema(**step["tool_input"])


def test_generated_plan_only_allows_approved_workspace_tools():
    plan = agent_service._validate_task_plan(
        {
            "steps": [
                {
                    "description": "Inspect the repository files",
                    "tool_name": "list_directory",
                    "tool_input": {"path": "."},
                }
            ]
        }
    )

    assert plan[0]["step_number"] == 1
    assert plan[0]["tool_name"] == "list_directory"

    with pytest.raises(ValueError, match="disallowed tool"):
        agent_service._validate_task_plan(
            {
                "steps": [
                    {
                        "description": "Run a command",
                        "tool_name": "docker_control",
                        "tool_input": {"command": "whoami"},
                    }
                ]
            }
        )


def test_generated_plan_rejects_invalid_tool_arguments():
    with pytest.raises(ValueError, match="invalid tool input"):
        agent_service._validate_task_plan(
            {
                "steps": [
                    {
                        "description": "Inspect the repository",
                        "tool_name": "list_directory",
                        "tool_input": {"unexpected": True},
                    }
                ]
            }
        )


@pytest.mark.asyncio
async def test_generate_task_plan_parses_model_response(monkeypatch):
    request_capture = {}
    response_content = json.dumps(
        {
            "steps": [
                {
                    "description": "Inspect the project root",
                    "tool_name": "list_directory",
                    "tool_input": {"path": "."},
                }
            ]
        }
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": response_content}}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

        async def post(self, url, json):
            request_capture["url"] = url
            request_capture["payload"] = json
            return FakeResponse()

    monkeypatch.setattr(agent_module.httpx, "AsyncClient", FakeAsyncClient)

    plan = await agent_service.generate_task_plan(
        "Inspect the project",
        memories=[{"memory_type": "project", "content": "Uses FastAPI"}],
    )

    assert plan[0]["tool_name"] == "list_directory"
    assert request_capture["payload"]["format"] == "json"
    assert request_capture["url"].endswith("/api/chat")
    planner_input = json.loads(request_capture["payload"]["messages"][1]["content"])
    assert planner_input["recalled_context"][0]["content"] == "Uses FastAPI"


@pytest.mark.asyncio
async def test_approval_gated_task_planner_graph_only_generates_a_plan(monkeypatch):
    calls = {}
    expected_plan = [
        {
            "step_number": 1,
            "description": "Inspect files",
            "tool_name": "list_directory",
            "tool_input": {"path": "."},
        }
    ]

    async def fake_generate_task_plan(title, description, memories):
        calls.update(title=title, description=description, memories=memories)
        return expected_plan

    monkeypatch.setattr(
        agent_service,
        "generate_task_plan",
        fake_generate_task_plan,
    )

    plan = await generate_approved_task_plan(
        "Review workspace",
        "Review the project workspace",
        [{"memory_type": "project", "content": "FastAPI app"}],
    )

    assert plan == expected_plan
    assert calls["title"] == "Review workspace"
    assert calls["description"] == "Review the project workspace"
    assert calls["memories"][0]["content"] == "FastAPI app"


def test_tool_outputs_are_verified_using_evidence(tmp_path, monkeypatch):
    assert _verify_tool_output(
        "run_tests",
        {},
        {"exit_code": 0, "output": "2 passed", "errors": ""},
    )["status"] == "verified"
    assert _verify_tool_output(
        "run_tests",
        {},
        {"exit_code": 5, "output": "no tests ran", "errors": ""},
    )["status"] == "failed"
    assert _verify_tool_output(
        "execute_command",
        {},
        {"exit_code": 1, "stdout": "", "stderr": "failed"},
    )["status"] == "failed"

    written_file = tmp_path / "created.txt"
    written_file.write_text("verified output", encoding="utf-8")
    monkeypatch.setattr(
        "app.routes.tasks._validate_path",
        lambda path: written_file,
    )
    verification = _verify_tool_output(
        "write_file",
        {"file_path": "created.txt", "content": "verified output"},
        "Successfully wrote 15 bytes.",
    )
    assert verification["status"] == "verified"
    assert verification["expected_bytes"] == 15


@pytest.mark.asyncio
async def test_terminal_task_outcome_is_stored_as_memory(monkeypatch):
    task = _task_with_steps(StepStatus.completed)
    task.status = TaskStatus.completed
    task.title = "Add verified feature"
    captured = {}

    class FakeDB:
        def add(self, instance):
            captured["memory"] = instance

    monkeypatch.setattr(
        "app.routes.tasks.get_embedding",
        lambda content: [0.0] * 384,
    )

    await _store_terminal_task_memory(FakeDB(), task)

    memory = captured["memory"]
    assert memory.memory_type == "episodic"
    assert memory.metadata_["task_id"] == str(task.id)
    assert memory.metadata_["verification_status"] == "verified"
    assert task.results["memory_update"]["status"] == "stored"


def test_tool_result_success_uses_structured_evidence():
    assert _tool_result_succeeded({"success": True})
    assert _tool_result_succeeded({"passed": True})
    assert _tool_result_succeeded({"exit_code": 0})
    assert not _tool_result_succeeded({"success": False})
    assert not _tool_result_succeeded({"passed": False})
    assert not _tool_result_succeeded({"exit_code": 1})
    assert not _tool_result_succeeded({})
    assert not _tool_result_succeeded("Error: file missing")
    assert not _tool_result_succeeded("")


def test_failed_step_fails_task_and_skips_unrun_steps():
    task = _task_with_steps(StepStatus.failed, StepStatus.pending)

    _finalize_task(task)

    assert task.status == TaskStatus.failed
    assert task.steps[1].status == StepStatus.skipped
    assert task.results["completed_steps_count"] == 0
    assert task.results["failed_steps_count"] == 1
    assert task.results["skipped_steps_count"] == 1


def test_task_completes_only_when_all_steps_are_completed():
    task = _task_with_steps(StepStatus.completed, StepStatus.completed)

    _finalize_task(task)

    assert task.status == TaskStatus.completed
    assert task.results["completed_steps_count"] == 2


def test_rejected_or_skipped_step_cancels_task():
    task = _task_with_steps(StepStatus.skipped, StepStatus.pending)

    _finalize_task(task)

    assert task.status == TaskStatus.cancelled
    assert task.steps[1].status == StepStatus.skipped


def test_task_without_steps_is_not_reported_as_completed():
    task = _task_with_steps()

    _finalize_task(task)

    assert task.status == TaskStatus.failed


@pytest.mark.asyncio
async def test_restart_recovery_fails_running_steps_without_retrying():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    task = _task_with_steps(
        StepStatus.completed,
        StepStatus.running,
        StepStatus.pending,
    )
    async with session_factory() as session:
        session.add(task)
        await session.commit()

    async with session_factory() as session:
        assert await recover_interrupted_tasks(session) == 1

    async with session_factory() as session:
        recovered_task = await session.get(Task, task.id, options=[selectinload(Task.steps)])
        assert recovered_task is not None
        assert recovered_task.status == TaskStatus.failed
        assert [step.status for step in recovered_task.steps] == [
            StepStatus.completed,
            StepStatus.failed,
            StepStatus.skipped,
        ]
        assert recovered_task.steps[1].tool_output["status"] == "interrupted"
        assert "not retried automatically" in recovered_task.steps[1].error_message
        assert recovered_task.results["interrupted_steps"] == [2]
        assert await recover_interrupted_tasks(session) == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_task_replan_creates_new_pending_approval_task(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    user = User(
        id=uuid.uuid4(),
        username="replanner",
        email="replanner@example.test",
        hashed_password="not-a-real-password-hash",
    )
    failed_task = _task_with_steps(StepStatus.failed, StepStatus.skipped)
    failed_task.user_id = user.id
    failed_task.status = TaskStatus.failed
    failed_task.description = "Update the project"
    failed_task.steps[0].error_message = "Test command exited with status 1."

    async with session_factory() as session:
        session.add_all([user, failed_task])
        await session.commit()

    captured = {}

    async def fake_plan(title, description, memories=None):
        captured["title"] = title
        captured["description"] = description
        return [
            {
                "step_number": 1,
                "description": "Inspect current files before retrying",
                "tool_name": "list_directory",
                "tool_input": {"path": "."},
            }
        ]

    monkeypatch.setattr(
        "app.routes.tasks.generate_approved_task_plan",
        fake_plan,
    )

    async with session_factory() as session:
        revised = await replan_failed_task(
            task_id=failed_task.id,
            current_user=user,
            db=session,
        )

        assert revised.status == TaskStatus.pending
        assert revised.steps[0].status == StepStatus.pending
        assert revised.results["replanned_from_task_id"] == str(failed_task.id)
        assert "Test command exited with status 1." in captured["description"]
        assert "Inspect the current workspace" in captured["description"]
        assert captured["title"] == failed_task.title

    await engine.dispose()


@pytest.mark.asyncio
async def test_step_log_subscribers_receive_threaded_sandbox_output():
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    event_queue = await subscribe_to_step(task_id, step_id)

    await asyncio.to_thread(
        publish_step_event,
        task_id,
        step_id,
        {"type": "output", "stream": "stdout", "chunk": "live"},
    )

    event = await event_queue.get()
    assert event == {"type": "output", "stream": "stdout", "chunk": "live"}
    unsubscribe_from_step(task_id, step_id, event_queue)


@pytest.mark.asyncio
async def test_completed_step_log_endpoint_returns_persisted_output():
    task_id = uuid.uuid4()
    step = TaskStep(
        id=uuid.uuid4(),
        task_id=task_id,
        step_number=1,
        description="Run command",
        status=StepStatus.completed,
        tool_output={
            "output": {
                "stdout": "persisted stdout",
                "stderr": "persisted stderr",
            }
        },
    )

    class FakeResult:
        def scalar_one_or_none(self):
            return step

    class FakeDB:
        async def execute(self, statement):
            return FakeResult()

    response = await stream_task_step_logs(
        task_id=task_id,
        step_id=step.id,
        current_user=type("TestUser", (), {"id": uuid.uuid4()})(),
        db=FakeDB(),
    )
    events = [event async for event in response.body_iterator]
    body = "".join(events)

    assert '"type": "connected"' in body
    assert "persisted stdout" in body
    assert "persisted stderr" in body
    assert '"type": "complete"' in body
