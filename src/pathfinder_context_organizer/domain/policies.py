# src/pathfinder_context_organizer/domain/policies.py
from __future__ import annotations

import dataclasses
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal

from pathfinder_context_organizer.domain.value_objects import Sensitivity


@dataclasses.dataclass(slots=True, frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class RedactionDecision:
    redact: bool
    replacement: str | None
    sensitivity: Sensitivity
    reason_code: str | None


@dataclasses.dataclass(slots=True, frozen=True)
class ProviderPreflightSnapshot:
    import_run_id: str
    provider_adapter: str
    model_name: str
    endpoint: str
    endpoint_is_loopback: bool
    may_route_externally: bool
    redacted_segment_count: int
    estimated_tokens: int
    redacted_scope_hash: str


@dataclasses.dataclass(slots=True, frozen=True)
class ProviderConsentGrant:
    preflight: ProviderPreflightSnapshot
    granted_at: str


class SourceAccessPolicy:
    def evaluate(
        self,
        paths: tuple[str, ...],
        *,
        selected_kind: Literal["file", "directory"],
        directory_approved: bool,
    ) -> PolicyDecision:
        if len(paths) != 1:
            return PolicyDecision(False, "SOURCE_COUNT")
        p = paths[0]
        if not p:
            return PolicyDecision(False, "SOURCE_EMPTY")
        is_abs_win = PureWindowsPath(p).is_absolute()
        is_abs_posix = PurePosixPath(p).is_absolute()
        if not (is_abs_win or is_abs_posix):
            return PolicyDecision(False, "SOURCE_NOT_ABS")
        if any(c in p for c in ("*", "?", "[", "]")):
            return PolicyDecision(False, "SOURCE_PATTERN")
        if selected_kind == "directory":
            if not directory_approved:
                return PolicyDecision(False, "DIR_NOT_APPROVED")
            return PolicyDecision(True, None)
        if selected_kind == "file":
            return PolicyDecision(True, None)
        return PolicyDecision(False, "INVALID_KIND")


class TransferPolicy:
    def evaluate(
        self,
        sensitivity: Sensitivity,
        *,
        private_approved: bool,
        sensitive_approved: bool,
        masking_applied: bool,
    ) -> PolicyDecision:
        if sensitivity is Sensitivity.SECRET:
            return PolicyDecision(False, "SECRET_NEVER_TRANSFER")
        if sensitivity is Sensitivity.SENSITIVE:
            if sensitive_approved and masking_applied:
                return PolicyDecision(True, None)
            return PolicyDecision(False, "SENSITIVE_REQUIRES_APPROVAL_AND_MASKING")
        if sensitivity is Sensitivity.PRIVATE:
            if private_approved or masking_applied:
                return PolicyDecision(True, None)
            return PolicyDecision(False, "PRIVATE_REQUIRES_APPROVAL_OR_MASKING")
        if sensitivity is Sensitivity.NORMAL:
            return PolicyDecision(True, None)
        return PolicyDecision(False, "UNKNOWN_SENSITIVITY")


class RedactionPolicy:
    def evaluate(
        self,
        *,
        detection_kind: str | None,
        high_entropy: bool,
        private_value: bool,
    ) -> RedactionDecision:
        if detection_kind == "API_KEY":
            return RedactionDecision(True, "[REDACTED:API_KEY]", Sensitivity.SECRET, None)
        if detection_kind == "TOKEN":
            return RedactionDecision(True, "[REDACTED:TOKEN]", Sensitivity.SECRET, None)
        if detection_kind == "PASSWORD":
            return RedactionDecision(True, "[REDACTED:PASSWORD]", Sensitivity.SECRET, None)
        if detection_kind == "PRIVATE_KEY":
            return RedactionDecision(True, "[REDACTED:PRIVATE_KEY]", Sensitivity.SECRET, None)
        if isinstance(detection_kind, str) and detection_kind.strip() != "":
            return RedactionDecision(
                True, "[REDACTED:SUSPECTED_SECRET]", Sensitivity.SECRET, "UNKNOWN_DETECTION_KIND"
            )
        if high_entropy:
            return RedactionDecision(True, "[REDACTED:SUSPECTED_SECRET]", Sensitivity.SECRET, None)
        if private_value:
            return RedactionDecision(True, "[REDACTED:PRIVATE_PATH]", Sensitivity.PRIVATE, None)
        return RedactionDecision(False, None, Sensitivity.NORMAL, None)


class ProviderConsentPolicy:
    def evaluate(
        self, current: ProviderPreflightSnapshot, grant: ProviderConsentGrant | None
    ) -> PolicyDecision:
        if grant is None:
            return PolicyDecision(False, "NO_CONSENT")
        if grant.preflight != current:
            return PolicyDecision(False, "PREFLIGHT_MISMATCH")
        return PolicyDecision(True, None)


class SupersessionPolicy:
    def evaluate(
        self,
        *,
        candidate_id: str,
        target_id: str,
        candidate_project_id: str,
        target_project_id: str,
        existing_supersedes_id: str | None,
        target_ancestor_ids: tuple[str, ...],
        same_scope: bool,
        replacement_intent: bool,
    ) -> PolicyDecision:
        if candidate_id == target_id:
            return PolicyDecision(False, "SELF_SUPERSEDE")
        if candidate_project_id != target_project_id:
            return PolicyDecision(False, "CROSS_PROJECT")
        if candidate_id in target_ancestor_ids:
            return PolicyDecision(False, "CYCLE")
        if existing_supersedes_id is not None and existing_supersedes_id != target_id:
            return PolicyDecision(False, "ALREADY_SUPERSEDED")
        if not same_scope:
            return PolicyDecision(False, "SCOPE_MISMATCH")
        if not replacement_intent:
            return PolicyDecision(False, "MISSING_REPLACEMENT_INTENT")
        return PolicyDecision(True, None)

