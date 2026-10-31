"""``SyntheticVenueLedgerWitness`` — the ``BrokerWitness`` over the synthetic venue's own ledger.

**Why a second synthetic witness exists (#1011 §1, plan 2026-10-31 §3.2).**
:class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness` reads the evidence store —
the SAME durable store the :class:`~tos_runtime.recon.ports.EvidenceReceiptReader` path reads —
so it declares ``independent_of_evidence_store=False`` and
:class:`~tos_runtime.recon.service.ReconciliationService` stamps it with the receipt path's own
independence class. Two byte-identical reads of one store are not two paths, the W2-R rule that
says so is correct, and the thing that was actually missing was a venue-side record. This witness
reads that record: :mod:`tos_runtime.venue_ledger.synthetic`'s separate
``venue_ledger.sqlite3``, written at the transport boundary, never derived from an evidence row.

**Independence, stated exactly.** ``provenance="synthetic-venue-ledger"`` — not
``"synthetic-ledger"`` (the store-derived one) and not a broker read. The structural claim is
"different file, different writer, not derived from the evidence store", which is what
``independent_of_evidence_store`` actually names. It is NOT the independence of a real broker:
the same process writes both files (plan §6 decision 2, accepted by the operator 2026-10-31).
Futures real orders are permanently blocked by policy (CLAUDE.md), so the synthetic venue IS the
final venue there, and this is the strongest honest record available for it.

**The constructor takes a ledger reader and nothing else that could reach the evidence store.**
:class:`~tos_runtime.venue_ledger.synthetic.VenueLedgerReader` opens one file through sqlite's
``mode=ro`` URI. There is no evidence-store parameter to pass, so "it read the evidence store
after all" is unrepresentable rather than merely disclosed — the mechanical form of the F2
finding that made ``independent_of_evidence_store`` a field in the first place.

**Side stays a policy-carried token.** ``buy_side_token``/``sell_side_token`` are REQUIRED
constructor arguments with no default, the same discipline
:class:`~tos_runtime.riskstate.position.EvidencePositionReader` already holds: a runtime module
that spells a side literally breaks long/short symmetry and the repo-wide pin in
``tos/runtime/tests/test_no_side_literals.py``. The caller sources them from the same
policy/config surface the venue side uses.

**Deliberately not re-exported from** :mod:`tos_runtime.recon`'s ``__init__``, unlike its two
sibling witnesses. :mod:`tos_runtime.venue_ledger.synthetic` already imports
``tos_runtime.recon.ports`` for :class:`~tos_runtime.recon.ports.WitnessUnavailable` (the shared
read-failure exception type — the same reuse :mod:`tos_runtime.riskstate.position` documents), so
a ``recon -> venue_ledger`` package edge would close an import cycle that breaks whenever
``tos_runtime.venue_ledger`` is imported first. Callers import this module by path.

Firewall: stdlib (``decimal``) + ``tos.engine`` (``FILL_RESULT_KINDS`` only) +
``tos_runtime.recon.ports`` + ``tos_runtime.recon.witness_synthetic`` (the shared result-kind →
witness-state table) + ``tos_runtime.venue_ledger``. No ``os.environ``, no network, no writer
call, and — load-bearing — no ``tos_runtime.evidence`` import at all.
"""

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

#: The honesty label on every snapshot this witness returns — distinct on sight from
#: ``"synthetic-ledger"`` (store-derived) and from any real broker read (module docstring).
SYNTHETIC_VENUE_LEDGER_PROVENANCE = "synthetic-venue-ledger"

#: The kernel's fill-bearing kinds as the bare tokens a ledger row stores — derived from
#: ``tos.engine.FILL_RESULT_KINDS``, never a second literal list (the same derivation
#: :mod:`tos_runtime.riskstate.position` uses).
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
        """Bind this witness to one venue ledger file.

        Args:
            ledger: The read-only venue-ledger reader. This is the ONLY durable source this
                class has — there is deliberately no evidence-store parameter (module
                docstring).
            buy_side_token: The policy/config-carried token for the position-increasing side.
            sell_side_token: The policy/config-carried token for the position-reducing side.
                Both are required and have no default: a literal spelled here would be exactly
                the long/short-symmetry break the repo-wide side-literal pin forbids.
            trading_date_now: Returns the KST trading date (``YYYYMMDD``) at this instant, or
                ``None``. The SAME injected reading the ledger's writer and the egress receipt
                use, recorded on the snapshot as
                :attr:`~tos_runtime.recon.ports.WitnessSnapshot.order_inquiry_date`. The join
                itself uses each order's own recorded ``order_date``, never this.
            provenance: The honesty label stamped on every snapshot — never overridden to claim
                a broker read.

        Raises:
            ValueError: ``buy_side_token`` and ``sell_side_token`` are equal or blank — two
                sides that cannot be told apart make every net position meaningless.
        """
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
        """Report what the venue ledger holds for ``scope``.

        Args:
            scope: The (account, instrument, attempt) window. Filtered by account and — when
                given — instrument ONLY; never by ``attempt_ids``, because an order the caller
                does not know about is precisely the orphan the reconciliation is looking for
                (:class:`~tos_runtime.recon.ports.WitnessScope`).

        Returns:
            The snapshot, with ``independent_of_evidence_store=True`` and
            ``positions_complete=True``: every row was read (an unreadable one raises instead),
            so an empty ``positions`` here genuinely means flat, not "nothing legible".

        Raises:
            WitnessUnavailable: The ledger file could not be read, or carries a row this
                witness cannot decode — never an empty snapshot standing in for a failed read.
        """
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
        """One ledger row as a :class:`~tos_runtime.recon.ports.WitnessOrder`.

        All three join axes are carried: ``attempt_id`` (the venue recorded the attempt it
        executed, so the direct join in
        ``tos_runtime.recon.service._join_orders_by_execution_id`` applies), plus the
        ``(broker_execution_id, order_date)`` identity pair that same function falls back to
        for an attempt-less broker order. ``quantity``/``remaining`` mirror
        :class:`~tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness`'s own mapping —
        the filled and remaining magnitudes the result reported.
        """
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
        """The net of the ledger's fills per instrument, zero nets omitted.

        A zero net is omitted rather than reported as ``0`` so that an instrument the venue
        closed out reads the same as one it never traded — both flat. Together with
        ``positions_complete=True`` that is what
        ``tos_runtime.posttrade.entry_discharge.broker_position_flat`` needs to prove flatness
        after a close; a non-zero net (negative for a short) keeps it held.

        Raises:
            WitnessUnavailable: A fill row carries no magnitude, or a side token this witness
                cannot sign — a dropped fill would read as a SMALLER net than the venue holds.
        """
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
        """``+1``/``-1`` for ``row``'s recorded side token (never a literal — see the module).

        Raises:
            WitnessUnavailable: The side is neither configured token.
        """
        if row.side == self._buy_side_token:
            return Decimal(1)
        if row.side == self._sell_side_token:
            return Decimal(-1)
        raise WitnessUnavailable(
            f"venue ledger row written_seq={row.written_seq}: side={row.side!r} is neither "
            "configured side token — a fill whose direction is unknown cannot be netted"
        )

    def _inquiry_date(self) -> str | None:
        """The trading date this observation was taken on, or ``None`` when unestablished.

        ``None`` is the field's own documented "did not query one date only" value and is
        harmless here: the cross-reference join reads each order's recorded ``order_date``, not
        this. A raising source degrades the same way — an unavailable clock must not turn a
        readable ledger into an unavailable witness.
        """
        try:
            trading_date = self._trading_date_now()
        except (
            Exception
        ):  # noqa: BLE001 - a clock failure never invalidates the ledger read
            return None
        return trading_date if valid_trading_date(trading_date) else None


def _in_scope(row: VenueLedgerFill, scope: WitnessScope) -> bool:
    """Whether ``row`` falls within ``scope`` — account, then optional instrument narrowing.

    Never filtered by ``attempt_id``: orphan detection needs the unfiltered orders
    (:class:`~tos_runtime.recon.ports.WitnessScope`'s own contract).
    """
    if row.account != scope.account:
        return False
    if not scope.instrument_keys:
        return True
    return any(row.instrument == key.instrument for key in scope.instrument_keys)
