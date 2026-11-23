# tests/unit/application/test_types_boundary.py
from __future__ import annotations

import ast
import dataclasses
import typing
from pathlib import Path

from pathfinder_context_organizer.application.safety import SafetyProcessor
from pathfinder_context_organizer.application.types import (
    RawSessionEvent,
    RedactedSegment,
    SafetyResult,
)
from pathfinder_context_organizer.domain.policies import RedactionPolicy


def test_raw_and_redacted_distinct() -> None:
    raw = RawSessionEvent("e1", 0, "user", None, "hello", None)
    assert type(raw) is not RedactedSegment


def test_process_accepts_raw_tuple_only_and_returns_safety_result() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    res = sp.process((RawSessionEvent("e1", 0, "user", None, "hi", None),), max_segment_chars=1000)
    assert isinstance(res, SafetyResult)
    for s in res.segments:
        assert isinstance(s, RedactedSegment)
        assert not hasattr(s, "body")


def test_redacted_segment_has_no_body_field() -> None:
    fields = {f.name for f in dataclasses.fields(RedactedSegment)}
    assert "body" not in fields


def test_redaction_finding_has_no_sensitivity() -> None:
    from pathfinder_context_organizer.application.types import RedactionFinding

    fields = {f.name for f in dataclasses.fields(RedactionFinding)}
    assert "sensitivity" not in fields


def test_process_signature_and_return_via_type_hints() -> None:
    hints = typing.get_type_hints(SafetyProcessor.process)
    assert hints["events"] == tuple[RawSessionEvent, ...]
    assert hints["return"] is SafetyResult


def test_empty_events_tuple_safe_result() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    res = sp.process((), max_segment_chars=1000)
    assert res.segments == ()
    assert res.findings == ()
    assert res.redaction_count == 0


def test_domain_does_not_import_application() -> None:
    domain_root = Path("src/pathfinder_context_organizer/domain")
    forbidden_prefix = "pathfinder_context_organizer.application"
    for py in domain_root.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefix), (
                        f"{py}: forbidden import {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(forbidden_prefix):
                    assert False, f"{py}: forbidden import from {node.module}"

