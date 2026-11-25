"""``SyntheticVenueLedgerWitness`` — the ``BrokerWitness`` over the synthetic venue's own ledger."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from tos.engine import FILL_RESULT_KINDS

from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
    WitnessUnavailable,
)
from tos_runtime.recon.witness_synthetic import EGRESS_KIND_TO_WITNESS_STATE
from tos_runtime.venue_ledger.synthetic import (
    VenueLedgerFill,
    VenueLedgerReader,
    valid_trading_date,
)

__all__ = [
    "SYNTHETIC_VENUE_LEDGER_PROVENANCE",
    "SyntheticVenueLedgerWitness",
]

SYNTHETIC_VENUE_LEDGER_PROVENANCE = "synthetic-venue-ledger"

_FILL_RESULT_TOKENS: frozenset[str] = frozenset(
    kind.value for kind in FILL_RESULT_KINDS
)


class SyntheticVenueLedgerWitness:
    """A :class:`~tos_runtime.recon.ports.BrokerWitness` over the synthetic venue ledger."""

    def __init__(
        self,
        ledger: VenueLedgerReader,
        *,
        buy_side_token: str,
        sell_side_token: str,
        trading_date_now: Callable[[], str | None],
        provenance: str = SYNTHETIC_VENUE_LEDGER_PROVENANCE,
    ) -> None:
        """Bind this witness to one venue ledger file."""
        if not buy_side_token.strip() or not sell_side_token.strip():
            raise ValueError(
                "SyntheticVenueLedgerWitness: buy_side_token/sell_side_token must both be "
                f"concrete policy tokens (got {buy_side_token!r} / {sell_side_token!r})"
            )
        if buy_side_token == sell_side_token:
            raise ValueError(
                "SyntheticVenueLedgerWitness: buy_side_token and sell_side_token are the same "
                f"token {buy_side_token!r} — a net position would be unsigned"
            )
        self._ledger = ledger
        self._buy_side_token = buy_side_token
        self._sell_side_token = sell_side_token
        self._trading_date_now = trading_date_now
        self._provenance = provenance

    def observe(self, scope: WitnessScope) -> WitnessSnapshot:
        """Report what the venue ledger holds for ``scope``."""
        rows = tuple(row for row in self._ledger.fills() if _in_scope(row, scope))
        orders = tuple(self._order_from_row(row) for row in rows)
        positions = self._net_positions(rows)
        return WitnessSnapshot(
            observed_at_generation=scope.as_of_generation,
            orders=orders,
            positions=positions,
            positions_complete=True,
            cash=None,
            provenance=self._provenance,
            independent_of_evidence_store=True,
            order_inquiry_date=self._inquiry_date(),
        )

    @staticmethod
    def _order_from_row(row: VenueLedgerFill) -> WitnessOrder:
        """One ledger row as a :class:`~tos_runtime.recon.ports.WitnessOrder`."""
        return WitnessOrder(
            attempt_id=row.attempt_id,
            broker_execution_id=row.broker_execution_id,
            quantity=row.filled_quantity,
            remaining=row.remaining_quantity,
            state=EGRESS_KIND_TO_WITNESS_STATE.get(
                row.result_kind, WitnessOrderState.UNKNOWN
            ),
            order_date=row.trading_date,
        )

    def _net_positions(
        self, rows: tuple[VenueLedgerFill, ...]
    ) -> tuple[tuple[str, Decimal], ...]:
        """The net of the ledger's fills per instrument, zero nets omitted."""
        nets: dict[str, Decimal] = {}
        for row in rows:
            if row.result_kind not in _FILL_RESULT_TOKENS:
                continue
            if row.filled_quantity is None:
                raise WitnessUnavailable(
                    f"venue ledger row written_seq={row.written_seq}: "
                    f"result_kind={row.result_kind!r} is a fill with no filled_quantity"
                )
            nets[row.instrument] = (
                nets.get(row.instrument, Decimal(0))
                + self._signed(row) * row.filled_quantity
            )
        return tuple(
            (instrument, net) for instrument, net in sorted(nets.items()) if net != 0
        )

    def _signed(self, row: VenueLedgerFill) -> Decimal:
        """``+1``/``-1`` for ``row``'s recorded side token (never a literal — see the module)."""
        if row.side == self._buy_side_token:
            return Decimal(1)
        if row.side == self._sell_side_token:
            return Decimal(-1)
        raise WitnessUnavailable(
            f"venue ledger row written_seq={row.written_seq}: side={row.side!r} is neither "
            "configured side token — a fill whose direction is unknown cannot be netted"
        )

    def _inquiry_date(self) -> str | None:
        """The trading date this observation was taken on, or ``None`` when unestablished."""
        try:
            trading_date = self._trading_date_now()
        except (
            Exception
        ):  # noqa: BLE001 - a clock failure never invalidates the ledger read
            return None
        return trading_date if valid_trading_date(trading_date) else None


def _in_scope(row: VenueLedgerFill, scope: WitnessScope) -> bool:
    """Whether ``row`` falls within ``scope`` — account, then optional instrument narrowing."""
    if row.account != scope.account:
        return False
    if not scope.instrument_keys:
        return True
    return any(row.instrument == key.instrument for key in scope.instrument_keys)
