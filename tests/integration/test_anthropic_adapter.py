import json
from hashlib import sha256

import httpx
import pytest

from pathfinder_context_organizer.adapters.anthropic_provider import model_request
from pathfinder_context_organizer.application.types import RedactedSegment
from pathfinder_context_organizer.domain.value_objects import Sensitivity
from pathfinder_context_organizer.ports.provider_types import ProviderPreflight


def test_anthropic_request_uses_only_approved_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    request = model_request(
        "https://example.invalid/v1/messages", "fixture-model", "PCO_FIXTURE_KEY"
    )
    monkeypatch.setenv("PCO_FIXTURE_KEY", "synthetic-fixture")
    scope = (RedactedSegment("0:0", ("e0",), "Status: approved text", Sensitivity.NORMAL, ()),)
    payload = json.dumps([["0:0", "Status: approved text"]], ensure_ascii=True, indent=2)
    preflight = ProviderPreflight(
        "test",
        "anthropic",
        "fixture-model",
        request.endpoint,
        False,
        True,
        1,
        len(payload),
        sha256(payload.encode()).hexdigest(),
        (Sensitivity.NORMAL,),
        "now",
        True,
    )
    transport_calls = []

    def handle(sent: httpx.Request) -> httpx.Response:
        transport_calls.append(sent)
        assert sent.headers["x-api-key"] == "synthetic-fixture"
        assert json.loads(sent.content)["messages"][0]["content"] == payload
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "text": json.dumps(
                            [
                                {
                                    "item_type": "status",
                                    "content_summary": "approved text",
                                    "source_segment_ids": ["0:0"],
                                }
                            ]
                        )
                    }
                ]
            },
        )

    client = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: client(transport=httpx.MockTransport(handle), **kwargs)
    )
    assert (
        request.provider.summarize(scope, preflight=preflight).candidates[0].content_summary
        == "approved text"
    )
    with pytest.raises(ValueError, match="scope changed"):
        request.provider.summarize(
            (RedactedSegment("0:0", ("e0",), "different", Sensitivity.NORMAL, ()),),
            preflight=preflight,
        )
    assert len(transport_calls) == 1

