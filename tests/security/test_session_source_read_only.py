# tests/security/test_session_source_read_only.py
from __future__ import annotations

import json
from pathlib import Path

from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource


def _write_jsonl(tmp: Path, name: str, lines: list[dict]) -> str:
    p = tmp / name
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return str(p.resolve())


def test_no_discovery_globbing_no_persistence(tmp_path: Path, monkeypatch) -> None:
    src = ClaudeCodeSessionSource()
    calls: list[str] = []
    import glob as globmod
    import os as osmod

    orig_glob = globmod.glob
    orig_listdir = osmod.listdir
    orig_walk = osmod.walk

    def fake_glob(*a, **kw):
        calls.append("glob")
        return orig_glob(*a, **kw)

    def fake_listdir(*a, **kw):
        calls.append("listdir")
        return orig_listdir(*a, **kw)

    def fake_walk(*a, **kw):
        calls.append("walk")
        yield from orig_walk(*a, **kw)

    monkeypatch.setattr(globmod, "glob", fake_glob)
    monkeypatch.setattr(osmod, "listdir", fake_listdir)
    monkeypatch.setattr(osmod, "walk", fake_walk)

    p = _write_jsonl(tmp_path, "sess.jsonl", [{"body": "x"}])
    _ = src.read_events(str(Path(p).resolve()))
    assert "glob" not in calls
    assert "listdir" not in calls
    assert "walk" not in calls


def test_no_writes_or_temp_or_cache_creations(tmp_path: Path) -> None:
    src = ClaudeCodeSessionSource()
    p = _write_jsonl(tmp_path, "sess.jsonl", [{"body": "x"}])
    before = set(tmp_path.rglob("*"))
    _ = src.read_events(str(Path(p).resolve()))
    src.get_fingerprint(str(Path(p).resolve()))
    src.get_last_modified(str(Path(p).resolve()))
    after = set(tmp_path.rglob("*"))
    assert before == after

