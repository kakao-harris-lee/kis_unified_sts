"""KIS-mock proof flow for CLOSE risk admission (#1004).

The OPEN fill and held-position proof use the composed asynchronous FETCH/APPLY path and the
production ``RiskStateService``. Only the fake broker and its local HTTP server are test doubles.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import tos_runtime.transport.kis_mock.pacer as pacer_module
import yaml
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.posttrade.fill_fetch import HeldPositionSnapshot
from tos_runtime.posttrade.fill_observer import (
    FILL_OBSERVER_CONFIG_NAME,
    FILL_OBSERVER_RELEASE_SNAPSHOT_KIND,
)
from tos_runtime.recon.ports import WitnessScope, WitnessSnapshot
from tos_runtime.riskstate.service import RiskStateService

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_kis_mock_e2e_honesty import _ORDER_PATH, _sealed_mock_deployment
from .test_kis_mock_fill_finality_e2e import (
    _ODNO,
    _close,
    _row,
    _rows,
    _sealed_quantity,
    _witness_paths,
)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_CLOSE_ODNO = "0000004481"
_ENVIRONMENT_LABEL = "non-live-test"


class _PacedClock:
    """Real monotonic time plus deterministic pacing advances from the KIS app-key pacer."""

    def __init__(self) -> None:
        self._offset_ms = 0
        self._lock = threading.Lock()

    def now_ms(self) -> int:
        with self._lock:
            return time.monotonic_ns() // 1_000_000 + self._offset_ms

    def advance(self, delta_ms: int) -> None:
        with self._lock:
            self._offset_ms += delta_ms

    def sleep(self, seconds: float) -> None:
        self.advance(round(seconds * 1000))


@pytest.fixture
def server() -> Iterator[FakeKisServer]:
    instance = FakeKisServer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def _write_close_strategy(config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = fx.band_reversion_strategy_mapping

    def close_strategy_mapping() -> dict[str, object]:
        mapping = original()
        policy = mapping["policy"]
        assert isinstance(policy, dict)
        rules = policy["rules"]
        assert isinstance(rules, list)
        rules.append(
            {
                "all_of": [
                    {
                        "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                        "op": "GT",
                        "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
                    }
                ],
                "decision": {
                    "kind": "ACTION",
                    "rationale": "close above upper band — mock held proof e2e",
                    "target": {
                        "kind": "ACTION",
                        "account": fx.ACCOUNT,
                        "instrument": fx.INSTRUMENT,
                        "direction": "SHORT",
                        "position_effect": "CLOSE",
                        "quantity_basis": "RISK",
                        "edge_or_confidence": "kis-mock-close-proof-e2e",
                        "rationale": "close above upper band — mock held proof e2e",
                    },
                },
            }
        )
        return mapping

    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", close_strategy_mapping)
    fx.write_band_strategy_file(config_dir)


def _speed_observer_polls(config_dir: Path) -> int:
    path = config_dir / FILL_OBSERVER_CONFIG_NAME
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["poll_interval_ms"] = 1
    raw["held_position_poll_interval_ms"] = 1
    raw["release_snapshot_max_age_ms"] = 60_000
    raw["held_position_max_age_ms"] = 30_000
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    max_age_ms = raw["held_position_max_age_ms"]
    assert isinstance(max_age_ms, int)
    return max_age_ms


def _script_order_ack(server: FakeKisServer, odno: str) -> None:
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={
            "rt_cd": "0",
            "msg_cd": "APBK0013",
            "msg1": "정상처리",
            "output": {"ODNO": odno},
        },
    )


def _script_witness(
    server: FakeKisServer,
    config_dir: Path,
    *,
    date: str,
    rows: list[dict[str, str]],
    holdings: tuple[tuple[str, Decimal], ...],
    pair_change: tuple[Decimal, Decimal] | None = None,
) -> tuple[str, str]:
    balance_path, order_path = _witness_paths(config_dir, date)
    balance_body: dict[str, Any] = {
        "rt_cd": "0",
        "output1": [
            {"pdno": symbol, "hldg_qty": format(quantity, "f")}
            for symbol, quantity in holdings
        ],
        "output2": [{"dnca_tot_amt": "1000000"}],
    }
    order_body: dict[str, Any] = {"rt_cd": "0", "output1": rows, "output2": {}}
    balance_count = 0

    def record_balance_request() -> None:
        nonlocal balance_count
        balance_count += 1
        if pair_change is not None and balance_count == 2:
            symbol, _first = holdings[0] if holdings else (fx.INSTRUMENT, Decimal(0))
            second = pair_change[1]
            balance_body["output1"] = (
                []
                if second == 0
                else [{"pdno": symbol, "hldg_qty": format(second, "f")}]
            )

    server.set_response(
        balance_path,
        status=200,
        body=balance_body,
        on_request=record_balance_request,
    )
    server.set_response(order_path, status=200, body=order_body)
    return balance_path, order_path


def _capture_worker_prefetches(observer, loop_thread: int) -> list[int]:
    snapshots = observer.snapshots
    assert snapshots is not None
    original = snapshots.prefetch
    calls: list[int] = []

    def prefetch(scope: WitnessScope, *, today: str, abort):
        calls.append(threading.get_ident())
        return original(scope, today=today, abort=abort)

    snapshots.prefetch = prefetch
    assert loop_thread == threading.get_ident()
    return calls


def _capture_published(
    observer,
) -> tuple[list[tuple[int, HeldPositionSnapshot]], Any]:
    original = observer.publish_held_position_snapshot
    assert original is not None
    bridge = original.__self__
    published: list[tuple[int, HeldPositionSnapshot]] = []

    def publish(snapshot) -> None:
        published.append((threading.get_ident(), snapshot))
        original(snapshot)

    observer.publish_held_position_snapshot = publish
    return published, bridge


def _wait_for_publish(
    observer, published: list[tuple[int, HeldPositionSnapshot]], after: int
) -> HeldPositionSnapshot:
    deadline = time.monotonic() + 15
    while len(published) <= after:
        observer.poll_if_due()
        if time.monotonic() >= deadline:
            raise AssertionError(
                "async held-position FETCH did not publish before timeout"
            )
        time.sleep(0.001)
    return published[-1][1]


def _wait_for_release_snapshot(
    observer: Any, runtime: Any, after: int
) -> dict[str, Any]:
    """Drive FETCH/APPLY until its independently prefetched release witness is recorded."""
    deadline = time.monotonic() + 15
    rows = _rows(runtime, FILL_OBSERVER_RELEASE_SNAPSHOT_KIND)
    while len(rows) <= after:
        observer.poll_if_due()
        if time.monotonic() >= deadline:
            raise AssertionError(
                "async finality/recovery did not record its release snapshot"
            )
        time.sleep(0.001)
        rows = _rows(runtime, FILL_OBSERVER_RELEASE_SNAPSHOT_KIND)
    return rows[-1]


def _risk_observations(runtime) -> list[dict[str, Any]]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' ORDER BY seq"
    ).fetchall()
    return [json.loads(payload_json)["payload"] for (payload_json,) in rows]


def _step_verdict(result, step: CommitmentStep):
    assert result.flow is not None
    (verdict,) = [item for item in result.flow.verdicts if item.step is step]
    return verdict


def _discover_and_approve(runtime, custody_root: Path, event):
    result = runtime.run_once((event,))[0]
    assert result.pipeline is not None and result.pipeline.proposal is not None
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=result.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    return result


@pytest.mark.parametrize(
    ("case", "expected_status"),
    [
        ("valid", "PROOF_ACCEPTED"),
        ("flat", "PROOF_UNAVAILABLE"),
        ("changed_pair", "PROOF_UNAVAILABLE"),
        ("stale_at_commit", "PROOF_ACCEPTED"),
        ("over_held", "QUANTITY_EXCEEDS_HELD"),
    ],
)
def test_kis_mock_close_needs_fresh_bounded_worker_position_proof(
    case: str,
    expected_status: str,
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server: FakeKisServer,
) -> None:
    """An OPEN is filled at KIS mock; only a matched, current worker proof can send CLOSE."""
    clock = _PacedClock()
    monkeypatch.setattr(pacer_module, "sleep", clock.sleep)
    _sealed_mock_deployment(
        config_dir_with_risk_state, custody_root, server, monkeypatch
    )
    _script_order_ack(server, _ODNO)
    _write_close_strategy(config_dir_with_risk_state, monkeypatch)
    held_max_age_ms = _speed_observer_polls(config_dir_with_risk_state)
    runtime = compose_paper_runtime(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        _ENVIRONMENT_LABEL,
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        transport_kind=TransportKind.KIS_MOCK,
        monotonic_source=clock,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    try:
        assert type(runtime.risk_state) is RiskStateService
        observer = runtime.fill_observer
        assert observer is not None and observer.snapshots is not None
        loop_thread = threading.get_ident()
        worker_threads = _capture_worker_prefetches(observer, loop_thread)
        published, bridge = _capture_published(observer)
        assert runtime.session_facts is not None
        date = runtime.session_facts.trading_date_now(fx.INSTRUMENT_CLASS)
        assert date is not None
        _script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[],
            holdings=(),
        )

        open_event = fx.crossing_event(seq=1)
        open_discovery = runtime.run_once((open_event,))[0]
        assert open_discovery.pipeline is not None
        assert open_discovery.pipeline.proposal is not None
        open_construction = runtime.construction_stage.construction
        assert open_construction is not None and open_construction.intent is not None
        open_quantity = open_construction.derivation.quantity
        assert open_quantity is not None and open_quantity > 0
        open_proposal_digest = open_discovery.pipeline.proposal.canonical_digest
        open_intent_digest = open_construction.intent.canonical_digest
        assert open_proposal_digest is not None
        assert open_intent_digest is not None
        write_approval_file(
            custody_root,
            proposal_digest=open_proposal_digest,
            environment_label=_ENVIRONMENT_LABEL,
            approved_intent_envelope_digest=open_intent_digest,
        )
        # Risk proof is ineligible before any entry is POSITION_CONSUMED; boot and OPEN approval
        # must not trigger an empty-account holdings poll.
        assert published == []

        open_row = _row(
            odno=_ODNO,
            date=date,
            ord_qty=open_quantity,
            filled=open_quantity,
            remaining=Decimal(0),
        )
        _script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=((fx.INSTRUMENT, open_quantity),),
        )
        open_result = runtime.run_once((open_event,))[0]
        assert open_result.flow is not None
        open_afg = next(
            item
            for item in open_result.flow.verdicts
            if item.step is CommitmentStep.ACTION_FLOW_DECISION
        )
        assert open_afg.outcome is StageOutcome.ADMIT, open_afg.reason
        assert open_result.flow.handed_off is True
        assert len(server.requests_for(_ORDER_PATH)) == 1
        assert _sealed_quantity(runtime) == open_quantity
        open_attempt = next(
            row["attempt_id"]
            for row in _rows(runtime, "EGRESS_RESULT_CONSUMED")
            if row["egress_result_kind"] == "ACK"
        )

        # This worker reads the real OPEN fill and a positive broker holding. APPLY publishes
        # against the pre-fill RCL tip, then consumes the fill and advances that tip.
        after_open_fetch = len(published)
        open_fill_pair = _wait_for_publish(observer, published, after_open_fetch)
        assert any(
            row["attempt_id"] == open_attempt
            and row["egress_result_kind"] == "FULL_FILL"
            for row in _rows(runtime, "EGRESS_RESULT_CONSUMED")
        )
        assert any(
            state is CapacityState.POSITION_CONSUMED
            for _reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
        )
        assert isinstance(open_fill_pair.first, WitnessSnapshot)
        assert open_fill_pair.first.positions == ((fx.INSTRUMENT, open_quantity),)
        assert open_fill_pair.first.positions_complete is True
        assert open_fill_pair.first.independent_of_evidence_store is True

        if case == "flat":
            current_holdings: tuple[tuple[str, Decimal], ...] = ()
            pair_change = None
        elif case == "over_held":
            current_holdings = ((fx.INSTRUMENT, Decimal(1)),)
            pair_change = None
        else:
            current_holdings = ((fx.INSTRUMENT, open_quantity),)
            pair_change = None
        if case == "changed_pair":
            current_holdings = ((fx.INSTRUMENT, open_quantity),)
            pair_change = (open_quantity, open_quantity - Decimal(1))

        # A new FETCH generation now exists after the OPEN RCL commit. The valid case receives
        # two identical complete snapshots; changed_pair varies only the second balance read.
        _script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=current_holdings,
            pair_change=pair_change,
        )
        after_open_fill = len(published)
        current_pair = _wait_for_publish(observer, published, after_open_fill)
        assert isinstance(current_pair.first, WitnessSnapshot)
        assert current_pair.confirmation is not None
        assert isinstance(current_pair.confirmation, WitnessSnapshot)
        assert current_pair.first.positions_complete is True
        if case == "changed_pair":
            assert isinstance(current_pair.first, WitnessSnapshot)
            assert isinstance(current_pair.confirmation, WitnessSnapshot)
            assert current_pair.first.positions != current_pair.confirmation.positions
        else:
            assert isinstance(current_pair.first, WitnessSnapshot)
            assert isinstance(current_pair.confirmation, WitnessSnapshot)
            assert current_pair.first.positions == current_pair.confirmation.positions
            assert current_pair.first.orders == current_pair.confirmation.orders
            assert current_pair.first.order_inquiry_date == date
            assert current_pair.confirmation.order_inquiry_date == date
        proof_reading = bridge.cell._proof
        if case in ("valid", "stale_at_commit", "over_held"):
            assert proof_reading is not None, (current_pair, bridge.tip())
            current_tip = bridge.tip()
            assert current_tip is not None and proof_reading.rcl_tip == current_tip, (
                proof_reading,
                current_tip,
            )
            assert proof_reading.scope == WitnessScope(
                account=fx.ACCOUNT,
                instrument_keys=(fx.instrument_key(),),
                as_of_generation=current_tip.last_seq,
            ), (proof_reading.scope, current_tip)
        else:
            assert proof_reading is None, current_pair
        assert worker_threads and all(
            thread_id != loop_thread for thread_id in worker_threads
        )
        assert (
            len(worker_threads) >= 2
        )  # each accepted/rejected held pair is two worker reads

        close_event = fx.crossing_event(seq=2, close=fx.UPPER_BAND + 1_000)
        if case == "stale_at_commit":
            # Proposal discovery records approval; the approved replay consumes the already
            # fetched proof at step 6. Step 9 then sees that exact proof age past its bound.
            _discover_and_approve(runtime, custody_root, close_event)
            _script_witness(
                server,
                config_dir_with_risk_state,
                date=date,
                rows=[open_row],
                holdings=current_holdings,
                pair_change=pair_change,
            )
            after_discovery = len(published)
            _wait_for_publish(observer, published, after_discovery)
            close_construction = runtime.construction_stage.construction
            assert close_construction is not None
            close_quantity = close_construction.derivation.quantity
            assert close_quantity is not None
            assert runtime.risk_state is not None
            original_validate = runtime.risk_state._held_position_currentness_reader
            assert original_validate is not None

            def expire_before_step9(proof):
                clock.advance(held_max_age_ms + 1)
                return original_validate(proof)

            runtime.risk_state._held_position_currentness_reader = expire_before_step9
            _script_order_ack(server, _CLOSE_ODNO)
            posts_before_close = len(server.requests_for(_ORDER_PATH))
            close_result = runtime.run_once((close_event,))[0]
            assert close_result.flow is not None
            assert (
                _step_verdict(
                    close_result, CommitmentStep.AGGREGATE_RISK_DECISION
                ).outcome
                is StageOutcome.ADMIT
            )
            assert len(server.requests_for(_ORDER_PATH)) == posts_before_close
            assert len(server.requests_for(_ORDER_PATH)) == 1
            assert (
                _rows(runtime, "RISK_STATE_OBSERVED")[-1]["close_effect"][
                    "proof_status"
                ]
                == expected_status
            )
            return

        _discover_and_approve(runtime, custody_root, close_event)
        close_construction = runtime.construction_stage.construction
        assert close_construction is not None
        close_quantity = close_construction.derivation.quantity
        assert close_quantity is not None
        _script_witness(
            server,
            config_dir_with_risk_state,
            date=date,
            rows=[open_row],
            holdings=current_holdings,
            pair_change=pair_change,
        )
        after_discovery = len(published)
        close_pair = _wait_for_publish(observer, published, after_discovery)
        assert isinstance(close_pair.first, WitnessSnapshot)
        assert isinstance(close_pair.confirmation, WitnessSnapshot)
        if case == "changed_pair":
            assert close_pair.first.positions != close_pair.confirmation.positions
        else:
            assert close_pair.first.positions == close_pair.confirmation.positions
            assert close_pair.first.orders == close_pair.confirmation.orders
        proof_reading = bridge.cell._proof
        if case in ("valid", "over_held"):
            assert proof_reading is not None
            current_tip = bridge.tip()
            assert current_tip is not None and proof_reading.rcl_tip == current_tip, (
                proof_reading,
                current_tip,
            )
        _script_order_ack(server, _CLOSE_ODNO)
        if proof_reading is not None:
            assert clock.now_ms() >= proof_reading.age_origin_ms
            assert (
                clock.now_ms() - proof_reading.age_origin_ms <= proof_reading.max_age_ms
            )
            assert proof_reading.trading_date == date
        consume_calls: list[tuple[Any, Any, Any, Any]] = []
        original_consume_for = bridge.cell.consume_for

        def capture_consume_for(
            account: Any, instrument: Any, side: Any, *, proposal_id: Any
        ) -> Any:
            result = original_consume_for(
                account, instrument, side, proposal_id=proposal_id
            )
            consume_calls.append((account, instrument, side, result))
            return result

        monkeypatch.setattr(bridge.cell, "consume_for", capture_consume_for)
        posts_before_close = len(server.requests_for(_ORDER_PATH))
        close_result = runtime.run_once((close_event,))[0]
        close_observations = [
            row for row in _risk_observations(runtime) if "close_effect" in row
        ]
        assert close_observations, _risk_observations(runtime)
        observation = close_observations[-1]
        assert consume_calls, close_result
        assert consume_calls[0][:2] == (fx.ACCOUNT, fx.INSTRUMENT)
        assert observation["close_effect"]["proof_status"] == expected_status, (
            observation["close_effect"],
            bridge.cell._proof,
            bridge.cell._consumed_proof,
            consume_calls,
        )
        if case == "valid":
            assert close_quantity <= open_quantity
            assert (
                Decimal(observation["close_effect"]["held_quantity"]) == open_quantity
            )
            assert (
                _step_verdict(
                    close_result, CommitmentStep.AGGREGATE_RISK_DECISION
                ).outcome
                is StageOutcome.ADMIT
            )
            assert (
                close_result.flow is not None and close_result.flow.handed_off is True
            )
            assert len(server.requests_for(_ORDER_PATH)) == posts_before_close + 1
            # The valid CLOSE was step-6 admitted and crossed the real step-9 close proof fence.
            close_posts = [
                request
                for request in server.requests_for(_ORDER_PATH)
                if request.method == "POST"
            ]
            assert len(close_posts) == 2
        else:
            if case == "over_held":
                assert close_quantity > Decimal(1)
                assert observation["close_effect"]["held_quantity"] == "1"
            assert (
                _step_verdict(
                    close_result, CommitmentStep.AGGREGATE_RISK_DECISION
                ).outcome
                is not StageOutcome.ADMIT
            )
            assert close_result.flow is None or close_result.flow.handed_off is not True
            assert len(server.requests_for(_ORDER_PATH)) == posts_before_close == 1
    finally:
        _close(runtime)
