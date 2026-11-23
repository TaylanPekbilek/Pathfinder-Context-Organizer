# tests/unit/domain/test_policies.py
from __future__ import annotations

import dataclasses

from pathfinder_context_organizer.domain.policies import (
    ProviderConsentGrant,
    ProviderConsentPolicy,
    ProviderPreflightSnapshot,
    RedactionDecision,
    RedactionPolicy,
    SourceAccessPolicy,
    SupersessionPolicy,
    TransferPolicy,
)
from pathfinder_context_organizer.domain.value_objects import Sensitivity


def _different(base: ProviderPreflightSnapshot, field: str) -> object:
    v = getattr(base, field)
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 1
    if isinstance(v, str):
        return v + "_x"
    raise AssertionError(f"unsupported field type for {field}")


def test_source_access_single_absolute_only_pure_syntax() -> None:
    p = SourceAccessPolicy()
    assert (
        p.evaluate(("C:/tmp/session.json",), selected_kind="file", directory_approved=False).allowed
        is True
    )
    assert p.evaluate((), selected_kind="file", directory_approved=False).allowed is False
    assert p.evaluate(("",), selected_kind="file", directory_approved=False).allowed is False
    assert (
        p.evaluate(("session.json",), selected_kind="file", directory_approved=False).allowed
        is False
    )
    assert (
        p.evaluate(("C:/tmp/*.json",), selected_kind="file", directory_approved=False).allowed
        is False
    )
    assert (
        p.evaluate(
            ("C:/tmp/session?.json",), selected_kind="file", directory_approved=False
        ).allowed
        is False
    )
    assert (
        p.evaluate(("C:/tmp/[0-9]*.json",), selected_kind="file", directory_approved=False).allowed
        is False
    )
    assert (
        p.evaluate(
            ("C:/tmp/a.json", "C:/tmp/b.json"), selected_kind="file", directory_approved=False
        ).allowed
        is False
    )
    assert (
        p.evaluate(("C:/tmp/",), selected_kind="directory", directory_approved=False).allowed
        is False
    )
    assert (
        p.evaluate(("C:/tmp/",), selected_kind="directory", directory_approved=True).allowed is True
    )
    assert (
        p.evaluate(
            (r"D:\AI-Projects\session.json",), selected_kind="file", directory_approved=False
        ).allowed
        is True
    )


def test_transfer_rules_or_and_never() -> None:
    p = TransferPolicy()
    assert (
        p.evaluate(
            Sensitivity.NORMAL,
            private_approved=False,
            sensitive_approved=False,
            masking_applied=False,
        ).allowed
        is True
    )
    assert (
        p.evaluate(
            Sensitivity.PRIVATE,
            private_approved=True,
            sensitive_approved=False,
            masking_applied=False,
        ).allowed
        is True
    )
    assert (
        p.evaluate(
            Sensitivity.PRIVATE,
            private_approved=False,
            sensitive_approved=False,
            masking_applied=True,
        ).allowed
        is True
    )
    assert (
        p.evaluate(
            Sensitivity.PRIVATE,
            private_approved=False,
            sensitive_approved=False,
            masking_applied=False,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            Sensitivity.SENSITIVE,
            private_approved=False,
            sensitive_approved=True,
            masking_applied=True,
        ).allowed
        is True
    )
    assert (
        p.evaluate(
            Sensitivity.SENSITIVE,
            private_approved=False,
            sensitive_approved=True,
            masking_applied=False,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            Sensitivity.SENSITIVE,
            private_approved=False,
            sensitive_approved=False,
            masking_applied=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            Sensitivity.SECRET, private_approved=True, sensitive_approved=True, masking_applied=True
        ).allowed
        is False
    )


def test_redaction_decisions_safe_placeholders() -> None:
    p = RedactionPolicy()
    d1 = p.evaluate(detection_kind="API_KEY", high_entropy=False, private_value=False)
    assert isinstance(d1, RedactionDecision)
    assert (
        d1.redact is True
        and d1.replacement == "[REDACTED:API_KEY]"
        and d1.sensitivity == Sensitivity.SECRET
    )
    d2 = p.evaluate(detection_kind="TOKEN", high_entropy=False, private_value=False)
    assert (
        d2.redact is True
        and d2.replacement == "[REDACTED:TOKEN]"
        and d2.sensitivity == Sensitivity.SECRET
    )
    d3 = p.evaluate(detection_kind="PASSWORD", high_entropy=False, private_value=False)
    assert (
        d3.redact is True
        and d3.replacement == "[REDACTED:PASSWORD]"
        and d3.sensitivity == Sensitivity.SECRET
    )
    d4 = p.evaluate(detection_kind="PRIVATE_KEY", high_entropy=False, private_value=False)
    assert (
        d4.redact is True
        and d4.replacement == "[REDACTED:PRIVATE_KEY]"
        and d4.sensitivity == Sensitivity.SECRET
    )
    d5 = p.evaluate(detection_kind="UNKNOWN_KIND", high_entropy=False, private_value=False)
    assert (
        d5.redact is True
        and d5.replacement == "[REDACTED:SUSPECTED_SECRET]"
        and d5.sensitivity == Sensitivity.SECRET
    )
    d6 = p.evaluate(detection_kind=None, high_entropy=True, private_value=False)
    assert (
        d6.redact is True
        and d6.replacement == "[REDACTED:SUSPECTED_SECRET]"
        and d6.sensitivity == Sensitivity.SECRET
    )
    d7 = p.evaluate(detection_kind=None, high_entropy=False, private_value=True)
    assert (
        d7.redact is True
        and d7.replacement == "[REDACTED:PRIVATE_PATH]"
        and d7.sensitivity == Sensitivity.PRIVATE
    )


def test_provider_consent_exact_match_all_fields_and_loopback() -> None:
    p = ProviderConsentPolicy()
    base = ProviderPreflightSnapshot(
        "ir1", "anthropic_compatible", "m", "http://api.example/v1", False, True, 1, 10, "h1"
    )
    assert p.evaluate(base, None).allowed is False
    grant = ProviderConsentGrant(base, "2026-10-25T00:00:00+00:00")
    assert p.evaluate(base, grant).allowed is True
    for field in dataclasses.fields(base):
        cur = dataclasses.replace(base, **{field.name: _different(base, field.name)})
        assert p.evaluate(cur, grant).allowed is False
    # loopback 127.0.0.1
    loop_cur_true = ProviderPreflightSnapshot(
        "ir1", "anthropic_compatible", "m", "http://127.0.0.1:4000/v1", True, True, 1, 10, "h1"
    )
    loop_grant_true = ProviderConsentGrant(loop_cur_true, "2026-10-25T00:00:00+00:00")
    assert p.evaluate(loop_cur_true, loop_grant_true).allowed is True
    loop_cur_false = ProviderPreflightSnapshot(
        "ir1", "anthropic_compatible", "m", "http://127.0.0.1:4000/v1", True, False, 1, 10, "h1"
    )
    loop_grant_false = ProviderConsentGrant(loop_cur_false, "2026-10-25T00:00:00+00:00")
    assert p.evaluate(loop_cur_false, loop_grant_false).allowed is True
    # localhost
    localhost_cur_true = ProviderPreflightSnapshot(
        "ir1", "anthropic_compatible", "m", "http://localhost:4000/v1", True, True, 1, 10, "h1"
    )
    localhost_grant_true = ProviderConsentGrant(localhost_cur_true, "2026-10-25T00:00:00+00:00")
    assert p.evaluate(localhost_cur_true, localhost_grant_true).allowed is True
    localhost_cur_false = ProviderPreflightSnapshot(
        "ir1", "anthropic_compatible", "m", "http://localhost:4000/v1", True, False, 1, 10, "h1"
    )
    localhost_grant_false = ProviderConsentGrant(localhost_cur_false, "2026-10-25T00:00:00+00:00")
    assert p.evaluate(localhost_cur_false, localhost_grant_false).allowed is True


def test_supersession_rules_with_target_ancestor_ids() -> None:
    p = SupersessionPolicy()
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="a",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id=None,
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p1",
            target_project_id="p2",
            existing_supersedes_id=None,
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id=None,
            target_ancestor_ids=("a",),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id="x",
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id="b",
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is True
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id=None,
            target_ancestor_ids=(),
            same_scope=False,
            replacement_intent=True,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id=None,
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=False,
        ).allowed
        is False
    )
    assert (
        p.evaluate(
            candidate_id="a",
            target_id="b",
            candidate_project_id="p",
            target_project_id="p",
            existing_supersedes_id=None,
            target_ancestor_ids=(),
            same_scope=True,
            replacement_intent=True,
        ).allowed
        is True
    )
