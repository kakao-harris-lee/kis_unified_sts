"""Projects one bar's proven position off durable evidence (plan P4 §2 D1/D3, stage S2)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from tos.canonical import ArtifactIntegrityError, CanonicalizationScheme
from tos.dsl import (
    ContextValueView,
    PositionContext,
    PositionSide,
    flat_position_context,
    project_position_context,
)
from tos.egressgw import admitted_shape_price_from_view
from tos.engine import EventKind, InstrumentKey

from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.projection import (
    ReservationProjectionReader,
    outstanding_reservations,
)
from tos_runtime.rcl.reservation_lookup import event_id_for_attempt
from tos_runtime.recon.ports import WitnessUnavailable
from tos_runtime.riskstate.close_bound import CloseBoundRefusal, EntryCloseBound
from tos_runtime.riskstate.position import EvidencePositionReader, PositionObservation

__all__ = [
    "ENTRY_PRICE_BASIS_EXECUTION",
    "ENTRY_PRICE_BASIS_ORDER",
    "EvidencePositionContextReader",
]

ENTRY_PRICE_BASIS_EXECUTION = "EXECUTION"

ENTRY_PRICE_BASIS_ORDER = "ORDER"

_SEND_SEALED_KIND = "SEND_SEALED"

_FILL_OBSERVED_KIND = "FILL_OBSERVED"

_VENUE_POLICY_BOUND_KIND = "VENUE_POLICY_BOUND"

_UNREADABLE = (WitnessUnavailable, sqlite3.Error)


def _payload_rows(
    store: SqliteEvidenceStore, kind: str
) -> list[tuple[int, dict[str, object]]]:
    """Every row of ``kind`` as ``(seq, scrubbed payload)`` in commit order."""
    rows = store.connection.execute(
        "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
        (kind,),
    ).fetchall()
    out: list[tuple[int, dict[str, object]]] = []
    for seq, payload_json in rows:
        decoded = json.loads(payload_json)
        payload = decoded.get("payload", decoded)
        if isinstance(payload, dict):
            out.append((int(seq), payload))
    return out


def _decimal(value: object) -> Decimal | None:
    """``value`` as a Decimal, or ``None`` when it is not one (bools are never numbers here)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int)):
        try:
            return Decimal(value)
        except (ValueError, ArithmeticError, InvalidOperation):
            return None
    return None


def _reads_positive(value: object) -> bool:
    """Whether ``value`` reads as a strictly positive number (``perf.py``'s own ``_positive``)."""
    magnitude = _decimal(value)
    return magnitude is not None and magnitude > 0


def _exact_positive_int(value: object) -> int | None:
    """``value`` as a positive int, only when it is EXACTLY integral (no repair, no rounding)."""
    magnitude = _decimal(value)
    if magnitude is None or magnitude <= 0:
        return None
    if magnitude != magnitude.to_integral_value():
        return None
    return int(magnitude)


def _max_as_of(view: ContextValueView) -> int | None:
    """The newest ``as_of`` the view's admitted values carry (``marketfeed/resolver.py``'s rule)."""
    return max((value.as_of for value in view.values), default=None)


def _nothing_unsettled(observation: PositionObservation) -> bool:
    """Whether no quantity of this scope is unknown or still in flight."""
    return (
        observation.unknown_buy == 0
        and observation.unknown_sell == 0
        and observation.in_flight_buy == 0
        and observation.in_flight_sell == 0
    )


class EvidencePositionContextReader:
    """Reads one tick's :class:`~tos.dsl.PositionContext` off durable evidence, or nothing."""

    def __init__(
        self,
        *,
        close_bound_reader: Callable[[], EntryCloseBound],
        position_reader: EvidencePositionReader,
        projection: ReservationProjectionReader,
        inbox: SqliteEventInbox,
        evidence_store: SqliteEvidenceStore,
        account: str,
        instrument: str,
        price_field_key: str,
        bar_interval_ms: int,
        scheme: CanonicalizationScheme,
    ) -> None:
        """Bind this reader to one tenant scope's durable stores and its declared price field."""
        self._close_bound_reader = close_bound_reader
        self._position_reader = position_reader
        self._projection = projection
        self._inbox = inbox
        self._evidence_store = evidence_store
        self._key = InstrumentKey(account=account, instrument=instrument)
        self._price_field_key = price_field_key
        self._bar_interval_ms = bar_interval_ms
        self._scheme = scheme

    def read(self, view: ContextValueView | None) -> PositionContext | None:
        """This bar's proven position, or ``None`` when any part of it is not established."""
        if view is None:
            return None
        price = admitted_shape_price_from_view(view, field_key=self._price_field_key)
        as_of = _max_as_of(view)
        if price is None or price <= 0 or as_of is None:
            return None
        try:
            observation = self._position_reader.observe()
            bound = self._close_bound_reader()
        except _UNREADABLE:
            return None
        # SAFETY: an unknown or in-flight quantity leaves the namespace absent — publishing a side while a send is unresolved would gate a declared stop-loss on a holding that may already be larger, smaller, or gone
        if not _nothing_unsettled(observation):
            return None
        if not bound.proven:
            return self._flat(bound, observation.confirmed_net, as_of=as_of)
        return self._held(bound, observation.confirmed_net, price=price, as_of=as_of)

    def _flat(
        self, bound: EntryCloseBound, confirmed_net: Decimal, *, as_of: int
    ) -> PositionContext | None:
        """The proven-flat context, but only when flatness was POSITIVELY established."""
        # SAFETY: only the one refusal meaning "no sole consumed entry here" may become FLAT — every other refusal means the bound could not be READ, and answering FLAT there would let an entry rule fire on top of a position nobody could prove
        if bound.refusal != CloseBoundRefusal.ENTRY_NOT_SOLE_CONSUMED_POSITION:
            return None
        if confirmed_net != 0:
            return None
        try:
            rows = self._projection.scope_reservations(self._key)
        except Exception:  # noqa: BLE001 - an unreadable projection proves nothing
            return None
        if outstanding_reservations(rows):
            return None
        tip = self._evidence_tip()
        return flat_position_context(
            source_ref=f"scope:{self._key.account}::{self._key.instrument}@evidence:{tip}",
            as_of=as_of,
            scheme=self._scheme,
        )

    def _held(
        self,
        bound: EntryCloseBound,
        confirmed_net: Decimal,
        *,
        price: int,
        as_of: int,
    ) -> PositionContext | None:
        """The proven holding's context, or ``None`` when any required fact is missing."""
        remaining, attempt_id = bound.remaining, bound.entry_attempt_id
        if remaining is None or attempt_id is None or remaining <= 0:
            return None
        if remaining != remaining.to_integral_value():
            return None
        if confirmed_net == 0:
            return None
        # SAFETY: the close-history remainder and the sealed-send fold must agree on the magnitude — two durable readings that disagree mean one is stale, and sizing an exit off the wrong one would send a quantity the scope does not hold
        if abs(confirmed_net) != remaining:
            return None
        entry = self._entry_price(attempt_id)
        entry_as_of = self._entry_as_of(attempt_id)
        if entry is None or entry_as_of is None:
            return None
        entry_price, basis = entry
        try:
            return project_position_context(
                side=(PositionSide.LONG if confirmed_net > 0 else PositionSide.SHORT),
                held_qty=int(remaining),
                entry_price=entry_price,
                entry_price_basis=basis,
                entry_as_of=entry_as_of,
                price=price,
                as_of=as_of,
                bar_interval_ms=self._bar_interval_ms,
                source_ref=(
                    f"attempt:{attempt_id}@rcl:"
                    f"{bound.rcl_writer_epoch}:{bound.rcl_last_seq}"
                ),
                scheme=self._scheme,
            )
        except ArtifactIntegrityError:
            return None

    def _evidence_tip(self) -> int:
        """The evidence chain's committed tip seq, or ``-1`` when nothing is committed yet."""
        last_seq, _digest, _generation = self._evidence_store.last_committed()
        return -1 if last_seq is None else int(last_seq)

    def _entry_seal(self, attempt_id: str) -> tuple[int, object] | None:
        """``(seq, outbound_price)`` of ``attempt_id``'s own in-scope ``SEND_SEALED`` row."""
        matched = [
            (seq, payload["send_seal"])
            for seq, payload in _payload_rows(self._evidence_store, _SEND_SEALED_KIND)
            if payload.get("attempt_id") == attempt_id
            and isinstance(payload.get("send_seal"), dict)
        ]
        if len(matched) != 1:
            return None
        seq, seal = matched[0]
        if not isinstance(seal, dict) or not self._seal_in_scope(seal):
            return None
        return seq, seal.get("outbound_price")

    def _seal_in_scope(self, seal: dict[str, object]) -> bool:
        """Whether a seal's ``instrument_key`` is this reader's own scope."""
        key = seal.get("instrument_key")
        if not isinstance(key, dict):
            return False
        return (key.get("account"), key.get("instrument")) == (
            self._key.account,
            self._key.instrument,
        )

    def _entry_price(self, attempt_id: str) -> tuple[int, str] | None:
        """``(entry price in view scale, basis)`` — the broker average when it converts exactly."""
        seal = self._entry_seal(attempt_id)
        if seal is None:
            return None
        seal_seq, raw_price = seal
        order_price = _exact_positive_int(raw_price)
        if order_price is None:
            return None
        executed = self._execution_price(attempt_id, seal_seq=seal_seq)
        if executed is None:
            return order_price, ENTRY_PRICE_BASIS_ORDER
        return executed, ENTRY_PRICE_BASIS_EXECUTION

    def _execution_price(self, attempt_id: str, *, seal_seq: int) -> int | None:
        """``avg_execution_price`` in VIEW scale, or ``None`` when absent or not exactly scaled."""
        observed = [
            payload.get("avg_execution_price")
            for _seq, payload in _payload_rows(
                self._evidence_store, _FILL_OBSERVED_KIND
            )
            if payload.get("attempt_id") == attempt_id
        ]
        priced = [value for value in observed if _reads_positive(value)]
        if not priced:
            return None
        average = _decimal(priced[-1])
        scale = self._price_scale_at(seal_seq)
        if average is None or scale is None:
            return None
        # SAFETY: the broker average is in whole currency units while the seal's price is the view integer, so the tree's own price_scale is what puts them on one scale, and an inexact product keeps the ORDER basis rather than rounding an entry price every declared bound divides by
        return _exact_positive_int(average * Decimal(scale))

    def _price_scale_at(self, seq: int) -> int | None:
        """The ``price_scale`` last bound at or before ``seq`` (``perf.py``'s own rule)."""
        current: int | None = None
        for bound_seq, payload in _payload_rows(
            self._evidence_store, _VENUE_POLICY_BOUND_KIND
        ):
            if bound_seq > seq:
                break
            scale = payload.get("price_scale")
            if isinstance(scale, int) and not isinstance(scale, bool) and scale > 0:
                current = scale
        return current

    def _entry_as_of(self, attempt_id: str) -> int | None:
        """The entry decision bar's newest ``as_of``, joined attempt -> event -> inbox row."""
        event_id = event_id_for_attempt(self._evidence_store, attempt_id)
        if event_id is None:
            return None
        event = self._inbox.event_by_id(event_id)
        if event is None or event.kind is not EventKind.DECISION_TICK:
            return None
        payload = event.decision_tick
        if payload is None or payload.value_view is None:
            return None
        return _max_as_of(payload.value_view)
