"""Issue #960 / #966 e2e — an entry and the exit that closes it, in ONE process.

Against the fake KIS server (MOCK order class, no real broker). An entry tick
(``close < lower_band``) yields an ``OPEN``/``LONG`` proposal sent as a BUY; a later exit tick
(``close > upper_band``) yields a ``CLOSE``/``SHORT`` proposal, and the command built for it
carries ``SELL``/``CLOSE``:

* through the standing session artifact, whose ``CLOSE-SHORT-SELL`` action matches it (before
  #960 the command said ``BUY``, so that boundary never matched and the exit never sent);
* through a per-proposal operator approval file, which sends the SELL and never a second BUY
  (before #960 that path bought another lot).

**#966 removed the workaround these tests used to need.** Both used to drive the exit as the
FIRST commit of the process, because an entry followed by an exit was unreachable for two
reasons that had nothing to do with the command's side:

1. step 8 (``LEDGER_VERIFICATION``) denied any second commit on a scope that already held a
   reservation row — "scope already holds a committed reservation at POSITION_CONSUMED";
2. the suite's own step-7 inputs provider froze ``decision_generation`` at 1, so once the first
   flow's commits moved the RCL tip, EVERY second flow in the process halted at step 7 with
   ``UNKNOWN`` (see ``_LiveRuntimeFacts`` in ``test_compose_root.py``).

Both are fixed, so the full cycle now runs here: entry → fill → close → fill → broker flat →
the entry's reservation RELEASED → a fresh entry ADMITs at step 8 again.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
import yaml
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import CapacityState

from ..transport.kis_mock._fake_kis_server import FakeKisServer
from . import _fixtures as fx
from .conftest import write_approval_file
from .test_kis_mock_e2e_honesty import _ENVIRONMENT_LABEL, _boot
from .test_kis_mock_fill_finality_e2e import (
    _ORDER_PATH,
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


@pytest.fixture()
def server() -> Iterator[FakeKisServer]:
    srv = FakeKisServer()
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def _exit_rule() -> dict[str, Any]:
    """``close > upper_band`` -> close the long: the closing ACTION's direction is SHORT
    (``build_flat`` "The direction of the closing action"; the shipped setup-D trees).
    """
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
    # Every writer of the band strategy file (the standing-artifact helper and the compose
    # boot itself) now writes the entry+exit strategy, so the artifact names the booted one.
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


class _Broker:
    """The fake broker's accumulated order book for one session.

    Every order this process sent stays in the inquiry response, which is what a real broker
    does — reconciliation folds EVERY receipt in scope, so dropping the entry's order once the
    close is sent would make the entry read as a stale reservation and hold the close's own
    release (measured; it is not a property of #966).
    """

    def __init__(self, server, config_dir) -> None:
        self._server = server
        self._config_dir = config_dir
        self._rows: list[dict[str, str]] = []

    def fill(self, runtime, *, odno: str, flat: bool = True) -> None:
        """Fully fill the latest ACKed order, then poll the observer once.

        ``flat`` drives the balance read the reconciliation witness makes: the account reports
        no holding (flat) unless a test needs an outstanding position reported.
        """
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
            list(self._rows),
            holdings=() if flat else ((fx.INSTRUMENT, qty),),
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


# ===========================================================================
# 1. the whole cycle in one process, through the standing boundary
# ===========================================================================


def test_an_entry_then_its_close_then_a_re_entry_in_one_process(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """#966's completion condition: entry → close → broker flat → re-entry admitted.

    Every assertion below was unreachable before #966 — the second flow of the process
    halted at step 7, and the one after that at step 8.
    """
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    # --- the entry: a BUY that fills and leaves a consumed position -------------------
    _order_response(server, "0000000201")
    (entry,) = runtime.run_once((_entry_tick(),))
    assert _verdict(entry, CommitmentStep.LEDGER_VERIFICATION).outcome is (
        StageOutcome.ADMIT
    )
    assert entry.flow.handed_off is True
    assert _tr_ids(server) == [transport["tr_id_buy"]]
    broker.fill(runtime, odno="0000000201")

    entry_reservations = _reservations(runtime)
    assert list(entry_reservations.values()) == [CapacityState.POSITION_CONSUMED]
    (entry_reservation_id,) = entry_reservations
    assert _rcl_releases(runtime) == 1

    # --- the exit: a SELL, admitted over that one consumed position -------------------
    _order_response(server, "0000000202")
    (exit_,) = runtime.run_once((_exit_tick(),))
    _assert_close_proposal(exit_)
    step8 = _verdict(exit_, CommitmentStep.LEDGER_VERIFICATION)
    assert step8.outcome is StageOutcome.ADMIT, step8.reason
    assert "one consumed position" in (step8.reason or "")
    assert exit_.flow.handed_off is True
    assert _tr_ids(server)[-1] == transport["tr_id_sell"]
    assert _sealed(runtime)[-1]["outbound_side"] == "SELL"
    assert runtime.construction_stage.attempt.position_effect == "CLOSE"

    # the close holds its OWN reservation, distinct from the entry's
    during_close = _reservations(runtime)
    assert len(during_close) == 2
    assert during_close[entry_reservation_id] is CapacityState.POSITION_CONSUMED

    # --- the close fills, broker reports flat: BOTH reservations end RELEASED ---------
    broker.fill(runtime, odno="0000000202")
    after_close = _reservations(runtime)
    assert set(after_close.values()) == {CapacityState.RELEASED}, after_close
    assert after_close[entry_reservation_id] is CapacityState.RELEASED
    assert _rows(runtime, "CAPACITY_RELEASE_HELD") == []
    destinations = [r["destination"] for r in _rows(runtime, "CAPACITY_RELEASE_INTENT")]
    assert destinations == ["POSITION_CONSUMED", "RELEASED", "RELEASED"]

    # --- and the scope trades again --------------------------------------------------
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
    """A close that fills but leaves the broker still holding does NOT release the entry.

    Concrete failing input: the close's own fill is complete, but the balance read still
    reports the instrument held. Capacity stays committed for a position that is still open
    (ADR-002-012 :179), and the hold says why.
    """
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
    held = [r["reason"] for r in _rows(runtime, "CAPACITY_RELEASE_HELD")]
    assert held == ["BROKER_POSITION_NOT_FLAT"]
    # The close's own reservation is still released — it opened no position either way.
    assert CapacityState.RELEASED in set(after.values())
    _close(runtime)


# ===========================================================================
# 2. the per-proposal boundary: an approved CLOSE sends a SELL, never a BUY
# ===========================================================================


def test_a_per_proposal_approval_of_a_close_sends_a_sell_never_a_buy(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """No standing artifact at all: the operator approves each proposal by file. Before
    #960 the approved close command was a BUY — the per-proposal path bought a second lot
    instead of closing."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)

    # the entry, approved by its own file, so the scope holds a consumed position
    _order_response(server, "0000000401")
    entry_event = _entry_tick()
    (pending_entry,) = runtime.run_once((entry_event,))
    _approve(runtime, custody_root, pending_entry)
    (entry,) = runtime.run_once((entry_event,))
    assert entry.flow.handed_off is True
    broker.fill(runtime, odno="0000000401")

    # first pass of the exit: the proposal exists, step 4 has no approval to consume
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
    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=result.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
