"""Issue #960 / #966 e2e — an entry and the exit that closes it, in ONE process."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
import tos_runtime.compose.root as compose_root
import yaml
from tos.egressgw import derive_economic_effect_envelope
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import CapacityState, CapacityVector
from tos_runtime.risk.ledger_stages import CloseProofCommitFence

from . import _fixtures as fx
from .conftest import approve_constructed_intent
from .test_kis_mock_e2e_honesty import (
    _ENVIRONMENT_LABEL,
)
from .test_kis_mock_e2e_honesty import (
    _boot as _boot_without_close_fence,
)
from .test_kis_mock_fill_finality_e2e import (
    _OMIT_OUTPUT1,
    _ORDER_PATH,
    _UNSET_CONTAINER,
    _close,
    _deploy,
    _rcl_releases,
    _row,
    _rows,
    _script_broker,
)
from .test_standing_session_approval import _document, _standing_uses, _write

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_EXIT_CLOSE = fx.UPPER_BAND + 1_000
_ENTRY_ONLY_MAPPING = fx.band_reversion_strategy_mapping
_ENTRY_DISCHARGE_PENDING = "ENTRY_DISCHARGE_PENDING"


def _boot(tmp_path, config_dir, data_dir, custody_root):
    """Boot with a test-only current CLOSE fence for this suite's synthetic risk inputs."""
    runtime_ref: dict[str, Any] = {}
    build_providers = compose_root.build_risk_state_providers

    def _build_test_providers(**kwargs):
        providers = build_providers(**kwargs)

        def _test_close_fence(request):
            runtime = runtime_ref.get("runtime")
            proposal_id = getattr(request.proposal, "proposal_id", None)
            if runtime is None or type(proposal_id) is not str or not proposal_id:
                return None
            log = runtime.rcl_log
            writer_epoch = log.current_epoch()
            view = log.read_linearizable(writer_epoch=writer_epoch)
            if view.last_seq is None:
                return None
            generation = view.last_seq
            return CloseProofCommitFence(
                proposal_id=proposal_id,
                account=request.instrument_key.account,
                instrument=request.instrument_key.instrument,
                attempt_ids=(),
                as_of_generation=generation,
                observed_at_generation=generation,
                trading_date="20261029",
                age_origin_ms=0,
                rcl_writer_epoch=writer_epoch,
                rcl_last_seq=view.last_seq,
                verified_rcl_writer_epoch=writer_epoch,
                verified_rcl_last_seq=view.last_seq,
                current_now_ms=0,
                current_trading_date="20261029",
                max_age_ms=1,
            )

        return replace(providers, close_fence=_test_close_fence)

    with pytest.MonkeyPatch.context() as patcher:
        patcher.setattr(
            compose_root, "build_risk_state_providers", _build_test_providers
        )
        runtime = _boot_without_close_fence(
            tmp_path, config_dir, data_dir, custody_root
        )
    runtime_ref["runtime"] = runtime
    return runtime


def _exit_rule() -> dict[str, Any]:
    """``close > upper_band`` -> close the long: the closing ACTION's direction is SHORT"""
    rationale = "close pierced the upper band — compose e2e exit"
    return {
        "all_of": [
            {
                "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                "op": "GT",
                "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
            }
        ],
        "decision": {
            "kind": "ACTION",
            "rationale": rationale,
            "target": {
                "kind": "ACTION",
                "account": fx.ACCOUNT,
                "instrument": fx.INSTRUMENT,
                "direction": "SHORT",
                "position_effect": "CLOSE",
                "quantity_basis": "RISK",
                "edge_or_confidence": "compose-e2e",
                "rationale": rationale,
            },
        },
    }


def _entry_exit_mapping() -> dict[str, object]:
    mapping = _ENTRY_ONLY_MAPPING()
    mapping["policy"]["rules"].append(_exit_rule())  # type: ignore[index]
    return mapping


def _deployed(config_dir, custody_root, server, monkeypatch) -> None:
    monkeypatch.setattr(fx, "band_reversion_strategy_mapping", _entry_exit_mapping)
    _deploy(config_dir, custody_root, server, monkeypatch)


def _standing_cycle_artifact(config_dir, custody_root) -> None:
    """The operator's standing artifact for this session: one entry, one exit, one re-entry."""
    document = _document(config_dir)
    document["actions"] = [
        {"position_effect": "OPEN", "direction": "LONG", "side": "BUY", "max_uses": 2},
        {
            "position_effect": "CLOSE",
            "direction": "SHORT",
            "side": "SELL",
            "max_uses": 1,
        },
    ]
    _write(custody_root, document)


def _verdict(result, step: CommitmentStep):
    assert result.flow is not None
    (verdict,) = [v for v in result.flow.verdicts if v.step is step]
    return verdict


def _sealed(runtime) -> list[dict[str, Any]]:
    return [r["send_seal"] for r in _rows(runtime, "SEND_SEALED")]


def _tr_ids(server) -> list[str]:
    return [r.headers["tr_id"] for r in server.requests_for(_ORDER_PATH)]


def _reservations(runtime) -> dict[str, CapacityState]:
    return {
        reservation_id: state
        for reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
    }


def _release_hold_reasons(runtime) -> list[str]:
    return [row["reason"] for row in _rows(runtime, "CAPACITY_RELEASE_HELD")]


def _step5_envelope(runtime) -> CapacityVector:
    """The step-5 envelope of the attempt the runtime just ran — the same derivation"""
    stage = runtime.construction_stage
    assert stage.construction is not None
    envelope = derive_economic_effect_envelope(
        stage.construction.derivation, stage.effect_specs
    )
    assert envelope.components, "a non-empty envelope is what step 5 admits"
    return envelope


class _Broker:
    """The fake broker's accumulated order book for one session."""

    def __init__(self, server, config_dir) -> None:
        self._server = server
        self._config_dir = config_dir
        self._rows: list[dict[str, str]] = []

    def fill(
        self,
        runtime,
        *,
        odno: str,
        flat: bool = True,
        raw_holdings: list[dict[str, Any]] | None = None,
        holdings_container: Any = _UNSET_CONTAINER,
        extra_order_rows: list[Any] | None = None,
    ) -> None:
        """Fully fill the latest ACKed order, then poll the observer once."""
        *_, ack = [
            r
            for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
            if r["egress_result_kind"] == "ACK"
        ]
        qty = Decimal(_sealed(runtime)[-1]["outbound_quantity"])
        date = ack["trading_date"]
        self._rows.append(
            _row(odno=odno, date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))
        )
        _script_broker(
            self._server,
            self._config_dir,
            date,
            [*self._rows, *(extra_order_rows or ())],
            holdings=() if flat else ((fx.INSTRUMENT, qty),),
            raw_holdings=raw_holdings,
            holdings_container=holdings_container,
        )
        observer = runtime.fill_observer
        assert observer is not None
        observer.poll_once()


def _order_response(server, odno: str) -> None:
    server.set_response(
        _ORDER_PATH,
        status=200,
        body={"rt_cd": "0", "msg_cd": "APBK0013", "output": {"ODNO": odno}},
    )


def _entry_tick(seq: int = 0):
    return fx.crossing_event(seq=seq)


def _exit_tick(seq: int = 1):
    return fx.crossing_event(seq=seq, close=_EXIT_CLOSE)


def _assert_close_proposal(result) -> None:
    proposal = result.pipeline.proposal
    assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
    assert _verdict(result, CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION).outcome is (
        StageOutcome.ADMIT
    )


def test_an_entry_then_its_close_then_a_re_entry_in_one_process(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """#966's completion condition: entry → close → broker flat → re-entry admitted."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000201")
    (entry,) = runtime.run_once((_entry_tick(),))
    assert _verdict(entry, CommitmentStep.LEDGER_VERIFICATION).outcome is (
        StageOutcome.ADMIT
    )
    assert entry.flow.handed_off is True
    assert _tr_ids(server) == [transport["tr_id_buy"]]
    entry_envelope = _step5_envelope(runtime)
    broker.fill(runtime, odno="0000000201")

    entry_reservations = _reservations(runtime)
    assert list(entry_reservations.values()) == [CapacityState.POSITION_CONSUMED]
    (entry_reservation_id,) = entry_reservations
    assert runtime.rcl_log.reservation_committed_vector(entry_reservation_id) == (
        entry_envelope
    )
    assert _rcl_releases(runtime) == 1

    _order_response(server, "0000000202")
    (exit_,) = runtime.run_once((_exit_tick(),))
    _assert_close_proposal(exit_)
    step6 = _verdict(exit_, CommitmentStep.AGGREGATE_RISK_DECISION)
    assert step6.outcome is StageOutcome.ADMIT, step6.reason
    step8 = _verdict(exit_, CommitmentStep.LEDGER_VERIFICATION)
    assert step8.outcome is StageOutcome.ADMIT, step8.reason
    assert "one consumed position" in (step8.reason or "")
    assert exit_.flow.handed_off is True
    assert _tr_ids(server)[-1] == transport["tr_id_sell"]
    assert _sealed(runtime)[-1]["outbound_side"] == "SELL"
    assert runtime.construction_stage.attempt.position_effect == "CLOSE"

    during_close = _reservations(runtime)
    assert len(during_close) == 2
    assert during_close[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    (close_reservation_id,) = set(during_close) - {entry_reservation_id}
    close_envelope = _step5_envelope(runtime)
    expected_close_vector = CapacityVector(
        components=tuple(
            component.model_copy(
                update={
                    "magnitude": (
                        None if component.magnitude is None else -component.magnitude
                    )
                }
            )
            for component in close_envelope.components
        )
    )
    assert runtime.rcl_log.reservation_committed_vector(close_reservation_id) == (
        expected_close_vector
    )

    broker.fill(runtime, odno="0000000202")
    after_close = _reservations(runtime)
    assert set(after_close.values()) == {CapacityState.RELEASED}, after_close
    assert after_close[entry_reservation_id] is CapacityState.RELEASED
    assert _release_hold_reasons(runtime) == [_ENTRY_DISCHARGE_PENDING]
    destinations = [r["destination"] for r in _rows(runtime, "CAPACITY_RELEASE_INTENT")]
    assert destinations == ["POSITION_CONSUMED", "RELEASED", "RELEASED"]

    _order_response(server, "0000000203")
    (again,) = runtime.run_once((_entry_tick(seq=2),))
    step8_again = _verdict(again, CommitmentStep.LEDGER_VERIFICATION)
    assert step8_again.outcome is StageOutcome.ADMIT, step8_again.reason
    assert again.flow.handed_off is True
    assert _tr_ids(server)[-1] == transport["tr_id_buy"]
    assert len(_standing_uses(runtime)) == 3
    _close(runtime)


def test_a_partial_close_leaves_the_entry_reservation_held(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """A close that fills but leaves the broker still holding does NOT release the entry."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000301")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000301")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000302")
    (exit_,) = runtime.run_once((_exit_tick(),))
    assert exit_.flow.handed_off is True
    broker.fill(runtime, odno="0000000302", flat=False)

    after = _reservations(runtime)
    assert after[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    assert _release_hold_reasons(runtime) == [
        _ENTRY_DISCHARGE_PENDING,
        "BROKER_POSITION_NOT_FLAT",
    ]
    assert CapacityState.RELEASED in set(after.values())
    _close(runtime)


def test_a_per_proposal_approval_of_a_close_sends_a_sell_never_a_buy(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """No standing artifact at all: the operator approves each proposal by file. Before"""
    _deployed(config_dir, custody_root, server, monkeypatch)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000401")
    entry_event = _entry_tick()
    (pending_entry,) = runtime.run_once((entry_event,))
    _approve(runtime, custody_root, pending_entry)
    (entry,) = runtime.run_once((entry_event,))
    assert entry.flow.handed_off is True
    broker.fill(runtime, odno="0000000401")

    _order_response(server, "0000000402")
    event = _exit_tick()
    (pending,) = runtime.run_once((event,))
    _assert_close_proposal(pending)
    assert _verdict(pending, CommitmentStep.INDEPENDENT_APPROVAL).outcome is (
        StageOutcome.UNKNOWN
    )
    assert _tr_ids(server) == [transport["tr_id_buy"]]

    _approve(runtime, custody_root, pending)
    (approved,) = runtime.run_once((event,))
    _assert_close_proposal(approved)
    assert _verdict(approved, CommitmentStep.INDEPENDENT_APPROVAL).outcome is (
        StageOutcome.ADMIT
    )
    assert approved.flow.handed_off is True
    assert _tr_ids(server)[-1] == transport["tr_id_sell"]
    assert _tr_ids(server).count(transport["tr_id_buy"]) == 1
    assert _sealed(runtime)[-1]["outbound_side"] == "SELL"
    _close(runtime)


def _approve(runtime, custody_root, result) -> None:
    """Write the operator approval file for ``result``'s own proposal + intent envelope."""
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=result.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
    )


@pytest.mark.parametrize("bad_quantity", ["", "  ", "N/A"])
def test_an_unreadable_holding_quantity_keeps_the_entry_and_denies_a_re_entry(
    bad_quantity, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """A balance row the PRODUCTION parser drops must not read as a flat account."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000501")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000501")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000502")
    (exit_,) = runtime.run_once((_exit_tick(),))
    assert exit_.flow.handed_off is True
    broker.fill(
        runtime,
        odno="0000000502",
        raw_holdings=[{"pdno": fx.INSTRUMENT, "hldg_qty": bad_quantity}],
    )

    after = _reservations(runtime)
    assert after[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    assert _release_hold_reasons(runtime) == [
        _ENTRY_DISCHARGE_PENDING,
        "BROKER_POSITION_NOT_FLAT",
    ]

    _order_response(server, "0000000503")
    (again,) = runtime.run_once((_entry_tick(seq=2),))
    step8 = _verdict(again, CommitmentStep.LEDGER_VERIFICATION)
    assert step8.outcome is StageOutcome.DENY, step8.reason
    assert "no pyramiding" in (step8.reason or "")
    assert again.flow.handed_off is False
    _close(runtime)


def test_a_zero_holding_quantity_is_proven_flat_and_releases_the_entry(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Positive control for the test above: ``hldg_qty: "0"`` PARSES, so the observation is"""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000601")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000601")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000602")
    runtime.run_once((_exit_tick(),))
    broker.fill(
        runtime,
        odno="0000000602",
        raw_holdings=[{"pdno": fx.INSTRUMENT, "hldg_qty": "0"}],
    )

    assert _reservations(runtime)[entry_reservation_id] is CapacityState.RELEASED
    assert _release_hold_reasons(runtime) == [_ENTRY_DISCHARGE_PENDING]

    _order_response(server, "0000000603")
    (again,) = runtime.run_once((_entry_tick(seq=2),))
    assert _verdict(again, CommitmentStep.LEDGER_VERIFICATION).outcome is (
        StageOutcome.ADMIT
    )
    _close(runtime)


@pytest.mark.parametrize(
    ("container", "label"),
    [
        (_OMIT_OUTPUT1, "output1 key absent"),
        (None, "output1: null"),
        ({}, "output1: {}"),
        ({"rt_cd": "0"}, "output1: a non-empty dict"),
    ],
    ids=["missing", "null", "empty-dict", "dict"],
)
def test_a_malformed_holdings_container_keeps_the_entry_and_denies_a_re_entry(
    container, label, config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """review-973 round 2 (HIGH): a balance page whose ``output1`` is not a list is not flat."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000701")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000701")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000702")
    (exit_,) = runtime.run_once((_exit_tick(),))
    assert exit_.flow.handed_off is True
    broker.fill(runtime, odno="0000000702", holdings_container=container)

    assert (
        _reservations(runtime)[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    ), label
    assert _release_hold_reasons(runtime) == [
        _ENTRY_DISCHARGE_PENDING,
        "BROKER_POSITION_NOT_FLAT",
    ]

    _order_response(server, "0000000703")
    (again,) = runtime.run_once((_entry_tick(seq=2),))
    step8 = _verdict(again, CommitmentStep.LEDGER_VERIFICATION)
    assert step8.outcome is StageOutcome.DENY, step8.reason
    assert again.flow.handed_off is False
    _close(runtime)


def test_a_holdings_pdno_that_is_not_a_string_keeps_the_entry_and_denies_a_re_entry(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Issue #981: a holdings row whose ``pdno`` is not a string names no symbol."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000901")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000901")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000902")
    (exit_,) = runtime.run_once((_exit_tick(),))
    assert exit_.flow.handed_off is True
    broker.fill(
        runtime, odno="0000000902", raw_holdings=[{"pdno": 5930, "hldg_qty": "10"}]
    )

    assert (
        _reservations(runtime)[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    )
    assert _release_hold_reasons(runtime) == [
        _ENTRY_DISCHARGE_PENDING,
        "BROKER_POSITION_NOT_FLAT",
    ]

    _order_response(server, "0000000903")
    (again,) = runtime.run_once((_entry_tick(seq=2),))
    step8 = _verdict(again, CommitmentStep.LEDGER_VERIFICATION)
    assert step8.outcome is StageOutcome.DENY, step8.reason
    assert again.flow.handed_off is False
    _close(runtime)


def test_an_unreadable_order_row_holds_the_close_instead_of_dropping_it(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """Issue #981, the orders axis: the order inquiry answers with the close's own fill row AND"""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000001001")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000001001")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000001002")
    (exit_,) = runtime.run_once((_exit_tick(),))
    assert exit_.flow.handed_off is True
    broker.fill(runtime, odno="0000001002", extra_order_rows=[None])

    assert [
        r["inquiry_date"] for r in _rows(runtime, "FILL_OBSERVER_READ_FAILED")
    ] != []
    assert [r["broker_execution_id"] for r in _rows(runtime, "FILL_OBSERVED")] == [
        "0000001001"
    ]
    assert [r["destination"] for r in _rows(runtime, "CAPACITY_RELEASE_INTENT")] == [
        CapacityState.POSITION_CONSUMED.value
    ]
    assert (
        _reservations(runtime)[entry_reservation_id] is CapacityState.POSITION_CONSUMED
    )
    _close(runtime)


def test_an_empty_holdings_list_is_proven_flat_and_releases_the_entry(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """The positive control: ``output1: []`` with no more pages IS a flat account."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    _order_response(server, "0000000801")
    runtime.run_once((_entry_tick(),))
    broker.fill(runtime, odno="0000000801")
    (entry_reservation_id,) = _reservations(runtime)

    _order_response(server, "0000000802")
    runtime.run_once((_exit_tick(),))
    broker.fill(runtime, odno="0000000802", holdings_container=[])

    assert _reservations(runtime)[entry_reservation_id] is CapacityState.RELEASED
    assert _release_hold_reasons(runtime) == [_ENTRY_DISCHARGE_PENDING]
    _close(runtime)
