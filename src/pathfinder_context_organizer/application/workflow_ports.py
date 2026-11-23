"""Repository operations used to coordinate consent-driven workflows."""

from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import Protocol

from pathfinder_context_organizer.domain.entities import ContextItem
from pathfinder_context_organizer.ports.context_repository import ContextRepository


class WorkflowRepository(ContextRepository, Protocol):
    def transaction(self) -> AbstractContextManager[None]: ...

    def has_import(self, source_id: str, fingerprint: str) -> bool: ...

    def supersede(self, item_id: str) -> None: ...

    def current_item_ids(self, project_id: str) -> frozenset[str]: ...

    def project_items(self, project_id: str) -> tuple[ContextItem, ...]: ...

    def deletion_snapshot(self, project_id: str) -> Mapping[str, tuple[str, ...]]: ...

    def project_render_ids(self, project_id: str) -> tuple[str, ...]: ...

    def delete_project(self, project_id: str) -> None: ...

