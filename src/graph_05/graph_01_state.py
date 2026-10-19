"""Graph flow 01: state carried through one stateless run."""

from __future__ import annotations

from typing import TypedDict

from src.domain_01.domain_01_enums import Law
from src.domain_01.domain_03_models import (
    GeneratedDraft,
    QueryResult,
    RetrievedChunk,
    RouterDecision,
)


class GraphState(TypedDict, total=False):
    """Transient state that is discarded after the request completes."""

    question: str
    decision: RouterDecision
    law: Law
    chunks: list[RetrievedChunk]
    draft: GeneratedDraft
    result: QueryResult
