"""Mappings between SQLite rows and domain records."""

import json
import sqlite3

from pathfinder_context_organizer.domain.entities import ContextItem
from pathfinder_context_organizer.domain.value_objects import (
    ConfidenceLevel,
    ContextItemType,
    LifecycleStatus,
    ReviewStatus,
    Sensitivity,
)


def row_to_context_item(row: sqlite3.Row, source_event_ids: tuple[str, ...]) -> ContextItem:
    return ContextItem(
        id=row["id"],
        import_run_id=row["import_run_id"],
        type=ContextItemType(row["type"]),
        title=row["title"],
        content_summary=row["content_summary"],
        evidence_summary=row["evidence_summary"],
        review_status=ReviewStatus(row["review_status"]),
        lifecycle_status=LifecycleStatus(row["lifecycle_status"]),
        sensitivity=Sensitivity(row["sensitivity"]),
        confidence_level=ConfidenceLevel(row["confidence_level"]),
        quality_signals=tuple(json.loads(row["quality_signals_json"])),
        source_event_ids=source_event_ids,
        source_range=row["source_range"],
        masked_source_ref_snapshot=row["masked_source_ref_snapshot"],
        supersedes_context_item_id=row["supersedes_context_item_id"],
        user_modified=bool(row["user_modified"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        confirmed_at=row["confirmed_at"],
    )

