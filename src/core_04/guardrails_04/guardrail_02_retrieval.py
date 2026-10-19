"""Guardrail flow 02: check locally retrieved evidence."""

from src.domain_01.domain_03_models import RetrievedChunk


def usable_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Keep complete records that can support a page citation."""

    return [
        chunk
        for chunk in chunks
        if chunk.chunk_id and chunk.source and chunk.page > 0 and chunk.text.strip()
    ]
