from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class FailureRecord:
    last_stderr_or_error: str
    last_cmd: str
    cwd: Optional[str] = None


class RetryLoop:
    """
    Simple retry policy holder.
    This matches the usage pattern in jarvis.py:
      - reset()
      - build_retry_prompt_suffix()
      - record_failure(cmd, stderr_or_error, cwd=...)
      - can_retry(cmd, stderr_or_error)
    """

    def __init__(self, max_retries: int = 2) -> None:
        self.max_retries = max_retries
        self.reset()

    def reset(self) -> None:
        self._failures: Dict[str, FailureRecord] = {}
        self._current_turn_retries = 0

    def build_retry_prompt_suffix(self) -> str:
        """
        Provide a short hint to the model when we are in a retry scenario.
        Keep it brief so it doesn't pollute the prompt.
        """
        if not self._failures:
            return ""

        # If multiple commands failed, we mention the most recent one in value.
        last_key = list(self._failures.keys())[-1]
        rec = self._failures[last_key]
        return (
            "\n\n[RETRY NOTE]\n"
            f"The previous command failed with: {rec.last_stderr_or_error}\n"
            "Please propose a corrected next action.\n"
        )

    def record_failure(self, cmd: str, stderr_or_error: str, cwd: Optional[str] = None) -> None:
        self._current_turn_retries += 1
        self._failures[cmd] = FailureRecord(
            last_stderr_or_error=stderr_or_error,
            last_cmd=cmd,
            cwd=cwd,
        )

    def can_retry(self, cmd: str, stderr_or_error: str) -> bool:
        # Retry count is tracked at jarvis.py via state.command_retry_count,
        # but we keep a local safety cap too.
        return self._current_turn_retries <= self.max_retries
