# tests/unit/adapters/test_claude_code_parser.py
from __future__ import annotations

import pytest

from pathfinder_context_organizer.adapters.claude_code.errors import SessionSourceParseError
from pathfinder_context_organizer.adapters.claude_code.parser import parse_claude_code_jsonl_line
from pathfinder_context_organizer.application.types import RawSessionEvent


def test_parse_minimal_line_defaults() -> None:
    ev = parse_claude_code_jsonl_line('{"body":"hello"}', 0)
    assert isinstance(ev, RawSessionEvent)
    assert ev.event_id == "e0"
    assert ev.sequence == 0
    assert ev.role == "user"
    assert ev.body == "hello"
    assert ev.occurred_at is None
    assert ev.tool_name is None


def test_parse_alternate_field_names() -> None:
    ev = parse_claude_code_jsonl_line(
        '{"id":"x1","index":3,"type":"assistant","content":"hi","timestamp":"2026-10-26T00:00:00Z","tool_name":"tool"}',
        2,
    )
    assert ev is not None
    assert ev.event_id == "x1"
    assert ev.sequence == 3
    assert ev.role == "assistant"
    assert ev.body == "hi"
    assert ev.occurred_at == "2026-10-26T00:00:00Z"
    assert ev.tool_name == "tool"


def test_parse_empty_line_returns_none() -> None:
    assert parse_claude_code_jsonl_line("", 5) is None
    assert parse_claude_code_jsonl_line("   ", 5) is None


def test_parse_malformed_json_raises_parse_error_no_leak() -> None:
    secret = "sk-EXAMPLE_NOTREAL_ABC123DEF456"
    with pytest.raises(SessionSourceParseError) as exc_info:
        parse_claude_code_jsonl_line('{"body":"' + secret + '"', 1)
    assert secret not in str(exc_info.value)

