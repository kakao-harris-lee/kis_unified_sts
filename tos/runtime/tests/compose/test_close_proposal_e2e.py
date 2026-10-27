"""Issue #960 e2e — a CLOSE proposal is sent as a SELL, through both approval boundaries.

Against the fake KIS server (MOCK order class, no real broker). An exit tick
(``close > upper_band``) yields a ``CLOSE``/``SHORT`` proposal, and the command built for it
carries ``SELL``/``CLOSE``:

* through the standing session artifact, whose ``CLOSE-SHORT-SELL`` action matches it (before
  #960 the command said ``BUY``, so that boundary never matched and the exit never sent);
* through a per-proposal operator approval file, which sends the SELL and never a second BUY
  (before #960 that path bought another lot).

Both drive the exit as the committed attempt of the process. An entry AND an exit in one loop
is not reachable in this runtime today for reasons that have nothing to do with the command's
side: step 8 (``LEDGER_VERIFICATION``) denies any second commit on a scope that already holds
a reservation — "scope already holds a committed reservation at POSITION_CONSUMED — not a
fresh scope eligible to originate COMMITTED_UNBOUND" (``tos_runtime.risk.ledger_stages``;
measured with a second OPEN too, so it is not CLOSE-specific). The OPEN path is unchanged by
#960 and pinned elsewhere: the entry e2e tests in this suite, and
``test_attempt_shape.py::test_the_open_arm_envelope_is_the_one_boot_always_built``.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
import yaml
from tos.engine.vocabulary import CommitmentStep, StageOutcome

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


def _standing_exit_artifact(config_dir, custody_root) -> None:
    """The operator's standing artifact for this session: the entry action it always carried,
    plus the exit action #960 makes reachable."""
    document = _document(config_dir)
    document["actions"] = [
        {"position_effect": "OPEN", "direction": "LONG", "side": "BUY", "max_uses": 1},
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


def _fill(runtime, server, config_dir, *, odno: str) -> None:
    """Script the broker so the latest ACKed order is fully filled, then poll once."""
    *_, ack = [
        r
        for r in _rows(runtime, "EGRESS_RESULT_CONSUMED")
        if r["egress_result_kind"] == "ACK"
    ]
    qty = Decimal(_sealed(runtime)[-1]["outbound_quantity"])
    date = ack["trading_date"]
    _script_broker(
        server,
        config_dir,
        date,
        [_row(odno=odno, date=date, ord_qty=qty, filled=qty, remaining=Decimal(0))],
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


def _exit_tick(seq: int = 1):
    return fx.crossing_event(seq=seq, close=_EXIT_CLOSE)


def _assert_close_proposal(result) -> None:
    proposal = result.pipeline.proposal
    assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
    assert _verdict(result, CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION).outcome is (
        StageOutcome.ADMIT
    )


# ===========================================================================
# 1. the standing exit boundary: CLOSE-SHORT-SELL matches, and a SELL is sent
# ===========================================================================


def test_a_close_proposal_sells_through_the_standing_exit_boundary(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    _deployed(config_dir, custody_root, server, monkeypatch)
    _standing_exit_artifact(config_dir, custody_root)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    _order_response(server, "0000000102")

    (exit_,) = runtime.run_once((_exit_tick(),))
    _assert_close_proposal(exit_)
    step4 = _verdict(exit_, CommitmentStep.INDEPENDENT_APPROVAL)
    assert step4.outcome is StageOutcome.ADMIT, step4.reason
    (consumed,) = _rows(runtime, "APPROVAL_STANDING_CONSUMED")
    assert consumed["proposal_digest"] == exit_.pipeline.proposal.canonical_digest
    assert len(_standing_uses(runtime)) == 1
    assert exit_.flow.handed_off is True

    # the SELL itself: the MOCK sell TR id on the wire, SELL/CLOSE in the send seal
    assert _tr_ids(server) == [transport["tr_id_sell"]]
    seal = _sealed(runtime)[-1]
    assert seal["outbound_side"] == "SELL"
    assert runtime.construction_stage.attempt.side == "SELL"
    assert runtime.construction_stage.attempt.position_effect == "CLOSE"

    _fill(runtime, server, config_dir, odno="0000000102")
    assert _rcl_releases(runtime) == 1
    _close(runtime)


# ===========================================================================
# 2. the per-proposal boundary: an approved CLOSE sends a SELL, never a BUY
# ===========================================================================


def test_a_per_proposal_approval_of_a_close_sends_a_sell_never_a_buy(
    config_dir, data_dir, custody_root, tmp_path, monkeypatch, server
) -> None:
    """No standing artifact at all: the operator approves this ONE proposal by file. Before
    #960 the approved command was a BUY — the per-proposal path bought a second lot instead
    of closing."""
    _deployed(config_dir, custody_root, server, monkeypatch)
    transport = yaml.safe_load((config_dir / "kis_mock_transport.yaml").read_text())
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    _order_response(server, "0000000103")

    # first pass: the proposal exists, step 4 has no approval to consume, nothing is sent
    event = _exit_tick()
    (pending,) = runtime.run_once((event,))
    _assert_close_proposal(pending)
    assert _verdict(pending, CommitmentStep.INDEPENDENT_APPROVAL).outcome is (
        StageOutcome.UNKNOWN
    )
    assert _tr_ids(server) == []

    construction = runtime.construction_stage.construction
    assert construction is not None and construction.intent is not None
    write_approval_file(
        custody_root,
        proposal_digest=pending.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )

    (approved,) = runtime.run_once((event,))
    _assert_close_proposal(approved)
    assert _verdict(approved, CommitmentStep.INDEPENDENT_APPROVAL).outcome is (
        StageOutcome.ADMIT
    )
    assert approved.flow.handed_off is True
    assert _tr_ids(server) == [transport["tr_id_sell"]]
    assert transport["tr_id_buy"] not in _tr_ids(server)
    assert _sealed(runtime)[-1]["outbound_side"] == "SELL"
    _close(runtime)
