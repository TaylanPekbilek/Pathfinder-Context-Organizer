"""Project-scoped review with immutable confirmed content."""

from dataclasses import replace

from pathfinder_context_organizer.application.import_session import (
    SAFETY,
    Confirm,
    audit,
    new_id,
    now,
    safe_text,
)
from pathfinder_context_organizer.application.workflow_ports import WorkflowRepository
from pathfinder_context_organizer.domain.entities import ContextItem, ContextItemTopic, Topic
from pathfinder_context_organizer.domain.policies import SupersessionPolicy
from pathfinder_context_organizer.domain.value_objects import (
    ContextItemType,
    ImportRunState,
    LifecycleStatus,
    ReviewStatus,
    Sensitivity,
)


class ReviewExtractionWorkflow:
    def __init__(self, repository: WorkflowRepository) -> None:
        self.repository = repository

    def list_items(self, project_id: str) -> tuple[ContextItem, ...]:
        return self.repository.project_items(project_id)

    def review(
        self,
        project_id: str,
        item_id: str,
        action: str,
        confirm: Confirm,
        text: str | None = None,
        kind: ContextItemType | None = None,
        *,
        topic_title: str | None = None,
        sensitivity: Sensitivity | None = None,
    ) -> str:
        repo = self.repository
        items = self.list_items(project_id)
        current = next((item for item in items if item.id == item_id), None)
        if current is None or current.review_status is ReviewStatus.REJECTED:
            raise ValueError("select a reviewable item in this project")
        if action not in {"confirm", "reject", "edit"}:
            raise ValueError("invalid review action")
        revision = current.review_status is ReviewStatus.CONFIRMED
        if revision and (
            action != "edit" or current.lifecycle_status is not LifecycleStatus.ACTIVE
        ):
            raise ValueError("use edit to propose a replacement for an active confirmed item")
        timestamp = now()
        levels = list(Sensitivity)
        _, findings = SAFETY.redact(text) if text is not None else ("", ())
        inferred = max(
            (SAFETY.finding_sensitivity(finding.detection_type) for finding in findings),
            key=levels.index,
            default=Sensitivity.NORMAL,
        )
        level = max(
            current.sensitivity, sensitivity or current.sensitivity, inferred, key=levels.index
        )
        result = replace(
            current,
            content_summary=safe_text(text) if text is not None else current.content_summary,
            type=kind or current.type,
            title=kind.value if kind else current.title,
            sensitivity=level,
            user_modified=current.user_modified
            or revision
            or text is not None
            or kind is not None
            or level != current.sensitivity,
            updated_at=timestamp,
        )
        if revision:
            result = replace(
                result,
                id=new_id(),
                review_status=ReviewStatus.PROPOSED,
                confirmed_at=None,
                created_at=timestamp,
                supersedes_context_item_id=current.id,
            )
        topic_title = safe_text(topic_title, limit=80) if topic_title else None
        similar = [
            item
            for item in items
            if item.id not in {current.id, current.supersedes_context_item_id}
            and item.type is result.type
            and item.review_status is ReviewStatus.CONFIRMED
            and item.lifecycle_status is LifecycleStatus.ACTIVE
        ]
        duplicates = sum(item.content_summary == result.content_summary for item in similar)
        other_status = sum(item.content_summary != result.content_summary for item in similar)
        preview = f"{action} {result.type.value} ({level.value}): {result.content_summary}"
        if topic_title:
            preview += f"\nAdd to topic: {topic_title}"
        if duplicates:
            preview += f"\nExisting confirmed duplicates: {duplicates}."
        if result.type is ContextItemType.STATUS and other_status:
            preview += f"\nOther active status items to compare: {other_status}."
        if revision or current.supersedes_context_item_id:
            preview += "\nThis proposal replaces an earlier confirmed item when confirmed."
        if not confirm(preview):
            return "Review cancelled."
        if action == "confirm":
            result = replace(result, review_status=ReviewStatus.CONFIRMED, confirmed_at=now())
        elif action == "reject":
            result = replace(result, review_status=ReviewStatus.REJECTED)
        with repo.transaction():
            if repo.get_context_item(item_id) != current:
                raise ValueError("item changed after preview")
            run = repo.get_import_run(current.import_run_id)
            if run is None or run.status not in {
                ImportRunState.AWAITING_REVIEW,
                ImportRunState.COMPLETED,
            }:
                raise ValueError("import is unavailable for review")
            if action == "confirm" and result.supersedes_context_item_id:
                target = repo.get_context_item(result.supersedes_context_item_id)
                if target is None or target.lifecycle_status is not LifecycleStatus.ACTIVE:
                    raise ValueError("replacement target is no longer active")
                if (
                    not SupersessionPolicy()
                    .evaluate(
                        candidate_id=result.id,
                        target_id=target.id,
                        candidate_project_id=project_id,
                        target_project_id=project_id
                        if target.id in {item.id for item in items}
                        else "",
                        existing_supersedes_id=current.supersedes_context_item_id,
                        target_ancestor_ids=(),
                        same_scope=result.import_run_id == target.import_run_id,
                        replacement_intent=True,
                    )
                    .allowed
                ):
                    raise ValueError("invalid replacement")
                repo.supersede(target.id)
            repo.save_context_items((result,))
            if revision:
                for link in repo.list_context_item_topics_by_context_item(current.id):
                    repo.save_context_item_topic(ContextItemTopic(result.id, link.topic_id))
            if topic_title:
                topic = next(
                    (
                        topic
                        for topic in repo.list_topics_by_project(project_id)
                        if topic.title == topic_title
                    ),
                    None,
                )
                if topic is None:
                    topic = Topic(new_id(), project_id, topic_title, timestamp, timestamp)
                    repo.save_topic(topic)
                if topic.id not in {
                    link.topic_id
                    for link in repo.list_context_item_topics_by_context_item(result.id)
                }:
                    repo.save_context_item_topic(ContextItemTopic(result.id, topic.id))
            if run.status is ImportRunState.AWAITING_REVIEW and all(
                item.review_status is not ReviewStatus.PROPOSED
                for item in repo.list_context_items_by_import_run(run.id)
            ):
                repo.save_import_run(
                    replace(run, status=ImportRunState.COMPLETED, finished_at=now())
                )
            audit(repo, action, "project", project_id)
        return f"Item {result.review_status.value}: {result.id}."
