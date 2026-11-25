"""The quantity a cancelled/expired partial fill left standing at the broker (#980)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from tos.engine.vocabulary import EgressResultKind

__all__ = [
    "NON_EXECUTION_KINDS",
    "NON_EXECUTION_KIND_VALUES",
    "ResultQuantity",
    "cancelled_partial_quantity",
]

NON_EXECUTION_KINDS: frozenset[EgressResultKind] = frozenset(
    {
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)

NON_EXECUTION_KIND_VALUES: frozenset[str] = frozenset(
    kind.value for kind in NON_EXECUTION_KINDS
)

_PARTIAL_FILL = EgressResultKind.PARTIAL_FILL.value
_FULL_FILL = EgressResultKind.FULL_FILL.value


@dataclass(frozen=True)
class ResultQuantity:
    """One recorded egress-result receipt, reduced to the three fields this rule reads."""

    kind: str | None
    filled: Decimal | None
    remaining: Decimal | None


def cancelled_partial_quantity(
    results: Sequence[ResultQuantity], *, terminal_kind: str | None
) -> Decimal | None:
    """The cumulative filled quantity ``terminal_kind`` made final, or ``None`` if unproven."""
    # SAFETY: every `return None` below leaves the reservation where it stood, which denies
    # both OPEN and CLOSE; returning a guessed quantity would instead let a CLOSE discharge
    # a position size no receipt proves.
    if terminal_kind not in NON_EXECUTION_KIND_VALUES:
        return None
    quantity = Decimal(0)
    authorized: Decimal | None = None
    closed = False
    for result in results:
        if result.kind == _FULL_FILL:
            return None
        filled = result.filled
        if result.kind != _PARTIAL_FILL:
            if result.kind in NON_EXECUTION_KIND_VALUES:
                closed = True
            # SAFETY: only a fill receipt may move the cumulative — a non-fill receipt that
            # states another quantity means a fill nobody recorded, so it proves nothing.
            if filled is None:
                continue
            if not filled.is_finite() or filled != quantity:
                return None
            continue
        # SAFETY: a fill receipt after the order was closed is a late/unmatched arrival — the
        # proof already issued names the earlier quantity, so raising the cumulative here would
        # let a CLOSE discharge more than any proof backs (#1160 review MEDIUM-1).
        if closed:
            return None
        if filled is None or not filled.is_finite() or filled < quantity:
            return None
        remaining = result.remaining
        if remaining is None or not remaining.is_finite() or remaining <= 0:
            return None
        total = filled + remaining
        if authorized is None:
            authorized = total
        elif total != authorized:
            return None
        quantity = filled
    if authorized is None or quantity <= 0:
        return None
    return quantity
