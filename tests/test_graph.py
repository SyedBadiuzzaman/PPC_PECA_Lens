"""Black-box graph tests with all external calls replaced by fakes."""

from __future__ import annotations

import asyncio

import pytest

from src.domain_01.domain_01_enums import Law, QueryStatus, Route
from src.domain_01.domain_02_exceptions import SensitiveInputError
from src.domain_01.domain_03_models import (
    CitationDraft,
    GeneratedDraft,
    RetrievedChunk,
    RouterDecision,
)
from src.graph_05.graph_02_nodes import GraphNodes
from src.graph_05.graph_03_workflow import QueryService, compile_graph


class FakeRouter:
    def __init__(self, route: Route) -> None:
        self.route_value = route
        self.calls = 0

    async def route(self, question: str) -> RouterDecision:
        self.calls += 1
        return RouterDecision(route=self.route_value, reason="test")


class FakeRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls = 0

    def token_count(self, question: str) -> int:
        return len(question.split())

    def retrieve(self, question: str, law: Law) -> list[RetrievedChunk]:
        self.calls += 1
        return self.chunks


class FakeGenerator:
    def __init__(self, draft: GeneratedDraft | None) -> None:
        self.draft = draft
        self.calls = 0

    async def generate(
        self,
        question: str,
        law: Law,
        chunks: list[RetrievedChunk],
    ) -> GeneratedDraft | None:
        self.calls += 1
        return self.draft


def _service(
    route: Route,
    chunks: list[RetrievedChunk],
    draft: GeneratedDraft | None,
) -> tuple[QueryService, FakeRouter, FakeRetriever, FakeGenerator]:
    router = FakeRouter(route)
    retriever = FakeRetriever(chunks)
    generator = FakeGenerator(draft)
    graph = compile_graph(
        GraphNodes(router=router, retriever=retriever, generator=generator)  # type: ignore[arg-type]
    )
    assert getattr(graph, "checkpointer", None) is None
    assert getattr(graph, "store", None) is None
    return QueryService(graph, request_timeout_seconds=15), router, retriever, generator


def test_ppc_answer_requires_exact_retrieved_quote() -> None:
    chunk = RetrievedChunk(
        "chunk-1", Law.PPC, "ppc.pdf", 22, "The supported legal wording.", 0.1
    )
    draft = GeneratedDraft(
        answer="Grounded answer.",
        citations=[CitationDraft(chunk_id="chunk-1", quote="supported legal wording")],
    )
    service, _, retriever, generator = _service(Route.PPC, [chunk], draft)

    result = asyncio.run(service.ask("What does this provision say?"))

    assert result.status is QueryStatus.ANSWERED
    assert result.law is Law.PPC
    assert result.sources[0].page == 22
    assert "not legal advice" in result.answer
    assert retriever.calls == 1
    assert generator.calls == 1


def test_invalid_citation_becomes_insufficient_context() -> None:
    chunk = RetrievedChunk("chunk-1", Law.PECA, "peca.pdf", 3, "Source text", 0.1)
    draft = GeneratedDraft(
        answer="Unsupported answer.",
        citations=[CitationDraft(chunk_id="chunk-1", quote="invented quote")],
    )
    service, _, _, _ = _service(Route.PECA, [chunk], draft)

    result = asyncio.run(service.ask("What does PECA say?"))

    assert result.status is QueryStatus.INSUFFICIENT_CONTEXT
    assert result.sources == ()


def test_empty_retrieval_skips_generation() -> None:
    service, _, _, generator = _service(Route.PPC, [], None)

    result = asyncio.run(service.ask("PPC question"))

    assert result.status is QueryStatus.INSUFFICIENT_CONTEXT
    assert generator.calls == 0


@pytest.mark.parametrize(
    ("route", "expected_status"),
    [
        (Route.BOTH, QueryStatus.NEEDS_CLARIFICATION),
        (Route.OUT_OF_SCOPE, QueryStatus.OUT_OF_SCOPE),
    ],
)
def test_non_single_law_routes_skip_retrieval(
    route: Route, expected_status: QueryStatus
) -> None:
    service, _, retriever, generator = _service(route, [], None)

    result = asyncio.run(service.ask("ambiguous question"))

    assert result.status is expected_status
    assert retriever.calls == 0
    assert generator.calls == 0


def test_pii_is_rejected_before_router_call() -> None:
    service, router, _, _ = _service(Route.PPC, [], None)

    with pytest.raises(SensitiveInputError):
        asyncio.run(service.ask("My CNIC is 12345-1234567-1. What is the law?"))

    assert router.calls == 0
