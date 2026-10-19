"""Ingestion flow 03: split pages with the Legal-BERT tokenizer."""

from __future__ import annotations

import hashlib
from typing import Protocol

from src.domain_01.domain_03_models import DocumentChunk, DocumentPage

CHUNK_TOKENS = 384
CHUNK_OVERLAP_TOKENS = 48


class ChunkTokenizer(Protocol):
    """Tokenizer operations needed by the splitter."""

    def offsets_for_chunking(self, text: str) -> list[tuple[int, int]]: ...


def split_page(
    page: DocumentPage,
    tokenizer: ChunkTokenizer,
    *,
    chunk_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP_TOKENS,
) -> list[DocumentChunk]:
    """Split one page without allowing a chunk to cross page boundaries."""

    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens must be greater than zero.")
    if overlap_tokens < 0 or overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be between zero and chunk_tokens - 1.")

    token_offsets = tokenizer.offsets_for_chunking(page.text)
    step = chunk_tokens - overlap_tokens
    chunks: list[DocumentChunk] = []
    for chunk_index, start in enumerate(range(0, len(token_offsets), step)):
        window = token_offsets[start : start + chunk_tokens]
        if not window:
            continue
        text = page.text[window[0][0] : window[-1][1]].strip()
        if not text:
            continue
        chunk_id = _chunk_id(page, chunk_index, text)
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                law=page.law,
                source=page.source,
                source_fingerprint=page.source_fingerprint,
                page=page.page,
                chunk_index=chunk_index,
                text=text,
            )
        )
        if start + chunk_tokens >= len(token_offsets):
            break
    return chunks


def _chunk_id(page: DocumentPage, chunk_index: int, text: str) -> str:
    identity = "|".join(
        (
            page.law.value,
            page.source_fingerprint,
            str(page.page),
            str(chunk_index),
            text,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
