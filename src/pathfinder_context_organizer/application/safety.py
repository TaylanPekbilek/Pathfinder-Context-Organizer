# src/pathfinder_context_organizer/application/safety.py
from __future__ import annotations

import math
import re
from collections import Counter

from pathfinder_context_organizer.application.types import (
    RawSessionEvent,
    RedactedSegment,
    RedactionFinding,
    SafetyResult,
)
from pathfinder_context_organizer.domain.policies import RedactionPolicy
from pathfinder_context_organizer.domain.value_objects import Sensitivity


class SafetyProcessor:
    _ABS_PATH_RE = re.compile(r"""(?<![\w:/])(?:[A-Z]:[\\/]|\\\\|/)[^\r\n"'<>|`]+""", re.IGNORECASE)
    _PRIVATE_KEY_RE = re.compile(
        r"-----BEGIN PRIVATE KEY-----.*?-----END PRIVATE KEY-----", re.DOTALL
    )
    _ASSIGN_RE = re.compile(
        r"""(?i)\b(api[_-]?key|token|access[_-]?token|password|secret)["']?\s*[:=]\s*(?:"[^"\r\n]*"|'[^'\r\n]*'|[^\s;]+)"""
    )
    _PREFIX_RE = re.compile(r"(?:(?:sk-ant-)|sk-|ghp_)[A-Za-z0-9_-]+")
    _WIN_PATH_RE = re.compile(r"""[A-Z]:\\Users\\[^\r\n"'<>|`]+""", re.IGNORECASE)

    def __init__(self, redaction_policy: RedactionPolicy) -> None:
        self._redaction_policy = redaction_policy

    @staticmethod
    def _shannon_entropy(s: str) -> float:
        if not s:
            return 0.0
        counts = Counter(s)
        n = len(s)
        ent = 0.0
        for c in counts.values():
            p = c / n
            ent -= p * math.log2(p)
        return ent

    @staticmethod
    def _is_high_entropy_candidate(candidate: str) -> bool:
        if len(candidate) < 20 or len(candidate) > 200:
            return False
        if any(ch.isspace() for ch in candidate):
            return False
        return SafetyProcessor._shannon_entropy(candidate) >= 4.0

    @staticmethod
    def _overlap_key(match: tuple[int, int, int, str]) -> tuple[int, int, int]:
        start, end, precedence, _ = match
        return (precedence, start, -(end - start))

    @staticmethod
    def finding_sensitivity(detection_type: str) -> Sensitivity:
        if detection_type == "PRIVATE_PATH":
            return Sensitivity.PRIVATE
        return Sensitivity.SECRET

    def redact(self, text: str, event_id: str = "") -> tuple[str, tuple[RedactionFinding, ...]]:
        matches = []
        for precedence, pattern, kind in (
            (0, self._PRIVATE_KEY_RE, "PRIVATE_KEY"),
            (1, self._ASSIGN_RE, ""),
            (1, self._PREFIX_RE, "TOKEN"),
            (2, self._WIN_PATH_RE, "PRIVATE_PATH"),
            (2, self._ABS_PATH_RE, "PRIVATE_PATH"),
            (3, re.compile(r"\S+"), "SUSPECTED_SECRET"),
        ):
            for match in pattern.finditer(text):
                if kind == "SUSPECTED_SECRET" and (
                    not self._is_high_entropy_candidate(match[0])
                    or re.fullmatch(r"\[REDACTED:[A-Z_]+\]", match[0])
                ):
                    continue
                detection = kind
                if not kind:
                    field = match[1].lower()
                    detection = (
                        "API_KEY"
                        if field.startswith("api")
                        else ("PASSWORD" if field in {"password", "secret"} else "TOKEN")
                    )
                matches.append((match.start(), match.end(), precedence, detection))
        selected: list[tuple[int, int, int, str]] = []
        for start, end, rank, detection in sorted(matches, key=self._overlap_key):
            overlaps = [m for m in selected if start < m[1] and m[0] < end]
            if overlaps:
                if rank < 3 and any(start < m[0] or end > m[1] for m in overlaps):
                    for overlap in overlaps:
                        selected.remove(overlap)
                    first = min(overlaps, key=self._overlap_key)
                    selected.append(
                        (
                            min(start, *(m[0] for m in overlaps)),
                            max(end, *(m[1] for m in overlaps)),
                            first[2],
                            first[3],
                        )
                    )
                continue
            selected.append((start, end, rank, detection))
        parts: list[str] = []
        findings = []
        cursor = 0
        for start, end, _, detection in sorted(selected):
            replacement = f"[REDACTED:{detection}]"
            findings.append(
                RedactionFinding(event_id, detection, start, end, replacement, detection)
            )
            parts.extend((text[cursor:start], replacement))
            cursor = end
        parts.append(text[cursor:])
        return "".join(parts), tuple(findings)

    def process(
        self, events: tuple[RawSessionEvent, ...], *, max_segment_chars: int
    ) -> SafetyResult:
        if max_segment_chars <= 0:
            raise ValueError("max_segment_chars must be greater than 0")
        segments = []
        all_findings: list[RedactionFinding] = []
        for event in events:
            if not isinstance(event, RawSessionEvent) or not isinstance(event.body, str):
                raise ValueError("invalid raw event")
            event_id, id_findings = self.redact(event.event_id)
            if id_findings or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", event_id):
                event_id = f"e{event.sequence}"
            text, findings = self.redact(event.body, event_id)
            all_findings.extend(findings)
            levels = {self.finding_sensitivity(f.detection_type) for f in findings}
            sensitivity = next(
                (level for level in (Sensitivity.SECRET, Sensitivity.PRIVATE) if level in levels),
                Sensitivity.NORMAL,
            )
            for index, offset in enumerate(range(0, len(text), max_segment_chars)):
                segments.append(
                    RedactedSegment(
                        f"{event.sequence}:{index}",
                        (event_id,),
                        text[offset : offset + max_segment_chars],
                        sensitivity,
                        findings,
                    )
                )
        return SafetyResult(tuple(segments), tuple(all_findings), len(all_findings))

