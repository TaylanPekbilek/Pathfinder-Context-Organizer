# src/pathfinder_context_organizer/domain/value_objects.py
from __future__ import annotations

from enum import Enum


class ImportRunState(str, Enum):
    PENDING = "pending"
    AWAITING_CONSENT = "awaiting_consent"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class SourceStatus(str, Enum):
    AVAILABLE = "available"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_CHANGED = "source_changed"


class ContextItemType(str, Enum):
    STATUS = "status"
    DECISION = "decision"
    OPEN_TASK = "open_task"
    FILE_REFERENCE = "file_reference"
    ASSUMPTION = "assumption"
    RISK = "risk"


class ReviewStatus(str, Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class LifecycleStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DISPUTED = "disputed"


class Sensitivity(str, Enum):
    NORMAL = "normal"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HandoffDisposition(str, Enum):
    INCLUDED = "included"
    EXPLICITLY_EXCLUDED = "explicitly_excluded"


class RenderTier(str, Enum):
    ESSENTIAL = "essential"
    STANDARD = "standard"
    DETAIL = "detail"


class RenderProfile(str, Enum):
    SHORT = "short"
    STANDARD = "standard"
    DETAILED = "detailed"


class TokenCountKind(str, Enum):
    EXACT = "exact"
    ESTIMATED = "estimated"


_ALLOWED: dict[ImportRunState, set[ImportRunState]] = {
    ImportRunState.PENDING: {
        ImportRunState.AWAITING_CONSENT,
        ImportRunState.IN_PROGRESS,
        ImportRunState.FAILED,
        ImportRunState.CANCELLED,
    },
    ImportRunState.AWAITING_CONSENT: {
        ImportRunState.IN_PROGRESS,
        ImportRunState.FAILED,
        ImportRunState.CANCELLED,
    },
    ImportRunState.IN_PROGRESS: {
        ImportRunState.AWAITING_REVIEW,
        ImportRunState.PARTIAL,
        ImportRunState.FAILED,
        ImportRunState.CANCELLED,
        ImportRunState.INTERRUPTED,
    },
    ImportRunState.AWAITING_REVIEW: {
        ImportRunState.COMPLETED,
        ImportRunState.PARTIAL,
        ImportRunState.FAILED,
        ImportRunState.CANCELLED,
    },
    ImportRunState.COMPLETED: set(),
    ImportRunState.PARTIAL: set(),
    ImportRunState.FAILED: set(),
    ImportRunState.CANCELLED: set(),
    ImportRunState.INTERRUPTED: set(),
}


def can_transition(from_state: ImportRunState, to_state: ImportRunState) -> bool:
    return to_state in _ALLOWED.get(from_state, set())


def get_allowed_transitions(state: ImportRunState) -> set[ImportRunState]:
    return set(_ALLOWED.get(state, set()))

