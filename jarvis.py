from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from config import CONFIG
from logger import Logger
from memory import Memory, AgentState
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from tools import Tools

from json_validation import extract_json_object, validate_agent_output
from retry_loop import RetryLoop


import requests

def call_ollama_chat(model: str, messages: list[dict[str, str]]) -> str:
    base = CONFIG.ollama_base_url.rstrip("/")
    url_chat = f"{base}/api/chat"
    url_gen = f"{base}/api/generate"

    payload_chat = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": getattr(CONFIG, "temperature", 0.7),
            "top_p": getattr(CONFIG, "top_p", 0.9),
        },
    }

    try:
        resp = requests.post(url_chat, json=payload_chat, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        content = data["message"]["content"]
        if content is None:
            raise RuntimeError("Ollama /api/chat returned message.content=None")
        return content

    except requests.exceptions.Timeout as e:
        print("[OLLAMA] TIMEOUT during /api/chat")
        raise

    except requests.exceptions.RequestException as e:
        # Fallback to GENERATE if chat fails for any request reason
        print("[OLLAMA] /api/chat failed, falling back to /api/generate")
        print("[OLLAMA] error:", repr(e))

        prompt = _messages_to_prompt(messages)

        payload_gen = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": getattr(CONFIG, "temperature", 0.7),
                "top_p": getattr(CONFIG, "top_p", 0.9),
            },
        }

        try:
            resp2 = requests.post(url_gen, json=payload_gen, timeout=120)
            resp2.raise_for_status()
            data2 = resp2.json()
            return data2["response"]
        except Exception as e2:
            print("[OLLAMA] /api/generate failed:", repr(e2))
            raise



def _messages_to_prompt(messages: list[dict[str, str]]) -> str:
    parts = []
    for m in messages:
        role = (m.get("role") or "").strip().lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue

        if role == "system":
            parts.append(f"[System]\n{content}\n")
        elif role == "user":
            parts.append(f"[User]\n{content}\n")
        elif role == "assistant":
            parts.append(f"[Assistant]\n{content}\n")
        else:
            parts.append(f"[{role or 'Message'}]\n{content}\n")

    return "\n".join(parts).strip()





def build_env_info(tools: Tools, root: str) -> dict[str, Any]:
    tree = tools.list_dir(root, recursive=False, max_items=200)
    info: dict[str, Any] = {"root": root}

    if tree.ok:
        info["dir_listing"] = tree.data
    else:
        info["dir_error"] = tree.error

    likely_files = [
        "package.json", "pyproject.toml", "requirements.txt", "README.md",
        "main.py", "app.py", "index.js", "src"
    ]
    existing = []
    for name in likely_files:
        p = Path(root) / name
        if p.exists():
            existing.append(str(p))
    info["likely_files"] = existing
    return info


def confirm_action(logger: Logger, title: str) -> bool:
    if not CONFIG.require_confirmation:
        return True
    ans = input(f"\nCONFIRM REQUIRED: {title}\nType YES to continue: ").strip().lower()
    ok = ans == "yes"
    logger.info("confirmation", {"title": title, "ok": ok})
    return ok


def apply_actions(
    tools: Tools,
    logger: Logger,
    state: AgentState,
    actions: list[dict[str, Any]]
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    modified: list[str] = []
    errors: list[str] = []
    command_failures: list[dict[str, Any]] = []

    for action in actions[:CONFIG.max_actions_per_turn]:
        action_type = action.get("action_type")
        details = action.get("details", {})

        try:
            if action_type == "read_file":
                res = tools.read_file(details["path"])
                logger.info("read_file", {"path": details.get("path"), "ok": res.ok})
                if not res.ok:
                    errors.append(res.error or "read_file failed")

            elif action_type == "list_dir":
                res = tools.list_dir(
                    details["path"],
                    recursive=details.get("recursive", False),
                    max_items=details.get("max_items", 300)
                )
                logger.info("list_dir", {"path": details.get("path"), "ok": res.ok})
                if not res.ok:
                    errors.append(res.error or "list_dir failed")

            elif action_type == "search_text":
                res = tools.search_text(
                    details["root"],
                    details["query"],
                    max_hits=details.get("max_hits", 50)
                )
                logger.info("search_text", {"root": details.get("root"), "query": details.get("query"), "ok": res.ok})
                if not res.ok:
                    errors.append(res.error or "search_text failed")

            elif action_type == "write_file":
                if CONFIG.require_confirmation:
                    if not confirm_action(logger, f"Write file: {details.get('path')}"):
                        errors.append("User denied write_file")
                        continue
                res = tools.write_file(
                    path=details["path"],
                    content=details["content"],
                    create_dirs=details.get("create_dirs", True)
                )
                logger.info("write_file", {"path": details.get("path"), "ok": res.ok})
                if res.ok:
                    modified.append(str(Path(details["path"]).resolve()))
                else:
                    errors.append(res.error or "write_file failed")

            elif action_type == "replace_in_file":
                if CONFIG.require_confirmation:
                    if not confirm_action(logger, f"Replace text in file: {details.get('path')}"):
                        errors.append("User denied replace_in_file")
                        continue
                res = tools.replace_in_file(
                    path=details["path"],
                    old=details["old"],
                    new=details["new"],
                    max_replacements=details.get("max_replacements", 1)
                )
                logger.info("replace_in_file", {"path": details.get("path"), "ok": res.ok})
                if res.ok:
                    modified.append(str(Path(details["path"]).resolve()))
                else:
                    errors.append(res.error or "replace_in_file failed")

            elif action_type == "delete_path":
                if CONFIG.require_confirmation:
                    if not confirm_action(logger, f"Delete path: {details.get('path')}"):
                        errors.append("User denied delete_path")
                        continue
                res = tools.delete_path(details["path"])
                logger.info("delete_path", {"path": details.get("path"), "ok": res.ok})
                if res.ok:
                    modified.append(str(Path(details["path"]).resolve()))
                else:
                    errors.append(res.error or "delete_path failed")

            elif action_type == "run_command":
                if CONFIG.require_confirmation:
                    if not confirm_action(logger, f"Run command: {details.get('cmd')}"):
                        errors.append("User denied run_command")
                        continue

                cmd = details["cmd"]
                cwd = details.get("cwd")
                res = tools.run_command(cmd=cmd, cwd=cwd)

                logger.info("run_command", {"cmd": cmd, "ok": res.ok})
                state.last_command = cmd
                state.last_command_output = json.dumps(res.data, ensure_ascii=False)[:10000]

                if not res.ok:
                    stderr_or_error = res.data.get("stderr") if isinstance(res.data, dict) else None
                    stderr_or_error = stderr_or_error or res.error or "run_command failed"
                    errors.append(stderr_or_error)
                    command_failures.append({
                        "cmd": cmd,
                        "cwd": cwd,
                        "stderr_or_error": stderr_or_error
                    })

            else:
                errors.append(f"Unsupported action_type: {action_type}")

        except Exception as e:
            errors.append(str(e))

    return modified, errors, command_failures


def main() -> None:
    logger = Logger(CONFIG.logs_dir)

    # IMPORTANT: explicit agent_state folder creation
    agent_state_dir = Path(CONFIG.agent_state_dir)
    agent_state_dir.mkdir(parents=True, exist_ok=True)
    (agent_state_dir / "logs").mkdir(parents=True, exist_ok=True)

    memory = Memory(str(agent_state_dir))
    tools = Tools(CONFIG, logger)
    state = memory.load()

    retry_loop = RetryLoop()
    print("Jarvis is ready. Type a goal, or 'exit' to quit.\n")

    while True:
        goal = input("You> ").strip()
        if goal.lower() in {"exit", "quit", "q"}:
            break
        if not goal:
            continue

        state.goal = goal
        state.iteration = 0
        state.last_summary = ""
        state.created_or_modified = []
        state.last_errors = []
        state.last_command = ""
        state.last_command_output = ""
        state.command_retry_count = 0
        state.last_command_failure = ""
        memory.save(state)

        retry_loop.reset()

        target_root = CONFIG.workspace_root
        path_match = re.search(r"[A-Za-z]:\\[^\"']+", goal)
        if path_match:
            target_root = path_match.group(0)

        for _ in range(CONFIG.max_iterations):
            state.iteration += 1
            env_info = build_env_info(tools, target_root)

            retry_suffix = retry_loop.build_retry_prompt_suffix()

            user_prompt = USER_PROMPT_TEMPLATE.format(
                goal=goal,
                iteration=state.iteration,
                last_summary=state.last_summary,
                created_or_modified=state.created_or_modified[-25:],
                last_errors=state.last_errors[-10:],
                last_command=state.last_command,
                env_info=json.dumps(env_info, ensure_ascii=False, indent=2),
            ) + retry_suffix

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]

            try:
                content = call_ollama_chat(CONFIG.model, messages)
            except Exception as e:
                logger.error("ollama_call_failed", {"error": str(e)})
                break

            try:
                obj = extract_json_object(content)
                obj = validate_agent_output(obj)
            except Exception as e:
                logger.error("json_parse_failed", {"error": str(e), "model_output": content[:1000]})
                state.last_errors = [f"JSON validation failed: {str(e)}"]
                memory.save(state)
                continue

            done = bool(obj.get("done", False))
            summary = obj.get("summary", "")
            state.last_summary = summary

            plan = obj.get("plan", []) or []
            state_updates = obj.get("state_updates", {}) or {}

            if isinstance(state_updates, dict):
                created = state_updates.get("created_or_modified", []) or []
                for x in created:
                    if x not in state.created_or_modified:
                        state.created_or_modified.append(x)
                state.last_errors = (state_updates.get("errors", []) or [])[-10:]

            logger.info("agent_step", {"iteration": state.iteration, "done": done, "summary": summary})

            all_actions: list[dict[str, Any]] = []
            for step in plan:
                if isinstance(step, dict):
                    all_actions.extend(step.get("actions", []) or [])

            command_failures: list[dict[str, Any]] = []
            if all_actions:
                modified, errors, command_failures = apply_actions(tools, logger, state, all_actions)
                for m in modified:
                    if m not in state.created_or_modified:
                        state.created_or_modified.append(m)
                if errors:
                    state.last_errors = [str(e) for e in errors[-10:]]

            if command_failures:
                last_fail = command_failures[-1]
                cmd = last_fail["cmd"]
                stderr_or_error = last_fail["stderr_or_error"]

                retry_loop.record_failure(cmd, stderr_or_error, cwd=last_fail.get("cwd"))
                state.last_command_failure = stderr_or_error
                state.command_retry_count += 1

                if retry_loop.can_retry(cmd, stderr_or_error):
                    logger.warn("command_retry_scheduled", {"cmd": cmd, "attempt": state.command_retry_count})
                else:
                    logger.error("command_retry_exhausted", {"cmd": cmd, "attempt": state.command_retry_count})
                    state.last_errors.append("Command retry attempts exhausted for this command.")

            next_cmd = obj.get("next_command")
            if isinstance(next_cmd, dict) and next_cmd.get("cmd"):
                if confirm_action(logger, f"Run next_command: {next_cmd['cmd']}"):
                    res = tools.run_command(next_cmd["cmd"], cwd=next_cmd.get("cwd"))
                    state.last_command = next_cmd["cmd"]
                    state.last_command_output = json.dumps(res.data, ensure_ascii=False)[:10000]
                    if not res.ok:
                        stderr = res.data.get("stderr") if isinstance(res.data, dict) else None
                        error_message = stderr or res.error or "Command failed"
                        state.last_errors = [str(error_message)]

            memory.save(state)

            if done:
                print("\nJarvis: completed.\n")
                print("Summary:", summary)
                break
        else:
            print("\nJarvis: max iterations reached.\n")

    print("Goodbye.")


if __name__ == "__main__":
    main()
