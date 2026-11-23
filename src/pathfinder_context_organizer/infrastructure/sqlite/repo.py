from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields

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
    HandoffDisposition,
    ImportRunState,
    RenderProfile,
    RenderTier,
    ReviewStatus,
    SourceStatus,
    TokenCountKind,
    can_transition,
)
from pathfinder_context_organizer.infrastructure.sqlite.mapping import row_to_context_item
from pathfinder_context_organizer.ports.context_repository import ContextRepository

_RE_REDACTED = re.compile(r"^\[REDACTED:[A-Z][A-Z0-9_]*\]$")
_RE_ASSIGN = re.compile(r"(?i)(api[_-]?key|access[_-]?token|token|password|secret)\s*=\s*([^\s;]+)")
_RE_SK_ANT = re.compile(r"sk-ant-[A-Za-z0-9_-]+")
_RE_SK = re.compile(r"sk-[A-Za-z0-9_-]+")
_RE_GHP = re.compile(r"ghp_[A-Za-z0-9]+")
_RE_WIN_USERS = re.compile(r"C:\\Users\\[^\s\\]+(?:\\[^\s\\]+)*", re.IGNORECASE)
_RE_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----", re.DOTALL
)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    ent = 0.0
    for c in counts.values():
        p = c / n
        ent -= p * math.log2(p)
    return ent


def _is_high_entropy(s: str) -> bool:
    if len(s) < 20 or len(s) > 200:
        return False
    if any(ch.isspace() for ch in s):
        return False
    return _shannon_entropy(s) >= 4.0


def _assert_persistable_texts(*texts: str) -> None:
    for t in texts:
        if not isinstance(t, str):
            continue
        if _RE_REDACTED.match(t):
            continue
        if _RE_PRIVATE_KEY_BLOCK.search(t):
            raise ValueError("forbidden content")
        if _RE_WIN_USERS.search(t):
            raise ValueError("forbidden content")
        if _RE_SK_ANT.search(t) or _RE_SK.search(t) or _RE_GHP.search(t):
            raise ValueError("forbidden content")
        if _RE_ASSIGN.search(t):
            raise ValueError("forbidden content")
        for token in t.split():
            if _is_high_entropy(token):
                raise ValueError("forbidden content")
    return None


def json_dumps(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _values(record: Project | SourceSession | Topic | ContextItemTopic) -> tuple[object, ...]:
    return tuple(getattr(record, field.name) for field in fields(record))


class SqliteContextRepository(ContextRepository):
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA secure_delete = ON")

    def save_import_run(self, import_run: ImportRun) -> None:
        if import_run.redacted_scope_hash and not re.fullmatch(
            r"[a-f0-9]{64}", import_run.redacted_scope_hash
        ):
            _assert_persistable_texts(import_run.redacted_scope_hash)
        cur = self._conn.execute("SELECT * FROM import_runs WHERE id = ?", (import_run.id,))
        row = cur.fetchone()
        if row is None:
            _assert_persistable_texts(import_run.event_range, import_run.error_code or "")
            with self.transaction():
                self._conn.execute(
                    "INSERT INTO import_runs(id,source_session_id,triggered_by,consent_granted_at,provider_adapter,model_name,redacted_scope_hash,event_range,status,started_at,finished_at,error_code,source_fingerprint_before,source_fingerprint_after,source_size_bytes,source_last_modified_at,interrupted_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        import_run.id,
                        import_run.source_session_id,
                        import_run.triggered_by,
                        import_run.consent_granted_at,
                        import_run.provider_adapter,
                        import_run.model_name,
                        import_run.redacted_scope_hash,
                        import_run.event_range,
                        import_run.status.value,
                        import_run.started_at,
                        import_run.finished_at,
                        import_run.error_code,
                        import_run.source_fingerprint_before,
                        import_run.source_fingerprint_after,
                        import_run.source_size_bytes,
                        import_run.source_last_modified_at,
                        import_run.interrupted_reason,
                    ),
                )
            return
        if row["source_session_id"] != import_run.source_session_id:
            raise ValueError("import_run immutable fields")
        if row["source_fingerprint_before"] != import_run.source_fingerprint_before:
            raise ValueError("import_run immutable fields")
        if row["started_at"] != import_run.started_at:
            raise ValueError("import_run immutable fields")
        cur_state = ImportRunState(row["status"])
        if not can_transition(cur_state, import_run.status):
            raise ValueError("import_run invalid transition")
        _assert_persistable_texts(import_run.event_range, import_run.error_code or "")
        with self.transaction():
            self._conn.execute(
                "UPDATE import_runs SET triggered_by=?,consent_granted_at=?,provider_adapter=?,model_name=?,redacted_scope_hash=?,event_range=?,status=?,finished_at=?,error_code=?,source_fingerprint_after=?,source_size_bytes=?,source_last_modified_at=?,interrupted_reason=? WHERE id=?",
                (
                    import_run.triggered_by,
                    import_run.consent_granted_at,
                    import_run.provider_adapter,
                    import_run.model_name,
                    import_run.redacted_scope_hash,
                    import_run.event_range,
                    import_run.status.value,
                    import_run.finished_at,
                    import_run.error_code,
                    import_run.source_fingerprint_after,
                    import_run.source_size_bytes,
                    import_run.source_last_modified_at,
                    import_run.interrupted_reason,
                    import_run.id,
                ),
            )

    def save_context_items(self, items: tuple[ContextItem, ...]) -> None:
        with self.transaction():
            for item in items:
                _assert_persistable_texts(
                    item.title,
                    item.content_summary,
                    item.evidence_summary,
                    item.masked_source_ref_snapshot,
                    item.source_range,
                )
                cur = self._conn.execute("SELECT * FROM context_items WHERE id = ?", (item.id,))
                row = cur.fetchone()
                if row is not None and ReviewStatus(row["review_status"]) is ReviewStatus.CONFIRMED:
                    raise ValueError("confirmed context item semantic immutable")
                self._conn.execute(
                    "INSERT INTO context_items(id,import_run_id,type,title,content_summary,evidence_summary,review_status,lifecycle_status,sensitivity,confidence_level,quality_signals_json,source_range,masked_source_ref_snapshot,supersedes_context_item_id,user_modified,created_at,updated_at,confirmed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET import_run_id=excluded.import_run_id,type=excluded.type,title=excluded.title,content_summary=excluded.content_summary,evidence_summary=excluded.evidence_summary,review_status=excluded.review_status,lifecycle_status=excluded.lifecycle_status,sensitivity=excluded.sensitivity,confidence_level=excluded.confidence_level,quality_signals_json=excluded.quality_signals_json,source_range=excluded.source_range,masked_source_ref_snapshot=excluded.masked_source_ref_snapshot,supersedes_context_item_id=excluded.supersedes_context_item_id,user_modified=excluded.user_modified,created_at=excluded.created_at,updated_at=excluded.updated_at,confirmed_at=excluded.confirmed_at",
                    (
                        item.id,
                        item.import_run_id,
                        item.type.value,
                        item.title,
                        item.content_summary,
                        item.evidence_summary,
                        item.review_status.value,
                        item.lifecycle_status.value,
                        item.sensitivity.value,
                        item.confidence_level.value,
                        json_dumps(tuple(item.quality_signals)),
                        item.source_range,
                        item.masked_source_ref_snapshot,
                        item.supersedes_context_item_id,
                        1 if item.user_modified else 0,
                        item.created_at,
                        item.updated_at,
                        item.confirmed_at,
                    ),
                )
                self._conn.execute(
                    "DELETE FROM context_item_source_events WHERE context_item_id = ?", (item.id,)
                )
                for ord_i, sev in enumerate(item.source_event_ids):
                    self._conn.execute(
                        "INSERT INTO context_item_source_events(context_item_id, source_event_id, ord) VALUES(?,?,?)",
                        (item.id, sev, ord_i),
                    )

    def save_audit_event(self, audit_event: AuditEvent) -> None:
        _assert_persistable_texts(
            audit_event.event_type, audit_event.entity_type, audit_event.reason_code or ""
        )
        if not re.fullmatch(r"[a-f0-9]{32}|[a-f0-9]{64}", audit_event.entity_id):
            _assert_persistable_texts(audit_event.entity_id)
        with self.transaction():
            self._conn.execute(
                "INSERT INTO audit_events(id,event_type,entity_type,entity_id,occurred_at,actor,changed_fields_json,result_status,reason_code) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    audit_event.id,
                    audit_event.event_type,
                    audit_event.entity_type,
                    audit_event.entity_id,
                    audit_event.occurred_at,
                    audit_event.actor,
                    json_dumps(tuple(audit_event.changed_fields)),
                    audit_event.result_status,
                    audit_event.reason_code,
                ),
            )

    def save_handoff_package(self, handoff_package: HandoffPackage) -> None:
        _assert_persistable_texts(
            handoff_package.purpose,
            handoff_package.scope_summary,
            handoff_package.project_name_snapshot,
        )
        with self.transaction():
            self._conn.execute(
                "INSERT INTO handoff_packages(id,project_id,topic_id,purpose,scope_summary,token_budget_applied,template_version,project_name_snapshot,topic_name_snapshot,approved_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    handoff_package.id,
                    handoff_package.project_id,
                    handoff_package.topic_id,
                    handoff_package.purpose,
                    handoff_package.scope_summary,
                    1 if handoff_package.token_budget_applied else 0,
                    handoff_package.template_version,
                    handoff_package.project_name_snapshot,
                    handoff_package.topic_name_snapshot,
                    handoff_package.approved_at,
                    handoff_package.created_at,
                ),
            )

    def save_handoff_package_items(self, items: tuple[HandoffPackageItem, ...]) -> None:
        with self.transaction():
            for item in items:
                _assert_persistable_texts(item.exclusion_reason or "")
                self._conn.execute(
                    "INSERT INTO handoff_package_items(id,handoff_package_id,context_item_id,disposition,sequence,exclusion_reason,masking_applied,render_tier) VALUES(?,?,?,?,?,?,?,?)",
                    (
                        item.id,
                        item.handoff_package_id,
                        item.context_item_id,
                        item.disposition.value,
                        item.sequence,
                        item.exclusion_reason,
                        1 if item.masking_applied else 0,
                        item.render_tier.value if item.render_tier is not None else None,
                    ),
                )

    def save_handoff_render(self, handoff_render: HandoffRender) -> None:
        if handoff_render.masked_output_ref != f"{handoff_render.id}.md" or not re.fullmatch(
            r"[a-f0-9]{32}", handoff_render.id
        ):
            _assert_persistable_texts(handoff_render.masked_output_ref or "")
        _assert_persistable_texts(handoff_render.error_code or "")
        with self.transaction():
            self._conn.execute(
                "INSERT INTO handoff_renders(id,handoff_package_id,profile,template_version,token_budget,token_count,token_count_kind,tokenizer_ref,status,generated_at,masked_output_ref,error_code) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    handoff_render.id,
                    handoff_render.handoff_package_id,
                    handoff_render.profile.value,
                    handoff_render.template_version,
                    handoff_render.token_budget,
                    handoff_render.token_count,
                    handoff_render.token_count_kind.value
                    if handoff_render.token_count_kind is not None
                    else None,
                    handoff_render.tokenizer_ref,
                    handoff_render.status,
                    handoff_render.generated_at,
                    handoff_render.masked_output_ref,
                    handoff_render.error_code,
                ),
            )

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._conn.in_transaction:
            self._conn.execute("SAVEPOINT repository_operation")
            try:
                yield
            except BaseException:
                self._conn.execute("ROLLBACK TO repository_operation")
                raise
            finally:
                self._conn.execute("RELEASE repository_operation")
        else:
            with self._conn:
                self._conn.execute("BEGIN IMMEDIATE")
                yield

    def save_project(self, project: Project) -> None:
        _assert_persistable_texts(project.name)
        with self.transaction():
            self._conn.execute("INSERT INTO projects VALUES (?,?,?,?)", _values(project))

    def save_source_session(self, source_session: SourceSession) -> None:
        _assert_persistable_texts(source_session.masked_source_ref)
        with self.transaction():
            self._conn.execute(
                "INSERT INTO source_sessions VALUES (?,?,?,?,?,?,?,?)", _values(source_session)
            )

    def save_topic(self, topic: Topic) -> None:
        _assert_persistable_texts(topic.title)
        with self.transaction():
            self._conn.execute("INSERT INTO topics VALUES (?,?,?,?,?)", _values(topic))

    def save_context_item_topic(self, link: ContextItemTopic) -> None:
        with self.transaction():
            self._conn.execute("INSERT INTO context_item_topics VALUES (?,?)", _values(link))

    def _context_item(self, row: sqlite3.Row) -> ContextItem:
        events = self._conn.execute(
            "SELECT source_event_id FROM context_item_source_events WHERE context_item_id=? ORDER BY ord",
            (row["id"],),
        )
        return row_to_context_item(row, tuple(event[0] for event in events))

    def get_context_item(self, context_item_id: str) -> ContextItem | None:
        row = self._conn.execute(
            "SELECT * FROM context_items WHERE id=?", (context_item_id,)
        ).fetchone()
        return self._context_item(row) if row else None

    def list_context_items_by_import_run(self, import_run_id: str) -> tuple[ContextItem, ...]:
        rows = self._conn.execute(
            "SELECT * FROM context_items WHERE import_run_id=? ORDER BY rowid", (import_run_id,)
        )
        return tuple(self._context_item(row) for row in rows)

    def list_topics_by_project(self, project_id: str) -> tuple[Topic, ...]:
        rows = self._conn.execute(
            "SELECT * FROM topics WHERE project_id=? ORDER BY id", (project_id,)
        )
        return tuple(Topic(**dict(row)) for row in rows)

    def list_context_item_topics_by_context_item(
        self, context_item_id: str
    ) -> tuple[ContextItemTopic, ...]:
        rows = self._conn.execute(
            "SELECT * FROM context_item_topics WHERE context_item_id=? ORDER BY topic_id",
            (context_item_id,),
        )
        return tuple(ContextItemTopic(**dict(row)) for row in rows)

    def list_handoff_package_items(self, handoff_package_id: str) -> tuple[HandoffPackageItem, ...]:
        rows = self._conn.execute(
            "SELECT * FROM handoff_package_items WHERE handoff_package_id=? ORDER BY sequence,id",
            (handoff_package_id,),
        )
        return tuple(
            HandoffPackageItem(
                **(
                    dict(row)
                    | {
                        "disposition": HandoffDisposition(row["disposition"]),
                        "render_tier": RenderTier(row["render_tier"])
                        if row["render_tier"]
                        else None,
                        "masking_applied": bool(row["masking_applied"]),
                    }
                )
            )
            for row in rows
        )

    def list_audit_events_by_entity(
        self, entity_type: str, entity_id: str
    ) -> tuple[AuditEvent, ...]:
        rows = self._conn.execute(
            "SELECT * FROM audit_events WHERE entity_type=? AND entity_id=? ORDER BY occurred_at,id",
            (entity_type, entity_id),
        )
        events = []
        for row in rows:
            values = dict(row)
            values["changed_fields"] = tuple(json.loads(values.pop("changed_fields_json")))
            events.append(AuditEvent(**values))
        return tuple(events)

    def get_project(self, project_id: str) -> Project | None:
        row = self._conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return Project(**dict(row)) if row else None

    def get_topic(self, topic_id: str) -> Topic | None:
        row = self._conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        return Topic(**dict(row)) if row else None

    def get_source_session(self, source_session_id: str) -> SourceSession | None:
        row = self._conn.execute(
            "SELECT * FROM source_sessions WHERE id=?", (source_session_id,)
        ).fetchone()
        return (
            SourceSession(**(dict(row) | {"source_status": SourceStatus(row["source_status"])}))
            if row
            else None
        )

    def get_import_run(self, import_run_id: str) -> ImportRun | None:
        row = self._conn.execute(
            "SELECT * FROM import_runs WHERE id=?", (import_run_id,)
        ).fetchone()
        return ImportRun(**(dict(row) | {"status": ImportRunState(row["status"])})) if row else None

    def get_handoff_package(self, handoff_package_id: str) -> HandoffPackage | None:
        row = self._conn.execute(
            "SELECT * FROM handoff_packages WHERE id=?", (handoff_package_id,)
        ).fetchone()
        return (
            HandoffPackage(
                **(dict(row) | {"token_budget_applied": bool(row["token_budget_applied"])})
            )
            if row
            else None
        )

    def get_handoff_render(self, handoff_render_id: str) -> HandoffRender | None:
        row = self._conn.execute(
            "SELECT * FROM handoff_renders WHERE id=?", (handoff_render_id,)
        ).fetchone()
        return (
            HandoffRender(
                **(
                    dict(row)
                    | {
                        "profile": RenderProfile(row["profile"]),
                        "token_count_kind": TokenCountKind(row["token_count_kind"])
                        if row["token_count_kind"]
                        else None,
                    }
                )
            )
            if row
            else None
        )

    def has_import(self, source_id: str, fingerprint: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM import_runs WHERE source_session_id=? AND source_fingerprint_before=? "
            "AND status IN ('awaiting_review','completed')",
            (source_id, fingerprint),
        ).fetchone()
        return row is not None

    def project_items(self, project_id: str) -> tuple[ContextItem, ...]:
        rows = self._conn.execute(
            "SELECT i.* FROM context_items i JOIN import_runs r ON r.id=i.import_run_id "
            "JOIN source_sessions s ON s.id=r.source_session_id WHERE s.project_id=? ORDER BY i.rowid",
            (project_id,),
        )
        return tuple(self._context_item(row) for row in rows)

    def supersede(self, item_id: str) -> None:
        with self.transaction():
            updated = self._conn.execute(
                "UPDATE context_items SET lifecycle_status='superseded' WHERE id=? "
                "AND review_status='confirmed' AND lifecycle_status='active'",
                (item_id,),
            )
            if updated.rowcount != 1:
                raise ValueError("replacement target is unavailable")

    def current_item_ids(self, project_id: str) -> frozenset[str]:
        rows = self._conn.execute(
            "SELECT i.id FROM context_items i JOIN import_runs r ON r.id=i.import_run_id "
            "JOIN source_sessions s ON s.id=r.source_session_id WHERE s.project_id=? "
            "AND i.review_status='confirmed' AND i.lifecycle_status='active' "
            "AND r.id=(SELECT latest.id FROM import_runs latest "
            "WHERE latest.source_session_id=s.id AND latest.status IN ('awaiting_review','completed') "
            "ORDER BY latest.rowid DESC LIMIT 1)",
            (project_id,),
        )
        return frozenset(row[0] for row in rows)

    def deletion_snapshot(self, project_id: str) -> dict[str, tuple[str, ...]]:
        result = {}
        for name, query in _PROJECT_DATA.items():
            rows = self._conn.execute(
                f"SELECT rowid,* FROM {name} WHERE {query} ORDER BY rowid", (project_id,)
            )
            result[name] = tuple(json_dumps(tuple(row)) for row in rows)
        return result

    def project_render_ids(self, project_id: str) -> tuple[str, ...]:
        rows = self._conn.execute(
            f"SELECT id FROM handoff_renders WHERE {_PROJECT_DATA['handoff_renders']} ORDER BY id",
            (project_id,),
        )
        return tuple(row[0] for row in rows)

    def delete_project(self, project_id: str) -> None:
        with self.transaction():
            for name, query in _PROJECT_DATA.items():
                if name == "context_items":
                    self._conn.execute(
                        f"UPDATE context_items SET supersedes_context_item_id=NULL WHERE {query}",
                        (project_id,),
                    )
                self._conn.execute(f"DELETE FROM {name} WHERE {query}", (project_id,))


_RUNS = "SELECT id FROM import_runs WHERE source_session_id IN (SELECT id FROM source_sessions WHERE project_id=?1)"
_ITEMS = f"SELECT id FROM context_items WHERE import_run_id IN ({_RUNS})"
_PACKAGES = "SELECT id FROM handoff_packages WHERE project_id=?1"
_PROJECT_DATA = {
    "audit_events": f"(entity_type='project' AND entity_id=?1) OR entity_id IN ({_RUNS}) "
    f"OR entity_id IN ({_ITEMS}) OR entity_id IN ({_PACKAGES})",
    "handoff_renders": f"handoff_package_id IN ({_PACKAGES})",
    "handoff_package_items": f"handoff_package_id IN ({_PACKAGES})",
    "handoff_packages": "project_id=?1",
    "context_item_topics": f"context_item_id IN ({_ITEMS})",
    "context_item_source_events": f"context_item_id IN ({_ITEMS})",
    "context_items": f"import_run_id IN ({_RUNS})",
    "import_runs": "source_session_id IN (SELECT id FROM source_sessions WHERE project_id=?1)",
    "topics": "project_id=?1",
    "source_sessions": "project_id=?1",
    "projects": "id=?1",
}
