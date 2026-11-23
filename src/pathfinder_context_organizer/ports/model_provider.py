# src/pathfinder_context_organizer/ports/model_provider.py
from __future__ import annotations

from typing import Protocol

from pathfinder_context_organizer.application.types import RedactedSegment
from pathfinder_context_organizer.ports.provider_types import ProviderPreflight, ProviderResult


class ModelProvider(Protocol):
    def summarize(
        self, segments: tuple[RedactedSegment, ...], *, preflight: ProviderPreflight
    ) -> ProviderResult:
        """Summarize only redacted segments. Must not accept RawSessionEvent.
        Returns a ProviderResult containing ProviderCandidate entries derived from redacted segments.
        """

