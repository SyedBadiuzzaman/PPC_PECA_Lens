"""Small deterministic metrics for the prototype evaluation set."""

from __future__ import annotations

from collections.abc import Sequence


def accuracy(matches: Sequence[bool]) -> float:
    """Return the fraction of exact matches, or zero for an empty set."""

    return sum(matches) / len(matches) if matches else 0.0


def page_hit_at_three(retrieved_pages: Sequence[int], expected_pages: Sequence[int]) -> bool:
    """Return whether the top three include an expected physical page."""

    return bool(set(retrieved_pages[:3]).intersection(expected_pages))


def citations_are_complete(sources: Sequence[object], status: str) -> bool:
    """Require at least one verified source for every answered result."""

    return status != "answered" or bool(sources)
