"""Runtime core 01: route between the PPC and PECA collections."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from src.domain_01.domain_02_exceptions import UpstreamResponseError
from src.domain_01.domain_03_models import RouterDecision
from src.utils_03.utils_01_llm_client import JsonCompletionClient, to_openrouter_messages

ROUTER_SYSTEM_PROMPT = """Classify an English legal-reference question for this fixed corpus.
Return only JSON with keys route and reason.
route must be one of: ppc, peca, both, out_of_scope.
Use ppc for Pakistan Penal Code offences, definitions, and punishments.
Use peca for electronic crimes, information systems, cyber offences, and PECA procedure.
Use both when both statutes are materially required.
Use out_of_scope for non-legal questions or law outside these two sources.
Do not answer the legal question."""


class LegalRouter:
    """Route one question using the configured OpenRouter model."""

    def __init__(self, client: JsonCompletionClient, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    async def route(self, question: str) -> RouterDecision:
        """Return a validated routing decision."""

        payload = await self._client.complete_json(
            model=self._model_id,
            messages=to_openrouter_messages(
                (SystemMessage(ROUTER_SYSTEM_PROMPT), HumanMessage(question))
            ),
            max_tokens=180,
        )
        try:
            return RouterDecision.model_validate(payload)
        except ValidationError as exc:
            raise UpstreamResponseError("The router returned an invalid decision.") from exc
