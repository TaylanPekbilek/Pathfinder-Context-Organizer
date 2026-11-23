# src/pathfinder_context_organizer/ports/context_repository.py
from __future__ import annotations

from typing import Protocol

from pathfinder_context_organizer.domain.entities import (
    AuditEvent,
    ContextItem,
    ContextItemTopic,
    HandoffPackage,
    HandoffPackageItem,
    HandoffRender,
    ImportRun,
    Project,
    SourceSession,
    Topic,
)


class ContextRepository(Protocol):
    def save_project(self, project: Project) -> None:
        """Persist Project."""

    def get_project(self, project_id: str) -> Project | None:
        """Retrieve Project by id."""

    def save_source_session(self, source_session: SourceSession) -> None:
        """Persist SourceSession."""

    def get_source_session(self, source_session_id: str) -> SourceSession | None:
        """Retrieve SourceSession by id."""

    def save_topic(self, topic: Topic) -> None:
        """Persist Topic."""

    def get_topic(self, topic_id: str) -> Topic | None:
        """Retrieve Topic by id."""

    def list_topics_by_project(self, project_id: str) -> tuple[Topic, ...]:
        """List Topics for a Project."""

    def save_import_run(self, import_run: ImportRun) -> None:
        """Persist ImportRun."""

    def get_import_run(self, import_run_id: str) -> ImportRun | None:
        """Retrieve ImportRun by id."""

    def save_context_items(self, items: tuple[ContextItem, ...]) -> None:
        """Persist ContextItems."""

    def get_context_item(self, context_item_id: str) -> ContextItem | None:
        """Retrieve ContextItem by id."""

    def list_context_items_by_import_run(self, import_run_id: str) -> tuple[ContextItem, ...]:
        """List ContextItems by ImportRun."""

    def save_context_item_topic(self, link: ContextItemTopic) -> None:
        """Persist ContextItemTopic link."""

    def list_context_item_topics_by_context_item(
        self, context_item_id: str
    ) -> tuple[ContextItemTopic, ...]:
        """List ContextItemTopic links for a ContextItem."""

    def save_handoff_package(self, handoff_package: HandoffPackage) -> None:
        """Persist HandoffPackage."""

    def get_handoff_package(self, handoff_package_id: str) -> HandoffPackage | None:
        """Retrieve HandoffPackage by id."""

    def save_handoff_package_items(self, items: tuple[HandoffPackageItem, ...]) -> None:
        """Persist HandoffPackageItems."""

    def list_handoff_package_items(self, handoff_package_id: str) -> tuple[HandoffPackageItem, ...]:
        """List HandoffPackageItems for a HandoffPackage."""

    def save_handoff_render(self, handoff_render: HandoffRender) -> None:
        """Persist HandoffRender."""

    def get_handoff_render(self, handoff_render_id: str) -> HandoffRender | None:
        """Retrieve HandoffRender by id."""

    def save_audit_event(self, audit_event: AuditEvent) -> None:
        """Persist AuditEvent."""

    def list_audit_events_by_entity(
        self, entity_type: str, entity_id: str
    ) -> tuple[AuditEvent, ...]:
        """List AuditEvents for an entity."""

