from __future__ import annotations

import ast
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pathfinder_context_organizer.domain.entities import ContextItem
from pathfinder_context_organizer.infrastructure.sqlite import mapping


def test_normalized_context_item_source_events_roundtrip_and_order() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
    CREATE TABLE import_runs(
        id TEXT PRIMARY KEY, source_session_id TEXT NOT NULL, triggered_by TEXT NOT NULL,
        consent_granted_at TEXT, provider_adapter TEXT, model_name TEXT,
        redacted_scope_hash TEXT NOT NULL, event_range TEXT NOT NULL,
        status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
        error_code TEXT, source_fingerprint_before TEXT NOT NULL,
        source_fingerprint_after TEXT, source_size_bytes INTEGER NOT NULL,
        source_last_modified_at TEXT NOT NULL, interrupted_reason TEXT
    );
    CREATE TABLE context_items(
        id TEXT PRIMARY KEY, import_run_id TEXT NOT NULL, type TEXT NOT NULL,
        title TEXT NOT NULL, content_summary TEXT NOT NULL, evidence_summary TEXT NOT NULL,
        review_status TEXT NOT NULL, lifecycle_status TEXT NOT NULL,
        sensitivity TEXT NOT NULL, confidence_level TEXT NOT NULL,
        quality_signals_json TEXT NOT NULL, source_range TEXT NOT NULL,
        masked_source_ref_snapshot TEXT NOT NULL, supersedes_context_item_id TEXT,
        user_modified INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        confirmed_at TEXT, FOREIGN KEY(import_run_id) REFERENCES import_runs(id) ON DELETE RESTRICT
    );
    CREATE TABLE context_item_source_events(
        context_item_id TEXT NOT NULL, source_event_id TEXT NOT NULL, ord INTEGER NOT NULL,
        PRIMARY KEY(context_item_id, source_event_id), UNIQUE(context_item_id, ord),
        FOREIGN KEY(context_item_id) REFERENCES context_items(id) ON DELETE RESTRICT
    );
    CREATE INDEX idx_cise_source_event ON context_item_source_events(source_event_id);
    """
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO import_runs VALUES('ir1','ss1','user',NULL,'adapter','model','hash','0-10','completed',?,NULL,NULL,'fpb',NULL,100,?,NULL)",
        (now, now),
    )
    conn.execute(
        "INSERT INTO context_items VALUES('ci1','ir1','status','title','summary','evidence','confirmed','active','normal','high','[]','range','mask',NULL,0,?,?,NULL)",
        (now, now),
    )
    for i, e in enumerate(["e2", "e1", "e0"]):
        conn.execute("INSERT INTO context_item_source_events VALUES('ci1', ?, ?)", (e, i))
    conn.commit()
    cur = conn.execute("SELECT * FROM context_items WHERE id='ci1'")
    row = cur.fetchone()
    c = conn.execute(
        "SELECT source_event_id FROM context_item_source_events WHERE context_item_id=? ORDER BY ord",
        ("ci1",),
    )
    ids = tuple(r[0] for r in c.fetchall())
    assert ids == ("e2", "e1", "e0")
    item = mapping.row_to_context_item(row, ids)
    assert isinstance(item, ContextItem)
    assert item.id == "ci1"
    assert item.source_event_ids == ("e2", "e1", "e0")
    conn.close()


def test_mapping_has_no_typing_any() -> None:
    p = Path("src/pathfinder_context_organizer/infrastructure/sqlite/mapping.py")
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            for alias in node.names:
                assert alias.name != "Any"
        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "typing"
                and node.attr == "Any"
            ):
                raise AssertionError
        elif isinstance(node, ast.Name):
            assert node.id != "Any"

