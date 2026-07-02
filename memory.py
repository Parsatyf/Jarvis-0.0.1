from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


@dataclass
class AgentState:
    goal: str = ""
    iteration: int = 0
    last_summary: str = ""
    created_or_modified: list[str] = field(default_factory=list)
    last_errors: list[str] = field(default_factory=list)
    last_command: str = ""
    last_command_output: str = ""

    # For retry / recovery coherence
    command_retry_count: int = 0
    last_command_failure: str = ""


class Memory:
    def __init__(self, state_dir: str) -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "state.json"

    def load(self) -> AgentState:
        """
        Safe load:
        - if file missing -> default state
        - if file empty/corrupt -> default state
        - if file has older/missing keys -> merge safely
        """
        if not self.state_file.exists():
            return AgentState()

        try:
            text = self.state_file.read_text(encoding="utf-8").strip()
            if not text:
                return AgentState()

            raw = json.loads(text)
            if not isinstance(raw, dict):
                return AgentState()

            # only keep keys that exist in AgentState
            valid_keys = set(AgentState().__dict__.keys())
            filtered = {k: raw.get(k, getattr(AgentState(), k)) for k in valid_keys}
            return AgentState(**filtered)

        except Exception:
            # If corrupted, do not crash the app
            return AgentState()

    def save(self, state: AgentState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
