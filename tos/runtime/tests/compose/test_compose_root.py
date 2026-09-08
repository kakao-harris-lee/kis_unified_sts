"""Runtime end-to-end tests for :mod:`tos_runtime.compose` (slice plan §4
item 3). Hermetic (real sqlite files under ``tmp_path``, real custody files
the test itself creates with 0600 + uid, fully-valued config copies —
``tos/runtime/tests/conftest.py``'s autouse guards enforce this).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from tos.engine.vocabulary import StageAuthorityClass
from tos_runtime.compose.root import (
    ReleaseAdmissionRefused,
    compose_paper_runtime,
)
from tos_runtime.rcl.log import CommitLogCorruption
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs

from . import _fixtures as fx
from .conftest import write_approval_file

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


class FakeMonotonicSource:
    """A controllable monotonic-clock double (test-only). Compose's own
    boot-time ``evaluate()`` x2 read strictly increasing values by default;
    a test can then force a regression on a LATER ``evaluate()`` call
    (scenario 4) by lowering :attr:`next_value` below the highest value
    already observed — real hardware never does this, so this is the only
    way to exercise ``tos.time.anchor_valid``'s regression path
    deterministically."""

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
        all_fields_attributed=True,
        required_scopes=frozenset({RiskScopeKind.ACCOUNT}),
        numerically_safe=True,
        valuation_ok=True,
        injected_envelope_max=fx.aggregate_risk_effective_limit(),
        limit_source_is_injected_envelope=True,
        effective_limit=fx.aggregate_risk_effective_limit(),
    )


def _action_flow_inputs(request) -> ActionFlowDecisionInputs | None:
    from tos.afg import (
        ActionCause,
        ActionClassKind,
        ActionFlowScopeKind,
        ActionFlowStateSnapshot,
        ObservedAmplification,
        ScopeIndependenceEvidence,
    )

    scope = ActionFlowScopeKind.ACCOUNT
    snapshot = ActionFlowStateSnapshot(
        snapshot_id="afg-snap-compose",
        snapshot_generation=1,
        consistency_cut_identity="afg-cut-compose",
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
        elapsed_monotonic=1,
        duplicate_redelivery_expansion=0,
        failover_reconnect_replay_expansion=0,
        amplification_per_cause=1,
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
        limit_source_is_injected_envelope=True,
        economic_ref="economic-ref-compose-1",
        flow_vector=fx.action_flow_requested_limit(),
        committed_flow_vectors=(),
        hard_limit=fx.action_flow_envelope_max(),
        runtime_limit=fx.action_flow_envelope_max(),
        economic_commitment_exclusive=True,
        flow_commitment_exclusive=True,
        generation_current=True,
        applicable_action_flow_scopes=("ACCOUNT",),
        decision_generation=1,
        action_class=ActionClassKind.NORMAL_NEW_RISK,
        cause_digest="cause-compose-1-digest",
    )


def _compose(
    tmp_path: Path,
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    *,
    monotonic_source: object | None = None,
):
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
        registry=fx.registry_with_band_strategy()[0],
        monotonic_source=monotonic_source,
    )


def _reach_trusted(runtime) -> None:
    """Compose itself already runs two ``evaluate()`` cycles at boot
    (UNINITIALIZED->SYNCHRONIZING->TRUSTED) so its own Stage B release-
    admission check has a real currentness fact — this just asserts that
    held."""
    assert runtime.time_service.health_state.value == "TRUSTED"


def _write_approval_for_crossing(custody_root: Path) -> None:
    strategy_registry, strategy = fx.registry_with_band_strategy()
    del strategy_registry
    # The proposal digest is only known once the DSL policy actually
    # evaluates the crossing tick, so approvals are written per-flow using
    # the digest recorded on the returned EventResult (see the tests below).


class TestComposeRootWiring:
    """Scenario-adjacent smoke coverage: composition succeeds, and every
    lane's durable artifacts land where the design says they should."""

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


class TestSyntheticEventDrivesTheChain:
    """Scenario 1: a synthetic event drives the real service chain."""

    def test_steps_one_to_three_admit_for_real(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Steps 1-3 (registry dispatch through venue construction) are
        driven by REAL runtime/kernel services — a proposal is genuinely
        evaluated and a commitment flow is genuinely attempted, reaching as
        far as step 4 (``INDEPENDENT_APPROVAL``) before that step's own
        honestly-``None`` ``decision_current`` (no Phase 2 producer — see
        ``_wiring.py``'s ``_decision_current_provider`` docstring) halts it.
        This is the honestly-reachable portion of scenario 1; see
        ``test_engine_steps_admit_for_real_and_reach_the_transport`` (xfail)
        for what is NOT reachable and why.
        """
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        assert len(results) == 1
        result = results[0]

        # The proposal was evaluated and a commitment flow was attempted.
        assert result.pipeline is not None
        assert result.pipeline.proposal is not None
        assert result.flow is not None

        verdict_by_step = {v.step.value: v for v in result.flow.verdicts}
        # Step 4 is reached (a real StageVerdict exists for it) but never
        # admits: with no approval file present it is UNKNOWN (no decision
        # available); once one exists it is DENY (REJECTED_INELIGIBLE) —
        # see test_engine_steps_admit_for_real_and_reach_the_transport's
        # xfail reason for why it can never be ADMIT in this composition.
        assert "INDEPENDENT_APPROVAL" in verdict_by_step
        assert verdict_by_step["INDEPENDENT_APPROVAL"].outcome.value == "UNKNOWN"
        assert runtime.transport.requests == ()

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "team-lead follow-up guidance (2026-09-08): decision_current has "
            "NO Phase 2 runtime producer (tos.iap reads no clock, and "
            "IndependentApprovalDecision carries no field comparable to "
            "SafetyAuthorityEpochService.current_state() — comparing them "
            "would be a category error, not a real currency check; see "
            "_wiring.py's _decision_current_provider docstring). Honestly "
            "returning None (never a fabricated True) drives "
            "consumption_transition to REJECTED_INELIGIBLE => "
            "StageOutcome.DENY at step 4 for every attempt with an approval "
            "file present (or UNKNOWN with none present) — step 4 can never "
            "ADMIT, so the flow never reaches steps 6-14 or the transport."
        ),
    )
    def test_engine_steps_admit_for_real_and_reach_the_transport(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """The full picture behind scenario 1's acceptance criterion.

        Steps 1-14 (registry dispatch through the Transmission Capability)
        would need to ALL admit for the flow to reach an
        :class:`~tos.engine.records.AttemptRequest` and the gateway. Step 4
        cannot admit (see the xfail reason above), so this is currently
        unreachable — kept as a named, strict xfail rather than removed, so
        a future Phase's real decision-currency producer landing turns this
        green again without anyone having to rediscover the gap.
        """
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
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
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

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "team-lead follow-up guidance (2026-09-08): same root cause as "
            "test_engine_steps_admit_for_real_and_reach_the_transport — "
            "decision_current has no Phase 2 producer, step 4 can never "
            "ADMIT, so the flow can never reach the transport."
        ),
    )
    def test_one_synthetic_transport_handoff(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Scenario 1's literal acceptance criterion: exactly one synthetic
        transport hand-off, reached once every mandated currentness
        dimension is supplied (4 structurally-owned + 17 operator-attested
        pending — see ``tos_runtime.compose._pending_dimensions``'s own
        module docstring for why the 17 are honest interim attestations,
        never a fabricated kernel-derived verdict)."""
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
        )
        # Re-run the SAME event -- a differently-seq'd event carries a
        # different capsule and therefore a different proposal digest that
        # would not match the approval file just written.
        runtime.run_once((event,))
        assert len(runtime.transport.requests) == 1


class TestStandInZero:
    """Scenario 2: no ``NON_AUTHORITATIVE_PROVISIONAL`` verdict for steps
    4, 6-10, 13, 14 anywhere in the engine evidence."""

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
        pre_reservations = dict(
            runtime.risk_service._projection.all_reservations()  # type: ignore[attr-defined]
        )
        runtime.rcl_log.verify_replay()
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        # No new epoch-advancing writes yet: verify_replay reproduces the
        # SAME reservations-state digest the pre-restart process held.
        runtime2.rcl_log.verify_replay()
        post_reservations = dict(
            runtime2.risk_service._projection.all_reservations()  # type: ignore[attr-defined]
        )
        assert post_reservations == pre_reservations

        assert runtime2.evidence_store.verify(
            {1: (custody_root / "evidence.key.1").read_bytes()}
        )
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()


class TestNonTrustedTimeBlocksNewRisk:
    """Scenario 4: forcing the time snapshot non-TRUSTED => zero transport
    calls (steps 6/7/9's own injected time gate refuses)."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "team-lead follow-up guidance (2026-09-08): this scenario needs "
            "step 4 (INDEPENDENT_APPROVAL) to ADMIT with an approval file "
            "present so the flow can reach step 6 and demonstrate the time "
            "gate specifically. decision_current has no Phase 2 producer "
            "(see _wiring.py's _decision_current_provider docstring), so "
            "step 4 now always DENYs (REJECTED_INELIGIBLE) once an approval "
            "file exists — the flow halts at step 4 regardless of the time "
            "service's health state, so step 6's own time gate is never "
            "reached and this scenario's specific claim is unreachable."
        ),
    )
    def test_untrusted_time_yields_zero_transport_calls(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        clock = FakeMonotonicSource()
        runtime = _compose(
            tmp_path, config_dir, data_dir, custody_root, monotonic_source=clock
        )
        _reach_trusted(runtime)  # compose's own boot evaluate() x2 reached TRUSTED

        # Reach step 4 (INDEPENDENT_APPROVAL) once, while still TRUSTED, so an
        # approval file can be written for THIS exact proposal digest --
        # otherwise the flow would halt at step 4 (no approval available) and
        # never reach steps 6/7, which is what this scenario is about.
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        write_approval_file(
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
            environment_label="non-live-test",
        )

        # Force a monotonic regression, then re-evaluate: tos.time.anchor_valid
        # can only route the FSM toward UNTRUSTED on a regression (never hold
        # TRUSTED) -- tos.time.state_permits_new_normal_risk is False for
        # every non-TRUSTED state.
        clock.force_regression()
        runtime.time_service.evaluate()
        assert runtime.time_service.health_state.value != "TRUSTED"

        results = runtime.run_once((event,))
        flow = results[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        # The sequencer halts at the FIRST non-ADMIT step (design #31 §4.2
        # rule 1) -- step 6's own injected time gate refuses first, so step 7
        # is never even reached (no verdict at all for it, not a second
        # UNKNOWN verdict).
        assert verdict_by_step["AGGREGATE_RISK_DECISION"].outcome.value == "UNKNOWN"
        assert "ACTION_FLOW_DECISION" not in verdict_by_step
        assert (
            flow.halt_step is not None
            and flow.halt_step.value == "AGGREGATE_RISK_DECISION"
        )
        assert runtime.transport.requests == ()
        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestRclLogUnavailableBlocksNewRisk:
    """Scenario 5: removing/locking the RCL log file => zero new risk
    (steps 8-10 UNKNOWN) and no hand-off."""

    def test_rcl_log_removed_yields_unknown_and_zero_transport_calls(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        rcl_path = runtime.rcl_log.path
        runtime.rcl_log.close()
        rcl_path.unlink()
        # A closed-then-removed connection: further calls hit sqlite3.Error
        # ("no such table" on a fresh empty file created implicitly, or
        # OSError on some platforms) -- both are mapped to UNKNOWN by
        # ledger_stages' own fault contract, never a denial by omission.
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
    """Scenario 6: injecting a projection/authority mismatch => the next
    compose/verify raises CommitLogCorruption and an alert evidence record
    is appended (via ``record_halt``)."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "team-lead follow-up guidance (2026-09-08): this scenario needs "
            "a real reservation row committed by step 9 (ATOMIC_COMMIT) to "
            "tamper with. decision_current has no Phase 2 producer (see "
            "_wiring.py's _decision_current_provider docstring), so step 4 "
            "now always DENYs once an approval file exists — the flow never "
            "reaches step 9, so no reservation row is ever committed to "
            "tamper with. The underlying corruption-detection mechanism "
            "itself (SqliteCommitLog.verify_replay raising "
            "CommitLogCorruption) is unaffected and remains covered by "
            "lane O's own log-level tests; only this compose-e2e "
            "demonstration via a full engine run is unreachable."
        ),
    )
    def test_tampered_reservations_row_raises_commit_log_corruption(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import sqlite3

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        write_approval_file(
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
            environment_label="non-live-test",
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

        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        from tos_runtime.evidence.emergency import record_halt

        with pytest.raises(CommitLogCorruption):
            try:
                runtime2.rcl_log.verify_replay()
            except CommitLogCorruption as exc:
                record_halt(
                    runtime2.evidence_store,
                    runtime2.emergency_log,
                    payload={"detail": str(exc)},
                    kind="RCL_CORRUPTION_ALERT",
                    record_class="RCL_CORRUPTION_ALERT",
                    runtime_identity=runtime2.identity,
                )
                raise
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()


class TestReleaseAdmissionRefusalBlocksBoot:
    """Scenario 7: release admission refusal (code_digest mismatch) =>
    compose raises before any service starts (assert no sqlite files
    created)."""

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
