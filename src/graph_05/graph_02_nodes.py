"""Graph flow 02: nodes for the linear legal-reference workflow."""

from __future__ import annotations

import asyncio

from src.core_04.core_01_router import LegalRouter
from src.core_04.core_02_retriever import LegalRetriever
from src.core_04.core_03_generator import LegalGenerator
from src.core_04.guardrails_04.guardrail_01_input import validate_question
from src.core_04.guardrails_04.guardrail_03_output import (
    PECA_SOURCE_WARNING,
    PPC_SOURCE_WARNING,
    PRIVACY_WARNING,
    append_disclaimer,
    verify_citations,
)
from src.domain_01.domain_01_enums import Law, QueryStatus, Route
from src.domain_01.domain_03_models import QueryResult
from src.graph_05.graph_01_state import GraphState


class GraphNodes:
    """Hold request-independent services used by graph nodes."""

    def __init__(
        self,
        *,
        router: LegalRouter,
        retriever: LegalRetriever,
        generator: LegalGenerator,
    ) -> None:
        self._router = router
        self._retriever = retriever
        self._generator = generator

    async def check_input(self, state: GraphState) -> GraphState:
        """Run local checks before the question leaves the machine."""

        await asyncio.to_thread(
            validate_question,
            state["question"],
            token_counter=self._retriever.token_count,
        )
        return {}

    async def route(self, state: GraphState) -> GraphState:
        """Classify the question into a supported legal collection."""

        decision = await self._router.route(state["question"])
        update: GraphState = {"decision": decision}
        if decision.route is Route.PPC:
            update["law"] = Law.PPC
        elif decision.route is Route.PECA:
            update["law"] = Law.PECA
        return update

    async def retrieve(self, state: GraphState) -> GraphState:
        """Retrieve evidence only for a single-law route."""

        law = state.get("law")
        if law is None:
            return {"chunks": []}
        chunks = await asyncio.to_thread(
            self._retriever.retrieve,
            state["question"],
            law,
        )
        return {"chunks": chunks}

    async def generate(self, state: GraphState) -> GraphState:
        """Generate only when the routed collection returned evidence."""

        law = state.get("law")
        chunks = state.get("chunks", [])
        if law is None or not chunks:
            return {}
        draft = await self._generator.generate(state["question"], law, chunks)
        return {"draft": draft} if draft is not None else {}

    async def check_output(self, state: GraphState) -> GraphState:
        """Build a public result after verifying every citation locally."""

        decision = state["decision"]
        if decision.route is Route.OUT_OF_SCOPE:
            return {
                "result": QueryResult(
                    status=QueryStatus.OUT_OF_SCOPE,
                    law=None,
                    answer=append_disclaimer(
                        "This question is outside the supplied PPC and PECA sources."
                    ),
                    warnings=(PRIVACY_WARNING,),
                )
            }
        if decision.route is Route.BOTH:
            return {
                "result": QueryResult(
                    status=QueryStatus.NEEDS_CLARIFICATION,
                    law=None,
                    answer=append_disclaimer(
                        "Please ask separately about the PPC offence or the PECA cyber-law issue."
                    ),
                    warnings=(PRIVACY_WARNING,),
                )
            }

        law = state["law"]
        warning = PPC_SOURCE_WARNING if law is Law.PPC else PECA_SOURCE_WARNING
        draft = state.get("draft")
        if draft is None:
            return {
                "result": _insufficient_result(law, warning),
            }
        sources = verify_citations(draft, state.get("chunks", []))
        if sources is None:
            return {
                "result": _insufficient_result(law, warning),
            }
        return {
            "result": QueryResult(
                status=QueryStatus.ANSWERED,
                law=law,
                answer=append_disclaimer(draft.answer),
                sources=sources,
                warnings=(warning, PRIVACY_WARNING),
            )
        }


def _insufficient_result(law: Law, warning: str) -> QueryResult:
    return QueryResult(
        status=QueryStatus.INSUFFICIENT_CONTEXT,
        law=law,
        answer=append_disclaimer(
            "The retrieved excerpts do not provide enough verified support for an answer."
        ),
        warnings=(warning, PRIVACY_WARNING),
    )
