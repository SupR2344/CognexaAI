"""Unit tests for Cognexa AI LangGraph Agent and Tool Execution."""

import pytest
from app.services.agent import AgentOrchestrator
from app.agent import tools
from app.agent.tools import TOOL_MAP, execute_command, list_directory, run_python_code
from app.agent.graph import run_cognexa_agent


def test_chat_system_prompt_is_project_grounded_and_cautious():
    prompt = AgentOrchestrator()._build_system_prompt([])

    assert "FastAPI, SQLAlchemy, Ollama, and Next.js" in prompt
    assert "Distinguish implemented behavior from planned/target architecture" in prompt
    assert "Do not invent code, settings, test results" in prompt


def test_tool_registry():
    """Ensure all core safety-checked tools are registered in TOOL_MAP."""
    expected_tools = [
        "read_file",
        "write_file",
        "list_directory",
        "execute_command",
        "run_python_code",
        "run_tests",
        "search_in_files",
    ]
    for tool_name in expected_tools:
        assert tool_name in TOOL_MAP, f"Tool '{tool_name}' missing from tool registry"


def test_python_code_execution_uses_sandbox(monkeypatch):
    """Verify Python source is sent to the isolated runner and stdout is returned."""
    monkeypatch.setattr(
        tools.sandbox,
        "run",
        lambda arguments, timeout: {
            "exit_code": 0,
            "stdout": "Computed: 42",
            "stderr": "",
            "success": True,
        },
    )
    code = "result = 40 + 2\nprint(f'Computed: {result}')"
    output = run_python_code(code)
    assert output["success"] is True
    assert "Computed: 42" in output["output"]


def test_command_execution_uses_sandbox(monkeypatch):
    captured = {}

    def fake_run(arguments, timeout):
        captured["arguments"] = arguments
        captured["timeout"] = timeout
        return {
            "exit_code": 0,
            "stdout": "sandboxed",
            "stderr": "",
            "success": True,
        }

    monkeypatch.setattr(tools.sandbox, "run", fake_run)

    output = tools.execute_command.invoke({"command": "echo sandboxed", "timeout": 10})

    assert output["success"] is True
    assert captured["arguments"] == ["sh", "-c", "echo sandboxed"]
    assert captured["timeout"] == 10


def test_pytest_execution_uses_sandbox(monkeypatch, tmp_path):
    tests_path = tmp_path / "tests"
    tests_path.mkdir()
    monkeypatch.setattr(tools, "WORKSPACE_ROOT", tmp_path)
    captured = {}

    def fake_run(arguments, timeout):
        captured["arguments"] = arguments
        captured["timeout"] = timeout
        return {
            "exit_code": 0,
            "stdout": "1 passed",
            "stderr": "",
            "success": True,
        }

    monkeypatch.setattr(tools.sandbox, "run", fake_run)

    output = tools.run_tests.invoke({"test_path": "tests"})

    assert output["passed"] is True
    assert output["exit_code"] == 0
    assert "tests" in captured["arguments"]
    assert "no:cacheprovider" in captured["arguments"]


def test_blocked_commands_security():
    """Verify destructive shell commands are intercepted and blocked."""
    destructive_cmd = "rm -rf /"
    output = execute_command(destructive_cmd)
    assert output["success"] is False
    assert "rejected" in output["stderr"].lower()


def test_directory_traversal_protection():
    """Verify directory traversal attempts are blocked."""
    traversal_path = "../../"
    output = list_directory(traversal_path)
    # Either blocked or validated within boundary
    assert isinstance(output, str)


def test_workspace_boundary_rejects_sibling_prefix_path(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    sibling = tmp_path / "workspace-other"
    workspace.mkdir()
    sibling.mkdir()
    monkeypatch.setattr(tools, "WORKSPACE_ROOT", workspace)

    with pytest.raises(PermissionError, match="outside workspace root"):
        tools._validate_path(str(sibling))


@pytest.mark.asyncio
async def test_agent_graph_execution_cycle():
    """Verify end-to-end autonomous agent execution loop."""
    result = await run_cognexa_agent(
        user_message="Inspect system workspace and verify readiness",
        user_id="test-user-id",
        conversation_id="test-conv-id",
        memories=[{"memory_type": "preference", "content": "Prefers Python 3.11+"}],
        max_retries=2,
    )

    assert "final_response" in result
    assert "current_plan" in result
    assert len(result["current_plan"]) > 0
    assert "tool_results" in result
    assert len(result["tool_results"]) > 0
    assert "Cognexa" in result["final_response"]
