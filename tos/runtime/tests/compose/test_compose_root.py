"""Runtime end-to-end tests for :mod:`tos_runtime.compose` (slice plan §4"""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass
from tos_runtime.calendar.ports import FixedWallClockReference, WallClockReference
from tos_runtime.compose._attempt_arm import attempt_position_effect
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose.root import (
    ReleaseAdmissionRefused,
    compose_paper_runtime,
)
from tos_runtime.rcl.log import CommitLogCorruption
from tos_runtime.rcl.reservation_identity import permit_reservation_id
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.strategy.bindings import STRATEGY_BINDINGS_FILE_NAME
from tos_runtime.strategy.resolve import StrategyRegistryResolutionRefused
from tos_runtime.time.sources import MonotonicSource

from . import _fixtures as fx
from .conftest import approve_constructed_intent

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class FakeMonotonicSource:
    """A controllable monotonic-clock double (test-only). Compose's own"""

    def __init__(self, start: int = 1_000_000) -> None:
        self.next_value = start
        self._step = 10

    def now_ms(self) -> int:
        value = self.next_value
        self.next_value += self._step
        return value

    def force_regression(self) -> None:
        self.next_value = 1


def _aggregate_inputs(request) -> AggregateRiskDecisionInputs | None:
    from tos.are import RiskScopeKind

    return AggregateRiskDecisionInputs(
        cells=fx.adverse_scenario_cells(),
        required_scenario_kinds=frozenset(
            {"ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ"}  # type: ignore[arg-type]
        ),
        applicable_risk_scopes=("ACCOUNT",),
        all_fields_attributed=None,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        numerically_safe=True,
        valuation_ok=True,
        injected_envelope_max=fx.aggregate_risk_effective_limit(),
        limit_source_is_injected_envelope=None,
        effective_limit=fx.aggregate_risk_effective_limit(),
    )


class _LiveRuntimeFacts:
    """Late-bound handle to the two LIVE facts this suite's step-7 inputs provider needs."""

    def __init__(self) -> None:
        self.runtime: Any = None

    def rcl_tip(self) -> int:
        """The RCL log's own current tip — exactly what ``_rcl_tip_generation_provider`` reads."""
        if self.runtime is None:
            return 0
        log = self.runtime.rcl_log
        view = log.read_linearizable(writer_epoch=log.current_epoch())
        return 0 if view.last_seq is None else view.last_seq

    def position_effect(self) -> str | None:
        """The position effect of the arm step 2 selected for the attempt under judgement."""
        if self.runtime is None:
            return None
        return attempt_position_effect(self.runtime.construction_stage)


def _action_flow_inputs_for(
    facts: _LiveRuntimeFacts,
) -> Callable[[Any], ActionFlowDecisionInputs | None]:
    """Bind :func:`_action_flow_inputs` to ``facts`` (see :class:`_LiveRuntimeFacts`)."""
    return lambda request: _action_flow_inputs(request, facts)


def _action_flow_inputs(
    request, facts: _LiveRuntimeFacts | None = None
) -> ActionFlowDecisionInputs | None:
    from tos.afg import (
        ActionCause,
        ActionClassKind,
        ActionFlowScopeKind,
        ActionFlowStateSnapshot,
        ObservedAmplification,
        ScopeIndependenceEvidence,
    )

    facts = _LiveRuntimeFacts() if facts is None else facts
    rcl_tip = facts.rcl_tip()
    action_class = (
        ActionClassKind.ORDINARY_REDUCE_OR_EXIT
        if facts.position_effect() == "CLOSE"
        else ActionClassKind.NORMAL_NEW_RISK
    )
    scope = ActionFlowScopeKind.ACCOUNT
    snapshot = ActionFlowStateSnapshot(
        snapshot_id=f"afg-snap-compose-{rcl_tip}",
        snapshot_generation=rcl_tip,
        consistency_cut_identity=f"afg-cut-compose-{rcl_tip}",
        covered_scopes=(scope,),
        scope_independence=(
            ScopeIndependenceEvidence(
                scope=scope,
                allocation_separated=True,
                refill_separated=True,
                broker_enforcement_separated=True,
                credential_session_state_separated=True,
                failure_domain_separated=True,
                final_route_separated=True,
                basis_is_local_counter_only=False,
                basis_is_scheduler_priority_only=False,
            ),
        ),
    )
    cause = ActionCause(
        root_cause_identity="cause-compose-1",
        parent_lineage=("cause-compose-0",),
        lineage_attested=True,
        cyclic=False,
        forked_beyond_bound=False,
        inconsistent=False,
    )
    observed = ObservedAmplification(
        fan_out=1,
        depth=1,
        attempts=1,
        mutations=1,
        queries=1,
        queue_depth=1,
        in_flight=1,
        elapsed_monotonic=Decimal(1),
        duplicate_redelivery_expansion=0,
        failover_reconnect_replay_expansion=0,
        amplification_per_cause=Decimal(1),
        duplicate_event_created_new_allowance=False,
        envelope_reset_on_duplicate=False,
        concurrent_consumers_share_one_envelope=True,
    )
    return ActionFlowDecisionInputs(
        cause=cause,
        snapshot=snapshot,
        required_scopes=frozenset({scope}),
        producer_self_declared_scope=False,
        observed_amplification=observed,
        requested_limit=fx.action_flow_requested_limit(),
        injected_envelope_max=fx.action_flow_envelope_max(),
        limit_source_is_injected_envelope=None,
        economic_ref="economic-ref-compose-1",
        flow_vector=fx.action_flow_requested_limit(),
        committed_flow_vectors=(),
        hard_limit=fx.action_flow_envelope_max(),
        runtime_limit=fx.action_flow_envelope_max(),
        economic_commitment_exclusive=None,
        flow_commitment_exclusive=None,
        generation_current=False,
        applicable_action_flow_scopes=("ACCOUNT",),
        decision_generation=rcl_tip,
        action_class=action_class,
        cause_digest="cause-compose-1-digest",
    )


def _compose(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    *,
    monotonic_source: MonotonicSource | None = None,
    transport_kind: TransportKind = TransportKind.SYNTHETIC,
    wall_clock: WallClockReference | None = None,
):
    """Composes via the FILE strategy source (TOS Phase 3 슬라이스 D-R"""
    fx.write_band_strategy_file(config_dir)
    facts = _LiveRuntimeFacts()
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs_for(facts),
        monotonic_source=monotonic_source,
        transport_kind=transport_kind,
        wall_clock=(
            wall_clock
            if wall_clock is not None
            else FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS)
        ),
    )
    facts.runtime = runtime
    return runtime


def _reach_trusted(runtime) -> None:
    """Compose itself already runs two ``evaluate()`` cycles at boot"""
    assert runtime.time_service.health_state.value == "TRUSTED"


def _write_rearm_approval(
    custody_root: Path,
    latched_evidence_seq: int,
    *,
    environment_label: str = "non-live-test",
    approvals: list[dict[str, str]] | None = None,
    mode: int = 0o600,
) -> Path:
    """Write one ``approvals/rearm/<latched_evidence_seq>.yaml`` operator decision file"""
    import os

    if approvals is None:
        approvals = [{"principal_id": "alice", "decision": "APPROVE"}]
    path = custody_root / "approvals" / "rearm" / f"{latched_evidence_seq}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "environment_label": environment_label,
                "latched_evidence_seq": latched_evidence_seq,
                "approvals": approvals,
            },
            sort_keys=False,
        )
    )
    os.chmod(path, mode)
    return path


def _reach_new_risk_halt_via_cancel_crossing_fill(runtime, custody_root: Path) -> int:
    """Drive the SAME cancel-crossing-fill scenario as ``TestRecomposeReplay"""
    from decimal import Decimal

    from tos.engine.records import EgressResultPayload, EngineEvent
    from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition

    event = fx.crossing_event()
    results = runtime.run_once((event,))
    proposal_digest = results[0].pipeline.proposal.canonical_digest
    assert proposal_digest is not None
    approve_constructed_intent(
        runtime,
        custody_root,
        proposal_digest=proposal_digest,
    )
    results2 = runtime.run_once((event,))
    assert results2[0].flow is not None and results2[0].flow.handed_off is True
    attempt_id = results2[0].flow.attempt.attempt_id

    def _egress_result(kind: EgressResultKind, **magnitudes: Decimal) -> EngineEvent:
        return EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload.model_validate(
                {
                    "instrument_key": fx.instrument_key(),
                    "attempt_id": attempt_id,
                    "kind": kind,
                    **magnitudes,
                }
            ),
        )

    cancel_result = runtime.driver.enqueue_and_run(
        _egress_result(EgressResultKind.CANCEL_ACK)
    )
    assert cancel_result.result_disposition is ResultDisposition.APPLIED

    late_fill_result = runtime.driver.enqueue_and_run(
        _egress_result(
            EgressResultKind.FULL_FILL,
            filled_quantity=Decimal("1"),
            remaining_quantity=Decimal("0"),
        )
    )
    assert (
        late_fill_result.result_disposition
        is ResultDisposition.NON_MONOTONIC_PROJECTION
    )

    halt = runtime.inbox.new_risk_halt()
    assert halt is not None
    evidence_seq = halt["evidence_seq"]
    assert isinstance(evidence_seq, int)
    return evidence_seq


def _write_approval_for_crossing(custody_root: Path) -> None:
    strategy_registry, strategy = fx.registry_with_band_strategy()
    del strategy_registry


def test_both_a_strategies_directory_and_an_injected_registry_refuses(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """TOS Phase 3 슬라이스 D-R ``[D-R-2]`` brief item 4: keep ONE refusal"""
    fx.write_band_strategy_file(config_dir)
    injected_registry = fx.registry_with_band_strategy()[0]
    with pytest.raises(StrategyRegistryResolutionRefused):
        compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs,
            registry=injected_registry,
        )


def test_neither_strategy_source_refuses_by_default(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """2026-09-09 independent-review finding #8, threaded end-to-end:"""
    with pytest.raises(StrategyRegistryResolutionRefused):
        compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs,
        )


def test_neither_strategy_source_with_allow_no_strategies_boots_empty(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """The stated-choice opt-out: ``allow_no_strategies=True`` boots"""
    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        allow_no_strategies=True,
    )
    assert runtime.registry.declared_keys() == ()
    runtime.rcl_log.close()
    runtime.evidence_store.close()


class TestComposeRootWiring:
    """Scenario-adjacent smoke coverage: composition succeeds, and every"""

    def test_compose_succeeds_and_wires_every_lane(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        assert runtime.release_admitted is True
        assert runtime.writer_epoch >= 1
        assert runtime.rcl_log.current_epoch() == runtime.writer_epoch
        assert runtime.evidence_store.key_generation == 1
        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_intent_registry_is_wired_with_the_runtime_time_service(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Kernel round #1 §2.2 re-review finding #3 (MEDIUM): before this"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        # noqa: SLF001 -- wiring proof, see this test's own docstring
        assert runtime.intent_registry._time is runtime.time_service
        assert runtime.intent_registry._time_config is runtime.time_service._config
        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_operator_attested_inputs_record_lists_exactly_the_attested_set(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Re-review reviewer Q3 / finding F4 (2026-09-08): compose must"""
        import json

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            ("OPERATOR_ATTESTED_INPUTS",),
        ).fetchall()
        assert len(rows) == 1
        stored = json.loads(rows[0][0])
        names = {c["name"] for c in stored["payload"]["attested_coordinates"]}
        assert names == {
            "monitor_coverage.yaml",
            "SYNTHETIC_FUTURES_ORDER",
            "numerically_safe",
            "valuation_ok",
            "all_fields_attributed",
            "limit_source_is_injected_envelope",
            "economic_commitment_exclusive",
            "flow_commitment_exclusive",
            "endpoint",
            "action",
            "method",
            "route_identity",
            "credential_generation",
            "broker_session_generation",
            "egress_generation",
            "active_principal",
            "capsule_terminus_fields",
            fx.BAND_STRATEGY_FILE_NAME,
        }
        for coordinate in stored["payload"]["attested_coordinates"]:
            assert coordinate["source_file"] in (
                "risk_attestations.yaml",
                "egress_coordinates.yaml",
                "broker_scopes.yaml",
                "monitor_coverage.yaml",
                fx.BAND_STRATEGY_FILE_NAME,
            )
            assert len(coordinate["source_file_digest"]) == 64

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_operator_attested_inputs_record_includes_bindings_file_when_present(
        self, config_dir: Path, data_dir: Path, custody_root: Path
    ) -> None:
        """TOS Phase 3 슬라이스 D-R ``[D-R-3c]``: when ``config_dir/"""
        import json

        fx.write_band_strategy_file(config_dir)
        bindings_path = config_dir / STRATEGY_BINDINGS_FILE_NAME
        bindings_path.write_text(
            yaml.safe_dump(
                {
                    "strategies": {
                        "band.strategy": {
                            "config_binding_version": "cfg-bind-compose",
                            "bindings": {},
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=_aggregate_inputs,
            action_flow_inputs_provider=_action_flow_inputs,
        )
        rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            ("OPERATOR_ATTESTED_INPUTS",),
        ).fetchall()
        assert len(rows) == 1
        stored = json.loads(rows[0][0])
        coordinates = stored["payload"]["attested_coordinates"]
        bindings_rows = [
            c for c in coordinates if c["source_file"] == STRATEGY_BINDINGS_FILE_NAME
        ]
        assert len(bindings_rows) == 1
        assert len(bindings_rows[0]["source_file_digest"]) == 64
        assert (
            bindings_rows[0]["source_file_digest"]
            == hashlib.sha256(bindings_path.read_bytes()).hexdigest()
        )

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestSyntheticEventDrivesTheChain:
    """Scenario 1: a synthetic event drives the real service chain."""

    def test_steps_one_to_three_admit_for_real(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Steps 1-3 (registry dispatch through venue construction) are"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        assert len(results) == 1
        result = results[0]

        assert result.pipeline is not None
        assert result.pipeline.proposal is not None
        assert result.flow is not None

        verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
        assert "INDEPENDENT_APPROVAL" in verdict_by_step
        assert verdict_by_step["INDEPENDENT_APPROVAL"].outcome.value == "UNKNOWN"
        assert runtime.transport.requests == ()

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_engine_steps_admit_for_real_and_reach_the_transport(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """The full picture behind scenario 1's acceptance criterion."""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        assert len(results) == 1
        result = results[0]

        assert result.pipeline is not None
        assert result.pipeline.proposal is not None
        assert result.flow is not None

        proposal_digest = result.pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )

        results2 = runtime.run_once((event,))
        result2 = results2[0]
        flow = result2.flow
        assert flow is not None

        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        for step_name in (
            "INDEPENDENT_APPROVAL",
            "AGGREGATE_RISK_DECISION",
            "ACTION_FLOW_DECISION",
            "LEDGER_VERIFICATION",
        ):
            assert step_name in verdict_by_step, (
                f"step {step_name} produced no verdict at all: "
                f"{sorted(verdict_by_step)}"
            )
            assert (
                verdict_by_step[step_name].outcome.value == "ADMIT"
            ), f"step {step_name}: {verdict_by_step[step_name].reason}"

        assert len(runtime.transport.requests) == 1

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_admitted_consumption_evidence_carries_a_real_receipt_anchor(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Kernel round #1 §2.2 re-review finding #3 (MEDIUM): before this"""
        import json

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )

        results2 = runtime.run_once((event,))
        flow = results2[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        assert verdict_by_step["INDEPENDENT_APPROVAL"].outcome.value == "ADMIT"

        rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'IAP_CONSUMPTION'"
        ).fetchall()
        assert len(rows) == 1
        payload = json.loads(rows[0][0])["payload"]
        assert payload["expiry_verdict"] == "NOT_CONFIGURED"
        assert payload["receipt_anchor"] is not None

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_one_synthetic_transport_handoff(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Scenario 1's literal acceptance criterion: exactly one synthetic"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )
        runtime.run_once((event,))
        assert len(runtime.transport.requests) == 1


class TestStandInZero:
    """Scenario 2: no ``NON_AUTHORITATIVE_PROVISIONAL`` verdict for steps"""

    def test_no_provisional_stand_in_verdicts_for_the_realized_steps(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        results = runtime.run_once((fx.crossing_event(),))
        flow = results[0].flow
        assert flow is not None
        realized_steps = {
            "INDEPENDENT_APPROVAL",
            "AGGREGATE_RISK_DECISION",
            "ACTION_FLOW_DECISION",
            "LEDGER_VERIFICATION",
            "ATOMIC_COMMIT",
            "COMMITMENT_UNAVAILABILITY",
            "ATTEMPT_BIND_VERIFICATION",
            "TRANSMISSION_CAPABILITY",
        }
        offending = [
            verdict
            for verdict in flow.verdicts
            if verdict.step.value in realized_steps
            and verdict.authority_class
            is StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL
        ]
        assert offending == []
        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestRecomposeReplay:
    """Scenario 3: re-compose over the same data_dir (simulated restart)."""

    def test_recompose_replays_identically(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        runtime.run_once((fx.crossing_event(),))
        pre_reservations = dict(runtime.risk_service._projection.all_reservations())
        runtime.rcl_log.verify_replay()
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime2.rcl_log.verify_replay()
        post_reservations = dict(runtime2.risk_service._projection.all_reservations())
        assert post_reservations == pre_reservations

        assert runtime2.evidence_store.verify(
            {1: (custody_root / "evidence.key.1").read_bytes()}
        )
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

    def test_recompose_after_a_real_hand_off_does_not_diverge(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Independent review finding #1 (2026-09-09), RED before the fix."""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )
        results2 = runtime.run_once((event,))
        assert results2[0].flow is not None and results2[0].flow.handed_off is True
        assert len(runtime.transport.requests) == 1
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

        runtime3 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime3.rcl_log.close()
        runtime3.evidence_store.close()

    def test_replay_does_not_re_execute_real_stages_across_a_reboot(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Independent review finding #2 (2026-09-09), RED before the fix — the #2 claim"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )
        results2 = runtime.run_once((event,))
        assert results2[0].flow is not None and results2[0].flow.handed_off is True

        watched_kinds = (
            "IAP_CONSUMPTION",
            "ARE_DECISION",
            "AFG_DECISION",
            "ARE_SNAPSHOT",
        )

        def _counts(store, kinds: tuple[str, ...]) -> dict[str, int]:
            return {
                kind: store.connection.execute(
                    "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
                ).fetchone()[0]
                for kind in kinds
            }

        before_reboot = _counts(runtime.evidence_store, watched_kinds)
        rcl_append_before = _counts(runtime.evidence_store, ("RCL_APPEND",))[
            "RCL_APPEND"
        ]
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        after_reboot = _counts(runtime2.evidence_store, watched_kinds)
        rcl_append_after = _counts(runtime2.evidence_store, ("RCL_APPEND",))[
            "RCL_APPEND"
        ]
        assert after_reboot == before_reboot, (
            f"boot-time replay re-executed a real stage's own evidence sink: "
            f"before={before_reboot} after={after_reboot}"
        )
        assert rcl_append_after == rcl_append_before + 1, (
            "RCL_APPEND should only ever gain the ordinary per-boot writer-epoch bump (+1), "
            f"never a replay-driven duplicate: before={rcl_append_before} "
            f"after={rcl_append_after}"
        )
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

    def test_recompose_after_a_coordinator_gate_refusal_does_not_diverge(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Independent review finding #1, WAVE 2 (2026-09-09, lane C-R2), RED before the fix."""
        from tos_runtime.rcl.log import SqliteCommitLog

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        usurper = SqliteCommitLog(
            runtime.rcl_log.path, evidence_port=runtime.evidence_store
        )
        usurper.acquire_epoch(runtime.identity)
        try:
            event = fx.crossing_event()
            results = runtime.run_once((event,))
            assert results[0].halt_reason is not None
            assert results[0].halt_reason.value == "AUTHORITY_NOT_CURRENT"
            assert results[0].outcome_digest is None
        finally:
            usurper.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

        runtime3 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime3.rcl_log.close()
        runtime3.evidence_store.close()

    def test_recompose_after_a_new_risk_latch_does_not_diverge(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Re-review finding R1 (2026-09-09), RED before the fix."""
        from decimal import Decimal

        from tos.engine.records import EgressResultPayload, EngineEvent
        from tos.engine.vocabulary import EgressResultKind, EventKind, ResultDisposition
        from tos_runtime.engine.orthostate_projection import (
            NEW_RISK_HALTED_BY_COUPLING_VIOLATION,
        )

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )
        results2 = runtime.run_once((event,))
        assert results2[0].flow is not None and results2[0].flow.handed_off is True
        attempt_id = results2[0].flow.attempt.attempt_id

        def _egress_result(
            kind: EgressResultKind, **magnitudes: Decimal
        ) -> EngineEvent:
            return EngineEvent(
                kind=EventKind.EGRESS_RESULT,
                egress_result=EgressResultPayload.model_validate(
                    {
                        "instrument_key": fx.instrument_key(),
                        "attempt_id": attempt_id,
                        "kind": kind,
                        **magnitudes,
                    }
                ),
            )

        cancel_result = runtime.driver.enqueue_and_run(
            _egress_result(EgressResultKind.CANCEL_ACK)
        )
        assert cancel_result.result_disposition is ResultDisposition.APPLIED

        late_fill_result = runtime.driver.enqueue_and_run(
            _egress_result(
                EgressResultKind.FULL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("0"),
            )
        )
        assert (
            late_fill_result.result_disposition
            is ResultDisposition.NON_MONOTONIC_PROJECTION
        )

        halt = runtime.inbox.new_risk_halt()
        assert halt is not None
        assert halt["reason"] == NEW_RISK_HALTED_BY_COUPLING_VIOLATION
        coupling_violation_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'COUPLING_VIOLATION'"
        ).fetchone()[0]
        assert coupling_violation_rows == 1

        refused_tick = runtime.driver.enqueue_and_run(fx.crossing_event(seq=99))
        assert NEW_RISK_HALTED_BY_COUPLING_VIOLATION in (refused_tick.detail or "")
        assert refused_tick.outcome_digest is None

        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

        runtime3 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime3.rcl_log.close()
        runtime3.evidence_store.close()


class TestNonTrustedTimeBlocksNewRisk:
    """Scenario 4: forcing the time snapshot non-TRUSTED => zero transport"""

    def test_untrusted_time_yields_zero_transport_calls(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        clock = FakeMonotonicSource()
        runtime = _compose(
            tmp_path, config_dir, data_dir, custody_root, monotonic_source=clock
        )
        _reach_trusted(runtime)

        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
        )

        clock.force_regression()
        runtime.time_service.evaluate()
        assert runtime.time_service.health_state.value != "TRUSTED"

        results = runtime.run_once((event,))
        flow = results[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        assert verdict_by_step["AGGREGATE_RISK_DECISION"].outcome.value == "UNKNOWN"
        assert "ACTION_FLOW_DECISION" not in verdict_by_step
        assert (
            flow.halt_step is not None
            and flow.halt_step.value == "AGGREGATE_RISK_DECISION"
        )
        assert runtime.transport.requests == ()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestStaleGenerationProviderYieldsUnknown:
    """Re-review finding F2 (2026-09-08): step 6 (``AggregateRiskDecisionStage``)"""

    def test_stale_writer_epoch_yields_unknown_not_a_decision_at_generation_zero(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        from tos.engine.records import InstrumentKey, StageRequest
        from tos.engine.vocabulary import CommitmentStep
        from tos_runtime.compose._wiring import _rcl_tip_generation_provider
        from tos_runtime.rcl.log import SqliteCommitLog
        from tos_runtime.risk.ledger_stages import AggregateRiskDecisionStage

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None

        second = SqliteCommitLog(
            runtime.rcl_log.path, evidence_port=runtime.evidence_store
        )
        try:
            second.acquire_epoch(runtime.identity)
            stale_provider = _rcl_tip_generation_provider(
                runtime.rcl_log, runtime.writer_epoch
            )
            stage = AggregateRiskDecisionStage(
                runtime.risk_service,
                inputs_provider=_aggregate_inputs,
                snapshot_generation_provider=stale_provider,
                decision_generation_provider=stale_provider,
                time_permits_new_risk=lambda: True,
            )
            request = StageRequest(
                step=CommitmentStep.AGGREGATE_RISK_DECISION,
                instrument_key=InstrumentKey(
                    account=fx.ACCOUNT, instrument=fx.INSTRUMENT
                ),
                proposal=first.pipeline.proposal,
            )
            verdict = stage(request)
            assert verdict.outcome.value == "UNKNOWN"
        finally:
            second.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestPermitPathStaleGenerationProviderYieldsUnknown:
    """Addendum A to the re-review (2026-09-08): a stale/unreachable RCL log"""

    def test_stale_writer_epoch_on_permit_path_yields_unknown_zero_appends(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import sqlite3

        from tos.afg import ActionFlowResult
        from tos.engine.records import InstrumentKey, StageRequest
        from tos.engine.vocabulary import CommitmentStep
        from tos.rcl import CapacityComponent, CapacityVector
        from tos_runtime.compose._wiring import _rcl_tip_generation_provider
        from tos_runtime.compose.context import make_permit_provider
        from tos_runtime.rcl.log import SqliteCommitLog
        from tos_runtime.risk.ledger_stages import AtomicCommitStage

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
        )
        runtime.run_once((event,))
        assert runtime.flow_governor.last_decision is not None
        assert runtime.flow_governor.last_decision.result is ActionFlowResult.GRANT

        rows_before = (
            sqlite3.connect(str(runtime.rcl_log.path))
            .execute("SELECT COUNT(*) FROM entries")
            .fetchone()[0]
        )

        second = SqliteCommitLog(
            runtime.rcl_log.path, evidence_port=runtime.evidence_store
        )
        try:
            second.acquire_epoch(runtime.identity)
            stale_provider = _rcl_tip_generation_provider(
                runtime.rcl_log, runtime.writer_epoch
            )
            permit_provider = make_permit_provider(
                runtime.flow_governor,
                permit_generation_provider=stale_provider,
                command_identity_provider=lambda request: (
                    request.proposal.canonical_digest or ""
                ),
            )
            stage = AtomicCommitStage(
                runtime.rcl_log,
                writer_epoch=runtime.writer_epoch,
                permit_provider=permit_provider,
                reservation_id_provider=lambda request, permit: permit_reservation_id(
                    request.instrument_key.account,
                    request.instrument_key.instrument,
                    permit.permit_id or "",
                ),
                time_permits_new_risk=lambda: True,
                effect_envelope_reader=lambda: CapacityVector(
                    components=(
                        CapacityComponent(
                            dimension_id="notional", magnitude=Decimal(1)
                        ),
                    )
                ),
            )
            request = StageRequest(
                step=CommitmentStep.ATOMIC_COMMIT,
                instrument_key=InstrumentKey(
                    account=fx.ACCOUNT, instrument=fx.INSTRUMENT
                ),
                proposal=first.pipeline.proposal,
            )
            verdict = stage(request)
            assert verdict.outcome.value == "UNKNOWN"
        finally:
            second.close()

        rows_after = (
            sqlite3.connect(str(runtime.rcl_log.path))
            .execute("SELECT COUNT(*) FROM entries")
            .fetchone()[0]
        )
        assert rows_after == rows_before

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestActionFlowWrapperStaleGenerationProviderYieldsUnknown:
    """Addendum A, step 7 half (2026-09-08): a stale/unreachable RCL log"""

    def test_stale_writer_epoch_yields_unknown_at_step_7(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        from tos.engine.records import InstrumentKey, StageRequest
        from tos.engine.vocabulary import CommitmentStep
        from tos_runtime.compose._risk_attestations import (
            RiskAttestations,
            wrap_action_flow_inputs_provider,
        )
        from tos_runtime.compose._wiring import _rcl_tip_generation_provider
        from tos_runtime.rcl.log import SqliteCommitLog
        from tos_runtime.risk.ledger_stages import ActionFlowDecisionStage

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None

        second = SqliteCommitLog(
            runtime.rcl_log.path, evidence_port=runtime.evidence_store
        )
        try:
            second.acquire_epoch(runtime.identity)
            stale_provider = _rcl_tip_generation_provider(
                runtime.rcl_log, runtime.writer_epoch
            )
            attestations = RiskAttestations(
                numerically_safe=True,
                valuation_ok=True,
                all_fields_attributed=True,
                limit_source_is_injected_envelope=True,
                economic_commitment_exclusive=True,
                flow_commitment_exclusive=True,
            )
            wrapped_provider = wrap_action_flow_inputs_provider(
                _action_flow_inputs, attestations, stale_provider
            )
            stage = ActionFlowDecisionStage(
                runtime.flow_governor,
                inputs_provider=wrapped_provider,
                time_permits_new_risk=lambda: True,
            )
            request = StageRequest(
                step=CommitmentStep.ACTION_FLOW_DECISION,
                instrument_key=InstrumentKey(
                    account=fx.ACCOUNT, instrument=fx.INSTRUMENT
                ),
                proposal=first.pipeline.proposal,
            )
            verdict = stage(request)
            assert verdict.outcome.value == "UNKNOWN"
        finally:
            second.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestRclLogUnavailableBlocksNewRisk:
    """Scenario 5: removing/locking the RCL log file => zero new risk"""

    def test_rcl_log_removed_yields_unknown_and_zero_transport_calls(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        rcl_path = runtime.rcl_log.path
        runtime.rcl_log.close()
        rcl_path.unlink()
        rcl_path.touch()
        with contextlib.suppress(Exception):
            results = runtime.run_once((fx.crossing_event(),))
            flow = results[0].flow
            if flow is not None:
                verdict_by_step = {v.step.value: v for v in flow.verdicts}
                if "LEDGER_VERIFICATION" in verdict_by_step:
                    assert verdict_by_step["LEDGER_VERIFICATION"].outcome.value in (
                        "UNKNOWN",
                        "DENY",
                    )
        assert runtime.transport.requests == ()
        runtime.evidence_store.close()


class TestProjectionAuthorityMismatchHalts:
    """Scenario 6: injecting a projection/authority mismatch => the next"""

    def test_tampered_reservations_row_raises_commit_log_corruption(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import sqlite3

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
        )
        second = runtime.run_once((event,))[0]
        assert second.flow is not None and second.flow.attempt is not None, (
            "expected the second pass (approval present) to reach an "
            f"AttemptRequest; halted at {second.flow.halt_step if second.flow else None} "
            f"({second.flow.halt_reason if second.flow else second.halt_reason})"
        )
        rcl_path = runtime.rcl_log.path
        conn = sqlite3.connect(str(rcl_path))
        try:
            rows = conn.execute("SELECT COUNT(*) FROM reservations").fetchone()
            assert rows[0] > 0, "expected step 9 to have committed a reservation row"
            conn.execute(
                "UPDATE reservations SET state = 'RELEASED' WHERE rowid = "
                "(SELECT rowid FROM reservations LIMIT 1)"
            )
            conn.commit()
        finally:
            conn.close()
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        with pytest.raises(CommitLogCorruption):
            _compose(tmp_path, config_dir, data_dir, custody_root)

        import json
        import os

        from tos_runtime.custody.key_provider import FileKeyProvider
        from tos_runtime.evidence.store import SqliteEvidenceStore

        key_provider = FileKeyProvider(custody_root, expected_owner_uid=os.getuid())
        evidence_store = SqliteEvidenceStore(
            data_dir / "evidence.sqlite3", key_provider=key_provider
        )
        try:
            rows = evidence_store.connection.execute(
                "SELECT payload_json FROM entries WHERE kind = ?",
                ("RCL_CORRUPTION_ALERT",),
            ).fetchall()
            assert len(rows) == 1, f"expected exactly one alert record, got {rows}"
            stored = json.loads(rows[0][0])
            assert "detail" in stored["payload"]
        finally:
            evidence_store.close()


class TestReleaseAdmissionRefusalBlocksBoot:
    """Scenario 7: release admission refusal (code_digest mismatch) =>"""

    def test_mismatched_code_digest_refuses_before_any_sqlite_file_exists(
        self,
        mismatched_release_config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ReleaseAdmissionRefused):
            _compose(tmp_path, mismatched_release_config_dir, data_dir, custody_root)
        assert list(data_dir.glob("*.sqlite3")) == []
        assert list(custody_root.glob("*.sqlite3")) == []

    def test_release_refusal_reason_is_reported(
        self,
        mismatched_release_config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(ReleaseAdmissionRefused) as excinfo:
            _compose(tmp_path, mismatched_release_config_dir, data_dir, custody_root)
        assert "expected_code_digest" in str(excinfo.value)


class TestIdentityCodeDigestBoundToObservation:
    """Re-review disposition (HIGH, 2026-09-12) — ``release/admission.py``'s"""

    def test_constant_identity_code_digest_refuses_at_stage_a(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import tos_runtime.compose._wiring as wiring_module

        real_build_identity = wiring_module._build_identity

        def _constant_digest_build_identity(environment_label, code_digest):
            identity = real_build_identity(environment_label, code_digest)
            return identity.model_copy(
                update={"code_digest": "a-hardcoded-constant-not-the-observation"}
            )

        monkeypatch.setattr(
            wiring_module, "_build_identity", _constant_digest_build_identity
        )
        with pytest.raises(ReleaseAdmissionRefused):
            _compose(tmp_path, config_dir, data_dir, custody_root)
        assert list(data_dir.glob("*.sqlite3")) == []
        assert list(custody_root.glob("*.sqlite3")) == []


class TestStageBReleaseProbeRunsBeforeTheMonitorOwners:
    """``_stage_b_release_probe`` runs right after the RCL log is verified, BEFORE"""

    def test_normal_boot_reports_the_real_admitted_verdict(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        composed = _compose(tmp_path, config_dir, data_dir, custody_root)
        assert composed.release_admitted is True

    def test_a_refused_stage_b_verdict_never_reaches_build_monitor_owners(
        self,
        config_dir: Path,
        data_dir: Path,
        custody_root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """M2-style guard: forcing ``ReleaseAdmissionService.decide`` to refuse must raise"""
        import tos_runtime.compose._wiring as wiring_module
        from tos_runtime.release.admission import ReleaseAdmissionService

        calls: list[object] = []
        real_build_monitor_owners = wiring_module.build_monitor_owners

        def _spy_build_monitor_owners(*args: Any, **kwargs: Any) -> object:
            calls.append(kwargs.get("evidence_store"))
            return real_build_monitor_owners(*args, **kwargs)

        monkeypatch.setattr(
            wiring_module, "build_monitor_owners", _spy_build_monitor_owners
        )
        monkeypatch.setattr(
            ReleaseAdmissionService,
            "decide",
            lambda _self, *_args, **_kwargs: False,
        )
        with pytest.raises(ReleaseAdmissionRefused):
            _compose(tmp_path, config_dir, data_dir, custody_root)
        assert calls == []


class TestCapacityObligationRecording:
    """Kernel round #1 §3 (lane B) — the compose root wires a REAL"""

    def test_wired_sink_records_the_obligation_against_the_real_committed_reservation(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )

        results2 = runtime.run_once((event,))
        flow = results2[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        assert verdict_by_step["ATOMIC_COMMIT"].outcome.value == "ADMIT"
        assert len(runtime.transport.requests) == 1
        contexts = runtime.context_resolver.contexts
        assert contexts, "no SendBoundaryContext was ever resolved"
        attempt_id = contexts[-1].reservation_attempt_id
        assert attempt_id is not None

        from tos.egressgw import SendVerifyItem
        from tos.egressgw.records import GatewayEvidenceRecord

        refusal = GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
            attempt_id=attempt_id,
            item=SendVerifyItem.CURRENTNESS,
            preserved_worst_credible_capacity=7,
        )
        # noqa: SLF001 -- wiring proof, see this class's own docstring
        runtime.gateway._sink.record(refusal)

        kinds = [m.kind for m in runtime.evidence_store.iter_entry_meta()]
        assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
        assert "CAPACITY_OBLIGATION_VIOLATION_ALERT" not in kinds

        row = next(
            r
            for r in runtime.evidence_store.connection.execute(
                "SELECT payload_json FROM entries WHERE kind = 'CAPACITY_OBLIGATION_PRESERVED'"
            )
        )
        import json

        payload = json.loads(row[0])["payload"]
        assert payload["reservation_id"] == permit_reservation_id(
            fx.ACCOUNT, fx.INSTRUMENT, flow.attempt.action_flow_permit_identity
        )
        assert payload["reservation_id"].startswith("resv-88888888-01-ES-afg-permit-")
        assert payload["reservation_state"] == "COMMITTED_UNBOUND"
        assert payload["verdict"] is True

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_removing_the_on_refusal_wiring_yields_no_obligation_evidence(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Mutation M-B1: with ``_finalize``'s ``on_refusal`` wiring absent"""
        from tos.egressgw import SendVerifyItem
        from tos.egressgw.records import GatewayEvidenceRecord
        from tos_runtime.evidence.sinks import GatewayEvidenceSinkAdapter

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        runtime.gateway._sink = GatewayEvidenceSinkAdapter(  # noqa: SLF001
            runtime.evidence_store, runtime_identity=runtime.identity
        )

        runtime.gateway._sink.record(  # noqa: SLF001
            GatewayEvidenceRecord(
                kind="SEND_REFUSED",
                step=CommitmentStep.SEND_BOUNDARY_VERIFICATION,
                attempt_id="attempt-mutation-probe",
                item=SendVerifyItem.CURRENTNESS,
                preserved_worst_credible_capacity=7,
            )
        )

        kinds = [m.kind for m in runtime.evidence_store.iter_entry_meta()]
        assert kinds.count("SEND_REFUSED") == 1
        assert "CAPACITY_OBLIGATION_PRESERVED" not in kinds

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestOrthostateAndFinalityProjectionWiring:
    """Team-lead CR-4 dispatch (plan §2.2): the driver-level orthostate + SYNTHETIC finality"""

    def test_full_fill_hand_off_records_finality_proof_and_composite(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """After a real synthetic ``FULL_FILL`` hand-off: exactly one"""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()

        first = runtime.run_once((event,))
        proposal_digest = first[0].pipeline.proposal.canonical_digest
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )

        second = runtime.run_once((event,))
        flow = second[0].flow
        assert flow is not None and flow.handed_off is True and flow.attempt is not None
        attempt_id = flow.attempt.attempt_id

        proof_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'POSTTRADE_FINALITY_PROOF'"
        ).fetchone()[0]
        assert proof_rows == 1
        obligation_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'ECONOMIC_OBLIGATION'"
        ).fetchone()[0]
        assert obligation_rows == 1

        stored = runtime.inbox.last_composite(attempt_id)
        assert stored is not None
        raw_composite, _revision = stored
        assert raw_composite["broker_order_state"] == "FILLED"

        assert runtime.inbox.finality_witness(attempt_id) is True

        violation_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'COUPLING_VIOLATION'"
        ).fetchone()[0]
        assert violation_rows == 0

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_full_fill_hand_off_never_releases_rcl_capacity_end_to_end(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """TOS Phase 5 W2-R (plan §10 row ①): the finality release consumer"""
        import json

        from tos.rcl import CapacityState
        from tos_runtime.rcl.reservation_identity import (
            attempt_request_reservation_id,
        )

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()

        first = runtime.run_once((event,))
        proposal_digest = first[0].pipeline.proposal.canonical_digest
        approve_constructed_intent(
            runtime,
            custody_root,
            proposal_digest=proposal_digest,
        )

        second = runtime.run_once((event,))
        flow = second[0].flow
        assert flow is not None and flow.handed_off is True and flow.attempt is not None

        released_or_consumed = [
            state
            for _reservation_id, state, _seq, _scope in runtime.rcl_log.reservation_rows()
            if state in (CapacityState.RELEASED, CapacityState.POSITION_CONSUMED)
        ]
        assert released_or_consumed == []

        held_payload_rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'CAPACITY_RELEASE_HELD'"
        ).fetchall()
        assert len(held_payload_rows) == 1
        held_payload = json.loads(held_payload_rows[0][0])["payload"]
        instrument_key = runtime.context_resolver.instrument_key
        assert held_payload["reservation_id"] == attempt_request_reservation_id(
            instrument_key, flow.attempt
        )
        assert held_payload["reason"] == "WITNESS_NOT_INDEPENDENT"
        assert held_payload["detail"] == "WITNESS_NOT_INDEPENDENT"
        intent_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'CAPACITY_RELEASE_INTENT'"
        ).fetchone()[0]
        assert intent_rows == 0

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestNewRiskHaltOperatorReArm:
    """Re-review finding R3 (2026-09-09): the operator re-arm path for the independent-review"""

    def test_clear_with_the_right_seq_lets_the_next_decision_tick_proceed(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        from tos_runtime.engine.inbox import NewRiskHaltClearOutcome

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        evidence_seq = _reach_new_risk_halt_via_cancel_crossing_fill(
            runtime, custody_root
        )

        _write_rearm_approval(custody_root, evidence_seq)
        outcome = runtime.clear_new_risk_halt(
            latched_evidence_seq=evidence_seq,
            approvals_dir=custody_root / "approvals",
        )
        assert outcome is NewRiskHaltClearOutcome.CLEARED
        assert runtime.inbox.new_risk_halt() is None

        rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'NEW_RISK_HALT_CLEARED_BY_OPERATOR'"
        ).fetchall()
        assert len(rows) == 1
        import json

        payload = json.loads(rows[0][0])["payload"]
        assert payload["latched_evidence_seq"] == evidence_seq
        assert payload["latched_reason"] == "NEW_RISK_HALTED_BY_COUPLING_VIOLATION"
        assert "operator_attestation_sha256" in payload
        assert len(payload["operator_attestation_sha256"]) == 64

        rearm_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'REARM_APPROVED'"
        ).fetchone()[0]
        assert rearm_rows == 1

        refused_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'NEW_RISK_HALT_CLEAR_REFUSED'"
        ).fetchone()[0]
        assert refused_rows == 0

        next_tick = runtime.driver.enqueue_and_run(fx.crossing_event(seq=99))
        assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" not in (next_tick.detail or "")
        assert next_tick.pipeline is not None

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_stale_seq_is_refused_and_latch_stays_intact(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import json

        from tos_runtime.engine.inbox import NewRiskHaltClearOutcome

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        evidence_seq = _reach_new_risk_halt_via_cancel_crossing_fill(
            runtime, custody_root
        )

        outcome = runtime.clear_new_risk_halt(
            latched_evidence_seq=evidence_seq - 1,
            approvals_dir=custody_root / "approvals",
        )
        assert outcome is NewRiskHaltClearOutcome.SEQ_MISMATCH
        assert runtime.inbox.new_risk_halt() is not None
        assert runtime.inbox.new_risk_halt()["evidence_seq"] == evidence_seq

        cleared_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'NEW_RISK_HALT_CLEARED_BY_OPERATOR'"
        ).fetchone()[0]
        assert cleared_rows == 0

        refused_rows = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'NEW_RISK_HALT_CLEAR_REFUSED'"
        ).fetchall()
        assert len(refused_rows) == 1
        payload = json.loads(refused_rows[0][0])["payload"]
        assert payload["outcome"] == "SEQ_MISMATCH"
        assert payload["requested_evidence_seq"] == evidence_seq - 1
        assert payload["current_latched_evidence_seq"] == evidence_seq

        next_tick = runtime.driver.enqueue_and_run(fx.crossing_event(seq=99))
        assert "NEW_RISK_HALTED_BY_COUPLING_VIOLATION" in (next_tick.detail or "")

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_no_approval_file_is_refused_and_latch_stays_intact(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """TOS Phase 5 W3 plan §2 decision 7 (mutation M6): with NO"""
        from tos_runtime.engine.inbox import NewRiskHaltClearOutcome

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        evidence_seq = _reach_new_risk_halt_via_cancel_crossing_fill(
            runtime, custody_root
        )

        outcome = runtime.clear_new_risk_halt(
            latched_evidence_seq=evidence_seq,
            approvals_dir=custody_root / "approvals",
        )
        assert outcome is NewRiskHaltClearOutcome.QUORUM_REFUSED
        assert runtime.inbox.new_risk_halt() is not None

        cleared_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'NEW_RISK_HALT_CLEARED_BY_OPERATOR'"
        ).fetchone()[0]
        assert cleared_rows == 0

        rearm_refused_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'REARM_REFUSED'"
        ).fetchone()[0]
        assert rearm_refused_rows == 1
        refused_rows = runtime.evidence_store.connection.execute(
            "SELECT COUNT(*) FROM entries WHERE kind = 'NEW_RISK_HALT_CLEAR_REFUSED'"
        ).fetchone()[0]
        assert refused_rows == 1

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_a_second_violation_after_clear_latches_again_with_a_new_seq(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """After a clear, a FRESH violation must latch again with a NEW ``evidence_seq`` — the"""
        from decimal import Decimal

        from tos.engine.records import EgressResultPayload, EngineEvent
        from tos.engine.vocabulary import EgressResultKind, EventKind
        from tos_runtime.engine.inbox import NewRiskHaltClearOutcome

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        first_evidence_seq = _reach_new_risk_halt_via_cancel_crossing_fill(
            runtime, custody_root
        )
        _write_rearm_approval(custody_root, first_evidence_seq)
        assert (
            runtime.clear_new_risk_halt(
                latched_evidence_seq=first_evidence_seq,
                approvals_dir=custody_root / "approvals",
            )
            is NewRiskHaltClearOutcome.CLEARED
        )
        assert runtime.inbox.new_risk_halt() is None

        halt_before = runtime.inbox.new_risk_halt()
        assert halt_before is None
        attempt_id_row = runtime.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'COUPLING_VIOLATION' ORDER BY seq LIMIT 1"
        ).fetchone()
        import json

        attempt_id = json.loads(attempt_id_row[0])["payload"]["attempt_id"]
        second_late_fill = EngineEvent(
            kind=EventKind.EGRESS_RESULT,
            egress_result=EgressResultPayload(
                instrument_key=fx.instrument_key(),
                attempt_id=attempt_id,
                kind=EgressResultKind.PARTIAL_FILL,
                filled_quantity=Decimal("1"),
                remaining_quantity=Decimal("1"),
            ),
        )
        runtime.driver.enqueue_and_run(second_late_fill)

        second_halt = runtime.inbox.new_risk_halt()
        assert second_halt is not None
        second_evidence_seq = second_halt["evidence_seq"]
        assert isinstance(second_evidence_seq, int)
        assert second_evidence_seq != first_evidence_seq
        assert second_evidence_seq > first_evidence_seq

        assert (
            runtime.clear_new_risk_halt(
                latched_evidence_seq=first_evidence_seq,
                approvals_dir=custody_root / "approvals",
            )
            is NewRiskHaltClearOutcome.SEQ_MISMATCH
        )
        assert runtime.inbox.new_risk_halt() is not None
        assert runtime.inbox.new_risk_halt()["evidence_seq"] == second_evidence_seq

        runtime.rcl_log.close()
        runtime.evidence_store.close()
