"""Issue #1025 — a FLAT exit's held quantity is the DURABLE entry remainder, end to end.

**The defect.** The kernel's construction rule 4 denies a ``ZERO_POSITION`` proposal that
carries no observed held position (``tos/src/tos/egressgw/construction.py:419-431``), and the
observation the kernel offers step 2 is ``ledger.outstanding_consumed_magnitude`` — a read of
the engine's IN-MEMORY reservation projection (``tos/src/tos/engine/sequencer.py:467``). The
runtime releases that memory reservation the moment the entry fills, because #966's at-most-one
pre-check needs it released before a CLOSE can pass at all. So for every entry that had
ACTUALLY filled, the memory read was ``None``. Two measured consequences on 2026-11-03:

* ``admitted_quantity_bases: ["RISK"]`` denied every FLAT proposal one rule earlier (rule 2) —
  295 step-2 halts on ``cp3-setup-d-long``, 251 on ``cp3-setup-d-short``, 30 on the stock tree;
* admitting ``ZERO_POSITION`` alone would have moved the denial to rule 4 and changed nothing,
  because the held position was still absent. A scope whose entry had filled could neither
  close (step 2) nor open again (step 8), so it sealed itself.

**What this file measures.** ``ProposalShapedConstructionStage`` now hands the kernel stage a
copy of the request whose ``held_position_magnitude`` is
:attr:`~tos_runtime.riskstate.close_bound.EntryCloseBound.remaining` — the same durable source
step 6's CLOSE bound already rests on (#1011/#1015). Every test here drives a real
``compose_paper_runtime`` and asserts either a concrete send or a concrete refusal. **Nothing
below injects a held position**: the lane probe this file replaces had to monkeypatch
``ProvisionalReservationLedger.outstanding_consumed_magnitude`` to get past step 2, and the
absence of that stand-in is the point of the file.

The shipped exit shape is used verbatim: ``decision.kind: FLAT`` with a ``target.kind: FLAT``
that declares NO ``quantity_basis``, exactly as ``setup_d_long.strategy.yaml``'s R2/R3 do, so
the kernel's own :data:`~tos.dsl.FLAT_QUANTITY_BASIS` is what travels.

Hermetic (D1.4): ``tmp_path`` only, no ambient env, no network. The stock test's one double is
the fake KIS server the other kis-mock suites use.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from tos.dsl import FLAT_QUANTITY_BASIS
from tos.engine.vocabulary import CommitmentStep, StageOutcome
from tos.rcl import CapacityState
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose.root import compose_paper_runtime

from . import _fixtures as fx
from . import _symmetry_fixtures as sfx
from .conftest import write_approval_file
from .test_compose_root import _reach_trusted
from .test_synthetic_close_bound_inert import _hand_off_a_filled_entry
from .test_synthetic_venue_ledger_e2e import _close_runtime, _reservations, _rows
from .test_venue_ledger_wiring import turn_the_venue_ledger_on

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

#: Captured at import, BEFORE any test monkeypatches the name, so each entry+exit mapping is
#: built from the real band strategy rather than from itself.
_BAND_ONLY_MAPPING = fx.band_reversion_strategy_mapping

_ENVIRONMENT_LABEL = "non-live-test"


# ===========================================================================
# the config line, the exit rule, and the readers this file asserts through
# ===========================================================================


def admit_the_flat_basis(config_dir: Path) -> Path:
    """Add the kernel's FLAT token to this tree's ``admitted_quantity_bases``.

    The exact edit the three shipped CP-3 trees now carry (#1025, operator approval
    2026-11-03). Written THROUGH the policy document — the same one line an operator writes —
    so no test here can pass by admitting the basis through a route a deployment does not have.
    """
    path = config_dir / "order_construction_policy.yaml"
    text = path.read_text(encoding="utf-8")
    assert 'admitted_quantity_bases: ["RISK"]' in text, text
    path.write_text(
        text.replace(
            'admitted_quantity_bases: ["RISK"]',
            f'admitted_quantity_bases: ["RISK", "{FLAT_QUANTITY_BASIS}"]',
        ),
        encoding="utf-8",
    )
    return path


def _flat_exit_rule(*, direction: str) -> dict[str, Any]:
    """``close > upper_band`` -> go FLAT, in the shipped Setup D R2/R3 shape.

    ``direction`` is the direction of the CLOSING ACTION (``tos/src/tos/dsl/proposal.py::
    build_flat``), so a long tree closes with ``SHORT`` and a short tree with ``LONG``. No
    ``quantity_basis`` is authored: that is what makes the proposal carry ``ZERO_POSITION``.
    """
    rationale = f"close pierced the upper band — FLAT exit ({direction})"
    return {
        "all_of": [
            {
                "left": {"ref": ["capsule", fx.VALUE_NAMESPACE, "close"]},
                "op": "GT",
                "right": {"ref": ["capsule", fx.VALUE_NAMESPACE, "upper_band"]},
            }
        ],
        "decision": {
            "kind": "FLAT",
            "rationale": rationale,
            "target": {
                "kind": "FLAT",
                "account": fx.ACCOUNT,
                "instrument": fx.INSTRUMENT,
                "direction": direction,
                "position_effect": "CLOSE",
                "rationale": rationale,
            },
        },
    }


def _long_entry_flat_exit_mapping() -> dict[str, object]:
    mapping = _BAND_ONLY_MAPPING()
    mapping["policy"]["rules"].append(_flat_exit_rule(direction="SHORT"))  # type: ignore[index]
    return mapping


def _short_entry_flat_exit_mapping() -> dict[str, object]:
    """The mirrored SHORT entry plus a FLAT exit whose closing action is ``LONG`` (-> BUY)."""
    mapping = sfx.mirrored_strategy_mapping()
    mapping["policy"]["rules"].append(_flat_exit_rule(direction="LONG"))  # type: ignore[index]
    return mapping


def _sides(runtime) -> list[str]:
    """Every sealed outbound side this process sent, in order."""
    return [row["send_seal"]["outbound_side"] for row in _rows(runtime, "SEND_SEALED")]


def _step2(result):
    assert result.flow is not None
    (verdict,) = [
        v
        for v in result.flow.verdicts
        if v.step is CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION
    ]
    return verdict


def _derived_quantity(runtime) -> Decimal | None:
    construction = runtime.construction_stage.construction
    assert construction is not None
    quantity: Decimal | None = construction.derivation.quantity
    return quantity


def _boot_synthetic(
    config_dir: Path, data_dir: Path, custody_root: Path, *, construction=None
):
    """A real synthetic boot with the PRODUCTION step-6/7 risk-state service.

    Not ``test_compose_root._compose``: a synthetic CLOSE's step-9 fence is minted from the
    bound the real :class:`~tos_runtime.riskstate.service.RiskStateService` stashes at step 6,
    and with the injected provider that stash never happens (the same reason
    ``test_synthetic_venue_ledger_e2e._boot_with_the_production_risk_service`` gives).
    """
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        _ENVIRONMENT_LABEL,
        construction=fx.construction_config() if construction is None else construction,
        aggregate_risk_inputs_provider=None,
        action_flow_inputs_provider=None,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )


def _approve_and_run(runtime, custody_root: Path, event):
    """Discover, write the operator approval for that exact proposal, then run it for real.

    Returns ``(discovery, result)``; ``result`` is ``None`` when the discovery pass produced no
    intent to approve, which is what a step-2 denial looks like from here.
    """
    (discovery,) = runtime.run_once((event,))
    assert discovery.pipeline is not None and discovery.pipeline.proposal is not None
    construction = runtime.construction_stage.construction
    if construction is None or construction.intent is None:
        return discovery, None
    write_approval_file(
        custody_root,
        proposal_digest=discovery.pipeline.proposal.canonical_digest,
        environment_label=_ENVIRONMENT_LABEL,
        approved_intent_envelope_digest=construction.intent.canonical_digest,
    )
    (result,) = runtime.run_once((event,))
    return discovery, result


def _exit_tick(seq: int):
    return fx.crossing_event(seq=seq, close=fx.UPPER_BAND + 1_000)


# ===========================================================================
# ① the synthetic trees: a FLAT exit sends, fills, and releases BOTH reservations
# ===========================================================================


def test_a_synthetic_long_flat_exit_sends_a_sell_and_releases_both_reservations(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry -> fill -> FLAT exit -> fill, on a LONG tree, with no held-position stand-in.

    Concrete input: a venue-ledger-ON tree whose OCP admits the FLAT basis, a band entry rule
    plus the shipped FLAT exit rule, and two ticks — a crossing entry and an exit above the
    upper band. Concrete result: the exit's command is a **SELL** (closing a long) for the
    entry's own derived quantity, it hands off, its fill nets the venue flat, and BOTH
    reservations end ``RELEASED``.

    Before this change the exit halted at step 2 for all 295 attempts measured on
    ``cp3-setup-d-long-data/A05611``, and the first halt reason was the admitted-set one.
    """
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)

        _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(runtime)
        assert entry_quantity is not None and entry_quantity > 0
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(runtime)

        discovery, exit_ = _approve_and_run(runtime, custody_root, _exit_tick(1))
        proposal = discovery.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert (proposal.position_effect, proposal.direction) == ("CLOSE", "SHORT")
        assert _step2(discovery).outcome is StageOutcome.ADMIT, _step2(discovery).reason
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail

        # The exit's size IS the entry's remainder — the structural derivation, not a budget.
        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["BUY", "SELL"], _sides(runtime)

        for _ in range(3):
            runtime.run_once(())
        after = _reservations(runtime)
        assert len(after) == 2, after
        assert {state for _id, state in after} == {CapacityState.RELEASED}, after
    finally:
        _close_runtime(runtime)


def test_a_synthetic_short_flat_exit_sends_a_buy_and_releases_both_reservations(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The long/short symmetry half: a SHORT tree's FLAT exit must be a **BUY**.

    Same sequence as the LONG test on the mirrored tree. The shipped SHORT tree's OCP binds
    ``DIRECTION: SHORT`` (``cp3-setup-d-short/order_construction_policy.yaml``), which is what
    selects the ``CLOSE.SHORT`` = BUY arm; the shared fixture binds ``LONG``, so this test
    flips that one axis the way the committed tree has it.
    """
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _short_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    ocp = config_dir_with_risk_state / "order_construction_policy.yaml"
    text = ocp.read_text(encoding="utf-8")
    long_axis = '- axis: "DIRECTION"\n        value: "LONG"'
    assert text.count(long_axis) == 1, text
    ocp.write_text(
        text.replace(long_axis, '- axis: "DIRECTION"\n        value: "SHORT"'),
        encoding="utf-8",
    )
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(
        config_dir_with_risk_state,
        data_dir,
        custody_root,
        construction=sfx.mirrored_construction_config(),
    )
    try:
        _reach_trusted(runtime)

        _, entry = _approve_and_run(runtime, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(runtime)
        for _ in range(3):
            runtime.run_once(())
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(runtime)

        discovery, exit_ = _approve_and_run(runtime, custody_root, _exit_tick(1))
        proposal = discovery.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert (proposal.position_effect, proposal.direction) == ("CLOSE", "LONG")
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail
        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["SELL", "BUY"], _sides(runtime)

        for _ in range(3):
            runtime.run_once(())
        after = _reservations(runtime)
        assert len(after) == 2, after
        assert {state for _id, state in after} == {CapacityState.RELEASED}, after
    finally:
        _close_runtime(runtime)


# ===========================================================================
# ① the stock (kis-mock) transport
# ===========================================================================


@pytest.fixture()
def server():
    from ..transport.kis_mock._fake_kis_server import FakeKisServer

    instance = FakeKisServer()
    instance.start()
    try:
        yield instance
    finally:
        instance.stop()


def test_the_stock_transport_sends_the_flat_exit_through_the_standing_boundary(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    server,
) -> None:
    """The stock tree's transport: entry ACK -> fill -> FLAT exit ACK, over the fake KIS server.

    Concrete input: the kis-mock deployment, the operator's standing session artifact for this
    session (one OPEN/LONG/BUY use and one CLOSE/SHORT/SELL use), the FLAT exit strategy, and
    two ticks. Concrete result: the exit's command is built as the standing artifact's exit row
    expects and the order POSTs — the row that #960's CLI note said "cannot match".

    On this transport the FLAT quantity is bounded TWICE: step 2 takes the durable entry
    remainder, and step 6 still caps it by the broker's own holding proof
    (``tos_runtime/riskstate/service.py::_broker_close_effect``, #1012 L3). That second bound is
    measured against the real ``BROKER_HELD_PROOF`` path in
    ``test_kis_mock_close_risk_e2e.py``; this test's step 6 uses this suite's synthetic risk
    inputs, which is why its boot wrapper supplies the step-9 CLOSE fence.
    """
    from .test_close_proposal_e2e import (
        _boot,
        _Broker,
        _entry_tick,
        _order_response,
        _standing_cycle_artifact,
    )
    from .test_kis_mock_fill_finality_e2e import _close, _deploy

    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    _deploy(config_dir, custody_root, server, monkeypatch)
    _standing_cycle_artifact(config_dir, custody_root)
    admit_the_flat_basis(config_dir)
    runtime = _boot(tmp_path, config_dir, data_dir, custody_root)
    broker = _Broker(server, config_dir)
    try:
        _order_response(server, "0000000201")
        (entry,) = runtime.run_once((_entry_tick(),))
        assert entry.flow is not None and entry.flow.handed_off is True
        entry_quantity = _derived_quantity(runtime)
        assert entry_quantity is not None and entry_quantity > 0
        broker.fill(runtime, odno="0000000201")

        _order_response(server, "0000000202")
        (exit_,) = runtime.run_once((_exit_tick(1),))
        proposal = exit_.pipeline.proposal
        assert proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert _step2(exit_).outcome is StageOutcome.ADMIT, _step2(exit_).reason
        assert (
            exit_.flow is not None and exit_.flow.handed_off is True
        ), exit_.flow.detail
        assert _derived_quantity(runtime) == entry_quantity
        assert _sides(runtime) == ["BUY", "SELL"], _sides(runtime)
    finally:
        _close(runtime)


# ===========================================================================
# ⑥ and ③ the refusals — step 2 denies with the kernel's own reason, and nothing is sent
# ===========================================================================

#: The kernel's rule-4 denial (``tos/src/tos/egressgw/construction.py:421-426``). Pinned as a
#: fragment so a refusal that happened for ANOTHER reason (an unadmitted basis, a missing
#: price) cannot pass as this one — the two tests below are about the held position alone.
_NO_HELD_POSITION = "closes a position but no held position was observed"


def test_a_flat_proposal_on_a_flat_scope_is_refused_at_step_2_and_sends_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No position, so nothing to close: the SAME outcome as before #1025, a different reason.

    Concrete input: a tree that admits the FLAT basis, driven with the exit tick FIRST so no
    entry ever existed. Concrete result: step 2 DENIES naming the absent held position (not the
    admitted set), the flow never reaches the send boundary, and no order was sealed.
    """
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        (result,) = runtime.run_once((_exit_tick(0),))
        assert result.pipeline is not None and result.pipeline.proposal is not None
        assert result.pipeline.proposal.quantity_basis == FLAT_QUANTITY_BASIS
        verdict = _step2(result)
        assert verdict.outcome is StageOutcome.DENY, verdict.reason
        assert _NO_HELD_POSITION in (verdict.reason or ""), verdict.reason
        assert result.flow is not None and result.flow.handed_off is not True
        assert _sides(runtime) == []
        assert _reservations(runtime) == []
    finally:
        _close_runtime(runtime)


def test_an_uncorroborated_entry_fill_refuses_the_flat_exit_and_sends_nothing(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The venue-ledger-OFF tree — every shipped tree today — still refuses the exit.

    Concrete input: the same entry+FLAT-exit strategy with the admitted basis, but WITHOUT
    ``finality.yaml::witness: synthetic_venue_ledger``. The entry hands off and its synthetic
    fill is recorded, yet the release is held with ``WITNESS_NOT_INDEPENDENT``, so the
    reservation stays ``COMMITTED_UNBOUND`` and
    :meth:`~tos_runtime.riskstate.close_bound.DurableEntryCloseBoundReader.read` refuses with
    ``ENTRY_NOT_SOLE_CONSUMED_POSITION``. Concrete result: step 2 denies for the absent held
    position and the exit sends nothing — a refused durable bound is never a permissive
    fallback to the memory read.

    This is the reachable instance of "no proven entry": the fix must not open a send path on a
    tree whose own fill was never independently corroborated.
    """
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)
    runtime = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(runtime)
        _hand_off_a_filled_entry(runtime, custody_root)
        assert [state for _id, state in _reservations(runtime)] == [
            CapacityState.COMMITTED_UNBOUND
        ], _reservations(runtime)
        held = _rows(runtime, "CAPACITY_RELEASE_HELD")
        assert [row["reason"] for row in held] == ["WITNESS_NOT_INDEPENDENT"], held

        sealed_before = len(_sides(runtime))
        (result,) = runtime.run_once((_exit_tick(1),))
        verdict = _step2(result)
        assert verdict.outcome is StageOutcome.DENY, verdict.reason
        assert _NO_HELD_POSITION in (verdict.reason or ""), verdict.reason
        assert len(_sides(runtime)) == sealed_before
    finally:
        _close_runtime(runtime)


# ===========================================================================
# ⑤ a restart: the FLAT passes with the same quantity, on a fresh memory ledger
# ===========================================================================


def test_a_restart_after_the_entry_fill_sizes_the_flat_from_the_durable_entry(
    config_dir_with_risk_state: Path,
    data_dir: Path,
    custody_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The evidence that step 2 no longer depends on the in-memory ledger at all.

    Concrete input: a corroborated entry handed off and filled in process A, then process A is
    closed and process B boots on the SAME config/data/custody directories and is driven with
    the exit tick. Process B's engine has never seen a reservation, so the kernel's own
    ``outstanding_consumed_magnitude`` observation is ``None`` there no matter what the fill
    did. Concrete result: the FLAT exit still passes step 2 and derives the SAME quantity
    process A's entry did, and it hands off.
    """
    monkeypatch.setattr(
        fx, "band_reversion_strategy_mapping", _long_entry_flat_exit_mapping
    )
    turn_the_venue_ledger_on(config_dir_with_risk_state)
    admit_the_flat_basis(config_dir_with_risk_state)
    fx.write_band_strategy_file(config_dir_with_risk_state)

    first = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(first)
        _, entry = _approve_and_run(first, custody_root, fx.crossing_event(seq=0))
        assert entry is not None and entry.flow is not None
        assert entry.flow.handed_off is True, entry.flow.detail
        entry_quantity = _derived_quantity(first)
        assert entry_quantity is not None and entry_quantity > 0
        for _ in range(3):
            first.run_once(())
        assert [state for _id, state in _reservations(first)] == [
            CapacityState.POSITION_CONSUMED
        ], _reservations(first)
    finally:
        _close_runtime(first)

    second = _boot_synthetic(config_dir_with_risk_state, data_dir, custody_root)
    try:
        _reach_trusted(second)
        discovery, exit_ = _approve_and_run(second, custody_root, _exit_tick(1))
        assert discovery.pipeline.proposal.quantity_basis == FLAT_QUANTITY_BASIS
        assert _step2(discovery).outcome is StageOutcome.ADMIT, _step2(discovery).reason
        assert _derived_quantity(second) == entry_quantity
        assert exit_ is not None and exit_.flow is not None
        assert exit_.flow.handed_off is True, exit_.flow.detail
        assert _sides(second)[-1] == "SELL", _sides(second)
    finally:
        _close_runtime(second)
