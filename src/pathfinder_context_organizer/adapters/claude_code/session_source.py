"""Read the one explicitly selected Claude Code JSONL file."""

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from pathfinder_context_organizer.adapters.claude_code.errors import (
    SessionSourceError,
    SessionSourceParseError,
    SessionSourceValidationError,
)
from pathfinder_context_organizer.adapters.claude_code.parser import parse_claude_code_jsonl_line
from pathfinder_context_organizer.application.types import RawSessionEvent
from pathfinder_context_organizer.ports.session_source import SessionSource


class ClaudeCodeSessionSource(SessionSource):
    @staticmethod
    def _path(source_ref: str) -> Path:
        if not isinstance(source_ref, str) or any(
            char in source_ref for char in (*"*?[]\0", os.pathsep)
        ):
            raise SessionSourceValidationError("select one absolute JSONL file")
        path = Path(source_ref)
        if not path.is_absolute() or path.suffix.lower() != ".jsonl" or ".." in path.parts:
            raise SessionSourceValidationError("select one absolute JSONL file")
        try:
            for part in (*reversed(path.parents), path):
                info = part.lstat()
                if stat.S_ISLNK(info.st_mode) or (
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise SessionSourceValidationError("source links are unsupported")
        except OSError:
            raise FileNotFoundError("source unavailable") from None
        if not stat.S_ISREG(info.st_mode):
            raise SessionSourceValidationError("source must be a regular file")
        return path

    @staticmethod
    def _fingerprint(info: os.stat_result) -> str:
        return f"{info.st_size}:{info.st_mtime_ns}:{info.st_dev}:{info.st_ino}"

    def read_events(self, source_ref: str) -> tuple[RawSessionEvent, ...]:
        path = self._path(source_ref)
        before = self.get_fingerprint(source_ref)
        events = []
        try:
            with path.open("r", encoding="utf-8-sig") as file:
                if self._fingerprint(os.fstat(file.fileno())) != before:
                    raise SessionSourceError("source changed")
                for index, line in enumerate(file):
                    try:
                        event = parse_claude_code_jsonl_line(line, index)
                    except SessionSourceParseError:
                        raise SessionSourceParseError(
                            f"invalid JSONL at line {index + 1}"
                        ) from None
                    if event is not None:
                        events.append(event)
                if self._fingerprint(os.fstat(file.fileno())) != before:
                    raise SessionSourceError("source changed")
        except UnicodeError:
            raise SessionSourceParseError("invalid UTF-8") from None
        except OSError:
            raise SessionSourceError("source unavailable") from None
        if self.get_fingerprint(source_ref) != before:
            raise SessionSourceError("source changed")
        return tuple(events)

    def get_fingerprint(self, source_ref: str) -> str:
        try:
            return self._fingerprint(self._path(source_ref).stat())
        except OSError:
            raise FileNotFoundError("source unavailable") from None

    def get_last_modified(self, source_ref: str) -> str | None:
        try:
            return datetime.fromtimestamp(self._path(source_ref).stat().st_mtime, UTC).isoformat()
        except OSError:
            raise FileNotFoundError("source unavailable") from None

