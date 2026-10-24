"""Agent Tools for Cognexa AI.

Provides sandboxed, safety-checked file system operations, subprocess execution,
Python execution, pytest test runners, and file search.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.sandbox import sandbox

try:
    from langchain_core.tools import tool
except ImportError:
    try:
        from langchain.tools import tool  # type: ignore
    except ImportError:
        # Fallback decorator if langchain is not available
        def tool(func: Any) -> Any:  # type: ignore
            func.name = func.__name__
            func.description = func.__doc__ or ""
            return func

logger = logging.getLogger(__name__)

# Base workspace directory boundary
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", os.getcwd())).resolve()

# Prohibited paths and destructive command patterns
BLOCKED_PATH_PATTERNS = [
    re.compile(r"(\.env|\.git/config|\.ssh|id_rsa|id_ed25519)", re.IGNORECASE),
    re.compile(r"(\\|/)(windows|system32|etc/shadow|etc/passwd)", re.IGNORECASE),
]

DISALLOWED_COMMANDS = [
    re.compile(r"\brm\s+-rf\s+(/|~|\$HOME|\.\.)", re.IGNORECASE),
    re.compile(r"\b(format\s+[a-z]:|mkfs|dd\s+if=)", re.IGNORECASE),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", re.IGNORECASE),  # forkbomb
    re.compile(r"\bdel\s+/[fF]\s+/[sS]\s+/[qQ]\s+[cC]:\\", re.IGNORECASE),
]


def _validate_path(path_str: str, allow_outside_root: bool = False) -> Path:
    """Validate and resolve a file path to prevent directory traversal and access to sensitive files.

    Args:
        path_str: Relative or absolute path string.
        allow_outside_root: Whether to allow paths outside workspace if explicitly configured.

    Returns:
        Resolved absolute Path.

    Raises:
        PermissionError: If path violates workspace boundaries or matches blocked patterns.
    """
    raw_path = Path(path_str)
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (WORKSPACE_ROOT / raw_path).resolve()

    # Check blocked sensitive file patterns
    str_resolved = str(resolved)
    for pattern in BLOCKED_PATH_PATTERNS:
        if pattern.search(str_resolved):
            raise PermissionError(f"Access to sensitive file or directory '{path_str}' is denied.")

    # Check workspace boundary containment unless explicitly permitted
    if not allow_outside_root:
        try:
            resolved.relative_to(WORKSPACE_ROOT)
        except ValueError:
            raise PermissionError(
                f"Path traversal detected: '{path_str}' resolves outside workspace root '{WORKSPACE_ROOT}'."
            )

    return resolved


@tool
def read_file(file_path: str) -> str:
    """Read the full text contents of a file.

    Args:
        file_path: Relative or absolute path to the file to read.

    Returns:
        File contents as text or an error message if the file cannot be accessed.
    """
    try:
        target = _validate_path(file_path)
        if not target.exists():
            return f"Error: File not found at '{file_path}'."
        if not target.is_file():
            return f"Error: Path '{file_path}' is a directory, not a file."

        # Limit read to 2MB to prevent memory exhaustion
        if target.stat().st_size > 2 * 1024 * 1024:
            return f"Error: File '{file_path}' is too large to read directly (>2MB)."

        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target.read_text(encoding="latin-1")

    except PermissionError as pe:
        return f"Security Error: {pe}"
    except Exception as err:
        logger.error("Error reading file %s: %s", file_path, err)
        return f"Error reading file '{file_path}': {err}"


@tool
def write_file(file_path: str, content: str) -> str:
    """Write text content to a file, creating parent directories if necessary.

    Args:
        file_path: Relative or absolute path to the file to create or overwrite.
        content: The text content to write into the file.

    Returns:
        A confirmation message on success or an error message on failure.
    """
    try:
        target = _validate_path(file_path)

        # Safety check: prevent overwriting critical system files
        if target.suffix.lower() in [".exe", ".dll", ".so", ".bin"]:
            return f"Security Error: Writing to binary executable extension '{target.suffix}' is disallowed."
        if len(content.encode("utf-8")) > 2 * 1024 * 1024:
            return "Error: File content exceeds the 2MB write limit."

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        byte_len = len(content.encode("utf-8"))
        return f"Successfully wrote {byte_len} bytes to '{file_path}'."

    except PermissionError as pe:
        return f"Security Error: {pe}"
    except Exception as err:
        logger.error("Error writing to file %s: %s", file_path, err)
        return f"Error writing file '{file_path}': {err}"


@tool
def list_directory(path: str = ".") -> str:
    """List the contents of a directory.

    Args:
        path: Path to the directory to inspect (defaults to current workspace directory).

    Returns:
        Formatted listing of files and subdirectories.
    """
    try:
        target = _validate_path(path)
        if not target.exists():
            return f"Error: Directory '{path}' does not exist."
        if not target.is_dir():
            return f"Error: Path '{path}' is a file, not a directory."

        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines: List[str] = [f"Directory listing of '{target}':"]

        for entry in entries[:200]:  # Cap at 200 items
            if entry.name.startswith(".git") or entry.name == "__pycache__":
                continue
            if entry.is_dir():
                lines.append(f"  [DIR]  {entry.name}/")
            else:
                try:
                    size = entry.stat().st_size
                    lines.append(f"  [FILE] {entry.name} ({size} bytes)")
                except Exception:
                    lines.append(f"  [FILE] {entry.name}")

        if len(entries) > 200:
            lines.append(f"  ... ({len(entries) - 200} more items)")

        return "\n".join(lines)

    except PermissionError as pe:
        return f"Security Error: {pe}"
    except Exception as err:
        logger.error("Error listing directory %s: %s", path, err)
        return f"Error listing directory '{path}': {err}"


@tool
def execute_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute an approved shell command inside the restricted Docker sandbox.

    Args:
        command: The shell command line string to run.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        Structured dict with stdout, stderr, exit_code, command, and success status.
    """
    # Security validation against destructive commands
    for pattern in DISALLOWED_COMMANDS:
        if pattern.search(command):
            return {
                "command": command,
                "exit_code": 126,
                "stdout": "",
                "stderr": f"Command rejected: matches dangerous operation pattern '{pattern.pattern}'.",
                "success": False,
            }
    if not command.strip() or len(command) > 20_000:
        return {
            "command": command[:200],
            "exit_code": 2,
            "stdout": "",
            "stderr": "Command must contain between 1 and 20000 characters.",
            "success": False,
        }

    try:
        result = sandbox.run(
            ["sh", "-c", command],
            timeout=max(1, min(timeout, settings.SANDBOX_TIMEOUT)),
        )
        return {
            "command": command,
            **result,
        }
    except Exception as err:
        logger.error("Sandbox command execution failed: %s", err)
        return {
            "command": command,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Sandbox execution error: {err}",
            "success": False,
        }


@tool
def run_python_code(code: str) -> Dict[str, Any]:
    """Execute Python code in the restricted Docker sandbox with captured output.

    Args:
        code: Python source code snippet to run.

    Returns:
        Structured dict containing output, errors, exit_code, and success status.
    """
    # Guard against obvious destructive calls
    if re.search(r"\bshutil\.rmtree\s*\(\s*['\"](/|[A-Za-z]:[\\/])", code):
        return {
            "code": code,
            "exit_code": 126,
            "output": "",
            "errors": "Code execution rejected: attempts root deletion.",
            "success": False,
        }

    if len(code) > 100_000:
        return {
            "code": "",
            "exit_code": 2,
            "output": "",
            "errors": "Python code exceeds the 100000 character limit.",
            "success": False,
        }

    try:
        result = sandbox.run(
            ["python", "-c", code],
            timeout=settings.SANDBOX_TIMEOUT,
        )
        return {
            "code": code,
            "exit_code": result["exit_code"],
            "output": result["stdout"].strip(),
            "errors": result["stderr"].strip(),
            "success": result["success"],
        }
    except Exception as err:
        return {
            "code": code,
            "exit_code": 1,
            "output": "",
            "errors": f"Execution exception: {err}",
            "success": False,
        }


@tool
def run_tests(test_path: str = "tests") -> Dict[str, Any]:
    """Run pytest in the restricted Docker sandbox and report pass/fail evidence.

    Args:
        test_path: File path or directory containing pytest tests.

    Returns:
        Structured dict containing test output, errors, exit code, and passed flag.
    """
    try:
        target = _resolve_test_path(test_path)
    except PermissionError as pe:
        return {
            "test_path": test_path,
            "exit_code": 1,
            "output": "",
            "errors": str(pe),
            "passed": False,
        }

    if target is None:
        return {
            "test_path": test_path,
            "exit_code": 1,
            "output": "",
            "errors": f"Test path '{test_path}' does not exist in the workspace.",
            "passed": False,
        }

    workspace_relative_path = target.relative_to(WORKSPACE_ROOT).as_posix()
    try:
        result = sandbox.run(
            [
                "python",
                "-m",
                "pytest",
                "-p",
                "no:cacheprovider",
                workspace_relative_path,
                "-v",
            ],
            timeout=max(settings.SANDBOX_TEST_TIMEOUT, settings.SANDBOX_TIMEOUT),
        )
        return {
            "test_path": test_path,
            "exit_code": result["exit_code"],
            "output": result["stdout"].strip(),
            "errors": result["stderr"].strip(),
            "passed": result["success"],
        }
    except Exception as err:
        return {
            "test_path": test_path,
            "exit_code": 1,
            "output": "",
            "errors": f"Sandboxed pytest execution failed: {err}",
            "passed": False,
        }


def _resolve_test_path(test_path: str) -> Optional[Path]:
    """Resolve a project test path, including the repository's backend/tests layout."""
    try:
        target = _validate_path(test_path)
        if target.exists():
            return target
        if test_path == "tests":
            backend_tests = _validate_path("backend/tests")
            if backend_tests.exists():
                return backend_tests
        elif test_path == "backend/tests":
            backend_local_tests = _validate_path("tests")
            if backend_local_tests.exists():
                return backend_local_tests
        return None
    except PermissionError:
        raise


@tool
def search_in_files(directory: str = ".", pattern: str = "") -> str:
    """Search for a regex or substring pattern across files in a directory.

    Args:
        directory: Directory to search recursively within.
        pattern: Text or regex pattern to search for.

    Returns:
        Formatted matches with relative file path and line numbers.
    """
    if not pattern:
        return "Error: Search pattern must not be empty."

    try:
        target = _validate_path(directory)
        if not target.exists() or not target.is_dir():
            return f"Error: Search directory '{directory}' does not exist or is not a directory."

        compiled_regex = re.compile(pattern, re.IGNORECASE)
        matches: List[str] = []
        max_matches = 100

        ignore_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode"}
        ignore_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".pyc", ".zip", ".tar", ".gz"}

        for root, dirs, files in os.walk(target):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".")]

            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in ignore_exts:
                    continue

                full_path = Path(root) / file_name
                try:
                    rel_path = full_path.relative_to(WORKSPACE_ROOT)
                except ValueError:
                    rel_path = full_path

                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if compiled_regex.search(line):
                                clean_line = line.strip()[:150]
                                matches.append(f"{rel_path}:{line_no}: {clean_line}")
                                if len(matches) >= max_matches:
                                    break
                except Exception:
                    continue

                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

        if not matches:
            return f"No occurrences of '{pattern}' found in '{directory}'."

        header = f"Found {len(matches)} match{'es' if len(matches) > 1 else ''} for '{pattern}':\n"
        return header + "\n".join(matches)

    except PermissionError as pe:
        return f"Security Error: {pe}"
    except Exception as err:
        logger.error("Error searching in files: %s", err)
        return f"Search error: {err}"


@tool
def create_project_zip(folder_path: str, zip_name: Optional[str] = None) -> str:
    """Bundle a project folder into a downloadable .zip archive.

    Args:
        folder_path: Directory path containing the project files to package.
        zip_name: Optional output zip filename (e.g. 'project.zip').

    Returns:
        JSON string with zip file name, file count, size, and download link.
    """
    import json
    import zipfile

    try:
        source_dir = _validate_path(folder_path, allow_outside_root=True)
        if not source_dir.is_dir():
            return json.dumps({"error": f"Path '{folder_path}' is not a valid directory."})

        target_zip_name = zip_name.strip() if zip_name else f"{source_dir.name}.zip"
        if not target_zip_name.lower().endswith(".zip"):
            target_zip_name += ".zip"

        exports_dir = Path("exports").resolve()
        exports_dir.mkdir(parents=True, exist_ok=True)
        output_path = exports_dir / target_zip_name

        file_count = 0
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                # Avoid recursing into git, caches, or export dir itself
                dirs[:] = [d for d in dirs if not d.startswith((".", "__pycache__", "node_modules", "exports"))]
                for file_name in files:
                    file_path = Path(root) / file_name
                    archive_name = file_path.relative_to(source_dir)
                    zf.write(file_path, str(archive_name))
                    file_count += 1

        size_kb = round(output_path.stat().st_size / 1024, 2)
        download_url = f"http://localhost:8001/downloads/{target_zip_name}"

        return json.dumps({
            "status": "success",
            "zip_filename": target_zip_name,
            "files_count": file_count,
            "size_kb": size_kb,
            "download_url": download_url,
            "message": f"Successfully packaged {file_count} files into {target_zip_name} ({size_kb} KB)."
        })
    except Exception as err:
        logger.error("Failed to create zip package: %s", err)
        return json.dumps({"error": f"Failed to package project zip: {err}"})


# Registry of available agent tools
ALL_TOOLS = [
    read_file,
    write_file,
    list_directory,
    execute_command,
    run_python_code,
    run_tests,
    search_in_files,
    create_project_zip,
]

TOOL_MAP: Dict[str, Any] = {tool_obj.name: tool_obj for tool_obj in ALL_TOOLS}
