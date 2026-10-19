"""Utility flow 01: async OpenRouter client with strict privacy preferences."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
from langchain_core.messages import BaseMessage

from src.domain_01.domain_02_exceptions import (
    UpstreamRateLimitError,
    UpstreamResponseError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)


class JsonCompletionClient(Protocol):
    """Structured completion behavior used by router and generators."""

    async def complete_json(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]: ...


class OpenRouterClient:
    """Call OpenRouter without retaining request or response content locally."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout_seconds
        self._transport = transport

    async def complete_json(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        max_tokens: int,
    ) -> dict[str, Any]:
        """Request one JSON response with ZDR and data collection disabled."""

        request_body = {
            "model": model,
            "messages": list(messages),
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "provider": {"zdr": True, "data_collection": "deny"},
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("OpenRouter timed out.") from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError("OpenRouter could not be reached.") from exc

        if response.status_code == 429:
            raise UpstreamRateLimitError("OpenRouter rate limit reached.")
        if response.status_code in {404, 408} or response.status_code >= 500:
            raise UpstreamUnavailableError("No eligible OpenRouter endpoint is available.")
        if response.status_code >= 400:
            raise UpstreamResponseError("OpenRouter rejected the request.")

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Completion content is not text.")
            parsed = json.loads(content)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise UpstreamResponseError(
                "OpenRouter returned malformed structured output."
            ) from exc
        if not isinstance(parsed, dict):
            raise UpstreamResponseError("OpenRouter returned a non-object JSON value.")
        return parsed


def to_openrouter_messages(
    messages: Sequence[BaseMessage],
) -> tuple[dict[str, str], ...]:
    """Convert LangChain messages to OpenRouter's simple chat format."""

    role_by_type = {"system": "system", "human": "user", "ai": "assistant"}
    converted: list[dict[str, str]] = []
    for message in messages:
        role = role_by_type.get(message.type)
        if role is None or not isinstance(message.content, str):
            raise ValueError("Only system, human, and AI text messages are supported.")
        converted.append({"role": role, "content": message.content})
    return tuple(converted)
