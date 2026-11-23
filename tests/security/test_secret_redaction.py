# tests/security/test_secret_redaction.py
from __future__ import annotations

import ast
import dataclasses
import hashlib
import string
from pathlib import Path

import pytest

from pathfinder_context_organizer.application.safety import SafetyProcessor
from pathfinder_context_organizer.application.types import RawSessionEvent, RedactedSegment
from pathfinder_context_organizer.domain.policies import RedactionPolicy


def _synth_secret(prefix: str) -> str:
    parts = ["EXAMPLE", "NOTREAL", "VALUE", "ABC123DEF456"]
    return prefix + "_".join(parts)


def _entropy_candidate(length: int) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(alphabet[i % len(alphabet)] for i in range(length))


def test_api_key_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"api_key={secret}", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:API_KEY]"


def test_api_key_hyphen_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"api-key={secret}", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:API_KEY]"


def test_token_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("ghp")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"token={secret}", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:TOKEN]"


def test_access_token_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("ghp")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"access_token={secret}", None),),
        max_segment_chars=1000,
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:TOKEN]"


def test_password_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("pwd")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"password={secret}", None),),
        max_segment_chars=1000,
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:PASSWORD]"


def test_secret_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("pwd")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"secret={secret}", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:PASSWORD]"


def test_sk_prefix_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = "sk-" + _synth_secret("EX")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, secret, None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:TOKEN]"


def test_sk_ant_prefix_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = "sk-ant-" + _synth_secret("EX")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, secret, None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:TOKEN]"


def test_ghp_prefix_placeholder() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = "ghp_" + _synth_secret("EX")
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, secret, None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert text == "[REDACTED:TOKEN]"


def test_private_key_block_multiline() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    block = "-----BEGIN PRIVATE KEY-----\nNOTAREALKEYMATERIAL\n-----END PRIVATE KEY-----"
    res = sp.process((RawSessionEvent("e1", 0, "user", None, block, None),), max_segment_chars=1000)
    text = "\n".join(s.text for s in res.segments)
    assert "NOTAREALKEYMATERIAL" not in text
    assert text == "[REDACTED:PRIVATE_KEY]"


def test_private_windows_path() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    path = r"C:\Users\Example\secret.txt"
    res = sp.process((RawSessionEvent("e1", 0, "user", None, path, None),), max_segment_chars=1000)
    text = "\n".join(s.text for s in res.segments)
    assert path not in text
    assert text == "[REDACTED:PRIVATE_PATH]"


def test_high_entropy_boundaries() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    c19 = _entropy_candidate(19)
    c20 = _entropy_candidate(20)
    c200 = _entropy_candidate(200)
    c201 = _entropy_candidate(201)
    assert len(c19) == 19
    assert len(c20) == 20
    assert len(c200) == 200
    assert len(c201) == 201
    r19 = sp.process((RawSessionEvent("e1", 0, "user", None, c19, None),), max_segment_chars=1000)
    r20 = sp.process((RawSessionEvent("e2", 0, "user", None, c20, None),), max_segment_chars=1000)
    r200 = sp.process((RawSessionEvent("e3", 0, "user", None, c200, None),), max_segment_chars=1000)
    r201 = sp.process((RawSessionEvent("e4", 0, "user", None, c201, None),), max_segment_chars=1000)
    t19 = "\n".join(s.text for s in r19.segments)
    t20 = "\n".join(s.text for s in r20.segments)
    t200 = "\n".join(s.text for s in r200.segments)
    t201 = "\n".join(s.text for s in r201.segments)
    assert t19 == c19
    assert t20 == "[REDACTED:SUSPECTED_SECRET]"
    assert t200 == "[REDACTED:SUSPECTED_SECRET]"
    assert t201 == c201


def test_whitespace_sentence_not_entropy_candidate() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    s = "This is a normal sentence with words and spaces."
    res = sp.process((RawSessionEvent("e1", 0, "user", None, s, None),), max_segment_chars=1000)
    text = "\n".join(t.text for t in res.segments)
    assert text == s


def test_low_entropy_not_unnecessarily_redacted() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    low = "AAAAABBBBBCCCCC11111"
    res = sp.process((RawSessionEvent("e1", 0, "user", None, low, None),), max_segment_chars=1000)
    text = "\n".join(s.text for s in res.segments)
    assert text == low


def test_private_key_wins_over_inner_token() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    inner = "sk-" + _synth_secret("IN")
    block = "-----BEGIN PRIVATE KEY-----\n" + inner + "\n-----END PRIVATE KEY-----"
    res = sp.process((RawSessionEvent("e1", 0, "user", None, block, None),), max_segment_chars=1000)
    text = "\n".join(s.text for s in res.segments)
    assert inner not in text
    assert text == "[REDACTED:PRIVATE_KEY]"
    findings_for_e1 = [f for f in res.findings if f.event_id == "e1"]
    assert len(findings_for_e1) == 1
    assert findings_for_e1[0].detection_type == "PRIVATE_KEY"


def test_secret_near_segment_boundary() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    long = "x" * 50 + "=" + secret + "y" * 50
    res = sp.process((RawSessionEvent("e1", 0, "user", None, long, None),), max_segment_chars=10)
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    for s in res.segments:
        assert isinstance(s, RedactedSegment)


def test_normal_text_unchanged() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, "hello world", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert text == "hello world"


def test_max_segment_chars_le_zero_raises_value_error_and_no_secret_in_message() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    with pytest.raises(ValueError, match=r"^max_segment_chars must be greater than 0$") as exc:
        sp.process((RawSessionEvent("e1", 0, "user", None, secret, None),), max_segment_chars=0)
    assert secret not in str(exc.value)


def test_deterministic_repeat() -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    events = (RawSessionEvent("e1", 0, "user", None, f"key={secret}", None),)
    r1 = sp.process(events, max_segment_chars=1000)
    r2 = sp.process(events, max_segment_chars=1000)
    assert r1 == r2


def test_no_secret_hash_or_derivative_and_no_leakage(caplog) -> None:
    sp = SafetyProcessor(RedactionPolicy())
    secret = _synth_secret("sk")
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    res = sp.process(
        (RawSessionEvent("e1", 0, "user", None, f"key={secret}", None),), max_segment_chars=1000
    )
    text = "\n".join(s.text for s in res.segments)
    assert secret not in text
    assert secret_hash not in text
    assert secret not in repr(res)
    assert secret_hash not in repr(res)
    d = dataclasses.asdict(res)
    s_dump = str(d)
    assert secret not in s_dump
    assert secret_hash not in s_dump
    for s in res.segments:
        assert secret not in repr(s)
        assert secret not in s.text
    for f in res.findings:
        assert secret not in f.replacement
        assert secret_hash not in f.replacement
        assert secret not in repr(f)
        assert len(f.replacement) <= 64
    assert caplog.records == []


def test_no_file_or_cache_writes_by_ast() -> None:
    app_root = Path("src/pathfinder_context_organizer/application")
    forbidden_calls = {"open", "write_text", "write_bytes", "mkdir", "makedirs", "sqlite3"}
    for py in app_root.rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    assert False, f"{py}: forbidden call {node.func.id}"
                if isinstance(node.func, ast.Attribute):
                    attr = node.func.attr
                    if attr in {"write_text", "write_bytes", "open"}:
                        assert False, f"{py}: forbidden attribute call {attr}"
