# src/pathfinder_context_organizer/application/types.py
from __future__ import annotations

import dataclasses

from pathfinder_context_organizer.domain.value_objects import Sensitivity


@dataclasses.dataclass(slots=True, frozen=True)
class RawSessionEvent:
    event_id: str
    sequence: int
    role: str
    occurred_at: str | None
    body: str
    tool_name: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class RedactionFinding:
    event_id: str
    detection_type: str
    start: int
    end: int
    replacement: str
    reason_code: str


@dataclasses.dataclass(slots=True, frozen=True)
class RedactedSegment:
    segment_id: str
    source_event_ids: tuple[str, ...]
    text: str
    sensitivity: Sensitivity
    findings: tuple[RedactionFinding, ...]


@dataclasses.dataclass(slots=True, frozen=True)
class SafetyResult:
    segments: tuple[RedactedSegment, ...]
    findings: tuple[RedactionFinding, ...]
    redaction_count: int

