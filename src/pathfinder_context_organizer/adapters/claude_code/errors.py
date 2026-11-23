# src/pathfinder_context_organizer/adapters/claude_code/errors.py
from __future__ import annotations


class SessionSourceError(Exception):
    pass


class SessionSourceValidationError(SessionSourceError, ValueError):
    pass


class SessionSourceParseError(SessionSourceError, ValueError):
    pass

