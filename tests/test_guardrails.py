"""Focused tests for local guardrails."""

import pytest

from src.core_04.guardrails_04.guardrail_01_input import validate_question
from src.core_04.guardrails_04.guardrail_03_output import LEGAL_DISCLAIMER, append_disclaimer
from src.domain_01.domain_02_exceptions import QuestionTooLongError, SensitiveInputError


@pytest.mark.parametrize(
    "question",
    [
        "Email me at person@example.com about PECA.",
        "My CNIC is 12345-1234567-1.",
        "Call 0300-1234567 about this PPC case.",
    ],
)
def test_common_personal_identifiers_are_rejected(question: str) -> None:
    with pytest.raises(SensitiveInputError):
        validate_question(question, token_counter=lambda value: 10)


def test_encoder_limit_is_enforced() -> None:
    with pytest.raises(QuestionTooLongError):
        validate_question("long question", token_counter=lambda value: 513)


def test_disclaimer_is_appended_once() -> None:
    first = append_disclaimer("Answer")
    second = append_disclaimer(first)

    assert first == second
    assert second.count(LEGAL_DISCLAIMER) == 1
