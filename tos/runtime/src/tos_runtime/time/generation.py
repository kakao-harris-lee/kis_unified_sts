"""In-process monotonic TTS-generation counter (slice plan §1 item 3).

Realizes design #40 D1.1's line "``runtime_generation`` 은 D2 epoch 와 같은
트랜잭션에서 증가" for the Trustworthy Time axis specifically: the kernel's
``transition_to_trusted_requires_new_generation`` predicate
(``tos/src/tos/time/predicates.py``) requires a strictly-greater generation on
every return to ``TRUSTED``; this class is the runtime counter that supplies
one.

**Durability is explicitly out of this slice's scope** (slice plan §1 item 3:
"durable 은 순서 3 에서 RCL 로그와 결합"). This counter is monotonic only
*within one process lifetime* — a restart seeds a brand-new counter from its
own start value, never resuming a prior process's count. That is exactly why
fault contract ⑤ ("재기동 새 generation 은 이전 스냅샷을 되살리지 않음") holds
without any extra bookkeeping here: a new process's generation 0 shares no
provable relationship with whatever an earlier process invalidated, and
``tos.time.recovery_generation_revives_nothing`` documents that this is by
design, never accidental.

**Slice #2 durable-seed helper** (slice plan #2 §3 "레인 간·후속 계약": "M 이
``acquire_epoch`` 와 함께 ``runtime_generation`` 을 ``epochs`` 행에 기록하되
**두 epoch 를 동일시하지 않는다** ... ``GenerationCounter`` 의 durable 시드는
이 행에서 읽는다"). :func:`seed_from` below reads that durable value back —
via a small structural :class:`_RuntimeGenerationSource` ``Protocol`` rather
than an import of ``tos_runtime.rcl`` (lane M's own package), keeping this
edit minimal and this module's dependency surface unchanged (duck-typed,
matching the K/L "Protocol, not concrete import" inter-lane convention from
slice #1 §3).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["GenerationCounter", "seed_from"]


class GenerationCounter:
    """A monotonically increasing, in-process generation counter.

    Args:
        start: The seed value this process's counter begins at. Must be
            non-negative — a negative generation is not a valid TTS
            generation (mirrors ``tos.time.TimeContinuityIdentity.tts_generation``
            being an ``int | None``, never negative in practice).

    Raises:
        ValueError: If ``start`` is negative.
    """

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
        """The generation :meth:`next` would produce, without advancing.

        Lets a caller (:class:`~tos_runtime.time.service.TrustworthyTimeService`)
        evaluate ``transition_to_trusted_requires_new_generation`` against the
        *candidate* generation before committing to the bump — so a refused
        transition never consumes a generation it did not use.
        """
        return self._current + 1

    def next(self) -> int:
        """Advance and return the new current generation."""
        self._current += 1
        return self._current


@runtime_checkable
class _RuntimeGenerationSource(Protocol):
    """The minimal seam :func:`seed_from` depends on — satisfied structurally by
    ``tos_runtime.rcl.log.SqliteCommitLog`` without an import edge from this
    module to ``tos_runtime.rcl``.
    """

    def latest_runtime_generation(self) -> int | None:
        """The most recently durably recorded ``runtime_generation``, or ``None``."""
        ...


def seed_from(source: _RuntimeGenerationSource) -> GenerationCounter:
    """Seed a fresh :class:`GenerationCounter` from the RCL log's durable record.

    "durable 은 순서 3 에서 RCL 로그와 결합" — this is that combination point:
    a freshly started process reads whatever ``runtime_generation`` the RCL
    log last durably recorded (via ``SqliteCommitLog.acquire_epoch``) instead
    of always starting a brand-new counter at ``0``, so a restart can resume
    counting from the last durably known generation. When the log has never
    recorded one (a fresh, never-acquired log), this seeds at ``0`` — the
    same starting point an in-process-only counter would use.

    Args:
        source: Anything satisfying :class:`_RuntimeGenerationSource` — in
            practice, a live ``tos_runtime.rcl.log.SqliteCommitLog``.

    Returns:
        A new :class:`GenerationCounter` seeded from the durable value.
    """
    durable_generation = source.latest_runtime_generation()
    return GenerationCounter(
        start=0 if durable_generation is None else durable_generation
    )
