"""Pure context item rules shared by extraction and persistence."""

from pathfinder_context_organizer.domain.entities import ContextItem
from pathfinder_context_organizer.domain.value_objects import ConfidenceLevel, ReviewStatus


def confidence_from_signals(signals: tuple[str, ...]) -> ConfidenceLevel:
    if "user_verified" in signals:
        return ConfidenceLevel.HIGH
    if "explicit_label" in signals:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def validate_context_item(item: ContextItem) -> None:
    if (
        not item.id
        or not item.import_run_id
        or not item.title.strip()
        or not item.content_summary.strip()
    ):
        raise ValueError("context item requires identity, title and summary")
    if not item.source_event_ids or any(not event for event in item.source_event_ids):
        raise ValueError("context item requires a source link")
    if len(set(item.source_event_ids)) != len(item.source_event_ids):
        raise ValueError("context item source links must be unique")
    if (item.review_status is ReviewStatus.CONFIRMED) != bool(item.confirmed_at):
        raise ValueError("review status and confirmation time disagree")
    if item.supersedes_context_item_id == item.id:
        raise ValueError("item cannot supersede itself")

