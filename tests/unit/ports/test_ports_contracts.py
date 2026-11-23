# tests/unit/ports/test_ports_contracts.py
from __future__ import annotations

import dataclasses
import typing

from pathfinder_context_organizer.application.types import RawSessionEvent, RedactedSegment
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
from pathfinder_context_organizer.domain.value_objects import Sensitivity
from pathfinder_context_organizer.ports.context_repository import ContextRepository
from pathfinder_context_organizer.ports.handoff_output import HandoffOutput
from pathfinder_context_organizer.ports.model_provider import ModelProvider
from pathfinder_context_organizer.ports.provider_types import (
    ProviderCandidate,
    ProviderPreflight,
    ProviderResult,
)
from pathfinder_context_organizer.ports.session_source import SessionSource


def test_port_types_are_protocols() -> None:
    for cls in (SessionSource, ModelProvider, ContextRepository, HandoffOutput):
        assert typing.Protocol in cls.__mro__


def test_session_source_type_hints() -> None:
    hints_read = typing.get_type_hints(SessionSource.read_events)
    assert hints_read["source_ref"] is str
    assert hints_read["return"] == tuple[RawSessionEvent, ...]

    hints_fp = typing.get_type_hints(SessionSource.get_fingerprint)
    assert hints_fp["source_ref"] is str
    assert hints_fp["return"] is str

    hints_lm = typing.get_type_hints(SessionSource.get_last_modified)
    assert hints_lm["source_ref"] is str
    assert hints_lm["return"] == str | None


def test_model_provider_only_redacted_segments_and_returns_provider_result() -> None:
    hints = typing.get_type_hints(ModelProvider.summarize)
    assert hints["segments"] == tuple[RedactedSegment, ...]
    assert hints["preflight"] is ProviderPreflight
    assert hints["return"] is ProviderResult
    assert "RawSessionEvent" not in str(hints["segments"])
    assert "RawSessionEvent" not in str(hints["return"])


def test_provider_preflight_type_hints() -> None:
    hints = typing.get_type_hints(ProviderPreflight)
    assert hints["import_run_id"] is str
    assert hints["provider_adapter"] is str
    assert hints["model_name"] is str
    assert hints["endpoint"] is str
    assert hints["endpoint_is_loopback"] is bool
    assert hints["may_route_externally"] is bool
    assert hints["redacted_segment_count"] is int
    assert hints["estimated_tokens"] is int
    assert hints["redacted_scope_hash"] is str
    assert hints["sensitivity_levels"] == tuple[Sensitivity, ...]
    assert hints["consent_granted_at"] is str
    assert hints["external_transfer_approved"] is bool


def test_provider_candidate_type_hints() -> None:
    hints = typing.get_type_hints(ProviderCandidate)
    assert hints["item_type"] is str
    assert hints["title"] is str
    assert hints["content_summary"] is str
    assert hints["evidence_summary"] is str
    assert hints["source_segment_ids"] == tuple[str, ...]
    assert hints["suggested_topic_labels"] == tuple[str, ...]


def test_provider_result_type_hints() -> None:
    hints = typing.get_type_hints(ProviderResult)
    assert hints["candidates"] == tuple[ProviderCandidate, ...]
    assert hints["input_tokens"] == int | None
    assert hints["output_tokens"] == int | None


def test_provider_dtos_are_frozen_slots() -> None:
    for cls in (ProviderPreflight, ProviderCandidate, ProviderResult):
        assert dataclasses.is_dataclass(cls)
        assert cls.__dataclass_params__.frozen is True
        assert hasattr(cls, "__slots__")


def test_model_provider_dtos_no_raw_session_event() -> None:
    for cls in (ProviderPreflight, ProviderCandidate, ProviderResult):
        hints = typing.get_type_hints(cls)
        for value in hints.values():
            assert "RawSessionEvent" not in str(value)


def test_context_repository_required_methods_exact_and_hints_clean() -> None:
    required = (
        "save_project",
        "get_project",
        "save_source_session",
        "get_source_session",
        "save_topic",
        "get_topic",
        "list_topics_by_project",
        "save_import_run",
        "get_import_run",
        "save_context_items",
        "get_context_item",
        "list_context_items_by_import_run",
        "save_context_item_topic",
        "list_context_item_topics_by_context_item",
        "save_handoff_package",
        "get_handoff_package",
        "save_handoff_package_items",
        "list_handoff_package_items",
        "save_handoff_render",
        "get_handoff_render",
        "save_audit_event",
        "list_audit_events_by_entity",
    )
    actual = {
        name
        for name, value in ContextRepository.__dict__.items()
        if not name.startswith("_") and callable(value)
    }
    assert actual == set(required)

    expected_hints = {
        "save_project": {"project": Project, "return": type(None)},
        "get_project": {"project_id": str, "return": Project | None},
        "save_source_session": {"source_session": SourceSession, "return": type(None)},
        "get_source_session": {"source_session_id": str, "return": SourceSession | None},
        "save_topic": {"topic": Topic, "return": type(None)},
        "get_topic": {"topic_id": str, "return": Topic | None},
        "list_topics_by_project": {"project_id": str, "return": tuple[Topic, ...]},
        "save_import_run": {"import_run": ImportRun, "return": type(None)},
        "get_import_run": {"import_run_id": str, "return": ImportRun | None},
        "save_context_items": {"items": tuple[ContextItem, ...], "return": type(None)},
        "get_context_item": {"context_item_id": str, "return": ContextItem | None},
        "list_context_items_by_import_run": {
            "import_run_id": str,
            "return": tuple[ContextItem, ...],
        },
        "save_context_item_topic": {"link": ContextItemTopic, "return": type(None)},
        "list_context_item_topics_by_context_item": {
            "context_item_id": str,
            "return": tuple[ContextItemTopic, ...],
        },
        "save_handoff_package": {"handoff_package": HandoffPackage, "return": type(None)},
        "get_handoff_package": {"handoff_package_id": str, "return": HandoffPackage | None},
        "save_handoff_package_items": {
            "items": tuple[HandoffPackageItem, ...],
            "return": type(None),
        },
        "list_handoff_package_items": {
            "handoff_package_id": str,
            "return": tuple[HandoffPackageItem, ...],
        },
        "save_handoff_render": {"handoff_render": HandoffRender, "return": type(None)},
        "get_handoff_render": {"handoff_render_id": str, "return": HandoffRender | None},
        "save_audit_event": {"audit_event": AuditEvent, "return": type(None)},
        "list_audit_events_by_entity": {
            "entity_type": str,
            "entity_id": str,
            "return": tuple[AuditEvent, ...],
        },
    }

    for name in required:
        method = ContextRepository.__dict__[name]
        hints = typing.get_type_hints(method)
        assert hints == expected_hints[name]
        assert all("RawSessionEvent" not in str(value) for value in hints.values())


def test_handoff_output_type_hints() -> None:
    hints = typing.get_type_hints(HandoffOutput.write_markdown)
    assert hints["path"] is str
    assert hints["content"] is str
    assert hints["return"] is type(None)


def test_ports_init_exports_all() -> None:
    from pathfinder_context_organizer import ports

    expected = {
        "ContextRepository",
        "HandoffOutput",
        "ModelProvider",
        "ProviderCandidate",
        "ProviderPreflight",
        "ProviderResult",
        "SessionSource",
    }
    assert set(ports.__all__) == expected
    for name in expected:
        assert hasattr(ports, name)
