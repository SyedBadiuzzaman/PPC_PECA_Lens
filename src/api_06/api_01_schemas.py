"""API flow 01: validated public request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain_01.domain_01_enums import Law, QueryStatus
from src.domain_01.domain_03_models import QueryResult


class QueryRequest(BaseModel):
    """One standalone English legal-reference question."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_must_contain_text(cls, value: str) -> str:
        """Reject values that become empty after whitespace normalization."""

        if not value.strip():
            raise ValueError("question must contain text")
        return value


class SourceResponse(BaseModel):
    """One locally verified source quotation."""

    law: Law
    source: str
    page: int
    chunk_id: str
    quote: str


class QueryResponse(BaseModel):
    """A grounded answer or explicit fallback."""

    status: QueryStatus
    law: Law | None
    answer: str
    sources: list[SourceResponse]
    warnings: list[str]

    @classmethod
    def from_result(cls, result: QueryResult) -> "QueryResponse":
        """Convert the internal immutable result to the API schema."""

        return cls(
            status=result.status,
            law=result.law,
            answer=result.answer,
            sources=[
                SourceResponse(
                    law=source.law,
                    source=source.source,
                    page=source.page,
                    chunk_id=source.chunk_id,
                    quote=source.quote,
                )
                for source in result.sources
            ],
            warnings=list(result.warnings),
        )


class HealthResponse(BaseModel):
    """Local readiness details that never trigger a paid model call."""

    status: str
    index_ready: bool
    configuration_ready: bool
    collections: dict[str, int]
