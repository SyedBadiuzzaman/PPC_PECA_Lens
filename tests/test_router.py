"""Tests for structured OpenRouter routing and transport behavior."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any

import httpx
import pytest

from src.core_04.core_01_router import LegalRouter
from src.domain_01.domain_01_enums import Route
from src.domain_01.domain_02_exceptions import (
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from src.utils_03.utils_01_llm_client import OpenRouterClient


class FakeJsonClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    async def complete_json(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        self.calls += 1
        return self.response


def test_router_accepts_valid_structured_output() -> None:
    client = FakeJsonClient({"route": "peca", "reason": "Electronic offence"})
    decision = asyncio.run(LegalRouter(client, "router-id").route("What is cyber stalking?"))

    assert decision.route is Route.PECA
    assert client.calls == 1


def test_router_rejects_unknown_route() -> None:
    client = FakeJsonClient({"route": "crpc", "reason": "Wrong corpus"})

    with pytest.raises(UpstreamResponseError):
        asyncio.run(LegalRouter(client, "router-id").route("Question"))


def test_openrouter_request_enforces_privacy_preferences() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"route":"ppc"}'}}]},
        )

    client = OpenRouterClient(
        api_key="secret",
        base_url="https://example.test/api/v1",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        client.complete_json(
            model="router-id",
            messages=({"role": "user", "content": "question"},),
            max_tokens=20,
        )
    )

    assert result == {"route": "ppc"}
    assert captured["provider"] == {"zdr": True, "data_collection": "deny"}


def test_openrouter_maps_rate_limit() -> None:
    client = OpenRouterClient(
        api_key="secret",
        base_url="https://example.test/api/v1",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda request: httpx.Response(429)),
    )

    with pytest.raises(UpstreamRateLimitError):
        asyncio.run(
            client.complete_json(
                model="router-id",
                messages=({"role": "user", "content": "question"},),
                max_tokens=20,
            )
        )


def test_openrouter_maps_unavailable_model() -> None:
    client = OpenRouterClient(
        api_key="secret",
        base_url="https://example.test/api/v1",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
    )

    with pytest.raises(UpstreamUnavailableError):
        asyncio.run(
            client.complete_json(
                model="missing-model",
                messages=({"role": "user", "content": "question"},),
                max_tokens=20,
            )
        )


def test_openrouter_maps_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    client = OpenRouterClient(
        api_key="secret",
        base_url="https://example.test/api/v1",
        timeout_seconds=1,
        transport=httpx.MockTransport(timeout),
    )

    with pytest.raises(UpstreamTimeoutError):
        asyncio.run(
            client.complete_json(
                model="router-id",
                messages=({"role": "user", "content": "question"},),
                max_tokens=20,
            )
        )
