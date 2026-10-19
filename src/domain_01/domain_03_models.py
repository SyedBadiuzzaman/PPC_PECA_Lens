"""Domain flow 03: models passed between ingestion, retrieval, and generation."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from src.domain_01.domain_01_enums import Law, QueryStatus, Route


@dataclass(frozen=True)
class DocumentPage:
    """Text extracted from one physical PDF page."""

    law: Law
    source: str
    source_fingerprint: str
    page: int
    text: str


@dataclass(frozen=True)
class DocumentChunk:
    """One deterministic unit stored in Chroma."""

    chunk_id: str
    law: Law
    source: str
    source_fingerprint: str
    page: int
    chunk_index: int
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned by similarity search."""

    chunk_id: str
    law: Law
    source: str
    page: int
    text: str
    distance: float


class RouterDecision(BaseModel):
    """Validated structured output from the router model."""

    model_config = ConfigDict(extra="forbid")

    route: Route
    reason: str = Field(min_length=1, max_length=300)


class CitationDraft(BaseModel):
    """A generator citation before local verification."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=1000)


class GeneratedDraft(BaseModel):
    """Validated structured output from a generator model."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=6000)
    citations: list[CitationDraft] = Field(min_length=1, max_length=5)


@dataclass(frozen=True)
class VerifiedSource:
    """A citation verified against retrieved local text."""

    law: Law
    source: str
    page: int
    chunk_id: str
    quote: str


@dataclass(frozen=True)
class QueryResult:
    """Final graph result before API serialization."""

    status: QueryStatus
    law: Law | None
    answer: str
    sources: tuple[VerifiedSource, ...] = ()
    warnings: tuple[str, ...] = ()
