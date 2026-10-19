"""HTTP contract tests for public endpoints and safe errors."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from src.api_06.api_02_main import create_app, get_query_service
from src.core_04.guardrails_04.guardrail_03_output import append_disclaimer
from src.domain_01.domain_01_enums import Law, QueryStatus
from src.domain_01.domain_02_exceptions import UpstreamResponseError, UpstreamTimeoutError
from src.domain_01.domain_03_models import QueryResult, VerifiedSource


class FakeService:
    request_timeout_seconds = 1.0

    def __init__(
        self,
        result: QueryResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    async def ask(self, question: str) -> QueryResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _client(service: FakeService) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_query_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_query_returns_stable_contract() -> None:
    result = QueryResult(
        status=QueryStatus.ANSWERED,
        law=Law.PPC,
        answer=append_disclaimer("Supported answer."),
        sources=(VerifiedSource(Law.PPC, "ppc.pdf", 22, "chunk-1", "quote"),),
        warnings=("dated source",),
    )
    response = _client(FakeService(result=result)).post(
        "/query", json={"question": "What is the PPC definition?"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["sources"][0]["page"] == 22
    assert response.headers["cache-control"] == "no-store"


def test_openapi_exposes_only_health_and_query_application_routes() -> None:
    schema = _client(FakeService()).get("/openapi.json").json()

    assert "/health" in schema["paths"]
    assert "/query" in schema["paths"]
    assert "/" not in schema["paths"]
    assert "/chat" not in schema["paths"]
    assert "/ui" not in schema["paths"]
    assert schema["paths"]["/query"]["post"]["responses"]["200"]["content"]


def test_frontend_pages_and_assets_use_private_static_delivery() -> None:
    client = _client(FakeService())
    pages = {
        "/": "text/html",
        "/chat": "text/html",
        "/ui/styles.css": "text/css",
        "/ui/app.js": "javascript",
        "/ui/data-flow.svg": "image/svg+xml",
    }

    for path, content_type in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"

    introduction = client.get("/").text
    chat = client.get("/chat").text
    javascript = client.get("/ui/app.js").text

    assert "Read the law." in introduction
    assert "Trace the source." in introduction
    assert "16 February 2017" in introduction
    assert "headed as a bill" in introduction
    assert "OCR errors" in introduction
    assert '<main id="main-content">' in introduction
    assert '<main id="chat-main"' in chat
    assert 'aria-live="polite"' in chat
    assert 'maxlength="4000"' in chat
    assert "previous turns are not sent as context" in chat
    assert '"/health"' in javascript
    assert '"/query"' in javascript
    for forbidden in ("localStorage", "sessionStorage", "document.cookie", "innerHTML"):
        assert forbidden not in javascript


def test_health_does_not_build_query_service(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VECTOR_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("INDEX_MANIFEST_PATH", str(tmp_path / "manifest.json"))
    app = create_app()

    response = TestClient(app, raise_server_exceptions=False).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "not_ready"
    assert app.state.query_service is None
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_invalid_request_does_not_echo_question() -> None:
    response = _client(FakeService()).post("/query", json={"question": "   "})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request."}
    assert "question" not in response.text.lower()


def test_malformed_upstream_response_maps_to_502() -> None:
    response = _client(FakeService(error=UpstreamResponseError())).post(
        "/query", json={"question": "A valid question"}
    )
    assert response.status_code == 502


def test_upstream_timeout_maps_to_504() -> None:
    response = _client(FakeService(error=UpstreamTimeoutError())).post(
        "/query", json={"question": "A valid question"}
    )
    assert response.status_code == 504
