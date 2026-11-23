# tests/unit/domain/test_entities_state_machine.py
from __future__ import annotations

import dataclasses
import typing

from pathfinder_context_organizer.domain.entities import (
    AuditEvent,
    ContextItem,
    ContextItemTopic,
    HandoffPackage,
    HandoffPackageItem,
    HandoffRender,
    ImportRun,
    Project,
    SourceSession,
    Topic,
)
from pathfinder_context_organizer.domain.value_objects import (
    ConfidenceLevel,
    ContextItemType,
    HandoffDisposition,
    ImportRunState,
    LifecycleStatus,
    RenderProfile,
    RenderTier,
    ReviewStatus,
    Sensitivity,
    SourceStatus,
    TokenCountKind,
    can_transition,
    get_allowed_transitions,
)


def test_enums_closed_sets() -> None:
    # ImportRunState
    assert {e.value for e in ImportRunState} == {
        "pending",
        "awaiting_consent",
        "in_progress",
        "awaiting_review",
        "completed",
        "partial",
        "failed",
        "cancelled",
        "interrupted",
    }
    # SourceStatus
    assert {e.value for e in SourceStatus} == {
        "available",
        "source_unavailable",
        "source_changed",
    }
    # ContextItemType
    assert {e.value for e in ContextItemType} == {
        "status",
        "decision",
        "open_task",
        "file_reference",
        "assumption",
        "risk",
    }
    # ReviewStatus
    assert {e.value for e in ReviewStatus} == {
        "proposed",
        "confirmed",
        "rejected",
    }
    # LifecycleStatus
    assert {e.value for e in LifecycleStatus} == {
        "active",
        "superseded",
        "disputed",
    }
    # Sensitivity
    assert {e.value for e in Sensitivity} == {
        "normal",
        "private",
        "sensitive",
        "secret",
    }
    # ConfidenceLevel
    assert {e.value for e in ConfidenceLevel} == {
        "high",
        "medium",
        "low",
    }
    # HandoffDisposition
    assert {e.value for e in HandoffDisposition} == {
        "included",
        "explicitly_excluded",
    }
    # RenderTier
    assert {e.value for e in RenderTier} == {
        "essential",
        "standard",
        "detail",
    }
    # RenderProfile
    assert {e.value for e in RenderProfile} == {
        "short",
        "standard",
        "detailed",
    }
    # TokenCountKind
    assert {e.value for e in TokenCountKind} == {
        "exact",
        "estimated",
    }


def test_all_entities_are_dataclasses_with_slots() -> None:
    for cls in (
        Project,
        SourceSession,
        Topic,
        ContextItem,
        HandoffPackage,
        HandoffPackageItem,
        HandoffRender,
        ImportRun,
        AuditEvent,
        ContextItemTopic,
    ):
        assert dataclasses.is_dataclass(cls), f"{cls} must be dataclass"
        assert hasattr(cls, "__slots__"), f"{cls} must have __slots__"
        params = cls.__dataclass_params__
        assert params.slots is True


def test_entity_fields_and_type_hints() -> None:
    # Project
    assert {f.name for f in dataclasses.fields(Project)} == {
        "id",
        "name",
        "created_at",
        "updated_at",
    }
    # SourceSession
    assert {f.name for f in dataclasses.fields(SourceSession)} == {
        "id",
        "project_id",
        "source_type",
        "session_identity",
        "masked_source_ref",
        "source_status",
        "first_seen_at",
        "last_checked_at",
    }
    hints = typing.get_type_hints(SourceSession)
    assert hints["source_status"] is SourceStatus
    # Topic
    assert {f.name for f in dataclasses.fields(Topic)} == {
        "id",
        "project_id",
        "title",
        "created_at",
        "updated_at",
    }
    # ContextItem
    assert {f.name for f in dataclasses.fields(ContextItem)} == {
        "id",
        "import_run_id",
        "type",
        "title",
        "content_summary",
        "review_status",
        "lifecycle_status",
        "sensitivity",
        "confidence_level",
        "quality_signals",
        "source_event_ids",
        "source_range",
        "evidence_summary",
        "masked_source_ref_snapshot",
        "supersedes_context_item_id",
        "user_modified",
        "created_at",
        "updated_at",
        "confirmed_at",
    }
    hints = typing.get_type_hints(ContextItem)
    assert hints["type"] is ContextItemType
    assert hints["review_status"] is ReviewStatus
    assert hints["lifecycle_status"] is LifecycleStatus
    assert hints["sensitivity"] is Sensitivity
    assert hints["confidence_level"] is ConfidenceLevel
    # HandoffPackage
    assert {f.name for f in dataclasses.fields(HandoffPackage)} == {
        "id",
        "project_id",
        "topic_id",
        "purpose",
        "scope_summary",
        "token_budget_applied",
        "template_version",
        "project_name_snapshot",
        "topic_name_snapshot",
        "approved_at",
        "created_at",
    }
    # HandoffPackageItem
    assert {f.name for f in dataclasses.fields(HandoffPackageItem)} == {
        "id",
        "handoff_package_id",
        "context_item_id",
        "disposition",
        "sequence",
        "exclusion_reason",
        "masking_applied",
        "render_tier",
    }
    hints = typing.get_type_hints(HandoffPackageItem)
    assert hints["disposition"] is HandoffDisposition
    assert hints["render_tier"] == (RenderTier | None)
    # HandoffRender
    assert {f.name for f in dataclasses.fields(HandoffRender)} == {
        "id",
        "handoff_package_id",
        "profile",
        "template_version",
        "token_budget",
        "token_count",
        "token_count_kind",
        "tokenizer_ref",
        "status",
        "generated_at",
        "masked_output_ref",
        "error_code",
    }
    hints = typing.get_type_hints(HandoffRender)
    assert hints["profile"] is RenderProfile
    assert hints["token_count_kind"] == (TokenCountKind | None)
    # ImportRun
    assert {f.name for f in dataclasses.fields(ImportRun)} == {
        "id",
        "source_session_id",
        "triggered_by",
        "consent_granted_at",
        "provider_adapter",
        "model_name",
        "redacted_scope_hash",
        "event_range",
        "status",
        "started_at",
        "finished_at",
        "error_code",
        "source_fingerprint_before",
        "source_fingerprint_after",
        "source_size_bytes",
        "source_last_modified_at",
        "interrupted_reason",
    }
    hints = typing.get_type_hints(ImportRun)
    assert hints["status"] is ImportRunState
    # AuditEvent
    assert {f.name for f in dataclasses.fields(AuditEvent)} == {
        "id",
        "event_type",
        "entity_type",
        "entity_id",
        "occurred_at",
        "actor",
        "changed_fields",
        "result_status",
        "reason_code",
    }


def test_context_item_topic_fields() -> None:
    assert {f.name for f in dataclasses.fields(ContextItemTopic)} == {
        "context_item_id",
        "topic_id",
    }
    # frozen=True for relationship record
    params = ContextItemTopic.__dataclass_params__
    assert params.frozen is True


# Full transition table (must match value_objects._ALLOWED exactly)
_EXPECTED_TRANSITIONS: dict[ImportRunState, set[ImportRunState]] = {
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


def test_full_transition_table() -> None:
    for state in ImportRunState:
        allowed = get_allowed_transitions(state)
        expected = _EXPECTED_TRANSITIONS[state]
        assert allowed == expected, f"{state}: got {allowed}, expected {expected}"


def test_can_transition_matches_table() -> None:
    for from_state in ImportRunState:
        for to_state in ImportRunState:
            expected = to_state in _EXPECTED_TRANSITIONS[from_state]
            assert can_transition(from_state, to_state) is expected


def test_terminal_states_no_outgoing() -> None:
    for state in (
        ImportRunState.COMPLETED,
        ImportRunState.PARTIAL,
        ImportRunState.FAILED,
        ImportRunState.CANCELLED,
        ImportRunState.INTERRUPTED,
    ):
        assert get_allowed_transitions(state) == set()
        for other in ImportRunState:
            if other != state:
                assert can_transition(state, other) is False


def test_in_progress_to_completed_forbidden() -> None:
    assert can_transition(ImportRunState.IN_PROGRESS, ImportRunState.COMPLETED) is False


def test_pending_to_completed_forbidden() -> None:
    assert can_transition(ImportRunState.PENDING, ImportRunState.COMPLETED) is False


def test_interrupted_from_in_progress_allowed() -> None:
    assert can_transition(ImportRunState.IN_PROGRESS, ImportRunState.INTERRUPTED) is True


def test_failure_and_cancel_from_pending_and_awaiting_consent() -> None:
    assert can_transition(ImportRunState.PENDING, ImportRunState.CANCELLED) is True
    assert can_transition(ImportRunState.AWAITING_CONSENT, ImportRunState.CANCELLED) is True
    assert can_transition(ImportRunState.PENDING, ImportRunState.FAILED) is True
    assert can_transition(ImportRunState.AWAITING_CONSENT, ImportRunState.FAILED) is True


def test_deterministic_only_pending_to_in_progress_allowed() -> None:
    assert can_transition(ImportRunState.PENDING, ImportRunState.IN_PROGRESS) is True
