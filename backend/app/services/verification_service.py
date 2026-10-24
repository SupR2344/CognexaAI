"""Verification Service for Cognexa AI.

Provides rigorous automated validation of command executions, pytest test runs,
file modifications, error classification, and comprehensive verification reports with evidence.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class VerificationService:
    """Service validating execution results, test outputs, file diffs, and failures."""

    def verify_observation(self, output: Any) -> Dict[str, Any]:
        """Verify that a read/search/list tool returned evidence rather than an error."""
        if not isinstance(output, str):
            return {
                "status": "failed",
                "summary": "Observation tool returned an unexpected result type.",
            }

        normalized = output.lstrip().lower()
        is_success = not normalized.startswith(
            ("error:", "security error:", "search error:", "execution error:")
        )
        return {
            "status": "verified" if is_success else "failed",
            "summary": (
                "Workspace observation completed."
                if is_success
                else output.strip()[:500]
            ),
            "output_characters": len(output),
        }

    def verify_file_write(self, expected: str, actual: str) -> Dict[str, Any]:
        """Compare persisted file content to the approved write request without echoing it."""
        expected_bytes = expected.encode("utf-8")
        actual_bytes = actual.encode("utf-8")
        matches = expected_bytes == actual_bytes
        return {
            "status": "verified" if matches else "failed",
            "summary": (
                "Written file contents match the approved input."
                if matches
                else "Written file contents do not match the approved input."
            ),
            "expected_bytes": len(expected_bytes),
            "actual_bytes": len(actual_bytes),
            "sha256": hashlib.sha256(actual_bytes).hexdigest() if matches else None,
        }

    def verify_command_result(
        self,
        expected: Optional[Union[str, Dict[str, Any]]] = None,
        actual_stdout: str = "",
        actual_stderr: str = "",
        exit_code: int = 0,
    ) -> Dict[str, Any]:
        """Check command execution results against expectations and exit status.

        Args:
            expected: Optional expected substring, regex pattern, or dictionary of expectations.
            actual_stdout: Standard output string from command.
            actual_stderr: Standard error string from command.
            exit_code: Process return code.

        Returns:
            Structured dictionary with validation status, matched flags, and analysis.
        """
        is_success = (exit_code == 0)
        has_warnings = False
        matched_expected = True
        reasons: List[str] = []

        if not is_success:
            reasons.append(f"Command returned non-zero exit code: {exit_code}")

        # Check expected output criteria
        if expected is not None:
            if isinstance(expected, str) and expected.strip():
                if expected not in actual_stdout and expected not in actual_stderr:
                    matched_expected = False
                    reasons.append(f"Expected output pattern '{expected}' not found in output.")
            elif isinstance(expected, dict):
                expected_str = expected.get("pattern") or expected.get("contains")
                if expected_str and (expected_str not in actual_stdout):
                    matched_expected = False
                    reasons.append(f"Expected pattern '{expected_str}' was not found in stdout.")

        # Classify stderr: warnings vs fatal errors
        if actual_stderr:
            fatal_keywords = ["fatal", "critical", "error:", "traceback", "exception", "failed"]
            lower_err = actual_stderr.lower()
            if any(k in lower_err for k in fatal_keywords) and not is_success:
                reasons.append(f"Fatal error detected in stderr: {actual_stderr[:200]}")
            else:
                has_warnings = True

        status = "verified" if (is_success and matched_expected) else "failed"
        summary = "; ".join(reasons) if reasons else "Command executed successfully and met expectations."

        return {
            "status": status,
            "exit_code": exit_code,
            "matched_expected": matched_expected,
            "has_warnings": has_warnings,
            "summary": summary,
            "errors": actual_stderr if not is_success else "",
        }

    def verify_test_results(self, test_output: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse pytest test output and determine pass/fail metrics and details.

        Args:
            test_output: Raw test output string or dict from run_tests tool.

        Returns:
            Structured dictionary containing pass/fail counts, verdict, and details.
        """
        output_text = ""
        exit_code = 0

        if isinstance(test_output, dict):
            output_text = test_output.get("output", "") + "\n" + test_output.get("errors", "")
            exit_code = test_output.get("exit_code", 0)
        else:
            output_text = str(test_output)

        passed_match = re.search(r"(\d+)\s+passed", output_text, re.IGNORECASE)
        failed_match = re.search(r"(\d+)\s+failed", output_text, re.IGNORECASE)
        errors_match = re.search(r"(\d+)\s+error(?:s)?", output_text, re.IGNORECASE)
        skipped_match = re.search(r"(\d+)\s+skipped", output_text, re.IGNORECASE)

        passed_count = int(passed_match.group(1)) if passed_match else 0
        failed_count = int(failed_match.group(1)) if failed_match else 0
        error_count = int(errors_match.group(1)) if errors_match else 0
        skipped_count = int(skipped_match.group(1)) if skipped_match else 0

        # Extract failure blocks if present
        failures: List[str] = []
        if "FAILURES" in output_text or "FAILED" in output_text:
            lines = output_text.splitlines()
            capture = False
            current_failure: List[str] = []
            for line in lines:
                if "___" in line and ("test_" in line or "Test" in line):
                    if current_failure:
                        failures.append("\n".join(current_failure[:20]))
                        current_failure = []
                    capture = True
                if capture:
                    current_failure.append(line)
                    if len(current_failure) > 30:
                        capture = False
            if current_failure:
                failures.append("\n".join(current_failure[:20]))

        # Check verdict
        if failed_count == 0 and error_count == 0 and (passed_count > 0 or exit_code == 0):
            if "no tests ran" in output_text.lower():
                status = "failed"
                summary = "Pytest completed but no tests were collected or ran."
            else:
                status = "verified"
                summary = f"All tests passed: {passed_count} passed, {skipped_count} skipped."
        else:
            status = "failed"
            summary = f"Tests failed: {failed_count} failed, {error_count} errors, {passed_count} passed."

        return {
            "status": status,
            "passed": passed_count,
            "failed": failed_count,
            "errors": error_count,
            "skipped": skipped_count,
            "summary": summary,
            "details": failures,
            "raw_exit_code": exit_code,
        }

    def verify_file_changes(
        self,
        original: Optional[str],
        modified: str,
        expected_changes: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """Verify modifications between original and modified text, including syntax checks.

        Args:
            original: Original file content (None if new file).
            modified: Modified or newly created file content.
            expected_changes: Specific tokens or phrases expected in the modified content.

        Returns:
            Structured dictionary with diff, syntax check, and validation status.
        """
        orig_str = original or ""
        orig_lines = orig_str.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)

        diff_gen = difflib.unified_diff(
            orig_lines,
            mod_lines,
            fromfile="original",
            tofile="modified",
            lineterm="",
        )
        diff_text = "\n".join(diff_gen)

        lines_added = sum(1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
        lines_removed = sum(1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---"))

        # Python syntax check if applicable
        syntax_valid = True
        syntax_error = None
        try:
            ast.parse(modified)
        except SyntaxError as se:
            # Only treat as syntax error if file looks like Python code
            if "def " in modified or "class " in modified or "import " in modified:
                syntax_valid = False
                syntax_error = f"Syntax error at line {se.lineno}: {se.msg}"
        except Exception:
            pass

        # Check expected tokens
        expected_tokens_matched = True
        missing_tokens: List[str] = []
        if expected_changes:
            tokens = [expected_changes] if isinstance(expected_changes, str) else expected_changes
            for token in tokens:
                if token not in modified:
                    expected_tokens_matched = False
                    missing_tokens.append(token)

        status = "verified" if (syntax_valid and expected_tokens_matched) else "failed"

        return {
            "status": status,
            "diff": diff_text,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "syntax_valid": syntax_valid,
            "syntax_error": syntax_error,
            "expected_tokens_matched": expected_tokens_matched,
            "missing_tokens": missing_tokens,
        }

    def classify_error(
        self,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify error message into root category and propose recovery strategy.

        Args:
            error_message: Error text or traceback.
            context: Optional contextual data about the step or tool.

        Returns:
            Dictionary with error_type, description, suggested_recovery, and recoverable flag.
        """
        msg = error_message.lower()

        if any(w in msg for w in ["syntaxerror", "indentationerror", "invalid syntax"]):
            return {
                "error_type": "SYNTAX_ERROR",
                "description": "Python source code contains invalid syntax or indentation errors.",
                "suggested_recovery": "Inspect file contents around the specified line number, correct formatting, and rewrite file.",
                "recoverable": True,
            }

        if any(w in msg for w in ["filenotfounderror", "no such file or directory", "cannot find the path"]):
            return {
                "error_type": "FILE_NOT_FOUND",
                "description": "Target file or directory does not exist.",
                "suggested_recovery": "Use list_directory or search_in_files to discover the correct relative path before accessing.",
                "recoverable": True,
            }

        if any(w in msg for w in ["modulenotfounderror", "importerror", "no module named"]):
            return {
                "error_type": "IMPORT_ERROR",
                "description": "Required module or dependency is not installed in current environment.",
                "suggested_recovery": "Install missing dependency using pip or verify virtual environment activation.",
                "recoverable": True,
            }

        if any(w in msg for w in ["permissionerror", "access is denied", "operation not permitted"]):
            return {
                "error_type": "PERMISSION_ERROR",
                "description": "File or system permission denied.",
                "suggested_recovery": "Ensure path is within the workspace boundary and that process has write/read permissions.",
                "recoverable": False,
            }

        if any(w in msg for w in ["timeoutexpired", "timed out", "timeout"]):
            return {
                "error_type": "TIMEOUT_ERROR",
                "description": "Operation exceeded the configured timeout limit.",
                "suggested_recovery": "Split workload into smaller sub-tasks or increase timeout parameter.",
                "recoverable": True,
            }

        if any(w in msg for w in ["assertionerror", "failed", "tests failed"]):
            return {
                "error_type": "ASSERTION_ERROR",
                "description": "Verification assertion or test assertion failed.",
                "suggested_recovery": "Inspect test failure traceback, fix underlying application logic, and re-run tests.",
                "recoverable": True,
            }

        if any(w in msg for w in ["connectionrefused", "connecterror", "network is unreachable"]):
            return {
                "error_type": "NETWORK_ERROR",
                "description": "Failed to connect to local or remote service endpoint.",
                "suggested_recovery": "Verify if the server or container (e.g. Ollama, PostgreSQL) is running on the expected port.",
                "recoverable": True,
            }

        return {
            "error_type": "UNKNOWN_ERROR",
            "description": f"Unclassified execution error: {error_message[:200]}",
            "suggested_recovery": "Analyze error traceback and formulate an alternative approach.",
            "recoverable": True,
        }

    def generate_verification_report(
        self,
        task: str,
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate comprehensive verification report with metrics and evidence trail.

        Args:
            task: Goal or task description.
            steps: List of executed step dictionaries with results and verification info.

        Returns:
            Structured dictionary containing overall verdict, metrics, evidence, and markdown report.
        """
        total = len(steps)
        verified_count = 0
        failed_count = 0
        evidence_items: List[Dict[str, Any]] = []

        report_lines: List[str] = [
            "# Cognexa AI Execution & Verification Report",
            f"**Task / Goal:** {task}\n",
            "| Step | Action / Tool | Status | Summary |",
            "| :--- | :--- | :---: | :--- |",
        ]

        for idx, step in enumerate(steps, 1):
            tool = step.get("tool", "unknown_tool")
            desc = step.get("description", f"Step {idx}")
            status = step.get("verification_status", "pending")
            result = step.get("result", {})
            error = step.get("error")

            if status == "verified":
                verified_count += 1
                status_icon = "PASS"
                summary_note = "Step executed and verified."
            elif status == "failed":
                failed_count += 1
                status_icon = "FAIL"
                summary_note = f"Failed: {error or 'Verification rejected result'}"
            else:
                status_icon = "SKIP"
                summary_note = "Step pending or skipped."

            report_lines.append(f"| {idx} | `{tool}` - {desc} | **{status_icon}** | {summary_note} |")

            evidence_items.append({
                "step_number": idx,
                "tool": tool,
                "status": status,
                "output_preview": str(result)[:300],
                "error": error,
            })

        overall_verdict = "PASSED" if (failed_count == 0 and verified_count > 0) else ("FAILED" if failed_count > 0 else "PARTIAL")

        report_lines.extend([
            "",
            "## Summary Metrics",
            f"- **Overall Verdict:** **{overall_verdict}**",
            f"- **Total Steps Planned:** {total}",
            f"- **Verified Steps:** {verified_count}",
            f"- **Failed Steps:** {failed_count}",
        ])

        return {
            "verdict": overall_verdict,
            "total_steps": total,
            "verified_steps": verified_count,
            "failed_steps": failed_count,
            "evidence": evidence_items,
            "markdown_report": "\n".join(report_lines),
        }
