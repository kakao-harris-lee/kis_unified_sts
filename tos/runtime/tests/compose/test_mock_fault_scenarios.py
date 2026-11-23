"""Off-hours fault injection for the stock MOCK tenant: does it get back to trading? (11-20)."""

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
    LATE_CANDIDATE_HALT_REASON,
    NEVER_ACCEPTED,
    UNCERTAIN_SEND_LATE_CANDIDATE_KIND,
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

_ODNO_PREFIX = "000000510"

_FOREIGN_ODNO_PREFIX = "000000190"

_FOREIGN_ORD_TMD_BASE = 93000
_OWN_ORD_TMD_BASE = 124800

_MIN_SEND_INTERVAL_MS = 20
_APP_KEY_WAIT_BUDGET_MS = 2_000
_FACTS_MAX_AGE_MS = 1_000
_TOKEN_REISSUE_MIN_INTERVAL_S = 1
_NEXT_BAR_ADVANCE_MS = 1_200
_REQUEST_TIMEOUT_S = 0.4
_TIMEOUT_DELAY_S = 1.2
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
    ord_tmd_base: int | None = _OWN_ORD_TMD_BASE

    def next_odno(self) -> str:
        """The broker order number the next order sent on this tenant answers with."""
        self.odno_serial += 1
        return f"{_ODNO_PREFIX}{self.odno_serial}"

    @property
    def own_ord_tmd(self) -> str | None:
        """The broker's 주문시각 for this tenant's own orders, from :attr:`ord_tmd_base`."""
        if self.ord_tmd_base is None:
            return None
        return f"{self.ord_tmd_base + self.odno_serial:06d}"

    @property
    def observer(self) -> Any:
        observer = self.runtime.fill_observer
        assert observer is not None
        return observer

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
    """The stuck state an order POST with no usable answer leaves — scenarios (d) and (e)."""
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


def test_a_token_error_on_the_first_proposal_then_ok_on_the_next_bar(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """2026-11-20: three tenants asked one app key for a token inside the same minute, KIS"""
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
    """2026-11-20, tenant 000660: the item-12 balance GET (VTTC8434R) answered ``rt_cd != 0``"""
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
    """2026-11-20: a 모의 REST 500 on the item-12 balance read is the other measured way the"""
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


def _seed_prior_same_day_orders(
    tenant: _Tenant, *, count: int, quantity: Decimal = Decimal(1)
) -> tuple[str, ...]:
    """Put ``count`` orders this tenant never placed into the broker's own daily-ccld history."""
    odnos = tuple(f"{_FOREIGN_ODNO_PREFIX}{serial}" for serial in range(1, count + 1))
    for serial, odno in enumerate(odnos, start=1):
        tenant.rows.append(
            _row(
                odno=odno,
                date=tenant.date,
                ord_qty=quantity,
                filled=quantity,
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
    """2026-11-20, tenants 000660 / 005930: leaves archived mid-day and rebooted at 12:48 onto"""
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
    """The worst 11-20-shaped fault: the order POST times out and the broker DID fill it."""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        quantity, odno = _open_that_times_out(tenant, seq=1)
        posts = tenant.order_posts()

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
    """Same fault as the test above, driven to the completion condition: the tenant reconciles"""
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
    """The fail-closed half of the same reconciliation: when TWO orders on the send's own"""
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


def test_g_an_earlier_order_of_the_same_shape_is_not_bound_to_a_timed_out_send(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """Issue #1127: the two 11-20 shapes together — an order POST that went blind, on a day"""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        quantity, _odno = _open_that_times_out(tenant, seq=1)
        posts = tenant.order_posts()
        (foreign,) = _seed_prior_same_day_orders(tenant, count=1, quantity=quantity)
        tenant.next_bar()

        _reconciled(tenant, NEVER_ACCEPTED)
        verdicts = _rows(tenant.runtime, UNCERTAIN_SEND_RECONCILED_KIND)
        assert [row["outcome"] for row in verdicts] == [NEVER_ACCEPTED], verdicts
        assert all(
            row["broker_execution_id"] != foreign for row in verdicts
        ), "the earlier order was adopted as ours"
        assert tenant.order_posts() == posts, "reconciliation sent an order"

        _assert_recovers_to_trading(tenant, first_seq=2)
        discards = _rows(tenant.runtime, _DISCARD_KIND)
        assert [row["reason"] for row in discards] == [NEVER_ACCEPTED_CAUSE], discards
    finally:
        _close(tenant.runtime)


def test_e_an_order_post_that_answered_http_500_is_never_duplicated(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """A 모의 REST 500 on the order POST itself. A 500 does not prove the order was refused,"""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        _open_that_answers_500(tenant, seq=1)
        posts = tenant.order_posts()

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
    """Same fault as the test above, driven to the completion condition: an order the broker"""
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


def test_the_late_candidate_lane_is_wired_and_latches_new_risk(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """Issue #1129: the released-send watch reaches a real latch — a booted tenant's own"""
    tenant = _boot_tenant(
        config_dir_with_risk_state, data_dir, custody_root, server, monkeypatch
    )
    try:
        reconciler = tenant.observer.uncertain_send
        assert reconciler is not None, "the gate is on in the shipped tenant config"
        assert reconciler.today is not None, "no trading date means no same-day watch"
        assert (
            reconciler.broker_clock_corroborated is not None
        ), "issue #1138: the foreign discard must rest on a measured skew"
        assert tenant.runtime.inbox.new_risk_halt() is None
        assert reconciler.halt is not None

        reconciler.halt(
            UNCERTAIN_SEND_LATE_CANDIDATE_KIND,
            {"attempt_id": "attempt-late-candidate", "trading_date": tenant.date},
        )

        latched = tenant.runtime.inbox.new_risk_halt()
        assert latched is not None, "a late candidate left new risk open"
        assert latched["reason"] == LATE_CANDIDATE_HALT_REASON
        assert latched["event_id"] == "attempt:attempt-late-candidate"
        rows = _rows(tenant.runtime, UNCERTAIN_SEND_LATE_CANDIDATE_KIND)
        assert [row["attempt_id"] for row in rows] == ["attempt-late-candidate"]
        assert (
            latched["evidence_seq"] is not None
        ), "the latch names no evidence to clear"
    finally:
        _close(tenant.runtime)
