"""The durable-evidence position projection one tick reads (plan P4 §2 D1/D3, stage S2)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    PolicyRef,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import (
    ENTRY_PRICE_BASES,
    ContextValue,
    ContextValueView,
    PositionContext,
    PositionSide,
)
from tos.engine import DecisionTickPayload, EngineEvent, EventKind, InstrumentKey
from tos.rcl import (
    AppendRefusal,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    ReservationScope,
    TransitionCause,
)
from tos.workload import RuntimeIdentity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_identity import permit_reservation_id
from tos_runtime.riskstate.close_bound import DurableEntryCloseBoundReader
from tos_runtime.riskstate.position import EvidencePositionReader
from tos_runtime.riskstate.position_context import (
    ENTRY_PRICE_BASIS_EXECUTION,
    ENTRY_PRICE_BASIS_ORDER,
    EvidencePositionContextReader,
)

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
_ACCOUNT = "88888888-01"
_INSTRUMENT = "000660"
_KEY = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
_BUY = "BUY"
_SELL = "SELL"
_PRICE_FIELD = "close"
_BAR_MS = 60_000
_ENTRY_ATTEMPT = "attempt-position-context-entry"
_ENTRY_PERMIT = "afg-permit-position-context-entry"
_PRICE_SCALE = 100
_ENTRY_PRICE = 7_010_000
_BAR_PRICE = 7_015_000
_BARS_HELD = 3
_ENTRY_AS_OF = 1_700_000_060_000
_BAR_AS_OF = _ENTRY_AS_OF + _BARS_HELD * _BAR_MS


def _capsule(seq: int) -> DecisionContextCapsule:
    issued = DecisionContextCapsule.issue(
        scheme=_SCHEME,
        issuer_principal_id="iss-position-context",
        critical_input_policy=PolicyRef(policy_id="pol-pc", canonical_digest="pd-pc"),
        critical_input_snapshot=SnapshotRef(
            snapshot_id=f"snap-pc-{seq}", canonical_digest=f"snap-pc-digest-{seq}"
        ),
        scope=CapsuleScope(
            environment="non-live-test",
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            decision_class="entry",
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="SHARES",
        ),
    )
    assert isinstance(issued, DecisionContextCapsule)
    return issued


def _view(
    *,
    as_of: int,
    close: object = _BAR_PRICE,
    field_key: str = _PRICE_FIELD,
    seq: int = 1,
) -> ContextValueView:
    return ContextValueView(
        snapshot_id=f"snap-pc-{seq}",
        snapshot_canonical_digest=f"snap-pc-digest-{seq}",
        values=(
            ContextValue(
                field_key=field_key,
                value=close,  # type: ignore[arg-type]
                as_of=as_of,
                payload_digest=f"payload-pc-{seq}",
                observation_ref=f"raw-pc-{seq}",
            ),
        ),
        canonical_digest=f"view-pc-digest-{seq}",
        canonicalization_version=_SCHEME.version,
    )


def _tick_event(*, as_of: int, seq: int = 1) -> EngineEvent:
    return EngineEvent(
        kind=EventKind.DECISION_TICK,
        decision_tick=DecisionTickPayload(
            instrument_key=_KEY,
            capsule=_capsule(seq),
            value_view=_view(as_of=as_of, seq=seq),
        ),
    )


def _commit(
    rcl_log: SqliteCommitLog,
    *,
    reservation_id: str,
    from_state: CapacityState,
    to_state: CapacityState,
    command_id: str,
    command_type: CommandType,
    cause: TransitionCause,
    finality_witness: bool | None,
) -> None:
    identity = RuntimeIdentity(cell_id="pc-test-cell", process_nonce="pc-test-nonce")
    epoch = rcl_log.current_epoch() or rcl_log.acquire_epoch(identity)
    view = rcl_log.read_linearizable(writer_epoch=epoch)
    receipt = rcl_log.apply_reservation_transition(
        CapacityReservationTransition(
            reservation_id=reservation_id,
            writer_epoch=epoch,
            from_state=from_state,
            to_state=to_state,
            scope=ReservationScope(account=_ACCOUNT, instrument=_INSTRUMENT),
        ),
        cause,
        command_type=command_type,
        command_id=command_id,
        command_digest=command_id,
        expected_seq=-1 if view.last_seq is None else view.last_seq,
        finality_witness=finality_witness,
    )
    assert not isinstance(receipt, AppendRefusal), receipt


def _record_join(
    store: SqliteEvidenceStore, *, attempt_id: str, permit_identity: str, event_id: str
) -> None:
    """The two rows ``tos_runtime.rcl.reservation_lookup`` joins attempt -> event on."""
    store.append(
        {
            "kind": "FLOW_STEP_ADMITTED",
            "step": "ATOMIC_COMMIT",
            "event_id": event_id,
            "bound_identity": permit_identity,
        },
        kind="FLOW_STEP_ADMITTED",
        record_class="FLOW_STEP_ADMITTED",
    )
    store.append(
        {
            "kind": "ATTEMPT_REQUEST_CREATED",
            "event_id": event_id,
            "attempt_id": attempt_id,
        },
        kind="ATTEMPT_REQUEST_CREATED",
        record_class="ATTEMPT_REQUEST_CREATED",
    )


def _record_seal(
    store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    side: str,
    quantity: str,
    price: object,
    instrument: str = _INSTRUMENT,
) -> None:
    store.append(
        {
            "kind": "SEND_SEALED",
            "attempt_id": attempt_id,
            "send_seal": {
                "attempt_id": attempt_id,
                "instrument_key": {"account": _ACCOUNT, "instrument": instrument},
                "outbound_side": side,
                "outbound_quantity": quantity,
                "outbound_price": price,
            },
        },
        kind="SEND_SEALED",
        record_class="SEND_SEALED",
    )


def _record_full_fill(
    store: SqliteEvidenceStore, *, attempt_id: str, filled: str
) -> None:
    store.append(
        {
            "attempt_id": attempt_id,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "egress_result_kind": "FULL_FILL",
            "filled_quantity": filled,
            "remaining_quantity": "0",
            "broker_execution_id": f"exec-{attempt_id}",
        },
        kind="EGRESS_RESULT_CONSUMED",
        record_class="EGRESS_RESULT_CONSUMED",
    )
    store.append(
        {"idempotency_key": f"synthetic-fqp-proof:{attempt_id}"},
        kind="POSTTRADE_FINALITY_PROOF",
        record_class="POSTTRADE_FINALITY_PROOF",
    )


def _record_venue_policy(store: SqliteEvidenceStore, *, price_scale: object) -> None:
    store.append(
        {"price_scale": price_scale},
        kind="VENUE_POLICY_BOUND",
        record_class="VENUE_POLICY_BOUND",
    )


def _reader(
    rcl_log: SqliteCommitLog,
    store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    *,
    price_field_key: str = _PRICE_FIELD,
    bar_interval_ms: int = _BAR_MS,
) -> EvidencePositionContextReader:
    projection = SqliteReservationProjectionReader(rcl_log)
    return EvidencePositionContextReader(
        close_bound_reader=DurableEntryCloseBoundReader(
            rcl_log=rcl_log,
            evidence_store=store,
            projection=projection,
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
        ).read,
        position_reader=EvidencePositionReader(
            store,
            account=_ACCOUNT,
            instrument=_INSTRUMENT,
            buy_side_token=_BUY,
            sell_side_token=_SELL,
        ),
        projection=projection,
        inbox=inbox,
        evidence_store=store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        price_field_key=price_field_key,
        bar_interval_ms=bar_interval_ms,
        scheme=_SCHEME,
    )


def _seed_held_entry(
    rcl_log: SqliteCommitLog,
    store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    *,
    side: str = _BUY,
    quantity: str = "1",
    price: object = _ENTRY_PRICE,
    price_scale: object = _PRICE_SCALE,
    avg_execution_price: str | None = None,
    entry_as_of: int = _ENTRY_AS_OF,
    consumed: bool = True,
    with_seal: bool = True,
    with_event: bool = True,
) -> None:
    """One proven held entry: its bar event, its join rows, its RCL state and its fill."""
    _record_venue_policy(store, price_scale=price_scale)
    event_id = inbox.enqueue(_tick_event(as_of=entry_as_of)).event_id
    if with_event:
        _record_join(
            store,
            attempt_id=_ENTRY_ATTEMPT,
            permit_identity=_ENTRY_PERMIT,
            event_id=event_id,
        )
    _commit(
        rcl_log,
        reservation_id=str(permit_reservation_id(_ACCOUNT, _INSTRUMENT, _ENTRY_PERMIT)),
        from_state=CapacityState.COMMITTED_UNBOUND,
        to_state=(
            CapacityState.POSITION_CONSUMED
            if consumed
            else CapacityState.POTENTIALLY_LIVE
        ),
        command_id="cmd-position-context-entry",
        command_type=(
            CommandType.RELEASE_RESERVATION if consumed else CommandType.BIND_ATTEMPT
        ),
        cause=(
            TransitionCause.FINAL_QUANTITY_PROOF
            if consumed
            else TransitionCause.STRONGLY_AUTHORIZED_COMMAND
        ),
        finality_witness=True if consumed else None,
    )
    if with_seal:
        _record_seal(
            store,
            attempt_id=_ENTRY_ATTEMPT,
            side=side,
            quantity=quantity,
            price=price,
        )
    _record_full_fill(store, attempt_id=_ENTRY_ATTEMPT, filled=quantity)


def _held(context: PositionContext | None) -> PositionContext:
    assert context is not None
    return context


def test_the_two_named_bases_are_exactly_the_kernel_s_own_closed_set() -> None:
    """Drift guard: the kernel exports the SET, so the runtime names its two members here."""
    assert {ENTRY_PRICE_BASIS_EXECUTION, ENTRY_PRICE_BASIS_ORDER} == set(
        ENTRY_PRICE_BASES
    )


def test_a_positively_flat_scope_reads_as_a_flat_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """No seal, no reservation, nothing in flight — FLAT, with no entry field at all."""
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.side is PositionSide.FLAT
    assert context.held_qty == 0
    assert context.as_of == _BAR_AS_OF
    assert context.as_environment_mapping() == {"side": "FLAT", "held_qty": 0}
    assert context.source_ref.startswith(f"scope:{_ACCOUNT}::{_INSTRUMENT}@evidence:")


def test_a_held_long_entry_projects_its_own_unrealized_figures(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """Hand-computed: 7_015_000 - 7_010_000 = +5_000 -> +7 bp, three bars held."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.side is PositionSide.LONG
    assert context.held_qty == 1
    assert context.entry_price == _ENTRY_PRICE
    assert context.entry_price_basis == ENTRY_PRICE_BASIS_ORDER
    assert context.unrealized == 5_000
    assert context.unrealized_bp == 7
    assert context.bars_held == _BARS_HELD
    assert context.source_ref.startswith(f"attempt:{_ENTRY_ATTEMPT}@rcl:")


def test_a_held_short_entry_mirrors_the_long_one(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """The SAME prices on the SELL side: the sign flips and nothing else does (symmetry)."""
    _seed_held_entry(rcl_log, evidence_store, inbox, side=_SELL)
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.side is PositionSide.SHORT
    assert context.held_qty == 1
    assert context.unrealized == -5_000
    assert context.unrealized_bp == -7
    assert context.bars_held == _BARS_HELD


def test_an_unresolved_send_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """A sealed send with no terminal result is in-flight quantity — the namespace is absent."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    _record_seal(
        evidence_store,
        attempt_id="attempt-position-context-unresolved",
        side=_SELL,
        quantity="1",
        price=_BAR_PRICE,
    )
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


def test_a_reservation_that_is_not_a_consumed_position_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """One outstanding non-consumed reservation is neither proven held nor proven flat."""
    _seed_held_entry(rcl_log, evidence_store, inbox, consumed=False)
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


def test_an_unreadable_projection_is_not_flat(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """A bound refusal that means "could not read" must never be reported as FLAT."""
    reader = _reader(rcl_log, evidence_store, inbox)
    rcl_log.close()
    assert reader.read(_view(as_of=_BAR_AS_OF)) is None


def test_a_missing_seal_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """A proven holding with no sealed send has no entry price to divide by."""
    _seed_held_entry(rcl_log, evidence_store, inbox, with_seal=False)
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


def test_a_seal_outside_this_scope_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """A seal whose instrument_key is another symbol's is not this scope's entry price."""
    _seed_held_entry(rcl_log, evidence_store, inbox, with_seal=False, quantity="1")
    _record_seal(
        evidence_store,
        attempt_id=_ENTRY_ATTEMPT,
        side=_BUY,
        quantity="1",
        price=_ENTRY_PRICE,
        instrument="005930",
    )
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


def test_a_missing_entry_bar_event_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """Without the attempt -> event join there is no entry bar instant, so no bars_held."""
    _seed_held_entry(rcl_log, evidence_store, inbox, with_event=False)
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


@pytest.mark.parametrize("close", ["7015000", 7_015_000.5, True])
def test_a_price_field_that_is_not_an_admitted_int_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    close: object,
) -> None:
    """The bar price is the EXACT admitted integer or nothing (``admitted_shape_price_from_view``)."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    reader = _reader(rcl_log, evidence_store, inbox)
    assert reader.read(_view(as_of=_BAR_AS_OF, close=close)) is None


def test_an_absent_price_field_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    _seed_held_entry(rcl_log, evidence_store, inbox)
    reader = _reader(rcl_log, evidence_store, inbox)
    assert reader.read(_view(as_of=_BAR_AS_OF, field_key="vwap")) is None


def test_an_absent_view_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    _seed_held_entry(rcl_log, evidence_store, inbox)
    assert _reader(rcl_log, evidence_store, inbox).read(None) is None


def test_a_non_integral_seal_price_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """The seal's price is the view integer — a fractional one is refused, never rounded."""
    _seed_held_entry(rcl_log, evidence_store, inbox, price="7010000.5")
    assert _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF)) is None


def test_the_broker_average_wins_when_it_scales_to_an_exact_integer(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """70,120 KRW x price_scale 100 = 7_012_000 -> EXECUTION basis and +4 bp."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    evidence_store.append(
        {"attempt_id": _ENTRY_ATTEMPT, "avg_execution_price": "70120"},
        kind="FILL_OBSERVED",
        record_class="FILL_OBSERVED",
    )
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.entry_price == 7_012_000
    assert context.entry_price_basis == ENTRY_PRICE_BASIS_EXECUTION
    assert context.unrealized == 3_000
    assert context.unrealized_bp == 4


@pytest.mark.parametrize(
    "avg_execution_price", ["70100.005", "0", None, "", "not-a-number"]
)
def test_an_unusable_broker_average_keeps_the_order_basis(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    avg_execution_price: object,
) -> None:
    """A non-integral, absent or non-positive average falls back — it never rounds an entry."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    evidence_store.append(
        {"attempt_id": _ENTRY_ATTEMPT, "avg_execution_price": avg_execution_price},
        kind="FILL_OBSERVED",
        record_class="FILL_OBSERVED",
    )
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.entry_price == _ENTRY_PRICE
    assert context.entry_price_basis == ENTRY_PRICE_BASIS_ORDER


def test_an_unknown_price_scale_keeps_the_order_basis(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """With no bound price_scale the broker average cannot be put on the view's scale."""
    _seed_held_entry(rcl_log, evidence_store, inbox, price_scale="not-an-int")
    evidence_store.append(
        {"attempt_id": _ENTRY_ATTEMPT, "avg_execution_price": "70120"},
        kind="FILL_OBSERVED",
        record_class="FILL_OBSERVED",
    )
    context = _held(
        _reader(rcl_log, evidence_store, inbox).read(_view(as_of=_BAR_AS_OF))
    )
    assert context.entry_price == _ENTRY_PRICE
    assert context.entry_price_basis == ENTRY_PRICE_BASIS_ORDER


def test_two_disagreeing_evidence_readings_leave_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """The sealed-send fold says 2, the close-history remainder says 1 — refuse, never pick."""
    _seed_held_entry(rcl_log, evidence_store, inbox, quantity="1")
    _record_seal(
        evidence_store,
        attempt_id="attempt-position-context-second",
        side=_BUY,
        quantity="1",
        price=_ENTRY_PRICE,
    )
    _record_full_fill(
        evidence_store, attempt_id="attempt-position-context-second", filled="1"
    )
    reader = _reader(rcl_log, evidence_store, inbox)
    bound = DurableEntryCloseBoundReader(
        rcl_log=rcl_log,
        evidence_store=evidence_store,
        projection=SqliteReservationProjectionReader(rcl_log),
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
    ).read()
    assert bound.proven and bound.remaining == Decimal("1")
    assert reader.read(_view(as_of=_BAR_AS_OF)) is None


def test_a_bar_older_than_its_own_entry_bar_leaves_no_context(
    rcl_log: SqliteCommitLog,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
) -> None:
    """The kernel refuses ``as_of < entry_as_of``; the reader turns that refusal into absence."""
    _seed_held_entry(rcl_log, evidence_store, inbox)
    reader = _reader(rcl_log, evidence_store, inbox)
    assert reader.read(_view(as_of=_ENTRY_AS_OF - _BAR_MS, seq=2)) is None
