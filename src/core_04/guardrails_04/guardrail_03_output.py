"""Guardrail flow 03: verify citations and add required notices."""

from __future__ import annotations

import re

from src.domain_01.domain_03_models import GeneratedDraft, RetrievedChunk, VerifiedSource

LEGAL_DISCLAIMER = (
    "This prototype provides general legal reference information, not legal advice. "
    "Consult a qualified Pakistani lawyer and verify the current official law."
)
PPC_SOURCE_WARNING = (
    "The supplied PPC source says it was last amended on 16 February 2017 and may be outdated."
)
PECA_SOURCE_WARNING = (
    "The supplied PECA source is headed as a bill and contains visible OCR errors."
)
PRIVACY_WARNING = (
    "Basic identifier checks can miss names and other personal information."
)


def append_disclaimer(answer: str) -> str:
    """Append the legal disclaimer once."""

    answer = answer.strip()
    if LEGAL_DISCLAIMER in answer:
        return answer
    return f"{answer}\n\n{LEGAL_DISCLAIMER}"


def verify_citations(
    draft: GeneratedDraft,
    chunks: list[RetrievedChunk],
) -> tuple[VerifiedSource, ...] | None:
    """Require every cited quotation to occur in its retrieved chunk."""

    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    verified: list[VerifiedSource] = []
    seen: set[tuple[str, str]] = set()
    for citation in draft.citations:
        chunk = chunks_by_id.get(citation.chunk_id)
        if chunk is None:
            return None
        normalized_quote = _normalize(citation.quote)
        if not normalized_quote or normalized_quote not in _normalize(chunk.text):
            return None
        identity = (chunk.chunk_id, normalized_quote)
        if identity in seen:
            continue
        seen.add(identity)
        verified.append(
            VerifiedSource(
                law=chunk.law,
                source=chunk.source,
                page=chunk.page,
                chunk_id=chunk.chunk_id,
                quote=citation.quote.strip(),
            )
        )
    return tuple(verified) if verified else None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
