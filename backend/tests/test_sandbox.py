"""Tests for the Docker sandbox runner without requiring a live Docker daemon."""

import io
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.sandbox import DockerSandbox


def test_runner_uses_restricted_read_only_container_and_redacts_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (tmp_path / "main.py").write_text("print('safe')", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=do-not-copy", encoding="utf-8")
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        mount = command[command.index("--mount") + 1]
        staged_workspace = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
        captured["workspace_files"] = {path.name for path in staged_workspace.iterdir()}
        return SimpleNamespace(returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr("app.services.sandbox.subprocess.run", fake_run)
    runner = DockerSandbox(workspace_root=tmp_path, image="cognexa-test", volume_from="")

    result = runner.run(["python", "-c", "print('ok')"], timeout=10)

    command = captured["command"]
    assert result["success"] is True
    assert result["stdout"] == "ok\n"
    assert captured["workspace_files"] == {"main.py"}
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--memory") + 1] == "512m"
    assert command[command.index("--cpus") + 1] == "1.0"
    assert command[command.index("--pids-limit") + 1] == "128"
    assert command[-4:] == ["cognexa-test", "python", "-c", "print('ok')"]


def test_volume_from_runner_masks_secrets_and_workspace_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    (tmp_path / ".env").write_text("TOKEN=hidden", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / ".env").write_text("TOKEN=hidden", encoding="utf-8")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.services.sandbox.subprocess.run", fake_run)
    runner = DockerSandbox(
        workspace_root=tmp_path,
        image="cognexa-test",
        volume_from="cognexa-backend",
    )

    result = runner.run(["python", "--version"], timeout=10)

    command = captured["command"]
    assert result["success"] is True
    assert command[command.index("--volumes-from") + 1] == "cognexa-backend:ro"
    assert any("/workspace/.env,readonly" in argument for argument in command)
    assert any("/workspace/backend/.env,readonly" in argument for argument in command)
    assert not any("/var/run/docker.sock" in argument for argument in command)
    assert command[command.index("--tmpfs") + 1].startswith("/tmp:")


def test_timeout_stops_named_sandbox_container(monkeypatch: pytest.MonkeyPatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, timeout=5, output=b"partial")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.services.sandbox.subprocess.run", fake_run)
    runner = DockerSandbox(workspace_root=Path("."), image="cognexa-test", volume_from="backend")

    result = runner.run(["python", "-c", "pass"], timeout=5)

    assert result["exit_code"] == 124
    assert result["stdout"] == "partial"
    assert result["success"] is False
    assert calls[1][1:3] == ["stop", "--time"]
    assert calls[0][calls[0].index("--name") + 1] in calls[1]


def test_runner_streams_output_when_capture_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = []

    class FakeProcess:
        def __init__(self, command, **kwargs):
            self.stdout = io.BytesIO(b"live stdout\n")
            self.stderr = io.BytesIO(b"live stderr\n")

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

        def kill(self):
            raise AssertionError("Successful command should not be killed.")

    monkeypatch.setattr("app.services.sandbox.subprocess.Popen", FakeProcess)
    runner = DockerSandbox(
        workspace_root=Path("."),
        image="cognexa-test",
        volume_from="backend",
    )

    with runner.capture_output(
        lambda stream, chunk: captured.append((stream, chunk))
    ):
        result = runner.run(["python", "-c", "print('live')"], timeout=10)

    assert result["success"] is True
    assert result["stdout"] == "live stdout\n"
    assert result["stderr"] == "live stderr\n"
    assert captured == [
        ("stdout", "live stdout\n"),
        ("stderr", "live stderr\n"),
    ] or captured == [
        ("stderr", "live stderr\n"),
        ("stdout", "live stdout\n"),
    ]
