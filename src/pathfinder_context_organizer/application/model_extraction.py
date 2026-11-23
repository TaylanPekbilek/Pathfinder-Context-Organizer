"""Opt-in extraction with source-grounded provider output."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace

from pathfinder_context_organizer.application.types import RedactedSegment
from pathfinder_context_organizer.domain.context_rules import confidence_from_signals
from pathfinder_context_organizer.domain.entities import ContextItem, ImportRun
from pathfinder_context_organizer.domain.value_objects import (
    ContextItemType,
    LifecycleStatus,
    ReviewStatus,
    Sensitivity,
)
from pathfinder_context_organizer.ports.model_provider import ModelProvider
from pathfinder_context_organizer.ports.provider_types import (
    ProviderCandidate,
    ProviderPreflight,
    ProviderResult,
)


@dataclass(frozen=True, slots=True)
class ModelRequest:
    provider: ModelProvider
    endpoint: str
    model: str
    loopback: bool


def model_payload(segments: tuple[RedactedSegment, ...]) -> str:
    return json.dumps(
        [(segment.segment_id, segment.text) for segment in segments], ensure_ascii=True, indent=2
    )


def extract_with_model(
    request: ModelRequest,
    segments: tuple[RedactedSegment, ...],
    run: ImportRun,
    confirm: Callable[[str], bool],
    clock: Callable[[], str],
    new_id: Callable[[], str],
    sanitize: Callable[[str], str],
) -> tuple[tuple[ContextItem, ...], ImportRun]:
    scope = tuple(segment for segment in segments if segment.sensitivity is Sensitivity.NORMAL)
    if not scope:
        return (), run
    lookup = {segment.segment_id: segment for segment in scope}
    payload = model_payload(scope)
    size = len(payload.encode())
    if len(lookup) != len(scope) or size > 32_000:
        return (), replace(run, error_code="MODEL_SCOPE_UNSUPPORTED")
    preview = (
        f"Provider: Anthropic-compatible. Endpoint: {request.endpoint}. Model: {request.model}.\n"
        f"Loopback: {request.loopback}. The endpoint may route externally.\n"
        f"Redacted scope: {len(scope)} segments. Conservative token estimate: {size}.\n"
        f"{payload}\nApprove sending this redacted scope for this import?"
    )
    if not confirm(preview):
        return (), run
    consent = clock()
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    preflight = ProviderPreflight(
        run.id,
        "anthropic",
        request.model,
        request.endpoint,
        request.loopback,
        True,
        len(scope),
        size,
        fingerprint,
        (Sensitivity.NORMAL,),
        consent,
        True,
    )
    run = replace(
        run,
        provider_adapter="anthropic",
        model_name=request.model,
        consent_granted_at=consent,
        redacted_scope_hash=fingerprint,
    )
    try:
        response = request.provider.summarize(scope, preflight=preflight)
    except (OSError, ValueError, RuntimeError):
        return (), replace(run, error_code="MODEL_UNAVAILABLE")
    if not isinstance(response, ProviderResult) or not isinstance(response.candidates, tuple):
        return (), replace(run, error_code="MODEL_OUTPUT_REJECTED")
    items = []
    rejected = len(response.candidates) > 100
    for candidate in response.candidates[:100]:
        try:
            if not isinstance(candidate, ProviderCandidate):
                raise ValueError
            kind = ContextItemType(candidate.item_type)
            if not isinstance(candidate.title, str) or not isinstance(
                candidate.evidence_summary, str
            ):
                raise ValueError
            if not isinstance(candidate.suggested_topic_labels, tuple) or not all(
                isinstance(label, str) for label in candidate.suggested_topic_labels
            ):
                raise ValueError
            if not isinstance(candidate.content_summary, str) or not isinstance(
                candidate.source_segment_ids, tuple
            ):
                raise ValueError
            if not candidate.source_segment_ids or not all(
                isinstance(link, str) and link in lookup for link in candidate.source_segment_ids
            ):
                raise ValueError
            linked = tuple(lookup[link] for link in candidate.source_segment_ids)
            summary = sanitize(candidate.content_summary)
            if summary != candidate.content_summary or not any(
                summary in " ".join(segment.text.split()) for segment in linked
            ):
                raise ValueError
        except (ValueError, TypeError):
            rejected = True
            continue
        items.append(
            ContextItem(
                new_id(),
                run.id,
                kind,
                kind.value,
                summary,
                ReviewStatus.PROPOSED,
                LifecycleStatus.ACTIVE,
                Sensitivity.NORMAL,
                confidence_from_signals(("model_extract",)),
                ("model_extract",),
                tuple(
                    dict.fromkeys(event for segment in linked for event in segment.source_event_ids)
                ),
                linked[0].segment_id,
                "Source-linked excerpt",
                "[SOURCE]",
                None,
                False,
                run.started_at,
                run.started_at,
                None,
            )
        )
    return tuple(items), replace(run, error_code="MODEL_OUTPUT_REJECTED" if rejected else None)

