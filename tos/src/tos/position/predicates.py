"""tos.position pure predicates (kernel round #4 K-2).

Ported verbatim (same arithmetic, same fail-closed shape) from
``tos_runtime.riskstate.position`` (DR-0003 §2.2). Every function here is pure — no I/O, no
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
``SEND_SEALED`` + ``EGRESS_RESULT_CONSUMED`` present      CONFIRMED: ``filled_quantity``
                                                           (``0`` if the row carries none)
                                                           signed by ``send.side``.
``SEND_SEALED`` + ``RESULT_UNMATCHED`` present (no        UNKNOWN: the FULL sealed
``EGRESS_RESULT_CONSUMED`` for the same attempt)          ``send.quantity``, signed by
                                                           ``send.side`` — a
                                                           recorded-but-not-applied result
                                                           proves nothing was safely resolved.
``SEND_SEALED`` with NEITHER receipt kind present         IN-FLIGHT: the full sealed
                                                           quantity, signed by ``send.side`` —
                                                           genuinely still outstanding.
A ``side`` that matches NEITHER of the two injected        UNKNOWN in BOTH directions
side tokens                                                 (fail-closed — an unrecognized
                                                             side token proves no direction
                                                             at all, never defaults to one).
======================================================  =================================

If BOTH a ``RESULT_UNMATCHED`` and an ``EGRESS_RESULT_CONSUMED`` fact exist for the same
attempt, the caller is expected to have already resolved that supersession (the runtime reader
builds ``consumed_by_attempt`` / ``unmatched_attempts`` so a CONSUMED attempt never also
appears in ``unmatched_attempts`` — the durably APPLIED fact governs); this module trusts that
input shape and does not re-derive it.

Pure module: stdlib (``decimal``, ``collections.abc``) + ``tos.position.records`` only; no
``shared.*``, no sibling ``tos.*`` (mirrors every other kernel package's §0.3 discipline).
"""

from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from decimal import Decimal

from tos.position.records import PositionObservation, SealedSend

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


def classify_sealed_sends(
    sealed: tuple[SealedSend, ...],
    *,
    consumed_by_attempt: Mapping[str, Decimal],
    unmatched_attempts: AbstractSet[str],
    buy_side_token: str,
    sell_side_token: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int]:
    """The module docstring's classification table, applied to every sealed send. Returns
    ``(confirmed_net, unknown_buy, unknown_sell, in_flight_buy, in_flight_sell,
    attempts_seen)`` — the exact six-tuple :class:`~tos.position.records.PositionObservation`'s
    matching fields are built from (the caller attaches ``scope_key`` / ``sources``, which this
    pure function has no way to know)."""
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
        if send.attempt_id in consumed_by_attempt:
            filled = consumed_by_attempt[send.attempt_id]
            if sign is None:
                # Unrecognized side on a CONFIRMED fill: fail-closed to UNKNOWN in both
                # directions rather than silently dropping the confirmed magnitude.
                unknown_buy += filled
                unknown_sell += filled
                continue
            confirmed_net += sign * filled
            continue
        quantity = send.quantity if send.quantity is not None else Decimal(0)
        if send.attempt_id in unmatched_attempts:
            if sign is None:
                unknown_buy += quantity
                unknown_sell += quantity
                continue
            if sign > 0:
                unknown_buy += quantity
            else:
                unknown_sell += quantity
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
