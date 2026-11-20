"""Off-hours fault injection for the stock MOCK tenant: does it get back to trading? (11-20).

Every scenario here is one shape of the 2026-11-20 live incident, replayed against the
:mod:`._kis_faults` broker double instead of waiting for the next market day. Each drives a
whole session — OPEN -> fill -> CLOSE -> fill -> release -> a SECOND OPEN admitted — with one
scripted broker fault inside it, and asserts the tenant reaches that second OPEN.

The incident (2026-11-20; tenants 005930 / 000660 / 005380 share one KIS app key): all three
asked for the mock token inside the same minute (KIS issues one per minute per app key), or a
balance GET (VTTC8434R) answered ``rt_cd != 0`` under the same key's rate limit. Either way
item 12's broker facts came back ``None``
(``tos_runtime.transport.kis_mock.broker_facts``), step 15 refused the send, and the
reservation the refused OPEN had taken was stranded — so every later OPEN that day was denied
``open_over_outstanding_reservation``. PR #1122 releases a send refused before transport,
which is what turns each refusal below into a recovery instead of a dead session.

Two of them are the order POST itself going blind — a timeout, and an HTTP 500. Both leave the
same stuck state, which :func:`_assert_quarantined_unknown` pins, and both leave it only until
the broker's own order history is read for the send's trading date
(:mod:`tos_runtime.posttrade.uncertain_send`): one unclaimed matching row binds the attempt, an
empty history twice over a settle window releases it, and anything less certain holds.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.engine.vocabulary import CommitmentStep, EgressKnowledge
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.uncertain_send import (
    AMBIGUOUS,
    BOUND,
    NEVER_ACCEPTED,
    UNCERTAIN_SEND_RECONCILED_KIND,
)
from tos_runtime.posttrade.unsent_release import (
    NEVER_ACCEPTED_CAUSE,
    REFUSED_BEFORE_TRANSPORT_CAUSE,
)
from tos_runtime.riskstate.service import RiskStateService
from tos_runtime.transport.kis_mock.broker_facts import BROKER_FACTS_CONFIG_NAME

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from . import test_kis_mock_close_risk_e2e as riskfx
from ._kis_faults import ORDER_PATH, Call, FaultKind, ScriptedKisBroker
from .test_kis_mock_fill_finality_e2e import _close, _row, _rows

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_TRANSPORT_CONFIG_NAME = "kis_mock_transport.yaml"
_DISCARD_KIND = "RESERVATION_DISCARDED_UNSENT"

#: Every order this harness sends gets its own broker order number. Reusing one inside a
#: trading date makes the broker's own daily-ccld history ambiguous, which the fill observer
#: fail-closes on (``ambiguous_rows``) — a harness bug that reads like a product bug.
_ODNO_PREFIX = "000000510"

#: Orders the tenant under test never placed, on its own symbol and trading date: an earlier,
#: archived leaf's round trips and an operator's manual flatten. A different prefix from
#: :data:`_ODNO_PREFIX` so no foreign order can collide with one the tenant sends — scenario
#: (f) asserts the release treats them as foreign, and a collision would make it vacuous.
_FOREIGN_ODNO_PREFIX = "000000190"

#: 주문시각 (``ord_tmd``, HHMMSS) the broker stamps on each side in scenario (f). The foreign
#: orders are the morning's; the tenant's own start after the 12:48 reboot. Only a strictly
#: earlier broker stamp makes an orphan provably not ours, so the gap here is the thing the
#: scenario actually tests — not the ODNO prefixes.
_FOREIGN_ORD_TMD_BASE = 93000
_OWN_ORD_TMD_BASE = 124800

#: The compressed waiting bounds this harness writes. An off-hours run must not spend the
#: shipped ones, and this suite's virtual clock (``riskfx._PacedClock``) only moves when the
#: KIS app-key pacer grants a slot — so every bound below is spent in pacer grants, not in
#: seconds. Compressing the pacing interval is what keeps a whole session inside
#: ``risk.yaml::max_elapsed_monotonic`` (60 s in this fixture, 30 s on the live tenant): at
#: the shipped 1100 ms a session's broker calls spend 60+ virtual seconds between one event's
#: proposal and its send, and step 7 then answers UNKNOWN on amplification. No fault here
#: depends on the interval's size — only on the order of the calls.
_MIN_SEND_INTERVAL_MS = 20
#: Real milliseconds, not virtual: this is the lock-wait budget two threads (the session loop
#: and the observer's FETCH worker) share. Keep it generous or a slow host reads as throttled.
_APP_KEY_WAIT_BUDGET_MS = 2_000
#: The shipped tree holds a FAILED broker-facts observation for ``max_age_ms`` 30 s and
#: refuses a token reissue for 60 s; both are why a live tenant recovers on a later bar rather
#: than on the next tick. The floor is the paced read window — the observation is stamped at
#: the first of its two GETs — so this stays well above 2 x the interval above.
_FACTS_MAX_AGE_MS = 1_000
_TOKEN_REISSUE_MIN_INTERVAL_S = 1
#: One "next bar" for this harness, on the virtual clock: past both bounds above. Moving the
#: monotonic clock FORWARD cannot trip the time service's process-suspension bound, which only
#: fires when the wall clock outruns the monotonic one.
_NEXT_BAR_ADVANCE_MS = 1_200
#: The per-request timeouts this harness writes, and the delay a ``TIMEOUT`` fault answers
#: with. A timed-out call therefore costs ~0.4 s of real time, not the shipped 5 s.
_REQUEST_TIMEOUT_S = 0.4
_TIMEOUT_DELAY_S = 1.2
#: The settle window the uncertain-send reconciliation spends before an EMPTY broker order
#: history proves a non-send. Compressed from the shipped 30 s for the same reason as every
#: bound above; what it bounds — two empty reads this far apart, the first this long after the
#: send was first seen — is pinned exactly in ``tests/posttrade/test_uncertain_send.py``.
_UNCERTAIN_SETTLE_MS = 100


def _compress_waiting_bounds(config_dir: Path) -> None:
    """Rewrite the shipped waiting bounds (see the constants above) for an off-hours run."""
    transport_path = config_dir / _TRANSPORT_CONFIG_NAME
    transport = yaml.safe_load(transport_path.read_text(encoding="utf-8"))
    transport["token_reissue_min_interval_s"] = _TOKEN_REISSUE_MIN_INTERVAL_S
    transport["request_timeout_s"] = _REQUEST_TIMEOUT_S
    transport["min_send_interval_ms"] = _MIN_SEND_INTERVAL_MS
    transport["app_key_request_wait_budget_ms"] = _APP_KEY_WAIT_BUDGET_MS
    transport_path.write_text(
        yaml.safe_dump(transport, sort_keys=False), encoding="utf-8"
    )

    facts_path = config_dir / BROKER_FACTS_CONFIG_NAME
    facts = yaml.safe_load(facts_path.read_text(encoding="utf-8"))
    facts["max_age_ms"] = _FACTS_MAX_AGE_MS
    facts_path.write_text(yaml.safe_dump(facts, sort_keys=False), encoding="utf-8")

    observer_path = config_dir / riskfx.FILL_OBSERVER_CONFIG_NAME
    observer = yaml.safe_load(observer_path.read_text(encoding="utf-8"))
    observer["witness_request_timeout_s"] = _REQUEST_TIMEOUT_S
    observer["loop_witness_request_timeout_s"] = _REQUEST_TIMEOUT_S
    observer["uncertain_send_settle_ms"] = _UNCERTAIN_SETTLE_MS
    observer_path.write_text(
        yaml.safe_dump(observer, sort_keys=False), encoding="utf-8"
    )


@dataclass
class _Tenant:
    """One booted stock MOCK tenant, the broker double it talks to, and the session it drives."""

    runtime: ComposedRuntime
    broker: ScriptedKisBroker
    server: FakeKisServer
    clock: riskfx._PacedClock
    config_dir: Path
    custody_root: Path
    date: str
    published: list[Any]
    rows: list[dict[str, str]] = field(default_factory=list)
    odno_serial: int = 0
    #: Set by a scenario that needs the broker to stamp 주문시각 on this tenant's own orders.
    ord_tmd_base: int | None = None

    def next_odno(self) -> str:
        """The broker order number the next order sent on this tenant answers with."""
        self.odno_serial += 1
        return f"{_ODNO_PREFIX}{self.odno_serial}"

    @property
    def own_ord_tmd(self) -> str | None:
        """The broker's 주문시각 for this tenant's own orders, once a scenario has set a base.

        ``None`` — the default — keeps every other scenario's rows exactly as they were, with
        no placement time, so nothing about their orphan handling changes.
        """
        if self.ord_tmd_base is None:
            return None
        return f"{self.ord_tmd_base + self.odno_serial:06d}"

    @property
    def observer(self) -> Any:
        observer = self.runtime.fill_observer
        assert observer is not None
        return observer

    # ------------------------------------------------------------------ broker state

    def broker_holds(self, quantity: Decimal) -> None:
        """Re-script what the broker holds and what its daily-ccld walk reports."""
        holdings = ((fx.INSTRUMENT, quantity),) if quantity > 0 else ()
        self.broker.witness(rows=self.rows, holdings=holdings)

    def broker_filled(self, odno: str, quantity: Decimal) -> None:
        """Add one fully-filled order to the broker's own history for this trading date."""
        self.rows.append(
            _row(
                odno=odno,
                date=self.date,
                ord_qty=quantity,
                filled=quantity,
                remaining=Decimal(0),
                ord_tmd=self.own_ord_tmd,
            )
        )

    def next_bar(self) -> None:
        """Move past the compressed waiting bounds — a failed fact is held until they pass."""
        self.clock.advance(_NEXT_BAR_ADVANCE_MS)

    # ------------------------------------------------------------------ driving

    def order_posts(self) -> int:
        return len(self.server.requests_for(ORDER_PATH))

    def quantity(self) -> Decimal:
        """The quantity the construction stage derived for the pass just driven."""
        construction = self.runtime.construction_stage.construction
        assert construction is not None
        quantity = construction.derivation.quantity
        assert isinstance(quantity, Decimal), quantity
        return quantity

    def propose(self, event: Any) -> Any:
        """Discovery pass: propose, then write the operator approval that pass's intent needs."""
        return riskfx._discover_and_approve(self.runtime, self.custody_root, event)

    def transmit(self, event: Any) -> Any:
        """Second pass over the same event: the approved intent reaches the send boundary."""
        return self.runtime.run_once((event,))[0]

    def settle(self) -> Any:
        """Drive the observer until its worker publishes one more held-position pair."""
        after = len(self.published)
        deadline = time.monotonic() + 15
        while len(self.published) <= after:
            self.observer.poll_if_due()
            if time.monotonic() >= deadline:
                raise AssertionError(
                    "the held-position FETCH never published\n" + _diagnose(self)
                )
            time.sleep(0.001)
        return self.published[-1][1]

    def release_snapshot(self) -> dict[str, Any]:
        """Drive the observer until the release reconciliation records its witness snapshot."""
        return riskfx._wait_for_release_snapshot(
            self.observer,
            self.runtime,
            len(_rows(self.runtime, riskfx.FILL_OBSERVER_RELEASE_SNAPSHOT_KIND)),
        )

    # ------------------------------------------------------------------ whole round trips

    def open_fills(self, *, seq: int) -> Decimal:
        """One OPEN proposed, approved, sent, ACKed, and filled at the broker."""
        event = fx.crossing_event(seq=seq)
        odno = self.next_odno()
        self.broker_holds(Decimal(0))
        self.propose(event)
        quantity = self.quantity()
        self.broker.order_ack(odno)
        self.broker_filled(odno, quantity)
        self.broker_holds(quantity)
        posts_before = self.order_posts()
        result = self.transmit(event)
        assert result.flow is not None and result.flow.handed_off is True, _diagnose(
            self
        )
        assert self.order_posts() == posts_before + 1, _diagnose(self)
        self.settle()
        assert any(
            row["egress_result_kind"] == "FULL_FILL"
            and Decimal(row["filled_quantity"]) == quantity
            for row in _rows(self.runtime, "EGRESS_RESULT_CONSUMED")
        ), _diagnose(self)
        return quantity

    def close_fills(self, *, seq: int, held: Decimal) -> Decimal:
        """One CLOSE proposed against a fresh holdings proof, sent, ACKed, and filled."""
        event = fx.crossing_event(seq=seq, close=fx.UPPER_BAND + 1_000)
        odno = self.next_odno()
        self.propose(event)
        self.broker_holds(held)
        self.settle()
        quantity = self.quantity()
        self.broker.order_ack(odno)
        posts_before = self.order_posts()
        result = self.transmit(event)
        assert result.flow is not None and result.flow.handed_off is True, _diagnose(
            self
        )
        assert self.order_posts() == posts_before + 1, _diagnose(self)
        self.broker_filled(odno, quantity)
        self.broker_holds(held - quantity)
        snapshot = self.release_snapshot()
        assert snapshot["read_ok"] is True, snapshot
        return quantity


def _boot_tenant(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    server: FakeKisServer,
    monkeypatch: pytest.MonkeyPatch,
) -> _Tenant:
    """A sealed stock MOCK deployment against the fault-injectable double, booted and trusted."""
    clock = riskfx._PacedClock()
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    riskfx._sealed_mock_deployment(config_dir, custody_root, server, monkeypatch)
    riskfx._write_close_strategy(config_dir, monkeypatch)
    riskfx._speed_observer_polls(config_dir)
    _compress_waiting_bounds(config_dir)
    broker = ScriptedKisBroker(server, config_dir, timeout_delay_s=_TIMEOUT_DELAY_S)
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        riskfx._ENVIRONMENT_LABEL,
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        transport_kind=TransportKind.KIS_MOCK,
        monotonic_source=clock,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    assert type(runtime.risk_state) is RiskStateService
    assert runtime.unsent_release is not None, "#1122's release pass is not wired"
    assert runtime.session_facts is not None
    date = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
    assert date is not None
    broker.bind_trading_date(date)
    published, _bridge = riskfx._capture_published(runtime.fill_observer)
    return _Tenant(
        runtime=runtime,
        broker=broker,
        server=server,
        clock=clock,
        config_dir=config_dir,
        custody_root=custody_root,
        date=date,
        published=published,
    )


def _reservation_states(tenant: _Tenant) -> dict[str, CapacityState]:
    states: dict[str, CapacityState] = {}
    for (
        reservation_id,
        state,
        _seq,
        _scope,
    ) in tenant.runtime.rcl_log.reservation_rows():
        assert isinstance(state, CapacityState)
        states[reservation_id] = state
    return states


def _diagnose(tenant: _Tenant) -> str:
    """What the last pass did — the one message a failing scenario needs to be read."""
    runtime = tenant.runtime
    keys = (
        "attempt_id",
        "kind",
        "reason",
        "status",
        "step",
        "item",
        "egress_result_kind",
        "capacity_state",
        "knowledge",
        "broker_execution_id",
        "detail",
        "cause",
    )
    parts = [
        f"reservations: {_reservation_states(tenant)}",
        f"ledger: {runtime.core.ledger.outstanding(fx.instrument_key())}",
    ]
    for kind in (
        "SEND_REFUSED",
        "TRANSPORT_SEND",
        "UNCERTAIN_SEND",
        "EGRESS_RESULT_CONSUMED",
        "FILL_OBSERVED",
        "FILL_OBSERVER_READ_FAILED",
        _DISCARD_KIND,
    ):
        rows = _rows(runtime, kind)
        brief = [{k: v for k, v in row.items() if k in keys} for row in rows[-2:]]
        parts.append(f"{kind}[{len(rows)}]: {brief}")
    return "\n".join(parts)


def _assert_refused_before_transport(
    tenant: _Tenant, result: Any, *, posts_before: int
) -> None:
    """The 11-20 refusal shape: handed off, refused at step 15, nothing sent, capacity back."""
    assert result.flow is not None and result.flow.handed_off is True, _diagnose(tenant)
    refusals = _rows(tenant.runtime, "SEND_REFUSED")
    assert refusals, "the send boundary did not refuse\n" + _diagnose(tenant)
    assert refusals[-1]["step"] == CommitmentStep.SEND_BOUNDARY_VERIFICATION.value
    assert refusals[-1]["item"] == (
        "VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION"
    ), refusals[-1]
    assert tenant.order_posts() == posts_before, "a refused send reached the broker"
    discards = _rows(tenant.runtime, _DISCARD_KIND)
    assert discards, "#1122: the refused send's reservation was never given back"
    assert discards[-1]["reason"] == REFUSED_BEFORE_TRANSPORT_CAUSE, discards[-1]
    assert tenant.runtime.core.ledger.outstanding(fx.instrument_key()) is None


def _assert_quarantined_unknown(tenant: _Tenant, *, transport_kind: str) -> None:
    """The stuck state an order POST with no usable answer leaves — scenarios (d) and (e).

    No release path exists for it: the result carries no ``broker_execution_id``, so the fill
    observer never tracks the attempt and never reads the broker's own order history for it.
    """
    runtime = tenant.runtime
    (send,) = _rows(runtime, "TRANSPORT_SEND")
    assert send["kind"] == transport_kind, send
    (uncertain,) = _rows(runtime, "UNCERTAIN_SEND")
    assert "no_capacity_release=True" in uncertain["detail"]
    (consumed,) = _rows(runtime, "EGRESS_RESULT_CONSUMED")
    assert consumed["broker_execution_id"] is None, consumed
    held = runtime.core.ledger.outstanding(fx.instrument_key())
    assert held is not None, _diagnose(tenant)
    assert held.capacity_state is CapacityState.QUARANTINED_UNKNOWN
    assert held.knowledge is EgressKnowledge.UNKNOWN
    assert set(_reservation_states(tenant).values()) == {
        CapacityState.COMMITTED_UNBOUND
    }, _diagnose(tenant)
    assert _rows(runtime, "FILL_OBSERVED") == []
    assert _rows(runtime, "FILL_OBSERVER_ACK_UNTRACKABLE") == []
    assert _rows(runtime, _DISCARD_KIND) == []


def _assert_recovers_to_trading(tenant: _Tenant, *, first_seq: int) -> None:
    """The completion condition: OPEN -> fill -> CLOSE -> fill -> release -> a second OPEN."""
    opened = tenant.open_fills(seq=first_seq)
    assert CapacityState.POSITION_CONSUMED in _reservation_states(tenant).values()

    closed = tenant.close_fills(seq=first_seq + 1, held=opened)
    assert closed == opened, (closed, opened)
    assert set(_reservation_states(tenant).values()) == {
        CapacityState.RELEASED
    }, _diagnose(tenant)

    tenant.next_bar()
    reopened = tenant.open_fills(seq=first_seq + 2)
    assert reopened == opened
    assert CapacityState.POSITION_CONSUMED in _reservation_states(tenant).values()


# --------------------------------------------------------------------------- scenarios


def test_a_token_error_on_the_first_proposal_then_ok_on_the_next_bar(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """2026-11-20: three tenants asked one app key for a token inside the same minute, KIS
    answered EGW00133 to the losers, item 12's facts came back None, and step 15 refused the
    OPEN. Reproduced as one token refusal on the session's first proposal."""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        tenant.broker.script(Call.TOKEN, FaultKind.TOKEN_ERROR)
        event = fx.crossing_event(seq=1)
        tenant.broker_holds(Decimal(0))
        tenant.propose(event)
        posts_before = tenant.order_posts()
        refused = tenant.transmit(event)
        _assert_refused_before_transport(tenant, refused, posts_before=posts_before)
        assert tenant.broker.pending(Call.TOKEN) == ()

        tenant.next_bar()
        _assert_recovers_to_trading(tenant, first_seq=2)
    finally:
        _close(tenant.runtime)


def test_b_a_balance_rt_cd_not_ok_mid_session_after_two_round_trips(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """2026-11-20, tenant 000660: the item-12 balance GET (VTTC8434R) answered ``rt_cd != 0``
    — the shared app key's rate limit — mid-session, so ``account_facts_current`` went false
    and that tenant's next send was refused. Reproduced after two completed round trips.
    """
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        for round_trip in range(2):
            opened = tenant.open_fills(seq=1 + round_trip * 2)
            assert tenant.close_fills(seq=2 + round_trip * 2, held=opened) == opened
            tenant.next_bar()

        tenant.broker.script(Call.FACTS_BALANCE, FaultKind.RT_CD_NOT_OK)
        event = fx.crossing_event(seq=5)
        tenant.broker_holds(Decimal(0))
        tenant.propose(event)
        posts_before = tenant.order_posts()
        refused = tenant.transmit(event)
        _assert_refused_before_transport(tenant, refused, posts_before=posts_before)
        assert tenant.broker.pending(Call.FACTS_BALANCE) == ()

        tenant.next_bar()
        _assert_recovers_to_trading(tenant, first_seq=6)
    finally:
        _close(tenant.runtime)


def test_c_http_500_on_the_balance_get_for_a_close_then_the_close_is_retried(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """2026-11-20: a 모의 REST 500 on the item-12 balance read is the other measured way the
    facts go unreadable when the shared key is squeezed. A CLOSE refused that way must give
    its capacity back and be retried on the next bar, or the position stays open to the bell.
    """
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        opened = tenant.open_fills(seq=1)

        tenant.next_bar()
        tenant.broker.script(Call.FACTS_BALANCE, FaultKind.HTTP_500)
        close_event = fx.crossing_event(seq=2, close=fx.UPPER_BAND + 1_000)
        tenant.propose(close_event)
        tenant.broker_holds(opened)
        tenant.settle()
        posts_before = tenant.order_posts()
        refused = tenant.transmit(close_event)
        _assert_refused_before_transport(tenant, refused, posts_before=posts_before)
        assert tenant.broker.pending(Call.FACTS_BALANCE) == ()
        assert CapacityState.POSITION_CONSUMED in _reservation_states(tenant).values()

        tenant.next_bar()
        assert tenant.close_fills(seq=3, held=opened) == opened
        assert set(_reservation_states(tenant).values()) == {CapacityState.RELEASED}

        tenant.next_bar()
        assert tenant.open_fills(seq=4) == opened
    finally:
        _close(tenant.runtime)


def _seed_prior_same_day_orders(tenant: _Tenant, *, count: int) -> tuple[str, ...]:
    """Put ``count`` orders this tenant never placed into the broker's own daily-ccld history.

    They are on its account, its symbol and its trading date, they are fully filled, and they
    net flat — the 2026-11-20 shape, where an archived leaf's morning round trips plus an
    operator's manual market SELL were still in 주식일별주문체결조회 when a fresh leaf booted
    at 12:48 against a flat account.
    """
    tenant.ord_tmd_base = _OWN_ORD_TMD_BASE
    odnos = tuple(f"{_FOREIGN_ODNO_PREFIX}{serial}" for serial in range(1, count + 1))
    for serial, odno in enumerate(odnos, start=1):
        tenant.rows.append(
            _row(
                odno=odno,
                date=tenant.date,
                ord_qty=Decimal(1),
                filled=Decimal(1),
                remaining=Decimal(0),
                ord_tmd=f"{_FOREIGN_ORD_TMD_BASE + serial:06d}",
            )
        )
    tenant.broker_holds(Decimal(0))
    return odnos


def test_f_a_fresh_leaf_releases_over_orders_it_never_placed(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """2026-11-20, tenants 000660 / 005930: leaves archived mid-day and rebooted at 12:48 onto
    a flat account could not release the OPEN they then filled. 주식일별주문체결조회 is keyed by
    (account, symbol, date), not by leaf, so the morning's orders and a manual flatten came
    back as witness orders the fresh leaf owned nothing of; each was an ORPHAN_BROKER_ORDER
    whose veto made gate 3 answer NOT_CORROBORATED (~30 times on 000660, ~32 on 005930). The
    capacity never came back, the engine never projected the fill, and every CLOSE was then
    refused at CANDIDATE_COMMAND_CONSTRUCTION with "no held position was observed". 005380,
    the one symbol with no earlier order that day, released on the same code at the same boot.
    """
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        foreign = _seed_prior_same_day_orders(tenant, count=6)

        opened = tenant.open_fills(seq=1)
        assert CapacityState.POSITION_CONSUMED in _reservation_states(tenant).values()

        closed = tenant.close_fills(seq=2, held=opened)
        assert closed == opened, (closed, opened)
        assert set(_reservation_states(tenant).values()) == {
            CapacityState.RELEASED
        }, _diagnose(tenant)

        tenant.next_bar()
        assert tenant.open_fills(seq=3) == opened

        held = _rows(tenant.runtime, "CAPACITY_RELEASE_HELD")
        assert [row for row in held if row["reason"] == "NOT_CORROBORATED"] == [], held
        unattributed = _rows(tenant.runtime, "FILL_OBSERVER_UNATTRIBUTED_ORDER")
        assert {row["broker_execution_id"] for row in unattributed} == set(
            foreign
        ), "a foreign order must still be recorded as unattributed, not silently dropped"
    finally:
        _close(tenant.runtime)


def _open_that_times_out(tenant: _Tenant, *, seq: int) -> tuple[Decimal, str]:
    """One OPEN whose order POST reaches the broker and never answers (the POST IS recorded)."""
    event = fx.crossing_event(seq=seq)
    tenant.broker_holds(Decimal(0))
    tenant.propose(event)
    quantity = tenant.quantity()
    odno = tenant.next_odno()
    tenant.broker.order_ack(odno)
    tenant.broker.script(Call.ORDER, FaultKind.TIMEOUT)
    posts_before = tenant.order_posts()
    result = tenant.transmit(event)
    assert result.flow is not None and result.flow.handed_off is True
    assert tenant.order_posts() == posts_before + 1, "the POST never reached the broker"
    return quantity, odno


def _open_that_answers_500(tenant: _Tenant, *, seq: int) -> None:
    """One OPEN whose order POST answers HTTP 500 — nothing was accepted at the broker."""
    event = fx.crossing_event(seq=seq)
    tenant.broker_holds(Decimal(0))
    tenant.propose(event)
    tenant.broker.order_ack(tenant.next_odno())
    tenant.broker.script(Call.ORDER, FaultKind.HTTP_500)
    posts_before = tenant.order_posts()
    result = tenant.transmit(event)
    assert result.flow is not None and result.flow.handed_off is True
    assert tenant.order_posts() == posts_before + 1


def _poll_the_observer(tenant: _Tenant, *, passes: int = 40) -> None:
    """Give the fill observer every chance to resolve the attempt from the broker's history."""
    for _ in range(passes):
        tenant.observer.poll_if_due()
        time.sleep(0.001)


def _poll_until(tenant: _Tenant, done: Any, what: str, *, seconds: float = 20) -> None:
    """Drive the observer until ``done()`` holds — FETCH/APPLY take several passes each."""
    deadline = time.monotonic() + seconds
    while not done():
        tenant.observer.poll_if_due()
        if time.monotonic() >= deadline:
            raise AssertionError(f"{what} never happened\n" + _diagnose(tenant))
        time.sleep(0.002)


def _reconciled(tenant: _Tenant, outcome: str) -> None:
    """Drive the uncertain-send reconciliation until it records ``outcome``."""
    _poll_until(
        tenant,
        lambda: any(
            row["outcome"] == outcome
            for row in _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND)
        ),
        f"the uncertain send was never reconciled as {outcome}",
    )


def test_d_an_order_post_that_timed_out_is_never_duplicated(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """The worst 11-20-shaped fault: the order POST times out and the broker DID fill it.
    What must hold — and does — is that the tenant sends nothing more while the attempt is
    unknown, and no later OPEN is admitted over it (RFC-005 §11: a timeout is neither a
    rejection nor safe to retry). This is the state BEFORE the broker is asked; what asking it
    then does is ``test_d_recovery_...``."""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        quantity, odno = _open_that_times_out(tenant, seq=1)
        posts = tenant.order_posts()

        # The broker filled the order the tenant never heard about.
        tenant.broker_filled(odno, quantity)
        tenant.broker_holds(quantity)

        _assert_quarantined_unknown(tenant, transport_kind="TIMEOUT")
        assert _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND) == []
        assert tenant.order_posts() == posts, "a duplicate order was sent"

        next_open = fx.crossing_event(seq=2)
        tenant.propose(next_open)
        denied = tenant.transmit(next_open)
        assert denied.flow is not None and denied.flow.handed_off is not True
        assert denied.flow.halt_step is CommitmentStep.LEDGER_VERIFICATION
        assert "QUARANTINED_UNKNOWN" in (denied.detail or ""), denied.detail
        assert tenant.order_posts() == posts, "a second order was sent while unknown"
    finally:
        _close(tenant.runtime)


def test_d_recovery_an_order_post_that_timed_out_was_filled_at_the_broker(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """Same fault as the test above, driven to the completion condition: the tenant reconciles
    the timed-out attempt against the broker's order history (which shows it FILLED), adopts
    the position, closes it, and trades again — without ever sending a second order."""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        quantity, odno = _open_that_times_out(tenant, seq=1)
        posts = tenant.order_posts()
        tenant.broker_filled(odno, quantity)
        tenant.broker_holds(quantity)
        tenant.next_bar()

        _reconciled(tenant, BOUND)
        (verdict,) = _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND)
        assert verdict["broker_execution_id"] == odno, verdict
        _poll_until(
            tenant,
            lambda: CapacityState.POSITION_CONSUMED
            in _reservation_states(tenant).values(),
            "the adopted fill never reached POSITION_CONSUMED",
        )
        assert any(
            row["egress_result_kind"] == "FULL_FILL"
            and row["broker_execution_id"] == odno
            for row in _rows(tenant.runtime, "EGRESS_RESULT_CONSUMED")
        ), _diagnose(tenant)
        assert tenant.order_posts() == posts, "reconciliation sent an order"
        assert (
            _rows(tenant.runtime, _DISCARD_KIND) == []
        ), "a filled send must never be released as never-accepted"

        # The adopted position closes, and the scope trades again on the next bar.
        assert tenant.close_fills(seq=2, held=quantity) == quantity
        assert set(_reservation_states(tenant).values()) == {
            CapacityState.RELEASED
        }, _diagnose(tenant)
        tenant.next_bar()
        assert tenant.open_fills(seq=3) == quantity
    finally:
        _close(tenant.runtime)


def test_d_ambiguous_two_broker_orders_this_send_could_own_stay_held(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """The fail-closed half of the same reconciliation: when TWO orders on the send's own
    trading date carry this instrument and this sealed quantity, nothing identifies which one
    the timed-out POST created. The tenant binds neither and releases nothing — it stays stuck,
    which is an operator matter, not a guess the runtime may make."""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        quantity, odno = _open_that_times_out(tenant, seq=1)
        posts = tenant.order_posts()
        tenant.broker_filled(odno, quantity)
        tenant.broker_filled(tenant.next_odno(), quantity)
        tenant.broker_holds(quantity * 2)
        tenant.next_bar()

        _reconciled(tenant, AMBIGUOUS)
        _poll_the_observer(tenant)
        assert [
            row["outcome"]
            for row in _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND)
        ] == [
            AMBIGUOUS
        ], "an ambiguous verdict must never settle into a bind or a release"
        _assert_quarantined_unknown(tenant, transport_kind="TIMEOUT")
        assert tenant.order_posts() == posts
    finally:
        _close(tenant.runtime)


def test_e_an_order_post_that_answered_http_500_is_never_duplicated(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """A 모의 REST 500 on the order POST itself. A 500 does not prove the order was refused,
    so the tenant treats it as UNKNOWN and sends nothing more — the safe half, and it holds.

    Here the order-history read fails too (the squeezed app key answers 500 to that GET as
    well), which is the third branch of the reconciliation: a read it could not complete proves
    nothing either way, so the hold stands and the next poll asks again.
    """
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        _open_that_answers_500(tenant, seq=1)
        posts = tenant.order_posts()

        # The broker holds nothing — and cannot be asked whether it took the order.
        tenant.broker_holds(Decimal(0))
        tenant.broker.script(Call.DAILY_CCLD, *([FaultKind.HTTP_500] * 60))
        tenant.next_bar()
        _poll_the_observer(tenant, passes=120)

        assert tenant.broker.calls(Call.DAILY_CCLD) > 0, "the broker was never asked"
        assert (
            _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND) == []
        ), "a read that failed must settle nothing"
        _assert_quarantined_unknown(tenant, transport_kind="UNKNOWN")
        assert tenant.order_posts() == posts
    finally:
        _close(tenant.runtime)


def test_e_recovery_an_order_post_that_answered_http_500_was_never_filled(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """Same fault as the test above, driven to the completion condition: an order the broker
    never accepted is provable from its own order history — empty twice, a settle window apart
    — and the reservation goes back through the never-sent release pass under its own cause.
    """
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        _open_that_answers_500(tenant, seq=1)
        tenant.broker_holds(Decimal(0))
        tenant.next_bar()

        _reconciled(tenant, NEVER_ACCEPTED)
        assert (
            tenant.runtime.core.ledger.outstanding(fx.instrument_key()) is not None
        ), "the release is the engine's own after-turn pass, not the observer's"

        _assert_recovers_to_trading(tenant, first_seq=2)
        discards = _rows(tenant.runtime, _DISCARD_KIND)
        assert [row["reason"] for row in discards] == [NEVER_ACCEPTED_CAUSE], discards
    finally:
        _close(tenant.runtime)
