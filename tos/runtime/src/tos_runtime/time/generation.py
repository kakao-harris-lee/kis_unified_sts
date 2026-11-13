"""In-process monotonic TTS-generation counter (slice plan §1 item 3)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["GenerationCounter", "seed_from"]


class GenerationCounter:
    """A monotonically increasing, in-process generation counter."""

    def __init__(self, start: int) -> None:
        if start < 0:
            raise ValueError(
                f"GenerationCounter start must be non-negative (got {start})"
            )
        self._current = start

    @property
    def current(self) -> int:
        """The current generation (unchanged until :meth:`next` is called)."""
        return self._current

    def peek_next(self) -> int:
        """The generation :meth:`next` would produce, without advancing."""
        return self._current + 1

    def next(self) -> int:
        """Advance and return the new current generation."""
        self._current += 1
        return self._current


@runtime_checkable
class _RuntimeGenerationSource(Protocol):
    """The minimal seam :func:`seed_from` depends on — satisfied structurally by"""

    def latest_runtime_generation(self) -> int | None:
        """The most recently durably recorded ``runtime_generation``, or ``None``."""
        ...


def seed_from(source: _RuntimeGenerationSource) -> GenerationCounter:
    """Seed a fresh :class:`GenerationCounter` from the RCL log's durable record."""
    durable_generation = source.latest_runtime_generation()
    return GenerationCounter(
        start=0 if durable_generation is None else durable_generation
    )
