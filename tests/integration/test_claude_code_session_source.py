# tests/integration/test_claude_code_session_source.py
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pathfinder_context_organizer.adapters.claude_code.errors import SessionSourceValidationError
from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.application.types import RawSessionEvent


def _write_jsonl(tmp: Path, name: str, lines: list[dict]) -> str:
    p = tmp / name
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return str(p.resolve())


def test_read_events_single_absolute_jsonl(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p = _write_jsonl(
        tmp_path,
        "sess.jsonl",
        [
            {"event_id": "e1", "sequence": 0, "role": "user", "body": "hello"},
            {"id": "e2", "index": 1, "type": "assistant", "content": "hi"},
        ],
    )
    events = src.read_events(p)
    assert isinstance(events, tuple) and len(events) == 2
    assert all(isinstance(e, RawSessionEvent) for e in events)
    assert events[0].body == "hello"
    assert events[1].body == "hi"


def test_reject_relative_path(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    _write_jsonl(tmp_path, "sess.jsonl", [{"body": "x"}])
    with pytest.raises(SessionSourceValidationError):
        src.read_events("sess.jsonl")


def test_reject_non_jsonl_extension(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p = tmp_path / "sess.txt"
    p.write_text('{"body":"x"}\n', encoding="utf-8")
    with pytest.raises(SessionSourceValidationError):
        src.read_events(str(Path(p).resolve()))


def test_reject_glob_patterns(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    with pytest.raises(SessionSourceValidationError):
        src.read_events(str(tmp_path / "*.jsonl"))
    with pytest.raises(SessionSourceValidationError):
        src.read_events(str(tmp_path / "s?.jsonl"))


def test_reject_multiple_paths(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p1 = _write_jsonl(tmp_path, "a.jsonl", [{"body": "x"}])
    p2 = _write_jsonl(tmp_path, "b.jsonl", [{"body": "y"}])
    with pytest.raises(SessionSourceValidationError):
        src.read_events(p1 + os.pathsep + p2)


def test_reject_directory(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    with pytest.raises(SessionSourceValidationError):
        src.read_events(str(tmp_path.resolve()))


def test_missing_file_raises(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    missing = str((tmp_path / "missing.jsonl").resolve())
    with pytest.raises((FileNotFoundError, OSError)):
        src.read_events(missing)


def test_malformed_json_line_safe_error_no_body_leak(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p = tmp_path / "bad.jsonl"
    secret = "sk-EXAMPLE_NOTREAL_ABC123DEF456"
    p.write_text('{"body":"' + secret + '"}\nNOT_JSON\n', encoding="utf-8")
    with pytest.raises(Exception) as exc_info:
        src.read_events(str(Path(p).resolve()))
    assert secret not in str(exc_info.value)


def test_get_fingerprint_deterministic_and_no_raw_content(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    secret = "ghp_EXAMPLE_NOTREAL_ABC123DEF456"
    p = _write_jsonl(tmp_path, "sess.jsonl", [{"body": secret}])
    fp1 = src.get_fingerprint(str(Path(p).resolve()))
    fp2 = src.get_fingerprint(str(Path(p).resolve()))
    assert fp1 == fp2
    assert isinstance(fp1, str)
    assert secret not in fp1


def test_get_last_modified_format(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p = _write_jsonl(tmp_path, "sess.jsonl", [{"body": "x"}])
    lm = src.get_last_modified(str(Path(p).resolve()))
    assert lm is None or isinstance(lm, str)

