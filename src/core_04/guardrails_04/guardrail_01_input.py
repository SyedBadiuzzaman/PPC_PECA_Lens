"""Guardrail flow 01: check input before any external request."""

from __future__ import annotations

import re
from collections.abc import Callable

from src.domain_01.domain_02_exceptions import QuestionTooLongError, SensitiveInputError

MAX_ENCODER_TOKENS = 512

_IDENTIFIER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\d)\d{5}-?\d{7}-?\d(?!\d)"),
    re.compile(r"(?<!\d)(?:\+92|0092|0)3\d{2}[\s-]?\d{7}(?!\d)"),
)


def validate_question(
    question: str,
    *,
    token_counter: Callable[[str], int],
) -> None:
    """Reject common identifiers and questions that exceed Legal-BERT's limit."""

    if any(pattern.search(question) for pattern in _IDENTIFIER_PATTERNS):
        raise SensitiveInputError(
            "The question contains a recognizable personal identifier."
        )
    if token_counter(question) > MAX_ENCODER_TOKENS:
        raise QuestionTooLongError("The question exceeds the encoder token limit.")
