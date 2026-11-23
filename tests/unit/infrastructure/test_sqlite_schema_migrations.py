from __future__ import annotations

import sqlite3
from contextlib import suppress
from unittest.mock import patch

import pytest

from pathfinder_context_organizer.infrastructure.sqlite import schema


@pytest.fixture()
def mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def test_migration_atomic_rollback_with_injected_bad_migration(
    mem_conn: sqlite3.Connection,
) -> None:
    bad = ((2, "CREATE TABLE bad_x(id TEXT PRIMARY KEY); THIS_IS_INVALID_SQL"),)
    with pytest.raises(Exception):
        schema.apply_migrations(mem_conn, migrations=bad)
    cur = mem_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bad_x'")
    assert cur.fetchone() is None
    cur2 = mem_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    )
    assert cur2.fetchone() is not None
    cur3 = mem_conn.execute("SELECT COUNT(*) AS c FROM schema_migrations WHERE version = 2")
    assert cur3.fetchone()["c"] == 0


def test_schema_migrations_bootstrapped_by_runner_only(mem_conn: sqlite3.Connection) -> None:
    schema.apply_migrations(mem_conn)
    cur = mem_conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    )
    row = cur.fetchone()
    assert row is not None
    cur2 = mem_conn.execute("SELECT COUNT(*) AS c FROM schema_migrations")
    assert cur2.fetchone()["c"] >= 1


def test_0001_init_has_no_schema_migrations_create() -> None:
    import importlib.resources as r

    p = r.files("pathfinder_context_organizer.infrastructure.sqlite.migrations").joinpath(
        "0001_init.sql"
    )
    sql = p.read_text(encoding="utf-8")
    assert "CREATE TABLE schema_migrations" not in sql
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" not in sql


def test_unknown_or_higher_schema_version_safe_error_without_write(
    mem_conn: sqlite3.Connection,
) -> None:
    schema.apply_migrations(mem_conn)
    mem_conn.execute(
        "INSERT INTO schema_migrations(version, applied_at) VALUES(999, datetime('now'))"
    )
    mem_conn.commit()

    snapshot_tables = mem_conn.execute(
        "SELECT name, sql FROM sqlite_master ORDER BY name"
    ).fetchall()
    snapshot_versions = mem_conn.execute(
        "SELECT version, applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()

    with pytest.raises(RuntimeError) as exc_info:
        schema.apply_migrations(mem_conn)

    msg = str(exc_info.value)
    assert "secret" not in msg
    assert "hash" not in msg
    assert "fingerprint" not in msg
    assert "path" not in msg

    tables_after = mem_conn.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
    versions_after = mem_conn.execute(
        "SELECT version, applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert tables_after == snapshot_tables
    assert versions_after == snapshot_versions


def test_migration_lock_retry_max_three_with_fixed_delays(tmp_path) -> None:
    db_path = tmp_path / "lock.db"
    conn_boot = sqlite3.connect(db_path)
    conn_boot.execute("PRAGMA busy_timeout = 0")
    schema.apply_migrations(conn_boot)
    conn_boot.close()

    conn1 = sqlite3.connect(db_path)
    conn1.execute("PRAGMA busy_timeout = 0")
    conn1.execute("BEGIN IMMEDIATE")
    conn2 = None
    try:
        calls: list[float] = []

        def fake_sleep(delay: float) -> None:
            calls.append(delay)

        conn2 = sqlite3.connect(db_path)
        conn2.execute("PRAGMA busy_timeout = 0")

        with patch(
            "pathfinder_context_organizer.infrastructure.sqlite.schema.time.sleep", fake_sleep
        ):
            with pytest.raises(sqlite3.OperationalError) as exc_info:
                schema.apply_migrations(conn2, migrations=((2, "CREATE TABLE t_retry(x TEXT);"),))

        assert calls == [0.05, 0.1, 0.2]
        err = exc_info.value
        assert getattr(err, "sqlite_errorcode", None) in (
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        )
    finally:
        with suppress(sqlite3.Error):
            conn1.rollback()
        with suppress(sqlite3.Error):
            conn1.close()
        if conn2 is not None:
            with suppress(sqlite3.Error):
                conn2.close()


def test_migration_no_retry_on_syntax_error(tmp_path) -> None:
    db_path = tmp_path / "syntax.db"
    conn_boot = sqlite3.connect(db_path)
    conn_boot.execute("PRAGMA busy_timeout = 0")
    schema.apply_migrations(conn_boot)
    conn_boot.close()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout = 0")
    calls: list[float] = []

    def fake_sleep(delay: float) -> None:
        calls.append(delay)

    try:
        with patch(
            "pathfinder_context_organizer.infrastructure.sqlite.schema.time.sleep", fake_sleep
        ):
            with pytest.raises(Exception) as exc_info:
                schema.apply_migrations(conn, migrations=((3, "THIS IS NOT VALID SQL;"),))
        assert calls == []
        err = exc_info.value
        err_code = getattr(err, "sqlite_errorcode", None)
        assert err_code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    finally:
        with suppress(sqlite3.Error):
            conn.close()

