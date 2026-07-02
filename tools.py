# C:\Users\Parsa\Desktop\jarvis\tools.py
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any]
    error: str | None = None


class Tools:
    def __init__(self, config: Any, logger: Any) -> None:
        self.config = config
        self.logger = logger

    # -------------------------
    # Path utilities
    # -------------------------
    def normalize_path(self, path: str) -> str:
        return str(Path(path).expanduser().resolve())

    def is_within_workspace(self, path: str) -> bool:
        try:
            root = Path(self.config.workspace_root).expanduser().resolve()
            target = Path(path).expanduser().resolve()
            target.relative_to(root)
            return True
        except ValueError:
            return False

    def is_safe_command(self, cmd: str) -> bool:
        if not cmd or not cmd.strip():
            return False
        blocked = ["&&", "||", ";", "|", "&", "`", "\n", "\r"]
        return not any(token in cmd for token in blocked)

    def is_denylisted_write(self, abs_path: str) -> bool:
        lowered = abs_path.lower()
        for prefix in self.config.deny_write_prefixes:
            if lowered.startswith(prefix.lower()):
                return True
        return False

    def ensure_parent_dir(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # Directory / file inspection
    # -------------------------
    def list_dir(self, path: str, recursive: bool = False, max_items: int = 300) -> ToolResult:
        try:
            abs_path = self.normalize_path(path)
            if not self.config.allow_read_anywhere and not self.is_within_workspace(abs_path):
                return ToolResult(False, {}, f"Path is outside the workspace: {abs_path}")
            p = Path(abs_path)
            if not p.exists():
                return ToolResult(False, {}, f"Path does not exist: {abs_path}")

            items: list[dict[str, Any]] = []
            if recursive:
                for idx, child in enumerate(p.rglob("*")):
                    if idx >= max_items:
                        break
                    items.append({
                        "path": str(child),
                        "type": "dir" if child.is_dir() else "file"
                    })
            else:
                for idx, child in enumerate(p.iterdir()):
                    if idx >= max_items:
                        break
                    items.append({
                        "path": str(child),
                        "type": "dir" if child.is_dir() else "file"
                    })

            return ToolResult(True, {"path": abs_path, "items": items})
        except Exception as e:
            return ToolResult(False, {}, str(e))

    def read_file(self, path: str) -> ToolResult:
        try:
            abs_path = self.normalize_path(path)
            if not self.config.allow_read_anywhere and not self.is_within_workspace(abs_path):
                return ToolResult(False, {}, f"Path is outside the workspace: {abs_path}")
            p = Path(abs_path)
            if not p.exists():
                return ToolResult(False, {}, f"File not found: {abs_path}")

            size = p.stat().st_size
            if size > self.config.max_file_bytes:
                return ToolResult(False, {}, f"File too large: {size} bytes")

            content = p.read_text(encoding="utf-8", errors="replace")
            return ToolResult(True, {
                "path": abs_path,
                "bytes": size,
                "content": content
            })
        except Exception as e:
            return ToolResult(False, {}, str(e))

    def search_text(self, root: str, query: str, max_hits: int = 50) -> ToolResult:
        try:
            abs_root = self.normalize_path(root)
            if not self.config.allow_read_anywhere and not self.is_within_workspace(abs_root):
                return ToolResult(False, {}, f"Root is outside the workspace: {abs_root}")
            rp = Path(abs_root)
            if not rp.exists():
                return ToolResult(False, {}, f"Root does not exist: {abs_root}")

            hits: list[dict[str, Any]] = []
            for file in rp.rglob("*"):
                if len(hits) >= max_hits:
                    break
                if not file.is_file():
                    continue
                try:
                    if file.stat().st_size > self.config.max_file_bytes:
                        continue
                    text = file.read_text(encoding="utf-8", errors="ignore")
                    if query in text:
                        hits.append({"path": str(file)})
                except Exception:
                    continue

            return ToolResult(True, {"root": abs_root, "query": query, "hits": hits})
        except Exception as e:
            return ToolResult(False, {}, str(e))

    # -------------------------
    # File editing
    # -------------------------
    def write_file(self, path: str, content: str, create_dirs: bool = True) -> ToolResult:
        try:
            abs_path = self.normalize_path(path)

            if self.config.allow_write_anywhere:
                pass
            elif not self.is_within_workspace(abs_path):
                return ToolResult(False, {}, f"Write denied: path is outside the workspace: {abs_path}")

            if self.is_denylisted_write(abs_path):
                return ToolResult(False, {}, f"Write denied for path: {abs_path}")

            encoded = content.encode("utf-8")
            if len(encoded) > self.config.max_write_bytes:
                return ToolResult(False, {}, "Content exceeds max_write_bytes")

            if create_dirs:
                self.ensure_parent_dir(abs_path)

            Path(abs_path).write_text(content, encoding="utf-8")
            return ToolResult(True, {"path": abs_path, "bytes": len(encoded)})
        except Exception as e:
            return ToolResult(False, {}, str(e))

    def replace_in_file(self, path: str, old: str, new: str, max_replacements: int = 1) -> ToolResult:
        try:
            abs_path = self.normalize_path(path)
            if not self.config.allow_write_anywhere and not self.is_within_workspace(abs_path):
                return ToolResult(False, {}, f"Write denied: path is outside the workspace: {abs_path}")
            p = Path(abs_path)
            if not p.exists():
                return ToolResult(False, {}, f"File not found: {abs_path}")

            text = p.read_text(encoding="utf-8", errors="replace")
            if old not in text:
                return ToolResult(False, {}, "Old text not found.")

            replaced = text.replace(old, new, max_replacements)
            p.write_text(replaced, encoding="utf-8")
            return ToolResult(True, {"path": abs_path, "replacements": max_replacements})
        except Exception as e:
            return ToolResult(False, {}, str(e))

    def delete_path(self, path: str) -> ToolResult:
        try:
            abs_path = self.normalize_path(path)
            if not self.config.allow_write_anywhere and not self.is_within_workspace(abs_path):
                return ToolResult(False, {}, f"Write denied: path is outside the workspace: {abs_path}")
            p = Path(abs_path)

            if not p.exists():
                return ToolResult(False, {}, f"Path not found: {abs_path}")

            if self.is_denylisted_write(abs_path):
                return ToolResult(False, {}, f"Delete denied for path: {abs_path}")

            if p.is_dir():
                shutil.rmtree(abs_path)
            else:
                p.unlink()

            return ToolResult(True, {"deleted": abs_path})
        except Exception as e:
            return ToolResult(False, {}, str(e))

    # -------------------------
    # Command execution
    # -------------------------
    def run_command(self, cmd: str, cwd: str | None = None) -> ToolResult:
        if not self.config.enable_command_execution:
            return ToolResult(False, {}, "Command execution disabled in config.")

        if not self.is_safe_command(cmd):
            return ToolResult(False, {}, "Command contains unsafe shell metacharacters")

        try:
            workdir = self.normalize_path(cwd) if cwd else self.normalize_path(self.config.default_command_cwd)
            self.logger.info("run_command", {"cmd": cmd, "cwd": workdir})

            proc = subprocess.run(
                cmd,
                cwd=workdir,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.command_timeout_sec
            )

            data = {
                "cmd": cmd,
                "cwd": workdir,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-50000:],
                "stderr": proc.stderr[-50000:]
            }
            ok = proc.returncode == 0
            return ToolResult(ok, data, None if ok else "Command returned non-zero exit code")
        except subprocess.TimeoutExpired:
            return ToolResult(False, {}, "Command timed out.")
        except Exception as e:
            return ToolResult(False, {}, str(e))
