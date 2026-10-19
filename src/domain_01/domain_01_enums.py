"""Domain flow 01: stable values used by the API and graph."""

from enum import StrEnum


class Law(StrEnum):
    """Legal collections supported by the prototype."""

    PPC = "ppc"
    PECA = "peca"


class Route(StrEnum):
    """Router outcomes before retrieval."""

    PPC = "ppc"
    PECA = "peca"
    BOTH = "both"
    OUT_OF_SCOPE = "out_of_scope"


class QueryStatus(StrEnum):
    """Public result statuses."""

    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    NEEDS_CLARIFICATION = "needs_clarification"
    OUT_OF_SCOPE = "out_of_scope"
