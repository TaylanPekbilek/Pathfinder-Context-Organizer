"""Consent, redaction and extraction for one explicitly selected file."""

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from pathfinder_context_organizer.application.model_extraction import (
    ModelRequest,
    extract_with_model,
)
from pathfinder_context_organizer.application.safety import SafetyProcessor
from pathfinder_context_organizer.application.types import RedactedSegment
from pathfinder_context_organizer.application.workflow_ports import WorkflowRepository
from pathfinder_context_organizer.domain.context_rules import confidence_from_signals
from pathfinder_context_organizer.domain.entities import (
    AuditEvent,
    ContextItem,
    ImportRun,
    Project,
    SourceSession,
)
from pathfinder_context_organizer.domain.policies import RedactionPolicy
from pathfinder_context_organizer.domain.value_objects import (
    ContextItemType,
    ImportRunState,
    LifecycleStatus,
    ReviewStatus,
    SourceStatus,
)
from pathfinder_context_organizer.ports.session_source import SessionSource

Confirm = Callable[[str], bool]
SAFETY = SafetyProcessor(RedactionPolicy())

_LABELS = {
    "status": ContextItemType.STATUS,
    "durum": ContextItemType.STATUS,
    "decision": ContextItemType.DECISION,
    "karar": ContextItemType.DECISION,
    "todo": ContextItemType.OPEN_TASK,
    "task": ContextItemType.OPEN_TASK,
    "açık iş": ContextItemType.OPEN_TASK,
    "file": ContextItemType.FILE_REFERENCE,
    "dosya": ContextItemType.FILE_REFERENCE,
    "assumption": ContextItemType.ASSUMPTION,
    "varsayım": ContextItemType.ASSUMPTION,
    "risk": ContextItemType.RISK,
}
_LABEL_LINE = re.compile(r"^\s*(?:[-*]\s+)?([^:]{1,25}):\s*(\S.*)$")


def now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return uuid4().hex


def safe_text(value: str, *, limit: int = 1200) -> str:
    cleaned, _ = SAFETY.redact(value)
    cleaned = " ".join(cleaned.split())
    if not cleaned or len(cleaned) > limit or any(not char.isprintable() for char in cleaned):
        raise ValueError("text is empty, too long, or contains control characters")
    return cleaned


def audit(
    repository: WorkflowRepository,
    action: str,
    entity_type: str,
    entity_id: str,
    result: str = "ok",
) -> None:
    repository.save_audit_event(
        AuditEvent(
            new_id(),
            action,
            entity_type,
            entity_id,
            now(),
            "local",
            (),
            result,
            None,
        )
    )


def extract(segments: tuple[RedactedSegment, ...], run: ImportRun) -> tuple[ContextItem, ...]:
    candidates = []
    seen = set()
    for segment in segments:
        for line in segment.text.splitlines():
            match = _LABEL_LINE.fullmatch(line)
            if not match:
                continue
            kind = _LABELS.get(match[1].strip().casefold())
            if kind is None:
                continue
            try:
                summary = safe_text(match[2])
            except ValueError:
                continue
            key = (kind, summary)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                ContextItem(
                    new_id(),
                    run.id,
                    kind,
                    kind.value,
                    summary,
                    ReviewStatus.PROPOSED,
                    LifecycleStatus.ACTIVE,
                    segment.sensitivity,
                    confidence_from_signals(("explicit_label",)),
                    ("explicit_label",),
                    segment.source_event_ids,
                    segment.segment_id,
                    "Explicitly labelled source line",
                    "[SOURCE]",
                    None,
                    False,
                    run.started_at,
                    run.started_at,
                    None,
                )
            )
    return tuple(candidates)


class ImportSessionWorkflow:
    def __init__(self, repository: WorkflowRepository, source: SessionSource) -> None:
        self.repository = repository
        self.source = source

    def run(
        self,
        project_name: str,
        source_ref: str,
        confirm: Confirm,
        model: ModelRequest | None = None,
    ) -> str:
        project_name = safe_text(project_name, limit=80)
        before = self.source.get_fingerprint(source_ref)
        last_modified = self.source.get_last_modified(source_ref) or ""
        size = int(before.split(":")[0])
        source_id = hashlib.sha256(
            (project_name + "\0" + os.path.normcase(os.path.normpath(source_ref))).encode()
        ).hexdigest()
        project_id = hashlib.sha256(project_name.encode()).hexdigest()
        if not confirm(
            f"Read the selected JSONL file into memory for project {project_name}? "
            f"Size: {size} bytes. Modified: {last_modified}."
        ):
            audit(self.repository, "source_read", "operation", new_id(), "cancelled")
            return "Import cancelled."
        if self.source.get_fingerprint(source_ref) != before:
            raise ValueError("source changed after preview")
        if self.repository.has_import(source_id, before):
            return "Already imported. Review the existing items."
        safe = SAFETY.process(self.source.read_events(source_ref), max_segment_chars=2400)
        started = now()
        run = ImportRun(
            new_id(),
            source_id,
            "local",
            started,
            None,
            None,
            "",
            str(len(safe.segments)),
            ImportRunState.PENDING,
            started,
            None,
            None,
            before,
            None,
            size,
            last_modified,
            None,
        )
        items = extract(safe.segments, run)
        if model is not None:
            extra, run = extract_with_model(
                model, safe.segments, run, confirm, now, new_id, safe_text
            )
            seen = {(item.type, item.content_summary) for item in items}
            for item in extra:
                key = (item.type, item.content_summary)
                if key not in seen:
                    items += (item,)
                    seen.add(key)
        if self.source.get_fingerprint(source_ref) != before:
            raise ValueError("source changed during import")
        repo = self.repository
        with repo.transaction():
            if repo.has_import(source_id, before):
                return "Already imported. Review the existing items."
            if repo.get_project(project_id) is None:
                repo.save_project(Project(project_id, project_name, started, started))
            if repo.get_source_session(source_id) is None:
                repo.save_source_session(
                    SourceSession(
                        source_id,
                        project_id,
                        "claude_code",
                        source_id,
                        "[SOURCE]",
                        SourceStatus.AVAILABLE,
                        started,
                        started,
                    )
                )
            repo.save_import_run(run)
            run = replace(run, status=ImportRunState.IN_PROGRESS)
            repo.save_import_run(run)
            repo.save_context_items(items)
            run = replace(
                run, status=ImportRunState.AWAITING_REVIEW, source_fingerprint_after=before
            )
            repo.save_import_run(run)
            if not items:
                repo.save_import_run(
                    replace(run, status=ImportRunState.COMPLETED, finished_at=now())
                )
            audit(repo, "import", "project", project_id)
        suffix = (
            " Model fallback or validation warning: " + run.error_code if run.error_code else ""
        )
        return f"{len(items)} proposals saved.{suffix}"
