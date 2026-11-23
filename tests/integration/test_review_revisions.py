import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.adapters.markdown_output import MarkdownHandoffOutput
from pathfinder_context_organizer.application.handoff import BuildHandoffWorkflow, project_key
from pathfinder_context_organizer.application.import_session import ImportSessionWorkflow
from pathfinder_context_organizer.application.review import ReviewExtractionWorkflow
from pathfinder_context_organizer.domain.value_objects import (
    LifecycleStatus,
    RenderProfile,
    RenderTier,
)
from pathfinder_context_organizer.infrastructure.sqlite.repo import SqliteContextRepository
from pathfinder_context_organizer.infrastructure.sqlite.schema import apply_migrations


def approve(_: str) -> bool:
    return True


def test_revision_does_not_rewrite_approved_package(tmp_path: Path) -> None:
    source = tmp_path / "fixture.jsonl"
    source.write_text('{"body":"Status: original text"}\n', encoding="utf-8")
    project = project_key("demo")
    output = MarkdownHandoffOutput(tmp_path / "exports")
    with closing(sqlite3.connect(":memory:")) as conn:
        apply_migrations(conn)
        repo = SqliteContextRepository(conn)
        importer = ImportSessionWorkflow(repo, ClaudeCodeSessionSource())
        importer.run("demo", str(source), approve)
        review = ReviewExtractionWorkflow(repo)
        original = repo.project_items(project)[0]
        review.review(project, original.id, "confirm", approve, topic_title="Docs")
        topic = repo.list_topics_by_project(project)[0]
        workflow = BuildHandoffWorkflow(repo, output, lambda rid: str(output.path_for(rid)))
        selection = ((original.id, RenderTier.ESSENTIAL),)
        initial = workflow.build(
            project, selection, "Continue", RenderProfile.SHORT, 4000, approve, topic.id
        )
        review.review(project, original.id, "edit", approve, text="corrected text")
        replacement = repo.project_items(project)[-1]
        review.review(project, replacement.id, "confirm", approve)
        old, new = repo.project_items(project)
        assert old.content_summary == "original text"
        assert old.lifecycle_status is LifecycleStatus.SUPERSEDED
        assert new.content_summary == "corrected text"
        with pytest.raises(ValueError, match="active item"):
            workflow.build(project, selection, "Continue", RenderProfile.SHORT, 4000, approve)
        package_id = initial.splitlines()[0].split()[1]
        exported = workflow.export(package_id, RenderProfile.SHORT, 4000, approve)
        assert (
            Path(initial.splitlines()[1]).read_bytes()
            == Path(exported.splitlines()[1]).read_bytes()
        )
        source.write_text('{"body":"Status: refreshed source"}\n', encoding="utf-8")
        importer.run("demo", str(source), approve)
        assert repo.current_item_ids(project) == frozenset()

