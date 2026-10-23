"""tos.position pure predicates (kernel round #4 K-2).

Ported (same fail-closed shape) from ``tos_runtime.riskstate.position`` (DR-0003 §2.2); the
consumed-result row was since corrected to tell terminal from non-terminal results (lane A
re-review #7, see "why IN-FLIGHT" below). Every function here is pure — no I/O, no
clock, no broker query, exactly the pure half of the runtime module's original mixed
pure-logic/impure-I/O module (the impure half — reading the durable evidence store, JSON
decoding, scope filtering — stays in ``tos_runtime.riskstate.position.EvidencePositionReader``,
which now calls into this package instead of carrying the logic itself).

**Classification table (per sealed attempt, DR-0003 §2.2 verbatim: "confirmed fills from
consumed egress results, signed by the sealed outbound side; every attempt that was sealed but
has no terminal result counted in full, in the direction that makes usage largest").**

======================================================  =================================
Evidence state for one ``attempt_id``                    Classification
======================================================  =================================
``SEND_SEALED`` + latest ``EGRESS_RESULT_CONSUMED``       CONFIRMED: ``filled_quantity``
whose ``result_kind`` is TERMINAL (one of the injected    (``0`` if the row carries none)
``terminal_result_kinds`` — the runtime injects           signed by ``send.side``; nothing
``tos.engine.TERMINAL_RESULT_KINDS``: ``FULL_FILL`` /     outstanding.
``REJECT`` / ``CANCEL_ACK`` / ``EXPIRED``)
``SEND_SEALED`` + latest ``EGRESS_RESULT_CONSUMED``       CONFIRMED: ``filled_quantity``
whose ``result_kind`` is NOT terminal (``ACK`` /          signed by ``send.side``, PLUS
``PARTIAL_FILL`` / ``TIMEOUT`` / ``UNKNOWN``, or a        IN-FLIGHT: the outstanding
missing / unrecognized token — fail-closed)               quantity ``max(remaining_quantity,
                                                           send.quantity - filled_quantity,
                                                           0)`` signed by ``send.side``.
``SEND_SEALED`` + ``RESULT_UNMATCHED`` not superseded     IN-FLIGHT: the FULL sealed
by a LATER ``EGRESS_RESULT_CONSUMED``                     ``send.quantity``, signed by
                                                           ``send.side`` — a
                                                           recorded-but-not-applied result
                                                           proves nothing was safely resolved.
``SEND_SEALED`` + ``RESULT_UNMATCHED`` recorded AFTER     As the non-terminal CONSUMED row,
the latest ``EGRESS_RESULT_CONSUMED``                     whatever that result's kind: the
                                                           consumed ``filled_quantity`` stays
                                                           CONFIRMED, the unfilled remainder
                                                           returns to IN-FLIGHT.
``SEND_SEALED`` with NEITHER receipt kind present         IN-FLIGHT: the full sealed
                                                           quantity, signed by ``send.side`` —
                                                           genuinely still outstanding.
A ``side`` that matches NEITHER of the two injected        UNKNOWN in BOTH directions
side tokens                                                 (fail-closed — an unrecognized
                                                             side token proves no direction
                                                             at all, never defaults to one);
                                                             any IN-FLIGHT quantity (non-
                                                             terminal remainder, unmatched or
                                                             unresulted) goes to IN-FLIGHT in
                                                             both directions.
======================================================  =================================

**Why a non-terminal remainder is IN-FLIGHT, not UNKNOWN (Phase-0 lane A re-review #7).**
``tos.engine.core`` records ``EGRESS_RESULT_CONSUMED`` for EVERY applied result, including the
non-terminal ``ACK`` / ``PARTIAL_FILL`` / ``TIMEOUT`` / ``UNKNOWN``, so "consumed" never implied
"resolved" — reading it as resolved dropped the unfilled quantity entirely (a sealed 10-lot
read 0 after an ACK, 7 after a 7/3 partial). DR-0003 §2.2 counts "every attempt that was sealed
but has no terminal result" in full; an attempt whose latest result is non-terminal is exactly
that, so its unfilled part keeps the classification it had BEFORE any result arrived — the
sealed-no-receipt IN-FLIGHT row. That bucket is also the one that cannot understate the risk
decision: ARE grants iff ``requested_increment <= headroom``, i.e. ``conservative_current_usage
+ command + required_concurrent_overlap_effect <= limit``; moving a quantity ``q`` from UNKNOWN
to IN-FLIGHT lowers ``conservative_current_usage`` by at most ``q`` (triangle inequality) and
raises the never-netted overlap by exactly ``q``, so the decision sum never falls — whereas
UNKNOWN nets against an opposite confirmed position (prior +10, an unknown 10-lot sell: sum 10
instead of the in-flight 20) and would let a ``TIMEOUT`` shrink the sum below the no-result
state. The remainder is the larger of the recorded ``remaining_quantity`` and ``send.quantity -
filled_quantity`` so an absent or under-reported remainder never shrinks it.

**Why an unmatched result is IN-FLIGHT too.** The same decision-sum argument applies: UNKNOWN
nets against an opposite confirmed position, IN-FLIGHT never does, so an unmatched 10-lot sell
over a confirmed +10 would read 10 as UNKNOWN but 20 as IN-FLIGHT — and 20 is what the attempt
read before the unmatched result was recorded. Moving the quantity to IN-FLIGHT can only raise
the sum, so recording a result never makes the position look safer than recording none.

**Supersession.** ``unmatched_attempts`` holds the attempts whose ``RESULT_UNMATCHED`` was NOT
superseded by a later ``EGRESS_RESULT_CONSUMED`` (the caller compares evidence ``seq`` — this
module trusts that input shape), so it may overlap ``consumed_by_attempt``. An unmatched result
recorded AFTER the latest consumed one is a result that was never applied (e.g. a
cancel-crossing fill arriving after a ``CANCEL_ACK``), so the attempt is not resolved even if
the consumed kind is terminal: its outstanding quantity is computed as for a non-terminal
result. An unmatched result recorded BEFORE a consumed one is superseded — the durably APPLIED
fact governs.

Pure module: stdlib (``decimal``, ``collections.abc``) + ``tos.position.records`` only; no
``shared.*``, no sibling ``tos.*`` (mirrors every other kernel package's §0.3 discipline).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from decimal import Decimal

from tos.position.records import ConsumedResult, PositionObservation, SealedSend

__all__ = [
    "worst_credible_directional_usage",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "sign_of",
    "classify_sealed_sends",
]


def worst_credible_directional_usage(obs: PositionObservation) -> Decimal:
    """The worst-credible directional usage magnitude (plan §2.2, pure function).

    ``max(|confirmed_net + unknown_buy + in_flight_buy|, |confirmed_net - unknown_sell -
    in_flight_sell|)`` — every unconfirmed/in-flight quantity pushed to the direction that
    makes usage LARGEST (ARE-INV-006: UNKNOWN consumes conservative capacity, never assumed
    safe). Adding an unknown attempt in either direction can only enlarge (or leave unchanged)
    this magnitude, never shrink it.
    """
    long_case = obs.confirmed_net + obs.unknown_buy + obs.in_flight_buy
    short_case = obs.confirmed_net - obs.unknown_sell - obs.in_flight_sell
    return max(abs(long_case), abs(short_case))


def conservative_current_usage(obs: PositionObservation) -> Decimal:
    """Like :func:`worst_credible_directional_usage`, but WITHOUT the in-flight terms (plan
    §2.2: "``conservative_current_usage`` = 이 값 − in-flight 항(in-flight 는
    ``required_concurrent_overlap_effect`` 로 별도)") — the confirmed-plus-unconfirmed-only
    worst-credible magnitude, excluding attempts that are still genuinely outstanding.
    """
    long_case = obs.confirmed_net + obs.unknown_buy
    short_case = obs.confirmed_net - obs.unknown_sell
    return max(abs(long_case), abs(short_case))


def in_flight_overlap_effect(obs: PositionObservation) -> Decimal:
    """The magnitude an ARE ``ProjectedCell.required_concurrent_overlap_effect`` would take
    from this observation (plan §2.2) — the sum of both in-flight buckets, never netted (an
    in-flight buy and an in-flight sell are both still-outstanding overlap exposure, not
    offsetting positions)."""
    return obs.in_flight_buy + obs.in_flight_sell


def sign_of(
    side: str | None, *, buy_side_token: str, sell_side_token: str
) -> int | None:
    """The directional sign for ``side`` against the two injected tokens, or ``None`` when it
    matches neither (fail-closed, never a guessed direction — side stays a policy/config-carried
    token, CLAUDE.md "Futures must preserve long/short symmetry")."""
    if side == buy_side_token:
        return 1
    if side == sell_side_token:
        return -1
    return None


def _outstanding_after(
    consumed: ConsumedResult,
    sealed_quantity: Decimal,
    *,
    terminal_result_kinds: AbstractSet[str],
    reopened: bool,
) -> Decimal:
    """The still-outstanding quantity of an attempt whose latest applied result is
    ``consumed`` (module docstring's "why IN-FLIGHT" note): ``0`` for a terminal result kind;
    otherwise the larger of the recorded remainder and ``sealed - filled`` (never negative). A
    missing or unrecognized ``result_kind`` is not terminal (fail-closed), and neither is any
    result that a later unmatched result ``reopened``."""
    if (
        not reopened
        and consumed.result_kind is not None
        and consumed.result_kind in terminal_result_kinds
    ):
        return Decimal(0)
    filled = consumed.filled_quantity or Decimal(0)
    remaining = consumed.remaining_quantity or Decimal(0)
    return max(remaining, sealed_quantity - filled, Decimal(0))


def classify_sealed_sends(
    sealed: tuple[SealedSend, ...],
    *,
    consumed_by_attempt: Mapping[str, ConsumedResult],
    unmatched_attempts: AbstractSet[str],
    buy_side_token: str,
    sell_side_token: str,
    terminal_result_kinds: AbstractSet[str],
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int]:
    """The module docstring's classification table, applied to every sealed send. Returns
    ``(confirmed_net, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell,
    attempts_seen)`` — the exact six-tuple :class:`~tos.position.records.PositionObservation`'s
    matching fields are built from (the caller attaches ``scope_key`` / ``sources``, which this
    pure function has no way to know).

    ``consumed_by_attempt`` maps each attempt to its LATEST applied result (the caller picks
    it — the runtime reader takes the highest evidence ``seq``); ``terminal_result_kinds`` is the
    injected terminal token set (the runtime passes ``tos.engine.TERMINAL_RESULT_KINDS``'s
    values), REQUIRED with no default for the same reason the side tokens are."""
    confirmed_net = Decimal(0)
    unknown_buy = Decimal(0)
    unknown_sell = Decimal(0)
    in_flight_buy = Decimal(0)
    in_flight_sell = Decimal(0)
    attempts_seen = 0
    for send in sealed:
        attempts_seen += 1
        sign = sign_of(
            send.side, buy_side_token=buy_side_token, sell_side_token=sell_side_token
        )
        quantity = send.quantity if send.quantity is not None else Decimal(0)
        consumed = consumed_by_attempt.get(send.attempt_id)
        if consumed is not None:
            filled = consumed.filled_quantity or Decimal(0)
            outstanding = _outstanding_after(
                consumed,
                quantity,
                terminal_result_kinds=terminal_result_kinds,
                reopened=send.attempt_id in unmatched_attempts,
            )
            if sign is None:
                # Unrecognized side on a CONFIRMED fill: fail-closed to UNKNOWN in both
                # directions rather than silently dropping the confirmed magnitude; the
                # outstanding remainder stays IN-FLIGHT in both directions.
                unknown_buy += filled
                unknown_sell += filled
                in_flight_buy += outstanding
                in_flight_sell += outstanding
                continue
            confirmed_net += sign * filled
            if sign > 0:
                in_flight_buy += outstanding
            else:
                in_flight_sell += outstanding
            continue
        if send.attempt_id in unmatched_attempts:
            if sign is None:
                in_flight_buy += quantity
                in_flight_sell += quantity
                continue
            if sign > 0:
                in_flight_buy += quantity
            else:
                in_flight_sell += quantity
            continue
        # Sealed, no terminal result at all: genuinely in-flight.
        if sign is None:
            in_flight_buy += quantity
            in_flight_sell += quantity
            continue
        if sign > 0:
            in_flight_buy += quantity
        else:
            in_flight_sell += quantity
    return (
        confirmed_net,
        unknown_buy,
        unknown_sell,
        in_flight_buy,
        in_flight_sell,
        attempts_seen,
    )
