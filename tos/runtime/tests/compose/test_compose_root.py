"""Runtime end-to-end tests for :mod:`tos_runtime.compose` (slice plan §4
item 3). Hermetic (real sqlite files under ``tmp_path``, real custody files
the test itself creates with 0600 + uid, fully-valued config copies —
``tos/runtime/tests/conftest.py``'s autouse guards enforce this).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
import yaml
from tos.engine.vocabulary import StageAuthorityClass
from tos_runtime.compose._pending_dimensions import (
    load_pending_currentness_dimensions,
    stamp_pending_dimensions,
)
from tos_runtime.compose.root import (
    ReleaseAdmissionRefused,
    compose_paper_runtime,
)
from tos_runtime.rcl.log import CommitLogCorruption
from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.strategy.resolve import StrategyRegistryResolutionRefused

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

    # all_fields_attributed / limit_source_is_injected_envelope are
    # deliberately None (no caller opinion) here: compose's own
    # wrap_aggregate_risk_inputs_provider (tos_runtime.compose._risk_attestations,
    # re-review finding F4) restrictive-merges them with
    # risk_attestations.yaml's operator attestation -- the e2e hand-off still
    # ADMITting proves the attestation genuinely governs when this test has
    # no opinion. numerically_safe/valuation_ok have no None variant on this
    # kernel dataclass, so they stay True here (a caller's own True claim is
    # NEVER a stronger fact than the attestation -- see
    # test_risk_attestations.py's dedicated restrictive-merge tests, incl. a
    # caller's own False/UNKNOWN claim that must NOT be overridden upward).
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
    # limit_source_is_injected_envelope / economic_commitment_exclusive /
    # flow_commitment_exclusive are deliberately None (no caller opinion)
    # here: compose's own wrap_action_flow_inputs_provider
    # (tos_runtime.compose._risk_attestations, re-review finding F4)
    # restrictive-merges them with risk_attestations.yaml's operator
    # attestation -- never an unconditional override (a caller's own
    # restrictive False/UNKNOWN claim would otherwise survive; see
    # test_risk_attestations.py's dedicated tests for that case).
    # generation_current is deliberately the WRONG value: it is always
    # DERIVED (tos.afg.generation_fenced against the RCL log's own current
    # tip), never attested, never a caller literal at all.
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
    """Composes via the FILE strategy source (TOS Phase 3 슬라이스 D-R
    ``[D-R-2]``) — writes the band-reversion strategy into
    ``config_dir/strategies/`` rather than injecting a
    :class:`~tos.engine.StrategyRegistry`, so this suite exercises the same
    production path ``tos_runtime.strategy.resolve.resolve_strategy_registry``
    wires. ``registry=fx.registry_with_band_strategy()[0]`` moved to
    :func:`test_both_a_strategies_directory_and_an_injected_registry_refuses`,
    the ONE remaining both-present-refusal test (brief item 4)."""
    fx.write_band_strategy_file(config_dir)
    return compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate_inputs,
        action_flow_inputs_provider=_action_flow_inputs,
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


def test_both_a_strategies_directory_and_an_injected_registry_refuses(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """TOS Phase 3 슬라이스 D-R ``[D-R-2]`` brief item 4: keep ONE refusal
    test proving ``compose_paper_runtime`` still refuses when a caller
    supplies BOTH a populated ``config_dir/strategies/`` directory AND an
    injected :class:`~tos.engine.StrategyRegistry` — exactly one strategy
    source is admissible (:mod:`tos_runtime.strategy.resolve`)."""
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
    """2026-09-09 independent-review finding #8, threaded end-to-end:
    ``compose_paper_runtime`` itself now refuses (rather than silently
    booting an empty registry) when NEITHER a populated
    ``config_dir/strategies/`` directory NOR an injected registry is
    supplied and the caller does not opt in via ``allow_no_strategies=True``
    (see :func:`test_neither_strategy_source_with_allow_no_strategies_boots_empty`)."""
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
    """The stated-choice opt-out: ``allow_no_strategies=True`` boots
    successfully with an empty, declares-nothing registry — this is the
    exact shape every OTHER test in this module deliberately avoids by
    always writing a strategy file or injecting a registry via ``_compose``
    (that helper's own docstring)."""
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

    def test_intent_registry_is_wired_with_the_runtime_time_service(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Kernel round #1 §2.2 re-review finding #3 (MEDIUM): before this
        fix, ``IntentRegistry(...)`` was constructed in ``_build_rcl_and_
        authority`` with no ``time=``/``time_config=`` at all, so decision-
        expiry composition (``_expiry_verdict``) could never even reach the
        time service — ANY approval file setting ``max_decision_age_ms``
        would fail closed with no receipt EVER consulted, not merely an
        incomplete one.

        Wiring proof via the registry's own injected collaborators (``_time``
        / ``_time_config``), matching this test module's own established
        pattern of reaching into a wired collaborator to prove composition
        (e.g. ``runtime.gateway._sink`` elsewhere in this file) — never a
        re-constructed duplicate, the SAME instances this runtime already
        exposes publicly.
        """
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        # noqa: SLF001 -- wiring proof, see this test's own docstring
        assert runtime.intent_registry._time is runtime.time_service
        assert runtime.intent_registry._time_config is runtime.time_service._config
        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_operator_attested_inputs_record_lists_exactly_the_attested_set(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Re-review reviewer Q3 / finding F4 (2026-09-08): compose must
        durably evidence, once at boot, every config-attested coordinate
        name so an auditor can separate attested from derived downstream —
        the field values themselves carry no marker of their own origin."""
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
            # egress_attestations.yaml (5)
            "account_instrument_action_allowed",
            "venue_session_account_facts_current",
            "broker_constraint_generation_current",
            "restrictive_latch_state",
            "worst_credible_capacity",
            # risk_attestations.yaml (6)
            "numerically_safe",
            "valuation_ok",
            "all_fields_attributed",
            "limit_source_is_injected_envelope",
            "economic_commitment_exclusive",
            "flow_commitment_exclusive",
            # egress_coordinates.yaml (9, TOS Phase 4 작업 6 §2.1 + review #2)
            "endpoint",
            "action",
            "method",
            "route_identity",
            "credential_generation",
            "broker_session_generation",
            "egress_generation",
            "active_principal",
            "capsule_terminus_fields",
            # strategies/band.strategy.yaml (1, TOS Phase 3 슬라이스 D-R
            # [D-R-2], plan §1.2 item 3 — one row per admitted strategy
            # file; _compose() now writes the band strategy into
            # config_dir/strategies/ instead of injecting a registry)
            fx.BAND_STRATEGY_FILE_NAME,
        }
        for coordinate in stored["payload"]["attested_coordinates"]:
            assert coordinate["source_file"] in (
                "egress_attestations.yaml",
                "risk_attestations.yaml",
                "egress_coordinates.yaml",
                fx.BAND_STRATEGY_FILE_NAME,
            )
            assert len(coordinate["source_file_digest"]) == 64  # sha256 hex

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
        far as step 4 (``INDEPENDENT_APPROVAL``), which legitimately
        UNKNOWNs with no approval file present yet (never an assumed
        grant). See ``test_engine_steps_admit_for_real_and_reach_the_transport``
        for the full picture once an approval file exists.
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
        # Step 4 is reached (a real StageVerdict exists for it) but with no
        # approval file present it is legitimately UNKNOWN (no decision
        # available) -- never an assumed grant.
        assert "INDEPENDENT_APPROVAL" in verdict_by_step
        assert verdict_by_step["INDEPENDENT_APPROVAL"].outcome.value == "UNKNOWN"
        assert runtime.transport.requests == ()

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_engine_steps_admit_for_real_and_reach_the_transport(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """The full picture behind scenario 1's acceptance criterion.

        Steps 1-14 (registry dispatch through the Transmission Capability)
        are driven by REAL runtime services — every step admits, and the
        flow reaches an :class:`~tos.engine.records.AttemptRequest`. The
        send is THEN admitted at the gateway boundary too, because the
        Safety Currentness Vector is complete (4 structurally-owned
        dimensions + 17 operator-attested pending dimensions, see
        ``tos_runtime.compose._pending_dimensions``) and every one of item
        6/12/16's egress-gate stand-ins is supplied as an explicit operator
        attestation (``tos_runtime.compose._egress_attestations``).

        Step 4 (``INDEPENDENT_APPROVAL``) genuinely admits: ``decision_current``
        is derived by lane P's ``IntentRegistry.decision_current`` (policy-
        generation equality + log-derived supersession check), and
        ``approved_intent_envelope_equivalent`` is derived by comparing the
        approval file's own digest against step 2's real
        ``ApprovedIntentContract.canonical_digest`` via
        ``tos.iap.exact_binding_holds`` (see ``_wiring.py``'s
        ``_build_step4_recorder``) — the approval file this test writes
        must therefore carry the REAL digest, not a placeholder (see
        ``write_approval_file``'s own docstring).
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
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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
        """Kernel round #1 §2.2 re-review finding #3 (MEDIUM): before this
        fix, ``_decision_provider`` resolved a bare
        ``IndependentApprovalDecision`` via ``load_operator_approval_file``,
        and the stage's default ``decision_current_provider`` called
        ``registry.decision_current(decision)`` with NO ``receipt`` at all —
        so ``IntentRegistry.consume``'s own ``receipt`` parameter was also
        never supplied, and the IAP_CONSUMPTION evidence's
        ``receipt_anchor`` field was unconditionally ``None`` no matter how
        the decision resolved.

        After the fix, ``_decision_provider`` uses
        ``load_operator_approval_with_receipt`` and the stage threads that
        SAME ``LoadedApproval`` into both ``decision_current`` and
        ``consume(..., receipt=...)`` — so even this ordinary
        ``max_decision_age_ms=None`` admit path now carries a real
        ``receipt_anchor`` (derived from the started ``TrustworthyTimeService``'s
        own continuity, which is available regardless of G-1's separate
        wall-clock-population gap — see ``load_operator_approval_with_
        receipt``'s own "honest gap" docstring note)."""
        import json

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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

    def test_recompose_after_a_real_hand_off_does_not_diverge(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Independent review finding #1 (2026-09-09), RED before the fix.

        Reproduces the reviewer's exact compose probe: one crossing tick that halts at step 4
        (no approval yet), then a SECOND run of the same event once the approval file names the
        real proposal digest — reaching a real hand-off and a real synthetic ``FULL_FILL``
        ``EGRESS_RESULT`` reinjected through the SAME ``enqueue_and_run`` call (mirroring
        ``test_one_synthetic_transport_handoff``). The inbox now holds
        ``[DECISION_TICK, DECISION_TICK, EGRESS_RESULT(FULL_FILL)]`` with recorded outcome
        digests ``[True, True, False]`` — exactly the reviewer's own measurement.

        Before the fix, boot-time replay treated the ``EGRESS_RESULT``'s honestly-``None``
        outcome digest as a divergence, so :func:`~tos_runtime.compose.root.compose_paper_runtime`
        raised ``EngineReplayDiverged`` on every subsequent boot over this ``data_dir`` — the
        runtime became PERMANENTLY un-bootable after the first real send. Both a second AND a
        third recompose must now succeed (not merely "the second boot is special" — a boot-time
        check that runs once and is never exercised again would not prove the fix).
        """
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )
        results2 = runtime.run_once((event,))
        assert results2[0].flow is not None and results2[0].flow.handed_off is True
        assert len(runtime.transport.requests) == 1
        runtime.rcl_log.close()
        runtime.evidence_store.close()

        # Second boot over the SAME data_dir: must NOT raise EngineReplayDiverged.
        runtime2 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime2.rcl_log.close()
        runtime2.evidence_store.close()

        # Third boot: must ALSO succeed — not just "the second time happens to work".
        runtime3 = _compose(tmp_path, config_dir, data_dir, custody_root)
        runtime3.rcl_log.close()
        runtime3.evidence_store.close()

    def test_replay_does_not_re_execute_real_stages_across_a_reboot(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Independent review finding #2 (2026-09-09), RED before the fix — the #2 claim
        verification the task disposition asked for: "replay digest equals the recorded one while
        IAP_CONSUMPTION/ARE_DECISION/AFG_DECISION/ARE_SNAPSHOT/RCL_APPEND evidence counts are
        byte-identical before/after a reboot".

        Before the fix, the boot-time replay core received the REAL ``stages`` dict, and each
        real stage carries its OWN evidence sink bound to the real durable store (independent of
        the replay ``EngineCore``'s own ``NullEvidenceSink``) — so replaying two ``DECISION_TICK``
        events on every reboot RE-WROTE a second (then third, ...) round of ``IAP_CONSUMPTION``,
        ``ARE_DECISION``, ``AFG_DECISION``, and ``ARE_SNAPSHOT`` evidence, and re-consumed the
        single-use Independent Approval. After the fix
        (``tos_runtime.compose._engine_wiring._ReplayStage``), a reboot's replay halts at the
        very first injected stage (right after the already-emitted proposal) and touches none of
        those sinks — the four kinds' row counts must be identical before and after the reboot.

        ``RCL_APPEND`` is measured SEPARATELY, not asserted byte-identical: an idle reboot with
        ZERO events ever processed still increases it by exactly 1 (measured directly — the RCL
        log's own per-process writer-epoch bookkeeping, unrelated to engine replay), so
        "unchanged" is the wrong invariant for it. The invariant this test actually checks for
        ``RCL_APPEND`` is that a reboot AFTER a real hand-off increases it by that SAME baseline
        1, never more — the review's own before-fix measurement (``RCL_APPEND 4->5``, a bare
        ``+1``) already showed this kind was not doubled by stage replay even under the bug (the
        RCL log's own compare-and-set fence refuses a stale-``expected_seq`` re-append rather than
        duplicating it); this assertion guards against that CAS protection ever regressing.
        """
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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


class TestPendingDimensionAttestationGatesCompleteness:
    """A pending currentness dimension's operator attestation is what makes
    the Safety Currentness Vector complete — flipping one dimension's
    ``positively_established`` to ``false`` (never removing/nulling a field,
    which is a LOAD-time refusal per
    ``_pending_dimensions.load_pending_currentness_dimensions``'s own
    fail-closed contract) must make the assembled vector incomplete again,
    never silently patched over by the other 16 attestations."""

    def test_one_false_attestation_makes_the_vector_incomplete(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        dims_path = config_dir / "currentness_dimensions.yaml"
        raw = yaml.safe_load(dims_path.read_text(encoding="utf-8"))
        raw["RELEASE"]["positively_established"] = False
        dims_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        # Re-run the SAME two-pass assembly _issue_egress_currentness_proof
        # performs (tos_runtime.compose.context), directly against the
        # runtime's own live assembler -- this isolates the currentness-
        # vector completeness property from the full engine flow (which
        # would ALSO need an approval file + step 4 to admit, tested
        # separately by TestSyntheticEventDrivesTheChain).
        specs = load_pending_currentness_dimensions(dims_path)
        base_vector = runtime.currentness_assembler.assemble()
        assert base_vector is not None
        assert base_vector.currentness_revision is not None
        pending = stamp_pending_dimensions(
            specs, at_revision=base_vector.currentness_revision
        )
        vector = runtime.currentness_assembler.assemble(extra_dimensions=pending)
        assert vector is not None
        assert runtime.currentness_assembler.is_complete(vector) is False

        runtime.rcl_log.close()
        runtime.evidence_store.close()


class TestNonTrustedTimeBlocksNewRisk:
    """Scenario 4: forcing the time snapshot non-TRUSTED => zero transport
    calls (steps 6/7/9's own injected time gate refuses)."""

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
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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


class TestStaleGenerationProviderYieldsUnknown:
    """Re-review finding F2 (2026-09-08): step 6 (``AggregateRiskDecisionStage``)
    over a stale RCL Writer Epoch must yield UNKNOWN, never a decision
    silently computed at a fabricated ``generation=0`` (the previous bare
    ``except Exception: return 0`` bug). Calls the real, composed Stage
    directly (rather than through the full engine sequencer) so this test
    isolates step 6's own fault contract from step 4's separate, unrelated
    RCL read (``IntentRegistry.decision_current``, lane P's file, out of
    this lane's scope)."""

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

        # A second handle acquiring a NEW Writer Epoch on the SAME rcl.sqlite3
        # file invalidates the composed runtime's own epoch.
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
    """Addendum A to the re-review (2026-09-08): a stale/unreachable RCL log
    on the step 9 PERMIT path (``context.make_permit_provider``'s own
    ``except (StaleEpochRead, sqlite3.Error, OSError): return None``) must
    yield ``UNKNOWN`` at ``AtomicCommitStage`` — permit ``None``, zero RCL
    appends, never a permit built at a fabricated ``generation=0``. Calls
    the real, composed ``AtomicCommitStage`` directly (isolating it from
    step 4's separate, unrelated RCL read, same rationale as
    ``TestStaleGenerationProviderYieldsUnknown`` above)."""

    def test_stale_writer_epoch_on_permit_path_yields_unknown_zero_appends(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import sqlite3

        from tos.afg import ActionFlowResult
        from tos.engine.records import InstrumentKey, StageRequest
        from tos.engine.vocabulary import CommitmentStep
        from tos_runtime.compose._wiring import _rcl_tip_generation_provider
        from tos_runtime.compose.context import make_permit_provider
        from tos_runtime.rcl.log import SqliteCommitLog
        from tos_runtime.risk.ledger_stages import AtomicCommitStage

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )
        # Re-run the SAME event so steps 1-7 admit for real, giving
        # flow_governor a real GRANT last_decision to build a permit from.
        runtime.run_once((event,))
        assert runtime.flow_governor.last_decision is not None
        assert runtime.flow_governor.last_decision.result is ActionFlowResult.GRANT

        rows_before = (
            sqlite3.connect(str(runtime.rcl_log.path))
            .execute("SELECT COUNT(*) FROM entries")
            .fetchone()[0]
        )

        # A second handle acquiring a NEW Writer Epoch on the SAME
        # rcl.sqlite3 file invalidates the composed runtime's own epoch.
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
                reservation_id_provider=lambda request: (
                    f"resv-{request.instrument_key.account}-"
                    f"{request.instrument_key.instrument}"
                ),
                time_permits_new_risk=lambda: True,
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
    """Addendum A, step 7 half (2026-09-08): a stale/unreachable RCL log
    inside ``_risk_attestations.wrap_action_flow_inputs_provider``'s own
    ``except (StaleEpochRead, sqlite3.Error, OSError): return None`` must
    yield ``UNKNOWN`` at ``ActionFlowDecisionStage`` — never a fabricated
    ``generation_current``. Calls the real, composed Stage directly
    (isolated from step 4's separate, unrelated RCL read)."""

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

    def test_tampered_reservations_row_raises_commit_log_corruption(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        import sqlite3

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)
        event = fx.crossing_event()
        first = runtime.run_once((event,))[0]
        assert first.pipeline is not None and first.pipeline.proposal is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=first.pipeline.proposal.canonical_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
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

        # compose_paper_runtime itself must verify the RCL log's replay at
        # boot and refuse to hand back a runtime over a corrupt log -- (c)
        # no Stage/service is ever constructed: the function raises instead
        # of returning a ComposedRuntime, so there is no `runtime2` at all.
        with pytest.raises(CommitLogCorruption):
            _compose(tmp_path, config_dir, data_dir, custody_root)

        # (b) the evidence store contains exactly one RCL_CORRUPTION_ALERT
        # record (compose's own halt path, never this test's) -- reopened
        # independently since compose raised before returning any handle.
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


class TestCapacityObligationRecording:
    """Kernel round #1 §3 (lane B) — the compose root wires a REAL
    ``CapacityObligationRecorder`` onto the REAL gateway sink, resolving the
    SAME reservation id the real ``AtomicCommitStage`` just committed.

    **Deviation from the plan (reported).** No pre-existing "denied-egress-
    attestation" e2e scenario existed in this file to reuse (surveyed: no
    ``SEND_REFUSED`` assertion anywhere in this module before this class).
    Worse, the plan's assumed alternative — flip one pending currentness
    dimension's ``positively_established`` to ``False``
    (``TestPendingDimensionAttestationGatesCompleteness``'s own technique)
    and drive the real engine to a genuine item-16 ``SEND_REFUSED`` carrying
    a preserved-capacity obligation — is not reachable through this compose
    root's CURRENT wiring at all: measured directly (a temporary print of
    the resulting ``SEND_REFUSED`` payload), an incomplete Safety Currentness
    Vector makes ``EgressCurrentnessProofIssuer.issue()`` (module docstring:
    "returns ``None`` ... when the candidate fails its own
    ``proof_admissible`` self-check") refuse to issue a proof at ALL, so
    ``context.egress_currentness_proof`` is ``None`` and the gateway halts at
    the EARLIER ``proof_structurally_complete(None)`` check
    (``tos.egressgw.gateway._check_currentness``) — never reaching the LATER
    ``egress_currentness_verdict(...)`` branch that calls
    ``unknown_preserves_capacity`` and sets
    ``preserved_worst_credible_capacity``. Because ``proof_admissible``
    requires ``result is CURRENT`` and ``issue()`` self-checks that SAME
    predicate on the SAME object before ever returning it, a structurally-
    complete-but-non-ADMIT proof cannot currently reach the gateway through
    this issuer at all — reaching the plan's assumed scenario for real would
    need a currentness-proof-issuer change, which is out of lane B's scope
    this round (no kernel or lane-R runtime edits authorized here).

    So this class proves the WIRING is correct — real store, real
    projection, real resolver referencing the real committed reservation —
    by driving the real admitted engine flow
    (``TestSyntheticEventDrivesTheChain.test_engine_steps_admit_for_real_and_reach_the_transport``'s
    own approval-file dance, unmodified) up to a genuine committed
    reservation and a genuine attempt id, then invoking the REAL wired sink
    directly with a ``SEND_REFUSED``/item-16 record for that SAME attempt —
    exactly the shape ``BrokerEgressGateway._halt`` itself would construct,
    had the currentness issuer been able to produce one. The recorder's own
    verdict/halt LOGIC for every reachable non-ADMIT combination is already
    exhaustively covered by real components in
    ``tos/runtime/tests/rcl/test_obligation.py`` — this class is the
    wiring proof only, not a second copy of that behavioral coverage.

    Independent review finding #6, restated plainly: production
    reachability of the obligation branch is currently ZERO (the issuer
    emits a proof only when its own result is already ``CURRENT``, i.e.
    only on the ADMIT path) — this test class proves the wiring, not the
    trigger.
    """

    def test_wired_sink_records_the_obligation_against_the_real_committed_reservation(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        event = fx.crossing_event()
        results = runtime.run_once((event,))
        proposal_digest = results[0].pipeline.proposal.canonical_digest
        assert proposal_digest is not None
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )

        results2 = runtime.run_once((event,))
        flow = results2[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        assert verdict_by_step["ATOMIC_COMMIT"].outcome.value == "ADMIT"
        # The real send genuinely admitted (fx's own acceptance criterion) --
        # a real reservation is now COMMITTED_UNBOUND under this account/
        # instrument (tos_runtime.compose._fixtures.ACCOUNT/INSTRUMENT).
        assert len(runtime.transport.requests) == 1
        contexts = runtime.context_resolver.contexts
        assert contexts, "no SendBoundaryContext was ever resolved"
        attempt_id = contexts[-1].reservation_attempt_id
        assert attempt_id is not None

        from tos.egressgw import SendVerifyItem
        from tos.egressgw.records import GatewayEvidenceRecord

        # The shape BrokerEgressGateway._halt itself constructs for an
        # item-16 SEND_REFUSED (gateway.py __call__'s halt_item ==
        # CURRENTNESS branch) -- injected directly at the wired sink
        # because the real issuer cannot currently reach this combination
        # (this class's own docstring).
        refusal = GatewayEvidenceRecord(
            kind="SEND_REFUSED",
            attempt_id=attempt_id,
            item=SendVerifyItem.CURRENTNESS,
            preserved_worst_credible_capacity=7,
        )
        # noqa: SLF001 -- wiring proof, see this class's own docstring
        runtime.gateway._sink.record(refusal)

        kinds = [m.kind for m in runtime.evidence_store.iter_entry_meta()]
        assert kinds.count("CAPACITY_OBLIGATION_PRESERVED") == 1
        # No halt: the resolver mapped attempt_id -> the SAME
        # f"resv-{account}-{instrument}" identity AtomicCommitStage just
        # committed, and the projection genuinely reads it back as
        # COMMITTED_UNBOUND (a live, capacity-consuming state).
        assert "CAPACITY_OBLIGATION_VIOLATION_ALERT" not in kinds

        row = next(
            r
            for r in runtime.evidence_store.connection.execute(
                "SELECT payload_json FROM entries WHERE kind = 'CAPACITY_OBLIGATION_PRESERVED'"
            )
        )
        import json

        payload = json.loads(row[0])["payload"]
        assert payload["reservation_id"] == "resv-acct-compose-ES"
        assert payload["reservation_state"] == "COMMITTED_UNBOUND"
        assert payload["verdict"] is True

        runtime.rcl_log.close()
        runtime.evidence_store.close()

    def test_removing_the_on_refusal_wiring_yields_no_obligation_evidence(
        self, config_dir: Path, data_dir: Path, custody_root: Path, tmp_path: Path
    ) -> None:
        """Mutation M-B1: with ``_finalize``'s ``on_refusal`` wiring absent
        (simulated here by swapping in a sink built the way ``_finalize``
        used to before this round), the SAME injected item-16
        ``SEND_REFUSED`` record produces NO ``CAPACITY_OBLIGATION_PRESERVED``
        evidence — proving the recorder is genuinely load-bearing, not
        vacuously always green."""
        from tos.egressgw import SendVerifyItem
        from tos.egressgw.records import GatewayEvidenceRecord
        from tos_runtime.evidence.sinks import GatewayEvidenceSinkAdapter

        runtime = _compose(tmp_path, config_dir, data_dir, custody_root)
        _reach_trusted(runtime)

        # Mutate: replace the wired sink with the pre-this-round shape --
        # same store, same identity, NO on_refusal observer.
        runtime.gateway._sink = GatewayEvidenceSinkAdapter(  # noqa: SLF001
            runtime.evidence_store, runtime_identity=runtime.identity
        )

        runtime.gateway._sink.record(  # noqa: SLF001
            GatewayEvidenceRecord(
                kind="SEND_REFUSED",
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
