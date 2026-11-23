import hashlib
import sqlite3
from contextlib import closing
from pathlib import Path

from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.adapters.markdown_output import MarkdownHandoffOutput
from pathfinder_context_organizer.application.handoff import (
    BuildHandoffWorkflow,
    DeleteLocalDataWorkflow,
    project_key,
)
from pathfinder_context_organizer.application.import_session import ImportSessionWorkflow
from pathfinder_context_organizer.application.review import ReviewExtractionWorkflow
from pathfinder_context_organizer.domain.value_objects import RenderProfile, RenderTier
from pathfinder_context_organizer.infrastructure.sqlite.repo import SqliteContextRepository
from pathfinder_context_organizer.infrastructure.sqlite.schema import apply_migrations


def test_mvp_workflow(tmp_path: Path) -> None:
    fixture = Path("examples/session.jsonl").resolve()
    original_hash = hashlib.sha256(fixture.read_bytes()).digest()
    database = tmp_path / "mvp.sqlite3"
    output = MarkdownHandoffOutput(tmp_path / "exports")
    with closing(sqlite3.connect(database)) as conn:
        apply_migrations(conn)
        repo = SqliteContextRepository(conn)
        importer = ImportSessionWorkflow(repo, ClaudeCodeSessionSource())
        key = project_key("demo")

        def yes(_: str) -> bool:
            return True

        def no(_: str) -> bool:
            return False

        importer.run("demo", str(fixture), no)
        assert repo.project_items(key) == ()
        importer.run("demo", str(fixture), yes)
        before = repo.project_items(key)
        assert len(before) == 8
        importer.run("demo", str(fixture), yes)
        assert repo.project_items(key) == before
        importer.run("other", str(fixture), yes)
        review = ReviewExtractionWorkflow(repo)
        first, second, third = before[:3]
        review.review(key, first.id, "confirm", yes)
        review.review(key, second.id, "reject", yes)
        review.review(key, third.id, "confirm", yes)
        handoff = BuildHandoffWorkflow(repo, output, lambda rid: str(output.path_for(rid)))
        selection = ((first.id, RenderTier.ESSENTIAL),)
        handoff.build(key, selection, "Continue", RenderProfile.STANDARD, 4000, no)
        assert not output.directory.exists()
        result = handoff.build(key, selection, "Continue", RenderProfile.STANDARD, 4000, yes)
        path = Path(result.splitlines()[1])
        assert path.read_bytes().startswith(b"# Pathfinder")
        assert b"documentation draft" in path.read_bytes()
        assert b"SQLite store" not in path.read_bytes()
        assert b"export wording" not in path.read_bytes()
        for data in (database.read_bytes(), path.read_bytes()):
            assert b"sk-EXAMPLE_NOTREAL" not in data
            assert b"Synthetic Person" not in data
        delete = DeleteLocalDataWorkflow(repo, output.remove)
        assert "blocked" in delete.run(key, yes, with_handoffs=False)
        assert path.exists()
        delete.run(key, yes, with_handoffs=True)
        assert not path.exists()
        assert repo.project_items(key) == ()
        assert len(repo.project_items(project_key("other"))) == 8
    assert hashlib.sha256(fixture.read_bytes()).digest() == original_hash

