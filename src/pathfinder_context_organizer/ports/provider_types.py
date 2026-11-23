# src/pathfinder_context_organizer/ports/provider_types.py
from __future__ import annotations

import dataclasses

from pathfinder_context_organizer.domain.value_objects import Sensitivity


@dataclasses.dataclass(slots=True, frozen=True)
class ProviderPreflight:
    import_run_id: str
    provider_adapter: str
    model_name: str
    endpoint: str
    endpoint_is_loopback: bool
    may_route_externally: bool
    redacted_segment_count: int
    estimated_tokens: int
    redacted_scope_hash: str
    sensitivity_levels: tuple[Sensitivity, ...]
    consent_granted_at: str
    external_transfer_approved: bool


@dataclasses.dataclass(slots=True, frozen=True)
class ProviderCandidate:
    item_type: str
    title: str
    content_summary: str
    evidence_summary: str
    source_segment_ids: tuple[str, ...]
    suggested_topic_labels: tuple[str, ...]


@dataclasses.dataclass(slots=True, frozen=True)
class ProviderResult:
    candidates: tuple[ProviderCandidate, ...]
    input_tokens: int | None
    output_tokens: int | None

