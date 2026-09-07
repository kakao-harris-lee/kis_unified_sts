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
"""

from __future__ import annotations

__all__ = ["GenerationCounter"]


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
