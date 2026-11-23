import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.adapters.markdown_output import MarkdownHandoffOutput
from pathfinder_context_organizer.application.handoff import BuildHandoffWorkflow, project_key
from pathfinder_context_organizer.application.import_session import ImportSessionWorkflow
from pathfinder_context_organizer.application.review import ReviewExtractionWorkflow
from pathfinder_context_organizer.domain.value_objects import RenderProfile, RenderTier
from pathfinder_context_organizer.infrastructure.sqlite.repo import SqliteContextRepository
from pathfinder_context_organizer.infrastructure.sqlite.schema import apply_migrations


def approve(_: str) -> bool:
    return True


def test_change_after_consent_leaves_no_import(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text('{"body":"Status: first"}\n', encoding="utf-8")

    def modify(_: str) -> bool:
        source.write_text('{"body":"Status: edited"}\n', encoding="utf-8")
        return True

    with closing(sqlite3.connect(":memory:")) as conn:
        apply_migrations(conn)
        repo = SqliteContextRepository(conn)
        workflow = ImportSessionWorkflow(repo, ClaudeCodeSessionSource())
        with pytest.raises(ValueError, match="source changed"):
            workflow.run("demo", str(source), modify)
        assert repo.get_project(project_key("demo")) is None
        assert "1 proposals" in workflow.run("demo", str(source), approve)


def test_interrupted_import_rolls_back_and_can_retry(tmp_path: Path) -> None:
    source = str(Path("examples/session.jsonl").resolve())
    db = tmp_path / "store.sqlite3"

    class InterruptedRepository(SqliteContextRepository):
        def save_context_items(self, items):
            super().save_context_items(items)
            raise KeyboardInterrupt

    with closing(sqlite3.connect(db)) as conn:
        apply_migrations(conn)
        workflow = ImportSessionWorkflow(InterruptedRepository(conn), ClaudeCodeSessionSource())
        with pytest.raises(KeyboardInterrupt):
            workflow.run("demo", source, approve)
    with closing(sqlite3.connect(db)) as conn:
        apply_migrations(conn)
        repo = SqliteContextRepository(conn)
        assert repo.get_project(project_key("demo")) is None
        assert "8 proposals" in ImportSessionWorkflow(repo, ClaudeCodeSessionSource()).run(
            "demo", source, approve
        )


def test_write_failure_preserves_package_for_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = str(Path("examples/session.jsonl").resolve())
    output = MarkdownHandoffOutput(tmp_path / "output")
    with closing(sqlite3.connect(":memory:")) as conn:
        apply_migrations(conn)
        repo = SqliteContextRepository(conn)
        ImportSessionWorkflow(repo, ClaudeCodeSessionSource()).run("demo", source, approve)
        project = project_key("demo")
        item = repo.project_items(project)[0]
        ReviewExtractionWorkflow(repo).review(project, item.id, "confirm", approve)
        workflow = BuildHandoffWorkflow(repo, output, lambda rid: str(output.path_for(rid)))
        method = Path.rename if __import__("os").name == "nt" else __import__("os").link

        def fail(*args, **kwargs):
            raise PermissionError("fixture")

        with monkeypatch.context() as patch:
            if method is Path.rename:
                patch.setattr(Path, "rename", fail)
            else:
                patch.setattr("os.link", fail)
            with pytest.raises(PermissionError):
                workflow.build(
                    project,
                    ((item.id, RenderTier.ESSENTIAL),),
                    "Continue",
                    RenderProfile.STANDARD,
                    4000,
                    approve,
                )
        assert not list(output.directory.iterdir())
        package_id = conn.execute("SELECT id FROM handoff_packages").fetchone()[0]
        first = workflow.export(package_id, RenderProfile.STANDARD, 4000, approve)
        second = workflow.export(package_id, RenderProfile.STANDARD, 4000, approve)
        assert Path(first.splitlines()[1]).read_bytes() == Path(second.splitlines()[1]).read_bytes()

