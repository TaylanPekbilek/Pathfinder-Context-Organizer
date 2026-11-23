import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pathfinder_context_organizer.adapters.claude_code.session_source import ClaudeCodeSessionSource
from pathfinder_context_organizer.application.handoff import project_key
from pathfinder_context_organizer.application.import_session import ImportSessionWorkflow
from pathfinder_context_organizer.application.model_extraction import ModelRequest
from pathfinder_context_organizer.application.types import RedactedSegment
from pathfinder_context_organizer.infrastructure.sqlite.repo import SqliteContextRepository
from pathfinder_context_organizer.infrastructure.sqlite.schema import apply_migrations
from pathfinder_context_organizer.ports.provider_types import (
    ProviderCandidate,
    ProviderPreflight,
    ProviderResult,
)


@pytest.mark.parametrize("mode", ["decline", "timeout", "invalid", "valid"])
def test_model_scope_consent_and_fallback(tmp_path: Path, mode: str) -> None:
    source = Path("examples/session.jsonl").resolve()
    calls = []
    previews = []

    class Provider:
        def summarize(
            self, segments: tuple[RedactedSegment, ...], *, preflight: ProviderPreflight
        ) -> ProviderResult:
            calls.append(preflight)
            assert preflight.external_transfer_approved
            assert all(isinstance(segment, RedactedSegment) for segment in segments)
            assert "sk-EXAMPLE_NOTREAL" not in repr(segments)
            assert "Synthetic Person" not in repr(segments)
            if mode == "timeout":
                raise TimeoutError("unsafe provider error")
            candidate = ProviderCandidate(
                "assumption",
                "unused",
                "The documentation draft is ready."
                if mode == "valid"
                else "sk-EXAMPLE_NOTREAL_ABC123DEF456",
                "",
                (segments[0].segment_id,) if mode == "valid" else ("nonexistent",),
                (),
            )
            return ProviderResult((candidate,), None, None)

    def confirm(preview: str) -> bool:
        previews.append(preview)
        return len(previews) == 1 or mode != "decline"

    db = tmp_path / "test.sqlite3"
    with closing(sqlite3.connect(db)) as conn:
        apply_migrations(conn)
        repository = SqliteContextRepository(conn)
        result = ImportSessionWorkflow(repository, ClaudeCodeSessionSource()).run(
            "Demo",
            str(source),
            confirm,
            ModelRequest(Provider(), "https://fake.example/v1/messages", "fake", False),
        )
        assert len(repository.project_items(project_key("Demo"))) == (9 if mode == "valid" else 8)
        assert len(previews) == 2
        assert len(calls) == (0 if mode == "decline" else 1)
        assert (
            "MODEL_UNAVAILABLE" in result
            if mode == "timeout"
            else "unsafe provider error" not in result
        )
        assert "MODEL_OUTPUT_REJECTED" in result if mode == "invalid" else True
        assert "sk-EXAMPLE_NOTREAL" not in repr(previews)
        assert "Synthetic Person" not in repr(previews)
    assert b"sk-EXAMPLE_NOTREAL" not in db.read_bytes()
    assert b"Synthetic Person" not in db.read_bytes()

