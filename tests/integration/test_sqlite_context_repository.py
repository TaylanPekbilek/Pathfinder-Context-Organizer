from __future__ import annotations

import ast
import inspect
import sqlite3
import typing
from pathlib import Path

import pytest

from pathfinder_context_organizer.domain.entities import (
    AuditEvent,
    ContextItem,
    HandoffPackage,
    HandoffPackageItem,
    HandoffRender,
    ImportRun,
    Project,
    SourceSession,
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
)
from pathfinder_context_organizer.infrastructure.sqlite import repo, schema


@pytest.fixture()
def repo_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    schema.apply_migrations(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture()
def repository(repo_conn: sqlite3.Connection) -> repo.SqliteContextRepository:
    return repo.SqliteContextRepository(repo_conn)


def _project() -> Project:
    return Project("p1", "Test", "2026-10-26T00:00:00+00:00", "2026-10-26T00:00:00+00:00")


def _source_session() -> SourceSession:
    return SourceSession(
        "s1",
        "p1",
        "claude_code_session",
        "identity",
        "masked",
        SourceStatus.AVAILABLE,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
    )


def _import_run() -> ImportRun:
    return ImportRun(
        "ir1",
        "s1",
        "user",
        "2026-10-26T00:00:00+00:00",
        "adapter",
        "model",
        "hash",
        "0-10",
        ImportRunState.COMPLETED,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T01:00:00+00:00",
        None,
        "fpb",
        "fpa",
        1000,
        "2026-10-26T00:00:00+00:00",
        None,
    )


def _context_item(confirmed: bool = False) -> ContextItem:
    return ContextItem(
        "ci1",
        "ir1",
        ContextItemType.STATUS,
        "title",
        "summary",
        ReviewStatus.CONFIRMED if confirmed else ReviewStatus.PROPOSED,
        LifecycleStatus.ACTIVE,
        Sensitivity.NORMAL,
        ConfidenceLevel.HIGH,
        ("signal",),
        ("e1", "e2"),
        "0-10",
        "evidence",
        "mask",
        None,
        False,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00" if confirmed else None,
    )


def _synth_secret(prefix: str) -> str:
    return prefix + "_EXAMPLE_NOTREAL_VALUE_ABC123DEF456"


def test_fk_batch_rollback_single_failure_via_repo(
    repository: repo.SqliteContextRepository,
) -> None:
    repository.save_project(_project())
    repository.save_source_session(_source_session())
    repository.save_import_run(_import_run())
    good = _context_item()
    bad = ContextItem(
        "ci2",
        "ir_missing",
        ContextItemType.STATUS,
        "t",
        "s",
        ReviewStatus.PROPOSED,
        LifecycleStatus.ACTIVE,
        Sensitivity.NORMAL,
        ConfidenceLevel.HIGH,
        (),
        ("e1",),
        "0-1",
        "ev",
        "m",
        None,
        False,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
        None,
    )
    with pytest.raises(Exception):
        repository.save_context_items((good, bad))
    assert repository.get_context_item("ci1") is None


def test_redacted_placeholder_roundtrip_via_repo(repository: repo.SqliteContextRepository) -> None:
    repository.save_project(_project())
    ss = SourceSession(
        "s1",
        "p1",
        "claude_code_session",
        "id",
        "[REDACTED:API_KEY]",
        SourceStatus.AVAILABLE,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
    )
    repository.save_source_session(ss)
    loaded = repository.get_source_session("s1")
    assert loaded is not None
    assert loaded.masked_source_ref == "[REDACTED:API_KEY]"


def test_synthetic_raw_secret_rejected_and_not_written_via_repo(
    repository: repo.SqliteContextRepository, caplog
) -> None:
    repository.save_project(_project())
    repository.save_source_session(_source_session())
    repository.save_import_run(_import_run())
    secret = _synth_secret("sk-")
    ci = ContextItem(
        "ci1",
        "ir1",
        ContextItemType.STATUS,
        "title",
        "summary",
        ReviewStatus.PROPOSED,
        LifecycleStatus.ACTIVE,
        Sensitivity.NORMAL,
        ConfidenceLevel.HIGH,
        (),
        ("e1",),
        "0-10",
        f"evidence with {secret}",
        "mask",
        None,
        False,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
        None,
    )
    with pytest.raises(ValueError) as exc_info:
        repository.save_context_items((ci,))
    assert secret not in str(exc_info.value)
    assert repository.get_context_item("ci1") is None
    for record in caplog.records:
        assert secret not in record.getMessage()


def test_confirmed_context_item_semantic_update_rejected_and_preserved_via_repo(
    repository: repo.SqliteContextRepository,
) -> None:
    repository.save_project(_project())
    repository.save_source_session(_source_session())
    repository.save_import_run(_import_run())
    ci = _context_item(confirmed=True)
    repository.save_context_items((ci,))
    loaded_before = repository.get_context_item("ci1")
    assert loaded_before is not None
    mutated = ContextItem(
        "ci1",
        "ir1",
        ContextItemType.DECISION,
        "new title",
        "new summary",
        ReviewStatus.CONFIRMED,
        LifecycleStatus.ACTIVE,
        Sensitivity.NORMAL,
        ConfidenceLevel.HIGH,
        ("new",),
        ("e1",),
        "0-5",
        "new evidence",
        "new mask",
        None,
        False,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T01:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
    )
    with pytest.raises(ValueError):
        repository.save_context_items((mutated,))
    loaded_after = repository.get_context_item("ci1")
    assert loaded_after == loaded_before


def test_audit_event_append_only_via_repo(repository: repo.SqliteContextRepository) -> None:
    repository.save_project(_project())
    ae1 = AuditEvent(
        "ae1",
        "create",
        "project",
        "p1",
        "2026-10-26T00:00:00+00:00",
        "user",
        ("name",),
        "success",
        None,
    )
    repository.save_audit_event(ae1)
    ae2 = AuditEvent(
        "ae1",
        "update",
        "project",
        "p1",
        "2026-10-26T01:00:00+00:00",
        "user",
        ("name",),
        "success",
        None,
    )
    with pytest.raises(Exception):
        repository.save_audit_event(ae2)
    events = repository.list_audit_events_by_entity("project", "p1")
    assert len(events) == 1
    assert events[0].id == "ae1"


def test_handoff_insert_only_via_repo(repository: repo.SqliteContextRepository) -> None:
    repository.save_project(_project())
    repository.save_source_session(_source_session())
    repository.save_import_run(_import_run())
    repository.save_context_items((_context_item(confirmed=True),))

    hp = HandoffPackage(
        "hp1",
        "p1",
        None,
        "purpose",
        "scope",
        True,
        "1.0",
        "proj",
        None,
        "2026-10-26T00:00:00+00:00",
        "2026-10-26T00:00:00+00:00",
    )
    repository.save_handoff_package(hp)
    hp2 = HandoffPackage(
        "hp1",
        "p1",
        None,
        "purpose2",
        "scope2",
        False,
        "1.1",
        "proj2",
        None,
        "2026-10-26T02:00:00+00:00",
        "2026-10-26T02:00:00+00:00",
    )
    with pytest.raises(Exception):
        repository.save_handoff_package(hp2)
    loaded_hp = repository.get_handoff_package("hp1")
    assert loaded_hp is not None
    assert loaded_hp.purpose == "purpose"

    hpi = HandoffPackageItem(
        "hpi1", "hp1", "ci1", HandoffDisposition.INCLUDED, 1, None, True, RenderTier.ESSENTIAL
    )
    repository.save_handoff_package_items((hpi,))
    hpi2 = HandoffPackageItem(
        "hpi1", "hp1", "ci1", HandoffDisposition.EXPLICITLY_EXCLUDED, 1, "reason", False, None
    )
    with pytest.raises(Exception):
        repository.save_handoff_package_items((hpi2,))
    items = repository.list_handoff_package_items("hp1")
    assert len(items) == 1
    assert items[0].disposition == HandoffDisposition.INCLUDED

    hr = HandoffRender(
        "hr1",
        "hp1",
        RenderProfile.STANDARD,
        "1.0",
        1000,
        500,
        TokenCountKind.EXACT,
        "tok",
        "ok",
        "2026-10-26T00:00:00+00:00",
        "out",
        None,
    )
    repository.save_handoff_render(hr)
    hr2 = HandoffRender(
        "hr1",
        "hp1",
        RenderProfile.DETAILED,
        "1.0",
        1000,
        800,
        TokenCountKind.EXACT,
        "tok",
        "ok",
        "2026-10-26T01:00:00+00:00",
        "out2",
        None,
    )
    with pytest.raises(Exception):
        repository.save_handoff_render(hr2)
    loaded_hr = repository.get_handoff_render("hr1")
    assert loaded_hr is not None
    assert loaded_hr.profile == RenderProfile.STANDARD


def test_save_import_run_state_transition_and_immutability(
    repository: repo.SqliteContextRepository,
) -> None:
    repository.save_project(_project())
    repository.save_source_session(_source_session())
    ir_pending = ImportRun(
        "ir1",
        "s1",
        "user",
        None,
        None,
        None,
        "hash",
        "0-10",
        ImportRunState.PENDING,
        "2026-10-26T00:00:00+00:00",
        None,
        None,
        "fpb",
        None,
        1000,
        "2026-10-26T00:00:00+00:00",
        None,
    )
    repository.save_import_run(ir_pending)
    ir_progress = ImportRun(
        "ir1",
        "s1",
        "user",
        ir_pending.consent_granted_at,
        "adapter",
        "model",
        "hash",
        "0-10",
        ImportRunState.IN_PROGRESS,
        ir_pending.started_at,
        None,
        None,
        "fpb",
        None,
        1000,
        "2026-10-26T00:00:00+00:00",
        None,
    )
    repository.save_import_run(ir_progress)
    loaded_progress = repository.get_import_run("ir1")
    assert loaded_progress is not None
    assert loaded_progress.status == ImportRunState.IN_PROGRESS

    ir_bad_completed = ImportRun(
        "ir1",
        "s1",
        "user",
        ir_progress.consent_granted_at,
        ir_progress.provider_adapter,
        ir_progress.model_name,
        ir_progress.redacted_scope_hash,
        ir_progress.event_range,
        ImportRunState.COMPLETED,
        ir_progress.started_at,
        "2026-10-26T02:00:00+00:00",
        None,
        ir_progress.source_fingerprint_before,
        ir_progress.source_fingerprint_after,
        ir_progress.source_size_bytes,
        ir_progress.source_last_modified_at,
        None,
    )
    with pytest.raises(ValueError):
        repository.save_import_run(ir_bad_completed)
    loaded_after_bad = repository.get_import_run("ir1")
    assert loaded_after_bad is not None
    assert loaded_after_bad == loaded_progress

    ir_change_session = ImportRun(
        "ir1",
        "s2",
        ir_progress.triggered_by,
        ir_progress.consent_granted_at,
        ir_progress.provider_adapter,
        ir_progress.model_name,
        ir_progress.redacted_scope_hash,
        ir_progress.event_range,
        ImportRunState.IN_PROGRESS,
        ir_progress.started_at,
        None,
        None,
        ir_progress.source_fingerprint_before,
        ir_progress.source_fingerprint_after,
        ir_progress.source_size_bytes,
        ir_progress.source_last_modified_at,
        None,
    )
    with pytest.raises(ValueError):
        repository.save_import_run(ir_change_session)

    ir_change_fpb = ImportRun(
        "ir1",
        ir_progress.source_session_id,
        ir_progress.triggered_by,
        ir_progress.consent_granted_at,
        ir_progress.provider_adapter,
        ir_progress.model_name,
        ir_progress.redacted_scope_hash,
        ir_progress.event_range,
        ImportRunState.IN_PROGRESS,
        ir_progress.started_at,
        None,
        None,
        "fpb_changed",
        ir_progress.source_fingerprint_after,
        ir_progress.source_size_bytes,
        ir_progress.source_last_modified_at,
        None,
    )
    with pytest.raises(ValueError):
        repository.save_import_run(ir_change_fpb)

    ir_change_started = ImportRun(
        "ir1",
        ir_progress.source_session_id,
        ir_progress.triggered_by,
        ir_progress.consent_granted_at,
        ir_progress.provider_adapter,
        ir_progress.model_name,
        ir_progress.redacted_scope_hash,
        ir_progress.event_range,
        ImportRunState.IN_PROGRESS,
        "2026-10-26T05:00:00+00:00",
        None,
        None,
        ir_progress.source_fingerprint_before,
        ir_progress.source_fingerprint_after,
        ir_progress.source_size_bytes,
        ir_progress.source_last_modified_at,
        None,
    )
    with pytest.raises(ValueError):
        repository.save_import_run(ir_change_started)

    loaded_final = repository.get_import_run("ir1")
    assert loaded_final == loaded_progress


def test_context_repository_protocol_methods_exact_and_callable(
    repository: repo.SqliteContextRepository,
) -> None:
    from pathfinder_context_organizer.ports.context_repository import ContextRepository

    required = [
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
    ]
    for name in required:
        assert hasattr(repository, name), f"Missing method: {name}"
        repo_m = getattr(repo.SqliteContextRepository, name)
        port_m = getattr(ContextRepository, name)
        assert callable(getattr(repository, name)), f"Not callable: {name}"
        assert inspect.signature(repo_m) == inspect.signature(port_m), f"Signature mismatch {name}"
        assert typing.get_type_hints(repo_m) == typing.get_type_hints(port_m), (
            f"Type hints mismatch {name}"
        )
        hints = typing.get_type_hints(repo_m)
        for v in hints.values():
            assert "RawSessionEvent" not in str(v), f"RawSessionEvent leak in {name}"


def test_ast_import_isolation_sqlite_repo() -> None:
    p = Path("src/pathfinder_context_organizer/infrastructure/sqlite/repo.py")
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden_mods = {
        "pathfinder_context_organizer.application",
        "pathfinder_context_organizer.workflows",
        "pathfinder_context_organizer.cli",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if any(
                    a.name == forbidden or a.name.startswith(forbidden + ".")
                    for forbidden in forbidden_mods
                ):
                    raise AssertionError(f"Forbidden import: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and any(
                node.module == f or node.module.startswith(f + ".") for f in forbidden_mods
            ):
                raise AssertionError(f"Forbidden import from: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(
                            arg.value == f or arg.value.startswith(f + ".") for f in forbidden_mods
                        ):
                            raise AssertionError(f"Forbidden __import__: {arg.value}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "importlib":
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            if any(
                                arg.value == f or arg.value.startswith(f + ".")
                                for f in forbidden_mods
                            ):
                                raise AssertionError(
                                    f"Forbidden importlib.import_module: {arg.value}"
                                )
