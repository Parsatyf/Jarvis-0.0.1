# C:\Users\Parsa\Desktop\jarvis\config.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Config:
    # Ollama / LLM
    ollama_base_url: str = "http://localhost:11434"
    model: str = "deepseek-coder:6.7b"
    temperature: float = 0.7
    top_p: float = 0.95

    # Agent behavior
    max_iterations: int = 15
    max_actions_per_turn: int = 25
    max_prompt_chars: int = 30000

    # Workspace / file handling
    workspace_root: str = str(PROJECT_ROOT)
    allow_read_anywhere: bool = False
    allow_write_anywhere: bool = False

    # Safety
    require_confirmation: bool = True
    deny_write_prefixes: tuple[str, ...] = (
        r"C:/Windows/",
        r"C:/Program Files/WindowsApps/",
    )

    # Limits
    max_file_bytes: int = 1_000_000
    max_write_bytes: int = 8_000_000
    command_timeout_sec: int = 35

    # Execution
    enable_command_execution: bool = True
    default_command_cwd: str = str(PROJECT_ROOT)

    # Runtime state
    agent_state_dir: str = str(PROJECT_ROOT / "agent_state")
    logs_dir: str = str(PROJECT_ROOT / "agent_state" / "logs")


CONFIG = Config()
