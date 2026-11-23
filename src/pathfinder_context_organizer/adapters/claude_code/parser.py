# src/pathfinder_context_organizer/adapters/claude_code/parser.py
from __future__ import annotations

import json

from pathfinder_context_organizer.adapters.claude_code.errors import SessionSourceParseError
from pathfinder_context_organizer.application.types import RawSessionEvent


def parse_claude_code_jsonl_line(line: str, index: int) -> RawSessionEvent | None:
    s = line.strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
    except (ValueError, RecursionError):
        raise SessionSourceParseError("invalid jsonl line") from None
    if not isinstance(obj, dict):
        raise SessionSourceParseError("invalid jsonl line")
    event_id = obj.get("event_id") or obj.get("id") or f"e{index}"
    sequence = obj.get("sequence")
    if sequence is None:
        sequence = obj.get("index")
    if sequence is None:
        sequence = index
    try:
        sequence_i = int(sequence)
    except (ValueError, TypeError, OverflowError):
        sequence_i = index
    role = obj.get("role") or obj.get("type") or "user"
    if not isinstance(role, str):
        role = "user"
    occurred_at = obj.get("occurred_at") or obj.get("timestamp")
    if occurred_at is not None and not isinstance(occurred_at, str):
        occurred_at = None
    body = obj.get("body")
    if body is None:
        body = obj.get("content")
    if body is None:
        body = obj.get("text")
    if body is None and isinstance(obj.get("message"), dict):
        body = obj["message"].get("content")
        if isinstance(body, list):
            body = "\n".join(
                part["text"]
                for part in body
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            )
    if body is None:
        body = ""
    if not isinstance(body, str):
        body = str(body)
    tool_name = obj.get("tool_name")
    if tool_name is not None and not isinstance(tool_name, str):
        tool_name = None
    return RawSessionEvent(
        event_id=str(event_id),
        sequence=sequence_i,
        role=role,
        occurred_at=occurred_at,
        body=body,
        tool_name=tool_name,
    )

