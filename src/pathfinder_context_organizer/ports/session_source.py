# src/pathfinder_context_organizer/ports/session_source.py
from __future__ import annotations

from typing import Protocol

from pathfinder_context_organizer.application.types import RawSessionEvent


class SessionSource(Protocol):
    def read_events(self, source_ref: str) -> tuple[RawSessionEvent, ...]:
        """Read raw session events from a single absolute source_ref.
        RawSessionEvent remains transient and must only be passed to SafetyProcessor.
        """

    def get_fingerprint(self, source_ref: str) -> str:
        """Return a stable fingerprint of the source at read time."""

    def get_last_modified(self, source_ref: str) -> str | None:
        """Return source last modified timestamp in ISO 8601 form if available, else None."""

