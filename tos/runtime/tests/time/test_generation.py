"""Hermetic tests for tos_runtime.time.generation (slice plan §1 item 3, §2 item 3)."""

from __future__ import annotations

import pytest
from tos_runtime.time.generation import GenerationCounter, seed_from


def test_negative_start_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        GenerationCounter(start=-1)


def test_current_reflects_seed_until_next_is_called() -> None:
    counter = GenerationCounter(start=5)
    assert counter.current == 5


def test_peek_next_does_not_advance() -> None:
    counter = GenerationCounter(start=0)
    assert counter.peek_next() == 1
    assert counter.current == 0
    assert counter.peek_next() == 1  # idempotent, still hasn't advanced


def test_next_advances_monotonically() -> None:
    counter = GenerationCounter(start=0)
    assert counter.next() == 1
    assert counter.current == 1
    assert counter.next() == 2
    assert counter.current == 2


class _FakeGenerationSource:
    """A minimal double satisfying ``_RuntimeGenerationSource`` structurally."""

    def __init__(self, latest: int | None) -> None:
        self._latest = latest

    def latest_runtime_generation(self) -> int | None:
        return self._latest


def test_seed_from_uses_the_source_durable_generation() -> None:
    counter = seed_from(_FakeGenerationSource(latest=7))
    assert counter.current == 7


def test_seed_from_defaults_to_zero_when_source_never_recorded_one() -> None:
    counter = seed_from(_FakeGenerationSource(latest=None))
    assert counter.current == 0
