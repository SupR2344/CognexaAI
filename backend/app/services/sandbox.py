"""Restricted Docker execution for approved workspace commands."""

from __future__ import annotations

import codecs
import logging
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

OUTPUT_LIMIT = 1024 * 1024
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", os.getcwd())).resolve()
SANDBOX_VOLUME_FROM = os.environ.get("SANDBOX_VOLUME_FROM", "").strip()
REDACTED_WORKSPACE_FILES = (
    ".env",
    "backend/.env",
    "frontend/.env.local",
    "backend/cognexa.db",
    "backend/cognexa.db-shm",
    "backend/cognexa.db-wal",
)


class DockerSandbox:
    """Run one approved command in a constrained, short-lived Docker container."""

    def __init__(
        self,
        workspace_root: Path = WORKSPACE_ROOT,
        image: str = settings.DOCKER_SANDBOX_IMAGE,
        volume_from: str = SANDBOX_VOLUME_FROM,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.image = image
        self.volume_from = volume_from
        self._output_context = threading.local()

    @contextmanager
    def capture_output(
        self,
        callback: Callable[[str, str], None],
    ) -> Iterator[None]:
        previous = getattr(self._output_context, "callback", None)
        self._output_context.callback = callback
        try:
            yield
        finally:
            self._output_context.callback = previous

    def run(self, arguments: List[str], timeout: int) -> Dict[str, Any]:
        """Execute an argv vector in an isolated container and return process evidence."""
        if not arguments or any(not isinstance(argument, str) for argument in arguments):
            raise ValueError("Sandbox command must be a non-empty string argument list.")

        container_name = f"cognexa-sandbox-{uuid.uuid4().hex[:16]}"
        command = [
            "docker",
            "run",
            "--rm",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--cpus",
            "1.0",
            "--user",
            "1001:1001",
            "--workdir",
            "/workspace",
            "--env",
            "HOME=/tmp",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONPATH=/workspace/backend",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
            "--tmpfs",
            "/workspace/.git:rw,noexec,nosuid,size=1m,mode=1777",
        ]

        if self.volume_from:
            command.extend(["--volumes-from", f"{self.volume_from}:ro"])
            if Path("/var/run/docker.sock").exists():
                command.extend(
                    [
                        "--mount",
                        "type=bind,source=/dev/null,target=/var/run/docker.sock,readonly",
                    ]
                )
            for relative_path in REDACTED_WORKSPACE_FILES:
                if not (self.workspace_root / relative_path).exists():
                    continue
                command.extend(
                    [
                        "--mount",
                        f"type=bind,source=/dev/null,target=/workspace/{relative_path},readonly",
                    ]
                )
        else:
            if not self.workspace_root.is_dir():
                raise ValueError(f"Workspace root is not a directory: {self.workspace_root}")
            with tempfile.TemporaryDirectory(prefix="cognexa-sandbox-") as staging:
                staged_root = Path(staging) / "workspace"
                shutil.copytree(
                    self.workspace_root,
                    staged_root,
                    ignore=shutil.ignore_patterns(
                        ".env*",
                        "*.env*",
                        ".git",
                        ".ssh",
                        ".next",
                        ".pytest_cache",
                        "__pycache__",
                        ".venv",
                        "venv",
                        "node_modules",
                        "cognexa.db",
                        "*.db-shm",
                        "*.db-wal",
                        "secrets.json",
                        "credentials.json",
                        "id_rsa",
                        "id_ed25519",
                        "*.pem",
                        "*.key",
                        "*.cert",
                        "*.crt",
                    ),
                )
                command.extend(
                    [
                        "--mount",
                        f"type=bind,source={staged_root},target=/workspace,readonly",
                    ]
                )
                return self._run_command(command, arguments, timeout, container_name)

        return self._run_command(command, arguments, timeout, container_name)

    def _run_command(
        self,
        docker_command: List[str],
        arguments: List[str],
        timeout: int,
        container_name: str,
    ) -> Dict[str, Any]:
        docker_command.extend([self.image, *arguments])
        on_output = getattr(self._output_context, "callback", None)

        if on_output is not None:
            return self._run_command_streaming(
                docker_command,
                timeout,
                container_name,
                on_output,
            )

        try:
            result = subprocess.run(
                docker_command,
                capture_output=True,
                text=True,
                timeout=max(1, min(timeout, 300)),
                check=False,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout[-OUTPUT_LIMIT:],
                "stderr": result.stderr[-OUTPUT_LIMIT:],
                "success": result.returncode == 0,
            }
        except FileNotFoundError as exc:
            logger.error("Docker CLI is unavailable for sandbox execution.")
            return {
                "exit_code": 127,
                "stdout": "",
                "stderr": f"Docker sandbox is unavailable: {exc}",
                "success": False,
            }
        except subprocess.TimeoutExpired as exc:
            self._stop_timed_out_container(container_name)
            return {
                "exit_code": 124,
                "stdout": self._output_text(exc.stdout)[-OUTPUT_LIMIT:],
                "stderr": (
                    f"Sandbox execution timed out after "
                    f"{max(1, min(timeout, 300))} seconds."
                ),
                "success": False,
            }

    def _run_command_streaming(
        self,
        docker_command: List[str],
        timeout: int,
        container_name: str,
        on_output: Callable[[str, str], None],
    ) -> Dict[str, Any]:
        bounded_timeout = max(1, min(timeout, 300))
        output_queue: queue.Queue[Tuple[str, Optional[str]]] = queue.Queue()
        stdout_parts: List[str] = []
        stderr_parts: List[str] = []
        output_sizes = {"stdout": 0, "stderr": 0}
        streamed_sizes = {"stdout": 0, "stderr": 0}
        stream_truncated = {"stdout": False, "stderr": False}
        readers: List[threading.Thread] = []

        try:
            process = subprocess.Popen(
                docker_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            logger.error("Docker CLI is unavailable for sandbox execution.")
            return {
                "exit_code": 127,
                "stdout": "",
                "stderr": f"Docker sandbox is unavailable: {exc}",
                "success": False,
            }

        def read_stream(stream_name: str, stream: Any) -> None:
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            try:
                while True:
                    raw_chunk = stream.read1(4096)
                    if not raw_chunk:
                        break
                    chunk = decoder.decode(raw_chunk)
                    if chunk:
                        output_queue.put((stream_name, chunk))
                remainder = decoder.decode(b"", final=True)
                if remainder:
                    output_queue.put((stream_name, remainder))
            finally:
                output_queue.put((stream_name, None))

        for stream_name, stream in (
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ):
            if stream is not None:
                reader = threading.Thread(
                    target=read_stream,
                    args=(stream_name, stream),
                    daemon=True,
                )
                reader.start()
                readers.append(reader)

        closed_streams = 0
        try:
            expires_at = time.monotonic() + bounded_timeout
            while closed_streams < len(readers):
                remaining = expires_at - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(docker_command, bounded_timeout)
                try:
                    stream_name, chunk = output_queue.get(timeout=min(0.25, remaining))
                except queue.Empty:
                    continue

                if chunk is None:
                    closed_streams += 1
                    continue

                target = stdout_parts if stream_name == "stdout" else stderr_parts
                current_size = output_sizes[stream_name]
                if current_size < OUTPUT_LIMIT:
                    accepted_chunk = chunk[: OUTPUT_LIMIT - current_size]
                    target.append(accepted_chunk)
                    output_sizes[stream_name] += len(accepted_chunk)
                streamed_size = streamed_sizes[stream_name]
                if streamed_size < OUTPUT_LIMIT:
                    streamed_chunk = chunk[: OUTPUT_LIMIT - streamed_size]
                    streamed_sizes[stream_name] += len(streamed_chunk)
                    try:
                        on_output(stream_name, streamed_chunk)
                    except Exception:
                        logger.exception("Unable to publish sandbox output chunk.")
                elif not stream_truncated[stream_name]:
                    stream_truncated[stream_name] = True
                    try:
                        on_output(
                            stream_name,
                            "\n[Further live output from this stream was truncated.]\n",
                        )
                    except Exception:
                        logger.exception("Unable to publish sandbox output truncation.")

            return_code = process.wait(timeout=max(0.1, expires_at - time.monotonic()))
            return {
                "exit_code": return_code,
                "stdout": "".join(stdout_parts),
                "stderr": "".join(stderr_parts),
                "success": return_code == 0,
            }
        except subprocess.TimeoutExpired:
            self._stop_timed_out_container(container_name)
            if process.poll() is None:
                process.kill()
            process.wait()
            return {
                "exit_code": 124,
                "stdout": "".join(stdout_parts),
                "stderr": (
                    f"Sandbox execution timed out after {bounded_timeout} seconds."
                ),
                "success": False,
            }
        finally:
            for reader in readers:
                reader.join(timeout=1)
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    @staticmethod
    def _output_text(value: Optional[Any]) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def _stop_timed_out_container(container_name: str) -> None:
        try:
            subprocess.run(
                ["docker", "stop", "--time", "1", container_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.error("Unable to stop timed-out sandbox container %s: %s", container_name, exc)


sandbox = DockerSandbox()
