# src/pathfinder_context_organizer/domain/entities.py
from __future__ import annotations

import dataclasses

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
)


@dataclasses.dataclass(slots=True, frozen=True)
class Project:
    id: str
    name: str
    created_at: str
    updated_at: str


@dataclasses.dataclass(slots=True, frozen=True)
class SourceSession:
    id: str
    project_id: str
    source_type: str
    session_identity: str
    masked_source_ref: str
    source_status: SourceStatus
    first_seen_at: str
    last_checked_at: str


@dataclasses.dataclass(slots=True, frozen=True)
class Topic:
    id: str
    project_id: str
    title: str
    created_at: str
    updated_at: str


@dataclasses.dataclass(slots=True, frozen=True)
class ContextItem:
    id: str
    import_run_id: str
    type: ContextItemType
    title: str
    content_summary: str
    review_status: ReviewStatus
    lifecycle_status: LifecycleStatus
    sensitivity: Sensitivity
    confidence_level: ConfidenceLevel
    quality_signals: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    source_range: str
    evidence_summary: str
    masked_source_ref_snapshot: str
    supersedes_context_item_id: str | None
    user_modified: bool
    created_at: str
    updated_at: str
    confirmed_at: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class HandoffPackage:
    id: str
    project_id: str
    topic_id: str | None
    purpose: str
    scope_summary: str
    token_budget_applied: bool
    template_version: str
    project_name_snapshot: str
    topic_name_snapshot: str | None
    approved_at: str
    created_at: str


@dataclasses.dataclass(slots=True, frozen=True)
class HandoffPackageItem:
    id: str
    handoff_package_id: str
    context_item_id: str
    disposition: HandoffDisposition
    sequence: int
    exclusion_reason: str | None
    masking_applied: bool
    render_tier: RenderTier | None


@dataclasses.dataclass(slots=True, frozen=True)
class HandoffRender:
    id: str
    handoff_package_id: str
    profile: RenderProfile
    template_version: str
    token_budget: int | None
    token_count: int | None
    token_count_kind: TokenCountKind | None
    tokenizer_ref: str | None
    status: str
    generated_at: str | None
    masked_output_ref: str | None
    error_code: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class ImportRun:
    id: str
    source_session_id: str
    triggered_by: str
    consent_granted_at: str | None
    provider_adapter: str | None
    model_name: str | None
    redacted_scope_hash: str
    event_range: str
    status: ImportRunState
    started_at: str
    finished_at: str | None
    error_code: str | None
    source_fingerprint_before: str
    source_fingerprint_after: str | None
    source_size_bytes: int
    source_last_modified_at: str
    interrupted_reason: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class AuditEvent:
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    occurred_at: str
    actor: str
    changed_fields: tuple[str, ...]
    result_status: str
    reason_code: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class ContextItemTopic:
    context_item_id: str
    topic_id: str

