"""Hermetic tests for tos_runtime.time.generation (slice plan §1 item 3)."""

from __future__ import annotations

import pytest
from tos_runtime.time.generation import GenerationCounter


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
