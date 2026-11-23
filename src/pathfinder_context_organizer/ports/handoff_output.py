# src/pathfinder_context_organizer/ports/handoff_output.py
from __future__ import annotations

from typing import Protocol


class HandoffOutput(Protocol):
    def write_markdown(self, path: str, content: str) -> None:
        """Write markdown content atomically to path. Content must be UTF-8 without BOM and LF."""

