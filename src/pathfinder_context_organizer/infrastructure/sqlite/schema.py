from __future__ import annotations

import importlib.resources
import re
import sqlite3
import time

_SQL_MIGRATION_RE = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")


def _load_migrations(migrations: tuple[tuple[int, str], ...] | None) -> tuple[tuple[int, str], ...]:
    if migrations is not None:
        seen: set[int] = set()
        out: list[tuple[int, str]] = []
        for v, s in migrations:
            if not isinstance(v, int) or v <= 0:
                raise RuntimeError("invalid migration version")
            if v in seen:
                raise RuntimeError("invalid migration version")
            seen.add(v)
            out.append((v, s))
        return tuple(sorted(out, key=lambda x: x[0]))

    try:
        pkg = importlib.resources.files(
            "pathfinder_context_organizer.infrastructure.sqlite.migrations"
        )
        entries = list(pkg.iterdir())
    except OSError:
        raise RuntimeError("migration resources unavailable") from None

    loaded: list[tuple[int, str]] = []
    loaded_versions: set[int] = set()
    for entry in entries:
        name = entry.name
        if name == "__init__.py" or name == "__pycache__" or name.endswith("/"):
            continue
        if not name.endswith(".sql"):
            continue
        if not _SQL_MIGRATION_RE.match(name):
            raise RuntimeError("invalid migration version")
        try:
            ver = int(name.split("_")[0])
        except Exception:
            raise RuntimeError("invalid migration version")
        if not isinstance(ver, int) or ver <= 0 or ver in loaded_versions:
            raise RuntimeError("invalid migration version")
        loaded_versions.add(ver)
        try:
            sql = entry.read_text(encoding="utf-8")
        except Exception:
            raise RuntimeError("migration resources unavailable") from None
        loaded.append((ver, sql))

    if not loaded:
        raise RuntimeError("migration resources unavailable")

    return tuple(sorted(loaded, key=lambda x: x[0]))


def _busy(error: sqlite3.OperationalError) -> bool:
    return (getattr(error, "sqlite_errorcode", 0) & 0xFF) in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    )


def _execute_migration(conn: sqlite3.Connection, sql: str) -> None:
    statement = ""
    for char in sql:
        statement += char
        if char == ";" and sqlite3.complete_statement(statement):
            conn.execute(statement)
            statement = ""
    if statement.strip():
        conn.execute(statement)


def apply_migrations(
    conn: sqlite3.Connection, migrations: tuple[tuple[int, str], ...] | None = None
) -> None:
    if conn.in_transaction:
        raise RuntimeError("migrations require an idle connection")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    known = dict(_load_migrations(migrations))
    delays = (0.05, 0.1, 0.2)
    for attempt in range(len(delays) + 1):
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations("
                "version INTEGER PRIMARY KEY CHECK(version > 0), applied_at TEXT NOT NULL)"
            )
            break
        except sqlite3.OperationalError as error:
            if attempt == len(delays) or not _busy(error):
                raise
            time.sleep(delays[attempt])

    for attempt in range(len(delays) + 1):
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
                max_applied = max(applied, default=0)
                if max_applied > max(known, default=0) or (
                    migrations is None and applied.difference(known)
                ):
                    raise RuntimeError("unknown schema version")
                for version, sql in known.items():
                    if version > max_applied:
                        _execute_migration(conn, sql)
                        conn.execute(
                            "INSERT INTO schema_migrations VALUES (?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))",
                            (version,),
                        )
            return
        except sqlite3.OperationalError as error:
            if attempt == len(delays) or not _busy(error):
                raise
            time.sleep(delays[attempt])

