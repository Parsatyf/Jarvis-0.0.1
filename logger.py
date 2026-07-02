# C:\Users\Parsa\Desktop\jarvis\logger.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LogEvent:
    ts: float
    level: str
    event: str
    data: dict[str, Any]


class Logger:
    def __init__(self, logs_dir: str) -> None:
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.logs_dir / f"session_{int(time.time())}.jsonl"

    def log(self, level: str, event: str, data: dict[str, Any] | None = None) -> None:
        evt = LogEvent(
            ts=time.time(),
            level=level,
            event=event,
            data=data or {}
        )
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(evt.__dict__, ensure_ascii=False) + "\n")

        print(f"[{level}] {event}")

    def info(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.log("INFO", event, data)

    def warn(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.log("WARN", event, data)

    def error(self, event: str, data: dict[str, Any] | None = None) -> None:
        self.log("ERROR", event, data)
