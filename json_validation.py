from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    """
    Extract the first valid JSON object found in `text`.
    Supports models that wrap JSON in markdown fences.

    Raises:
        ValueError: if no JSON object can be extracted/parsed.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Empty model output; cannot extract JSON object.")

    # Common case:

    cleaned = text.strip()
    # Check for markdown fences and try to extract JSON from them
    parts = cleaned.split("```")

        # Typically fences look like: [pre, "json\n{...}", post]
    for i in range(1, len(parts)):
            candidate = parts[i]
            # Remove a possible leading language tag
            candidate = candidate.lstrip()
            if candidate.startswith(("json", "JSON")):
                # remove first line
                candidate = "\n".join(candidate.splitlines()[1:])
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

    # Generic fallback: try direct parse first
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
        raise ValueError("Parsed JSON is not an object.")
    except Exception:
        pass

    # Last resort: scan for the first {...} block by brace counting
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No '{' found in model output; cannot extract JSON object.")

    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]

        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        return obj
                    raise ValueError("Extracted JSON is not an object.")
                except Exception as e:
                    raise ValueError(f"Found JSON-like block but failed to parse: {e}") from e

    raise ValueError("Could not locate a complete JSON object in model output.")


def validate_agent_output(obj: dict[str, Any]) -> dict[str, Any]:
    """
    Minimal schema validation for the agent output.

    Expected keys (best-effort; we won't be overly strict):
      - done: bool (optional but recommended)
      - summary: str (optional)
      - plan: list (optional)
      - state_updates: dict (optional)
      - next_command: dict (optional)

    Raises:
        ValueError: if required structural types are wildly wrong.
    """
    if not isinstance(obj, dict):
        raise ValueError("Agent output must be a JSON object (dict).")

    done = obj.get("done", False)
    if not isinstance(done, bool):
        # tolerate truthy/falsy but normalize
        obj["done"] = bool(done)

    summary = obj.get("summary", "")
    if summary is None:
        obj["summary"] = ""
    elif not isinstance(summary, str):
        obj["summary"] = str(summary)

    plan = obj.get("plan", [])
    if plan is None:
        obj["plan"] = []
    elif not isinstance(plan, list):
        raise ValueError("Field 'plan' must be a list.")

    state_updates = obj.get("state_updates", {})
    if state_updates is None:
        obj["state_updates"] = {}
    elif not isinstance(state_updates, dict):
        raise ValueError("Field 'state_updates' must be an object/dict.")

    next_command = obj.get("next_command", None)
    if next_command is not None and not isinstance(next_command, dict):
        raise ValueError("Field 'next_command' must be an object/dict if provided.")

    return obj
