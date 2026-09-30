"""``tos_runtime.riskstate.service.RiskStateService`` /
``tos_runtime.compose._riskstate_wiring.build_risk_state_service`` (TOS risk state service
wave, lane b; ``docs/plans/2026-09-16-tos-risk-state-service-plan.md``).

Two layers, deliberately NOT sharing fixtures across suites (mirrors
``tests/riskstate/conftest.py``'s own "cross-suite imports are forbidden" convention):

* **Unit layer** — :class:`RiskStateService` exercised directly over the SAME hermetic
  evidence/inbox/rcl-log doubles :mod:`tests.riskstate.conftest` uses (re-implemented here,
  not imported, per that module's own convention) plus the SAME
  ``aggregate_risk_policy.yaml``/``action_flow_policy.yaml`` builders from
  :mod:`tests.riskstate._documents` (plain string builders, not pytest fixtures — importing
  those is not a fixture-sharing violation). ``StageRequest``/``Proposal`` are built via
  ``model_construct`` (bypasses pydantic validation) rather than the real decision pipeline —
  a ``Proposal`` is a DRAFT-invariant ``IdDerivedArtifact`` that refuses a non-``None``
  ``proposal_id``/``canonical_digest`` unless properly ``.issue()``-d through a full capsule,
  which this suite's own attempt-identity needs are too shallow to justify building.
* **Wiring layer** — :func:`build_risk_state_service`'s five cross-checks, against a MINIMAL
  config directory this file owns alone (NOT ``tests/compose/conftest.py``'s shared
  ``config_dir`` — that fixture's own ``safety_envelope.yaml``/``safety_activation.yaml``
  serve ~400 other compose e2e tests whose HSE governed-dimension set and activation member
  count must stay exactly as they are; extending it here would risk a regression this suite
  has no way to detect until CI runs the whole compose suite).
* One ``compose_paper_runtime``-level boot-refusal test (``RiskStateConfigError``) using the
  shared ``config_dir`` fixture UNMODIFIED (it never carries the two risk-state policy files,
  so it is the correct fixture for "files absent" cases).
* **E2E layer (``TestComposeE2E``)** — the plan's own acceptance criterion (§1: "합성 paper
  e2e 에서 step 6/7 GRANT 가 손으로 지은 리터럴 없이 도달"): the FULL compose stack, driven
  through the SAME 2-``run_once``-call pattern ``test_compose_root.py``'s own ADMIT tests use
  (first call discovers the proposal digest and writes the operator approval file; second call
  reaches the steps this wave's own service feeds), with BOTH
  ``aggregate_risk_inputs_provider``/``action_flow_inputs_provider`` left ``None`` — the
  production :class:`~tos_runtime.riskstate.service.RiskStateService` default. Uses
  ``config_dir_with_risk_state`` (:mod:`tests.compose.conftest`), an OPT-IN layered fixture
  built on top of the shared ``config_dir`` (mirroring that module's own
  ``mismatched_release_config_dir`` idiom) — the ~400 other compose e2e tests requesting
  ``config_dir`` directly are completely unaffected.

  **Resolved (2026-09-16), TOS action-flow observation completion wave
  (``docs/plans/2026-09-16-tos-action-flow-observation-plan.md``): step 7
  (ACTION_FLOW_DECISION) now reaches a real ``GRANT``, not ``UNKNOWN``.** The prior gap was
  structural, not a wiring bug: ``amplification_bounded``
  (``tos/src/tos/afg/predicates.py:311-353``) requires a concrete bound AND a concrete
  observed count on every one of 11 axes; two of those —
  ``duplicate_redelivery_expansion``/``failover_reconnect_replay_expansion`` — had no durable
  per-root-cause read surface anywhere in ``tos_runtime``. This wave's lane a closed both with
  ZERO schema change:
  :func:`~tos_runtime.riskstate.flow_observation.count_duplicate_dispositions` counts kernel
  ``RESULT_UNMATCHED`` rows whose ``result_disposition`` is ``DUPLICATE`` and whose
  ``attempt_id`` traces to the root cause;
  :func:`~tos_runtime.riskstate.flow_observation.count_recovery_markers` counts durable
  restart-recovery marker rows keyed to the root event's own content-addressed identity — an
  accepted, disclosed-under-count proxy
  (:attr:`~tos_runtime.riskstate.flow_observation.FlowObservation.replays_definition`). See
  :mod:`tos_runtime.riskstate.flow_observation`'s own module docstring for the full
  derivation.

  **Honest scope correction (unchanged from the review of PR #704, 2026-09-16, LOW — still
  applies now that step 7 reaches ``GRANT``):** this docstring makes no claim that this suite
  independently confirms the other four ``action_flow_decision`` witnesses
  (``scope_graph_complete``, ``cause_lineage_complete``, ``envelope_not_enlarged``,
  ``atomic_economic_flow_coverage``) beyond what ``amplification_bounded``'s own ``GRANT``
  outcome already implies — :class:`~tos.afg.records.ActionFlowDecision` (kernel,
  ``tos.afg.predicates.action_flow_decision``) carries no per-witness boolean in its issued,
  immutable shape (only digests and the final ``result``), so no assertion in this file
  inspects those four witnesses individually.

  **A real fix landed alongside the prior wave's finding, still in effect:**
  :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader.observe`'s own
  ``this_attempt_lineage_found`` falls back to "the root event's own durable presence at a
  positively resolved inbox seq" (via the SAME ``current_seq_reader`` this wave already wired)
  when NO sealed row exists yet for a brand-new attempt being evaluated at step 7, strictly
  BEFORE step 15 ever seals anything for it — the SEND_SEALED-tracing check still stands,
  unchanged, for an ALREADY-sealed attempt whose seal does NOT trace to its claimed root (a
  genuine inconsistency).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from tos.afg import ActionClassKind
from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl.proposal import Proposal
from tos.engine.records import (
    EgressResultPayload,
    EngineEvent,
    InstrumentKey,
    StageRequest,
)
from tos.engine.vocabulary import CommitmentStep, EgressResultKind, EventKind
from tos.ioc import AxisBinding, ConformanceAxis
from tos.ordering import OrderingEvent
from tos.spg import GovernedDimensionLimit, HardSafetyEnvelope
from tos.venue import ActionClass
from tos_runtime.calendar.ports import FixedWallClockReference
from tos_runtime.compose._riskstate_wiring import (
    RiskPolicyScopeMismatch,
    build_risk_state_service,
)
from tos_runtime.compose._types import RiskStateConfigError
from tos_runtime.compose.root import compose_paper_runtime
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import KeyProvider, SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.flow_observation import (
    REPLAYS_DEFINITION,
    FlowObservation,
    InboxFlowReader,
)
from tos_runtime.riskstate.policies import (
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import EvidencePositionReader, PositionObservation
from tos_runtime.riskstate.service import RiskStateService
from tos_runtime.venue import PolicyNotActivated

from ..riskstate._documents import (
    action_flow_policy_yaml,
    aggregate_risk_policy_yaml,
)
from . import _fixtures as fx
from . import _symmetry_fixtures as sfx
from .conftest import (
    _RISK_STATE_ENVELOPE_MAX,
    call_wrapped_fixture,
    write_approval_file,
)
from .conftest import config_dir as _config_dir_fixture
from .conftest import config_dir_with_risk_state as _config_dir_with_risk_state_fixture
from .conftest import custody_root as _custody_root_fixture
from .conftest import data_dir as _data_dir_fixture

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")

_ACCOUNT = "acct-compose"
_INSTRUMENT = "ES"
_ARE_DIM_ID = "INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL"
_AFG_DIM_ID = "afg.ORDER"


class _FixedKeyProvider:
    """Mirrors ``tests/riskstate/conftest.py``'s own re-declared double (that module's own
    docstring: cross-suite imports are forbidden)."""

    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-riskstate-wiring-suite")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-riskstate-wiring-suite"


@pytest.fixture
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
    key_provider: KeyProvider = _FixedKeyProvider()
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=key_provider
    )
    yield instance
    instance.close()


@pytest.fixture
def inbox(tmp_path: Path) -> Iterator[SqliteEventInbox]:
    instance = SqliteEventInbox(tmp_path / "inbox.sqlite3", scheme=_SCHEME)
    yield instance
    instance.close()


@pytest.fixture
def rcl_log(
    tmp_path: Path, evidence_store: SqliteEvidenceStore
) -> Iterator[SqliteCommitLog]:
    instance = SqliteCommitLog(tmp_path / "rcl.sqlite3", evidence_port=evidence_store)
    yield instance
    instance.close()


def _seed_send_sealed(
    store: SqliteEvidenceStore,
    *,
    attempt_id: str,
    side: str,
    quantity: str,
    event_id: str = "root-event-1",
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_send_sealed`` exactly (cross-suite import
    forbidden by that module's own convention)."""
    payload = {
        "kind": "SEND_SEALED",
        "attempt_id": attempt_id,
        "send_seal": {
            "attempt_id": attempt_id,
            "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
            "outbound_side": side,
            "outbound_quantity": quantity,
            "reference": {"event_id": event_id, "causal_predecessor_ids": []},
        },
    }
    store.append(payload, kind="SEND_SEALED", record_class="SEND_SEALED")


def _seed_egress_result(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    attempt_id: str,
    filled_quantity: str | None,
    result_disposition: str | None = None,
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_egress_result`` exactly (including
    ``result_disposition`` — ``tos/src/tos/engine/core.py:705-720``'s own ``RESULT_UNMATCHED``
    payload shape)."""
    payload = {
        "attempt_id": attempt_id,
        "instrument_key": {"account": _ACCOUNT, "instrument": _INSTRUMENT},
        "egress_result_kind": "FULL_FILL" if filled_quantity is not None else "ACK",
        "filled_quantity": filled_quantity,
        "remaining_quantity": None,
        "result_disposition": result_disposition,
    }
    store.append(payload, kind=kind, record_class=kind)


def _seed_recovery_marker(
    store: SqliteEvidenceStore,
    *,
    kind: str,
    event_id: str,
    handling_started_evidence_seq: int | None = None,
) -> None:
    """Mirrors ``tests/riskstate/conftest.py::seed_recovery_marker`` exactly — the
    ``{"event_id": ..., "handling_started_evidence_seq": ...}`` shape
    ``EngineDriver._handle_interrupted_event`` durably appends
    (``tos_runtime/engine/driver.py:517-535`` — ``record_halt``'s own payload for
    ``HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND``, and the plain ``evidence_store.append`` for
    ``DECISION_TICK_DROPPED_ON_RECOVERY``, both carry ``event_id``; only the former also
    carries ``handling_started_evidence_seq`` — omitted (``None``) for the latter)."""
    payload: dict[str, object] = {"event_id": event_id}
    if handling_started_evidence_seq is not None:
        payload["handling_started_evidence_seq"] = handling_started_evidence_seq
    store.append(payload, kind=kind, record_class=kind)


def _stage_request(
    *, step: CommitmentStep, proposal_id: str = "prop-1", event_id: str = "root-event-1"
) -> StageRequest:
    """A ``StageRequest`` built via ``model_construct`` (module docstring) — the proposal's
    ``proposal_id`` is the only field :class:`RiskStateService` reads off it."""
    proposal = Proposal.model_construct(proposal_id=proposal_id)
    key = InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT)
    reference = OrderingEvent.model_construct(
        event_id=event_id, causal_predecessor_ids=()
    )
    return StageRequest.model_construct(
        step=step,
        instrument_key=key,
        proposal=proposal,
        reference=reference,
        prior_verdicts=(),
        attempt=None,
        value_view=None,
        held_position_magnitude=None,
    )


def _hse(*, envelope_max: str = "1") -> HardSafetyEnvelope:
    return HardSafetyEnvelope(
        governed_dimensions=(
            GovernedDimensionLimit(
                dimension=_ARE_DIM_ID,
                envelope_max=Decimal(envelope_max),
                unit="CONTRACTS",
            ),
        )
    )


def _scenario_set() -> AdverseScenarioSet:
    scenario_set = AdverseScenarioSet.issue(
        scheme=_SCHEME,
        scenario_set_id="riskstate-wiring-scenario-set",
        scenario_set_generation=1,
        policy_binding_id=None,
        covered_scenario_kinds=(
            AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ,
        ),
        evidence_package_ref=None,
    )
    assert isinstance(scenario_set, AdverseScenarioSet)
    return scenario_set


def _service(
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    max_attempts: int | None = 4,
    action_class: ActionClass = ActionClass.NEW_LONG,
    rcl_tip_reader: Callable[[], int | None] | None = None,
    hse_envelope_max: str = "1",
    effective_limit_value: str = "1",
    current_seq_reader: Callable[[], int | None] | None = None,
    monotonic_reader: Callable[[], int | None] | None = None,
) -> RiskStateService:
    are_path = tmp_path / "aggregate_risk_policy.yaml"
    are_path.write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{_INSTRUMENT}"]',
            account_scope=f'["{_ACCOUNT}"]',
            effective_limit_value=effective_limit_value,
        ),
        encoding="utf-8",
    )
    afg_path = tmp_path / "action_flow_policy.yaml"
    afg_path.write_text(
        action_flow_policy_yaml(account_scope=f'["{_ACCOUNT}"]'), encoding="utf-8"
    )
    are_policy = load_aggregate_risk_policy(are_path, scheme=_SCHEME)
    afg_policy = load_action_flow_policy(afg_path, scheme=_SCHEME)

    position_reader = EvidencePositionReader(
        evidence_store,
        account=_ACCOUNT,
        instrument=_INSTRUMENT,
        buy_side_token="BUY",
        sell_side_token="SELL",
    )
    flow_reader = InboxFlowReader(inbox, evidence_store, rcl_log, scheme=_SCHEME)
    return RiskStateService(
        are_policy=are_policy,
        afg_policy=afg_policy,
        scheme=_SCHEME,
        hse_envelope=_hse(envelope_max=hse_envelope_max),
        scenario_set=_scenario_set(),
        required_scenario_kinds=are_policy.required_scenario_kinds,
        position_reader=position_reader,
        flow_reader=flow_reader,
        rcl_log=rcl_log,
        construction_stage_reader=lambda: None,
        effect_envelope_reader=lambda: None,
        rcl_tip_reader=(rcl_tip_reader if rcl_tip_reader is not None else (lambda: 1)),
        monotonic_reader=(
            monotonic_reader if monotonic_reader is not None else (lambda: 1_000)
        ),
        max_attempts_reader=lambda: max_attempts,
        current_seq_reader=(
            current_seq_reader if current_seq_reader is not None else (lambda: None)
        ),
        evidence_store=evidence_store,
        environment_label="riskstate-wiring-test",
        action_class=action_class,
        activated_member_digests=("are-activation-digest", "afg-activation-digest"),
    )


# ===========================================================================
# Unit layer — RiskStateService
# ===========================================================================


class TestAggregateInputsFor:
    def test_empty_evidence_yields_zero_usage_cells(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert (
            len(inputs.cells) == 1
        )  # one (scope, dimension) x one required scenario kind
        cell = inputs.cells[0]
        assert cell.conservative_current_usage == Decimal("0")
        assert cell.conservative_current_usage_already_committed == Decimal("0")
        assert cell.required_concurrent_overlap_effect == Decimal("0")
        assert cell.effective_limit == Decimal("1")
        assert cell.max_credible_command_effect is None  # no construction yet
        # attestation-only fields are never authored by the service:
        assert inputs.all_fields_attributed is None
        assert inputs.numerically_safe is None
        assert inputs.valuation_ok is None
        assert inputs.limit_source_is_injected_envelope is None
        assert inputs.injected_envelope_max is not None
        assert inputs.injected_envelope_max.magnitude(_ARE_DIM_ID) == Decimal("1")
        assert inputs.grant_identity == "prop-1"
        assert inputs.lineage_ref == "root-event-1"

    def test_confirmed_fill_raises_conservative_usage(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="3")
        _seed_egress_result(
            evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="a1",
            filled_quantity="3",
        )
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("3")

    def test_unmatched_result_counts_full_sealed_quantity_as_unknown(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (3): a ``RESULT_UNMATCHED`` attempt's full sealed quantity counts in
        full toward conservative usage (the position-observation boundary GRANT→DENY case).
        """
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="5")
        _seed_egress_result(
            evidence_store,
            kind="RESULT_UNMATCHED",
            attempt_id="a1",
            filled_quantity=None,
        )
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("5")

    def test_new_short_mirrors_new_long_usage_magnitude(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (7): NEW_SHORT mirror — position sign flips, usage magnitude equal."""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="SELL", quantity="4")
        _seed_egress_result(
            evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="a1",
            filled_quantity="4",
        )
        service = _service(
            tmp_path, evidence_store, inbox, rcl_log, action_class=ActionClass.NEW_SHORT
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("4")

    def test_in_flight_sealed_send_feeds_overlap_effect_not_current_usage(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (4)'s own position-side half: a sealed send with NO terminal result
        contributes to ``required_concurrent_overlap_effect``, never
        ``conservative_current_usage`` (position.py's own ``in_flight_overlap_effect`` vs
        ``conservative_current_usage`` split)."""
        _seed_send_sealed(evidence_store, attempt_id="a1", side="BUY", quantity="2")
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        assert inputs.cells[0].conservative_current_usage == Decimal("0")
        assert inputs.cells[0].required_concurrent_overlap_effect == Decimal("2")

    def test_records_risk_state_observed_evidence(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        service.aggregate_inputs_for(request)
        cursor = evidence_store.connection.execute(
            "SELECT kind FROM entries ORDER BY seq ASC"
        )
        kinds = [row[0] for row in cursor.fetchall()]
        assert "RISK_STATE_OBSERVED" in kinds
        assert "AGGREGATE_RISK_POLICY_BOUND" in kinds
        assert "ACTION_FLOW_POLICY_BOUND" in kinds

    def test_injected_envelope_max_is_hse_bound_not_policy_effective_limit(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-3 (review of PR #704, 2026-09-16): every OTHER test in this suite sets the HSE
        ``envelope_max`` and the policy's ``effective_limit`` to the SAME value, so a mutation
        that swaps ``injected_envelope_max`` (``service.py``, plan §2.1's own "ARE
        ``injected_envelope_max`` comes from the already-loaded HSE") for
        ``self._are_policy.effective_limits`` (bypassing the HSE entirely) stays green. This
        test separates the two sources: HSE ``envelope_max=5``, policy
        ``effective_limit_value=100`` — a policy document that (incorrectly) tries to claim a
        limit twenty times its own governing envelope.
        """
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            hse_envelope_max="5",
            effective_limit_value="100",
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None
        # The HSE bound, not the policy's own (inflated) claim:
        assert inputs.injected_envelope_max is not None
        assert inputs.injected_envelope_max.magnitude(_ARE_DIM_ID) == Decimal("5")
        # The policy's own claim is carried too (untouched, for the predicate to compare
        # against) — proving the two sources really are independent in this service, not
        # silently unified upstream:
        assert inputs.effective_limit is not None
        assert inputs.effective_limit.magnitude(_ARE_DIM_ID) == Decimal("100")
        # The real kernel predicate this separation exists to feed: even if some other layer
        # mistakenly asserted `limit_source_is_injected_envelope=True`, a 100-vs-5 mismatch is
        # correctly refused — the safety invariant this field separation protects.
        from tos.are.predicates import envelope_bound_not_enlarged

        assert (
            envelope_bound_not_enlarged(
                decision_effective_limit=inputs.effective_limit,
                injected_envelope_max=inputs.injected_envelope_max,
                limit_source_is_injected_envelope=True,
            )
            is False
        )


class TestActionFlowInputsFor:
    def test_none_rcl_tip_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        service._rcl_tip_reader = lambda: None  # simulate a read failure
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        assert service.action_flow_inputs_for(request) is None

    def test_uncovered_action_class_yields_none_inputs(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(
            tmp_path, evidence_store, inbox, rcl_log, action_class=ActionClass.AMEND
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        assert service.action_flow_inputs_for(request) is None

    def test_happy_path_shape(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.action_class is ActionClassKind.NORMAL_NEW_RISK
        assert inputs.decision_generation == 1
        assert inputs.generation_current is False  # always re-derived by the wrapper
        assert inputs.producer_self_declared_scope is False
        assert inputs.economic_ref == f"resv-{_ACCOUNT}-{_INSTRUMENT}"
        assert inputs.committed_flow_vectors == ()
        assert inputs.flow_vector is not None
        assert inputs.flow_vector.magnitude(_AFG_DIM_ID) == Decimal("1")
        assert inputs.cause is not None
        assert inputs.cause.root_cause_identity == "root-event-1"
        assert (
            inputs.cause.forked_beyond_bound is False
        )  # attempts_for_cause(1) <= max(4)
        assert inputs.snapshot is not None
        assert inputs.snapshot.snapshot_generation == 1
        # attestation-only fields are never authored by the service:
        assert inputs.limit_source_is_injected_envelope is None
        assert inputs.economic_commitment_exclusive is None
        assert inputs.flow_commitment_exclusive is None

    def test_max_attempts_none_leaves_forked_beyond_bound_unknown(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        service = _service(tmp_path, evidence_store, inbox, rcl_log, max_attempts=None)
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.cause is not None
        assert inputs.cause.forked_beyond_bound is None

    def test_decision_generation_tracks_rcl_tip_reader(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-1 (review of PR #704, 2026-09-16): every OTHER test in this suite (and every
        e2e fixture) fixes ``rcl_tip_reader=lambda: 1``, so a mutation that hardcodes
        ``decision_generation=1`` (``service.py``, instead of the real ``rcl_tip``) stays
        green. ``_risk_attestations.py``'s own ``wrap_action_flow_inputs_provider`` feeds this
        value straight into ``generation_fenced`` to detect stale/replayed commits — a
        constant here silently disables that detection. This test uses a reader whose return
        value CHANGES between two calls and asserts the field tracks it both times."""
        tip_values = iter([7, 8])
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            rcl_tip_reader=lambda: next(tip_values),
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)

        first = service.action_flow_inputs_for(request)
        assert first is not None
        assert first.decision_generation == 7

        second_request = _stage_request(
            step=CommitmentStep.ACTION_FLOW_DECISION, proposal_id="prop-2"
        )
        second = service.action_flow_inputs_for(second_request)
        assert second is not None
        assert second.decision_generation == 8

    def test_elapsed_monotonic_ms_consumes_real_handling_started_receipt(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Re-review residual of HIGH-4 (review of PR #704, 2026-09-16): the earlier fix pinned
        ``InboxFlowReader`` resolving ``handling_started_monotonic`` from a real inbox row
        (``tests/riskstate/test_flow_observation.py``), but nothing pinned
        :class:`RiskStateService` actually CONSUMING that value into
        ``ActionFlowDecisionInputs.observed_amplification.elapsed_monotonic`` via
        :meth:`RiskStateService._elapsed_monotonic_ms` — a mutation making that method always
        return ``None`` stayed green across the full suite. This test enqueues a real
        ``EngineEvent``, marks it handling-started with a real ``EVENT_HANDLING_STARTED``
        evidence receipt, reads back that receipt's OWN real
        ``appended_at_monotonic_ns`` (the SAME column the service itself reads — never a
        hand-typed literal standing in for it), and supplies a ``monotonic_reader`` fixed at a
        KNOWN offset past it, so the expected millisecond difference is exact and
        deterministic despite the receipt's own timestamp being a real wall-clock read.
        """
        payload = EgressResultPayload(
            instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
            attempt_id="prop-1",
            kind=EgressResultKind.ACK,
        )
        event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        receipt = inbox.enqueue(event)
        marker = evidence_store.append(
            {"event_id": receipt.event_id},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        assert marker.seq is not None and marker.key_generation is not None
        inbox.mark_handling_started(
            receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
        )
        started_ns = next(
            entry.appended_at_monotonic_ns
            for entry in evidence_store.iter_entry_meta()
            if entry.seq == marker.seq
        )
        started_ms = started_ns // 1_000_000
        expected_elapsed_ms = 5_000
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            current_seq_reader=lambda: receipt.seq,
            monotonic_reader=lambda: started_ms + expected_elapsed_ms,
        )
        request = _stage_request(step=CommitmentStep.ACTION_FLOW_DECISION)
        inputs = service.action_flow_inputs_for(request)
        assert inputs is not None
        assert inputs.observed_amplification is not None
        assert inputs.observed_amplification.elapsed_monotonic == Decimal(
            expected_elapsed_ms
        )


# ===========================================================================
# HIGH-2 (review of PR #704, 2026-09-16) — RISK_STATE_OBSERVED.absent_fields honesty
# ===========================================================================


def _read_last_observed_absent_fields(evidence_store: SqliteEvidenceStore) -> list[str]:
    """Reads the most recently appended ``RISK_STATE_OBSERVED`` row's own ``absent_fields``
    list straight off the durable store (the SAME ``entries.payload_json`` shape
    ``tos_runtime.evidence.store.SqliteEvidenceStore.append`` itself writes — ``{"payload":
    ..., "masked_keys": [...]}`` — mirroring how this file's own ``_evidence_kind_counts``
    already reads the ``entries`` table directly rather than through a decrypt/query API this
    store does not expose)."""
    import json

    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "no RISK_STATE_OBSERVED row was recorded"
    payload = json.loads(row[0])["payload"]
    absent = payload["absent_fields"]
    assert isinstance(absent, list)
    return absent


def _read_last_risk_state_observed(evidence_store: SqliteEvidenceStore) -> dict:
    """Reads the most recently appended ``RISK_STATE_OBSERVED`` row's FULL payload dict —
    sibling of :func:`_read_last_observed_absent_fields` for tests that need more than just
    ``absent_fields`` (e.g. ``flow.duplicates_rejected``/``flow.replays_definition``).
    """
    import json

    row = evidence_store.connection.execute(
        "SELECT payload_json FROM entries WHERE kind = 'RISK_STATE_OBSERVED' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "no RISK_STATE_OBSERVED row was recorded"
    payload = json.loads(row[0])["payload"]
    assert isinstance(payload, dict)
    return payload


class TestAbsentFieldsHonesty:
    def test_isolated_flow_absence_reports_exactly_the_one_remaining_structural_gap(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-2, isolated form: calls the private ``_record_observation`` directly (module
        docstring's own "split out ... purely for that method's own 100-line size budget" —
        it is the SAME code path :meth:`RiskStateService.aggregate_inputs_for` calls) with a
        hand-built, REALISTIC :class:`FlowObservation` — ``duplicates_rejected``/``replays``
        are concrete ``0``s (TOS action-flow observation completion wave, 2026-09-16:
        :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader.observe` never returns
        ``None`` for either once a scan ran), ``root_event_seq``/``handling_started_monotonic``/
        ``lineage_found`` are also concrete, and only ``committed_vectors`` is empty —
        isolating the claim from step 6's OWN absent fields
        (``max_credible_command_effect``/``effect_digest``, present whenever
        construction/effect-envelope readers return ``None``, exercised separately below). A
        mutation hardcoding ``absent_fields=[]`` (the review's own M5 finding) must fail this
        exact assertion."""
        service = _service(tmp_path, evidence_store, inbox, rcl_log)
        flow_obs = FlowObservation(
            queue_depth=0,
            in_flight=0,
            attempts_for_cause=0,
            duplicates_rejected=0,
            replays=0,
            root_event_seq=3,
            handling_started_monotonic=123456,
            lineage_found=True,
            sources=("inbox:current_seq",),
            replays_definition=REPLAYS_DEFINITION,
        )
        position_obs = PositionObservation(
            scope_key=f"{_ACCOUNT}::{_INSTRUMENT}",
            confirmed_net=Decimal("0"),
            unknown_buy=Decimal("0"),
            unknown_sell=Decimal("0"),
            in_flight_buy=Decimal("0"),
            in_flight_sell=Decimal("0"),
            attempts_seen=0,
            sources=(),
        )
        service._record_observation(
            attempt_id="prop-isolated",
            position_obs=position_obs,
            flow_obs=flow_obs,
            committed_vectors=(),
            extra_absent=(),
        )
        absent = _read_last_observed_absent_fields(evidence_store)
        assert absent == ["committed_flow_vectors"]

    def test_real_first_attempt_absent_fields_include_only_the_one_remaining_gap(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """HIGH-2, realistic form: drives the SAME real ``aggregate_inputs_for`` path a brand
        new first attempt takes (real inbox row, real ``EVENT_HANDLING_STARTED`` marker, real
        ``current_seq_reader``) and asserts the ONE remaining structurally-unobservable name
        (``committed_flow_vectors``) is present while EVERY flow name this wave now observes
        (``duplicates_rejected``/``replays``/``root_event_seq``/``handling_started_monotonic``/
        ``lineage_found``) is NOT — documenting, honestly, that step 6's own construction-time
        absent fields (``max_credible_command_effect``/``effect_digest``, since this suite's
        ``_service`` fixes ``construction_stage_reader``/``effect_envelope_reader`` to
        ``lambda: None``) are ALSO present here, same as the isolated test above avoids by
        calling ``_record_observation`` directly."""
        payload = EgressResultPayload(
            instrument_key=InstrumentKey(account=_ACCOUNT, instrument=_INSTRUMENT),
            attempt_id="prop-1",
            kind=EgressResultKind.ACK,
        )
        event = EngineEvent(kind=EventKind.EGRESS_RESULT, egress_result=payload)
        receipt = inbox.enqueue(event)
        marker = evidence_store.append(
            {"event_id": receipt.event_id},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        assert marker.seq is not None and marker.key_generation is not None
        inbox.mark_handling_started(
            receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
        )
        service = _service(
            tmp_path,
            evidence_store,
            inbox,
            rcl_log,
            current_seq_reader=lambda: receipt.seq,
        )
        request = _stage_request(step=CommitmentStep.AGGREGATE_RISK_DECISION)
        inputs = service.aggregate_inputs_for(request)
        assert inputs is not None

        absent = set(_read_last_observed_absent_fields(evidence_store))
        assert "committed_flow_vectors" in absent
        assert "duplicates_rejected" not in absent
        assert "replays" not in absent
        assert "root_event_seq" not in absent
        assert "handling_started_monotonic" not in absent
        assert "lineage_found" not in absent


# ===========================================================================
# Wiring layer — build_risk_state_service cross-checks
# ===========================================================================


def _write_riskstate_wiring_config(
    tmp_path: Path,
    *,
    account: str = _ACCOUNT,
    instrument: str = _INSTRUMENT,
    action_class_map: str | None = None,
    buy_side_token: str = "BUY",
    sell_side_token: str = "SELL",
    activate_are: bool = True,
    activate_afg: bool = True,
) -> Path:
    """A minimal, self-contained config directory for
    :func:`~tos_runtime.compose._riskstate_wiring.build_risk_state_service`'s own cross-check
    tests — deliberately NOT the shared ``tests/compose/conftest.py::config_dir`` fixture
    (module docstring)."""
    directory = tmp_path / "riskstate-config"
    directory.mkdir()
    (directory / "aggregate_risk_policy.yaml").write_text(
        aggregate_risk_policy_yaml(
            instrument_scope=f'["{instrument}"]', account_scope=f'["{account}"]'
        ),
        encoding="utf-8",
    )
    (directory / "action_flow_policy.yaml").write_text(
        action_flow_policy_yaml(
            account_scope=f'["{account}"]',
            action_class_map=action_class_map,
            buy_side_token=buy_side_token,
            sell_side_token=sell_side_token,
        ),
        encoding="utf-8",
    )
    are_loaded = load_aggregate_risk_policy(
        directory / "aggregate_risk_policy.yaml", scheme=_SCHEME
    )
    afg_loaded = load_action_flow_policy(
        directory / "action_flow_policy.yaml", scheme=_SCHEME
    )
    members = []
    if activate_are:
        members.append(
            {
                "kind": "AGGREGATE_RISK_POLICY",
                "member_id": are_loaded.policy.policy_id,
                "generation": are_loaded.policy.policy_generation,
                "digest": are_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            }
        )
    if activate_afg:
        members.append(
            {
                "kind": "ACTION_FLOW_POLICY",
                "member_id": afg_loaded.policy.policy_id,
                "generation": afg_loaded.policy.policy_generation,
                "digest": afg_loaded.policy.canonical_digest,
                "resolved": True,
                "immutable": True,
            }
        )
    (directory / "safety_activation.yaml").write_text(
        yaml.safe_dump({"members": members}, sort_keys=False), encoding="utf-8"
    )
    return directory


def _build_service_from_wiring_config(
    directory: Path,
    tmp_path: Path,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    *,
    hse_dimension: str = _ARE_DIM_ID,
    venue_allowed_sides: frozenset[str] = frozenset({"BUY", "SELL"}),
    scenario_set: AdverseScenarioSet | None = None,
) -> RiskStateService:
    del tmp_path
    construction = fx.construction_config()
    hse = HardSafetyEnvelope(
        governed_dimensions=(
            GovernedDimensionLimit(
                dimension=hse_dimension, envelope_max=Decimal("1"), unit="CONTRACTS"
            ),
        )
    )
    return build_risk_state_service(
        config_dir=directory,
        scheme=_SCHEME,
        construction=construction,
        environment_label="riskstate-wiring-test",
        evidence_store=evidence_store,
        inbox=inbox,
        rcl_log=rcl_log,
        hse_envelope=hse,
        scenario_set=scenario_set if scenario_set is not None else _scenario_set(),
        required_scenario_kinds=frozenset(
            {AdverseScenarioKind.ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ}
        ),
        rcl_tip_reader=lambda: 1,
        monotonic_reader=lambda: 1_000,
        max_attempts_reader=lambda: 4,
        construction_stage_reader=lambda: None,
        effect_envelope_reader=lambda: None,
        venue_allowed_sides=venue_allowed_sides,
    )


class TestBuildRiskStateServiceCrossChecks:
    def test_happy_path_builds(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        service = _build_service_from_wiring_config(
            directory, tmp_path, evidence_store, inbox, rcl_log
        )
        assert isinstance(service, RiskStateService)

    def test_account_mismatch_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(
            tmp_path, account="some-other-account"
        )
        with pytest.raises(RiskPolicyScopeMismatch, match="account_scope"):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_hse_dimension_missing_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (5): a policy dimension the HSE does not declare refuses at boot."""
        directory = _write_riskstate_wiring_config(tmp_path)
        with pytest.raises(RiskPolicyScopeMismatch, match="governed_dimensions"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                hse_dimension="INSTRUMENT::SOME_OTHER_DIMENSION",
            )

    def test_members_activation_missing_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        """Plan §5 실증 (6): a ``members:`` mismatch (here: absent entirely) refuses at boot."""
        directory = _write_riskstate_wiring_config(tmp_path, activate_are=False)
        with pytest.raises(PolicyNotActivated):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_scenario_coverage_gap_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        empty_scenario_set = AdverseScenarioSet.issue(
            scheme=_SCHEME,
            scenario_set_id="empty-scenario-set",
            scenario_set_generation=1,
            policy_binding_id=None,
            covered_scenario_kinds=(),
            evidence_package_ref=None,
        )
        assert isinstance(empty_scenario_set, AdverseScenarioSet)
        with pytest.raises(RiskPolicyScopeMismatch, match="covered_scenario_kinds"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                scenario_set=empty_scenario_set,
            )

    def test_action_class_not_covered_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(
            tmp_path, action_class_map='{"DECREASE": "ORDINARY_REDUCE_OR_EXIT"}'
        )
        with pytest.raises(RiskPolicyScopeMismatch, match="action_class_map"):
            _build_service_from_wiring_config(
                directory, tmp_path, evidence_store, inbox, rcl_log
            )

    def test_side_token_not_in_venue_allowed_sides_refuses(
        self,
        tmp_path: Path,
        evidence_store: SqliteEvidenceStore,
        inbox: SqliteEventInbox,
        rcl_log: SqliteCommitLog,
    ) -> None:
        directory = _write_riskstate_wiring_config(tmp_path)
        with pytest.raises(RiskPolicyScopeMismatch, match="side_tokens"):
            _build_service_from_wiring_config(
                directory,
                tmp_path,
                evidence_store,
                inbox,
                rcl_log,
                venue_allowed_sides=frozenset({"LONG", "SHORT"}),
            )


# ===========================================================================
# compose_paper_runtime level — (9) run/boot rule
# ===========================================================================


def test_compose_paper_runtime_refuses_when_files_absent_and_a_provider_is_none(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Plan §3 "run 차단 목록" — the shared ``config_dir`` fixture never carries
    ``aggregate_risk_policy.yaml``/``action_flow_policy.yaml``, so leaving either provider
    ``None`` must refuse at boot rather than silently admit a permanently-UNKNOWN runtime.
    """
    fx.write_band_strategy_file(config_dir)
    with pytest.raises(RiskStateConfigError):
        compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
        )


def test_compose_paper_runtime_with_explicit_providers_leaves_risk_state_none(
    config_dir: Path, data_dir: Path, custody_root: Path
) -> None:
    """Plan §5 실증 (8): explicit providers are still honored when the two policy files are
    absent — ``ComposedRuntime.risk_state`` stays ``None`` (the pre-existing test seam).
    """
    from tos_runtime.risk.aggregate import AggregateRiskDecisionInputs
    from tos_runtime.risk.flow import ActionFlowDecisionInputs

    fx.write_band_strategy_file(config_dir)

    def _aggregate(request: object) -> AggregateRiskDecisionInputs | None:
        return None

    def _action_flow(request: object) -> ActionFlowDecisionInputs | None:
        return None

    runtime = compose_paper_runtime(
        config_dir,
        data_dir,
        custody_root,
        "non-live-test",
        construction=fx.construction_config(),
        aggregate_risk_inputs_provider=_aggregate,
        action_flow_inputs_provider=_action_flow,
        wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
    )
    assert runtime.risk_state is None


# ===========================================================================
# E2E layer — the plan's own acceptance criterion (module docstring)
# ===========================================================================


def _fresh_risk_state_dirs(root: Path) -> tuple[Path, Path, Path]:
    """One independent ``(config_dir_with_risk_state, data_dir, custody_root)`` triple under
    ``root`` — mirrors ``test_symmetry.py::_fresh_compose_dirs``'s own ``__wrapped__`` idiom
    (pytest refuses a fixture function called directly; the plain function each decorator
    wraps is reachable via ``__wrapped__``), extended one layer to also apply
    ``config_dir_with_risk_state`` on top of the base ``config_dir``."""
    root.mkdir(parents=True, exist_ok=True)
    config_dir = call_wrapped_fixture(_config_dir_fixture, root)
    config_dir = call_wrapped_fixture(_config_dir_with_risk_state_fixture, config_dir)
    data_dir = call_wrapped_fixture(_data_dir_fixture, root)
    custody_root = call_wrapped_fixture(_custody_root_fixture, root)
    return config_dir, data_dir, custody_root


def _drive_two_calls(runtime, custody_root: Path, event):
    """The SAME two-``run_once``-call pattern ``test_compose_root.py``'s own ADMIT tests use
    (first call discovers the proposal digest and writes the approval file; second call
    reaches the steps this wave's service feeds) — returns the second call's own
    ``FlowResult``."""
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
    results2 = runtime.run_once((event,))
    flow = results2[0].flow
    assert flow is not None
    return {v.step.value: v for v in flow.verdicts}


def _evidence_kind_counts(runtime) -> dict[str, int]:
    rows = runtime.evidence_store.connection.execute(
        "SELECT kind FROM entries ORDER BY seq ASC"
    ).fetchall()
    counts: dict[str, int] = {}
    for (kind,) in rows:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


class TestComposeE2E:
    """The plan's own acceptance criterion, driven through the FULL compose stack with no
    explicit providers (module docstring's own "E2E layer" section — read that first for the
    honest step 7 finding this class's own assertions reflect)."""

    def test_first_attempt_reaches_aggregate_risk_grant(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (1) — no explicit providers, the production
        :class:`~tos_runtime.riskstate.service.RiskStateService` supplies both steps 6/7's
        inputs. Step 6 (AGGREGATE_RISK_DECISION) reaches a real ``GRANT``/``ADMIT`` with no
        hand-built literal cell anywhere in this test. Step 7 (ACTION_FLOW_DECISION) ALSO
        reaches a real ``GRANT``/``ADMIT`` (TOS action-flow observation completion wave,
        2026-09-16 — this test previously asserted the honest ``amplification_bounded`` gap
        this suite's own module docstring used to document; that gap is now closed, see the
        module docstring's own "Resolved" section). Both ``*_POLICY_BOUND`` rows and exactly
        one ``RISK_STATE_OBSERVED`` row are recorded, with no ``duplicates_rejected``/
        ``replays`` absence (a brand-new, first-ever attempt still gets concrete ``0``s on
        both axes — a completed scan finding nothing is a real fact, not a gap). Also asserts
        (re-review residual of HIGH-4, 2026-09-16) that the REAL first attempt's own step-7
        inputs carry a non-``None`` ``observed_amplification.elapsed_monotonic`` — captured via
        a spy on ``runtime.risk_state.action_flow_inputs_for`` (an instance-attribute override
        shadows the bound method for the SAME object the compose thunks already close over,
        per ``root.py``'s own ``risk_state_cell`` — never a second, separately-built service).
        """
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None

        captured_action_flow_inputs = []
        original_action_flow_inputs_for = runtime.risk_state.action_flow_inputs_for

        def _spy(request):
            result = original_action_flow_inputs_for(request)
            if result is not None:
                captured_action_flow_inputs.append(result)
            return result

        runtime.risk_state.action_flow_inputs_for = _spy  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)

        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason
        assert are_verdict.native_verdict_value == "GRANT"

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "ADMIT", (
            "expected step 7 GRANT (module docstring's own 'Resolved' section) — got "
            f"{afg_verdict.outcome.value}: {afg_verdict.reason}"
        )
        assert afg_verdict.native_verdict_value == "GRANT"

        assert captured_action_flow_inputs, (
            "action_flow_inputs_for was never called with a non-None result — the spy "
            "captured nothing"
        )
        first_attempt_inputs = captured_action_flow_inputs[0]
        assert first_attempt_inputs.observed_amplification is not None
        assert first_attempt_inputs.observed_amplification.elapsed_monotonic is not None
        # M1 pin (plan §5): the two amplification axes this wave observes are concrete ``0``s
        # for a brand-new first attempt, never ``None`` — reverting either to a literal
        # ``None`` (module docstring's pre-fix state) collapses this to UNKNOWN, failing the
        # ADMIT/GRANT assertions above.
        assert (
            first_attempt_inputs.observed_amplification.duplicate_redelivery_expansion
            == 0
        )
        assert (
            first_attempt_inputs.observed_amplification.failover_reconnect_replay_expansion
            == 0
        )

        counts = _evidence_kind_counts(runtime)
        assert counts.get("AGGREGATE_RISK_POLICY_BOUND") == 1
        assert counts.get("ACTION_FLOW_POLICY_BOUND") == 1
        assert counts.get("RISK_STATE_OBSERVED") == 1

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        flow_row = observed_row["flow"]
        assert flow_row["duplicates_rejected"] == 0
        assert flow_row["replays"] == 0
        assert flow_row["replays_definition"] == REPLAYS_DEFINITION
        assert "duplicates_rejected" not in observed_row["absent_fields"]
        assert "replays" not in observed_row["absent_fields"]

    def test_seeded_prior_fill_flips_aggregate_risk_decision_to_deny(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (2) — a durable prior fill large enough to exceed the policy's own
        effective limit (``_RISK_STATE_ENVELOPE_MAX``, ``tests/compose/conftest.py``) flips
        step 6 from ``GRANT`` to ``DENY`` on the very next attempt, via the REAL
        ``tos.are.adverse_increment`` headroom check over the position observation's own
        durable-evidence fold — no hand-built cell anywhere in this test either.

        The prior fill is DERIVED from this attempt's own real derived quantity
        (``construction.derivation.quantity``, read off the FIRST ``run_once`` call — the
        same discovery call ``_drive_two_calls`` always makes first, before any approval file
        exists), never a literal restating what that quantity happens to be today. This wave
        has already been bitten twice by exactly that coupling (a hardcoded expectation
        silently invalidated by an unrelated fixture-bound change elsewhere — lane C's own
        instance, and this test's prior ``quantity="99990"`` against a ``max_quantity``
        lane A later raised for the sizing cross-check, 2026-09-16). Computing the prior fill
        from the real derived quantity means a future bound change moves this test with it.

        ⚠ **What this test does and does not guarantee** (code-review MEDIUM, 2026-09-16): the
        prior fill is computed as ``envelope_max - derived_quantity + 1``, which makes
        ``prior_fill + derived_quantity == envelope_max + 1`` true BY CONSTRUCTION — this test
        proves step 6 correctly flips ``GRANT`` -> ``DENY`` off whatever real derived quantity
        the runtime produces (the plumbing), but it does NOT independently prove that derived
        quantity is itself the RIGHT number (a derivation that deterministically returned 0, or
        any other fixed value, would still make this test pass — the ``derived_quantity > 0``
        assertion below only catches an absent or degenerate value, not a wrong one). Quantity
        CORRECTNESS — that the derived value matches what the governed sizing bound actually
        authorizes — is lane C's job, pinned by its own invariant tests against the derivation's
        output; that coverage exists, it is just not duplicated here.
        """
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )

        # First call (the SAME discovery call _drive_two_calls makes): no approval file exists
        # yet, so this denies at step 4 IAP, but step 2 construction — and its real derivation
        # — already ran, giving us the one real fact this test's arithmetic depends on.
        event = fx.crossing_event()
        results = runtime.run_once((event,))
        pipeline = results[0].pipeline
        assert pipeline is not None and pipeline.proposal is not None
        proposal_digest = pipeline.proposal.canonical_digest
        assert (
            proposal_digest is not None
        )  # an ISSUED proposal always has a concrete digest
        construction = runtime.construction_stage.construction
        assert construction is not None and construction.intent is not None
        assert construction.intent.canonical_digest is not None  # ISSUED, same as above
        derived_quantity = construction.derivation.quantity
        assert (
            derived_quantity is not None
        ), "no derived quantity to compute a prior fill from"
        assert derived_quantity > 0, (
            f"derived_quantity {derived_quantity} is not a sane, non-degenerate positive "
            "value — a zero or negative derivation would make the arithmetic below trivially "
            "satisfiable without the plumbing it claims to exercise actually running"
        )
        write_approval_file(
            custody_root,
            proposal_digest=proposal_digest,
            environment_label="non-live-test",
            approved_intent_envelope_digest=construction.intent.canonical_digest,
        )

        # A durable prior fill that sits just UNDER the effective limit given THIS attempt's
        # own derived quantity — adding the real derived quantity must cross the limit,
        # regardless of what that derived quantity happens to be. The SAME durable
        # evidence-row SHAPE the real synthetic transport would produce (module docstring's
        # own unit-layer helpers, reused here against the real evidence store).
        envelope_max = Decimal(_RISK_STATE_ENVELOPE_MAX)
        prior_fill = envelope_max - derived_quantity + 1
        assert prior_fill > 0, (
            f"derived_quantity {derived_quantity} leaves no room for a positive prior fill "
            f"under the {envelope_max} effective limit — the fixture's own headroom assumption "
            "no longer holds"
        )
        _seed_send_sealed(
            runtime.evidence_store,
            attempt_id="prior-fill-attempt",
            side="BUY",
            quantity=str(prior_fill),
        )
        _seed_egress_result(
            runtime.evidence_store,
            kind="EGRESS_RESULT_CONSUMED",
            attempt_id="prior-fill-attempt",
            filled_quantity=str(prior_fill),
        )

        # Second call: the prior fill plus THIS attempt's own real derived quantity together
        # exceed the effective limit by construction (prior_fill + derived_quantity ==
        # envelope_max + 1), so step 6 must flip to DENY.
        results2 = runtime.run_once((event,))
        flow = results2[0].flow
        assert flow is not None
        verdict_by_step = {v.step.value: v for v in flow.verdicts}
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "DENY", are_verdict.reason
        assert are_verdict.native_verdict_value == "DENY"

    def test_duplicate_dispositions_beyond_envelope_flip_action_flow_decision_to_unknown(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (2), CORRECTED against the real kernel composer (finding, reported —
        the plan text says "DENY"; the kernel says otherwise, see below) — ``RESULT_UNMATCHED
        {DUPLICATE}`` rows for an attempt sealed against THIS tick's own root event (traced
        via ``SEND_SEALED`` lineage, the SAME set
        :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader._scan_sealed_lineage`
        builds), seeded BEYOND the fixture's own ``max_duplicate_redelivery_expansion`` (2,
        ``tests/compose/conftest.py``), flip step 7 from ``GRANT`` to ``UNKNOWN`` — never
        ``DENY`` — through the REAL ``tos.afg.predicates._decide_action_flow_result`` composer:
        ``if amplification_ok is not True: return ActionFlowResult.UNKNOWN``
        (``tos/src/tos/afg/predicates.py:584-585``) is evaluated BEFORE any of the composer's
        two ``DENY`` branches (empty requested scope; ``envelope_ok is not True``) even run —
        an unbounded/exceeded amplification axis is restrictive-UNKNOWN by kernel design
        ("every unproven premise resolves to UNKNOWN... before any DENY/GRANT conclusion is
        drawn", same module's own docstring), not a proven denial. No hand-built cell anywhere
        in this test. A tiny sealed quantity (``"1"``) keeps step 6's own conservative-usage
        check at ``GRANT`` (unlike the prior-fill test above, which deliberately exceeds it).

        **Seeding mechanics**: ``EngineDriver.enqueue_and_run``'s own ``_stamp`` DISCARDS the
        event's caller-supplied ``reference`` and re-stamps a fresh one from its own internal
        counter on every admission (``driver.py:396-403``, "the caller-supplied reference is
        discarded entirely") — so the REAL ``root_event_id`` this attempt's step 6/7 evaluate
        against is only known at the moment
        :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader.observe` is actually
        invoked, never derivable in advance from the fixture's own ``event`` object. This test
        wraps ``runtime.risk_state._flow_reader.observe`` to seed using the REAL
        ``root_event_id`` it is called with, then delegates to the original implementation —
        never a guessed or pre-computed identifier."""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None
        reader = runtime.risk_state._flow_reader
        original_observe = reader.observe
        seeded = {"done": False}

        def _seeding_observe(*, root_event_id, attempt_id, root_event_seq=None):
            if not seeded["done"]:
                seeded["done"] = True
                _seed_send_sealed(
                    runtime.evidence_store,
                    attempt_id="dup-attempt-1",
                    side="BUY",
                    quantity="1",
                    event_id=root_event_id,
                )
                # 3 DUPLICATE rows for the SAME attempt — exceeds
                # max_duplicate_redelivery_expansion=2.
                for _ in range(3):
                    _seed_egress_result(
                        runtime.evidence_store,
                        kind="RESULT_UNMATCHED",
                        attempt_id="dup-attempt-1",
                        filled_quantity=None,
                        result_disposition="DUPLICATE",
                    )
            return original_observe(
                root_event_id=root_event_id,
                attempt_id=attempt_id,
                root_event_seq=root_event_seq,
            )

        reader.observe = _seeding_observe  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        assert seeded[
            "done"
        ], "InboxFlowReader.observe was never invoked — nothing seeded"
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "UNKNOWN", afg_verdict.reason

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        assert observed_row["flow"]["duplicates_rejected"] == 3

    def test_recovery_markers_beyond_envelope_flip_action_flow_decision_to_unknown(
        self,
        config_dir_with_risk_state: Path,
        data_dir: Path,
        custody_root: Path,
    ) -> None:
        """Plan §5 실증 (3), CORRECTED against the real kernel composer (same finding as the
        DUPLICATE test above) — restart-recovery marker rows keyed to THIS tick's own
        content-addressed root event identity, seeded BEYOND the fixture's own
        ``max_failover_reconnect_replay_expansion`` (2), flip step 7 from ``GRANT`` to
        ``UNKNOWN`` — never ``DENY`` — for the SAME reason: ``amplification_ok is not True``
        resolves to ``UNKNOWN`` before the composer's own ``DENY`` branches ever run
        (``tos/src/tos/afg/predicates.py:584-585``).

        **Seeding mechanics**: as in the DUPLICATE test above, ``EngineDriver.enqueue_and_run``
        re-stamps a fresh reference on every admission, so the exact content-addressed
        ``event_id`` this attempt's own ``EVENT_HANDLING_STARTED`` marker carries cannot be
        derived in advance from the fixture's own ``event`` object — it is only knowable via
        :meth:`~tos_runtime.riskstate.flow_observation.InboxFlowReader
        ._resolve_root_content_event_id` at the moment ``observe`` actually runs (the SAME
        method production code calls). This test wraps ``observe`` to resolve the REAL content
        identity via that exact method, seed against it, then delegate to the original
        implementation — never a guessed or pre-computed identifier."""
        fx.write_band_strategy_file(config_dir_with_risk_state)
        runtime = compose_paper_runtime(
            config_dir_with_risk_state,
            data_dir,
            custody_root,
            "non-live-test",
            construction=fx.construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None
        reader = runtime.risk_state._flow_reader
        original_observe = reader.observe
        seeded = {"done": False}

        def _seeding_observe(*, root_event_id, attempt_id, root_event_seq=None):
            if not seeded["done"]:
                seeded["done"] = True
                content_event_id = reader._resolve_root_content_event_id(root_event_seq)
                assert content_event_id is not None, (
                    "the root row's own content-addressed event_id could not be resolved — "
                    "nothing to seed against"
                )
                # 2 markers of EACH recovery kind (4 total) for THIS tick's own
                # content-addressed event — exceeds max_failover_reconnect_replay_expansion=2.
                # Deliberately a MIX, not one kind repeated: dropping either
                # `DECISION_TICK_DROPPED_ON_RECOVERY` or
                # `HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND` from
                # `_RECOVERY_MARKER_KINDS` would still leave 2 of the other kind — exactly
                # AT the bound, no longer exceeding it — so this test goes RED under either
                # single-kind-removed mutation (review HIGH, PR #707).
                for _ in range(2):
                    _seed_recovery_marker(
                        runtime.evidence_store,
                        kind="DECISION_TICK_DROPPED_ON_RECOVERY",
                        event_id=content_event_id,
                    )
                for _ in range(2):
                    _seed_recovery_marker(
                        runtime.evidence_store,
                        kind="HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND",
                        event_id=content_event_id,
                        handling_started_evidence_seq=root_event_seq,
                    )
            return original_observe(
                root_event_id=root_event_id,
                attempt_id=attempt_id,
                root_event_seq=root_event_seq,
            )

        reader.observe = _seeding_observe  # type: ignore[method-assign]

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        assert seeded[
            "done"
        ], "InboxFlowReader.observe was never invoked — nothing seeded"
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "UNKNOWN", afg_verdict.reason

        observed_row = _read_last_risk_state_observed(runtime.evidence_store)
        assert observed_row["flow"]["replays"] == 4

    def test_new_short_mirrors_new_long_at_aggregate_risk_grant(
        self, tmp_path: Path
    ) -> None:
        """Plan §5 실증 (7) — the NEW_SHORT mirror (:mod:`tests.compose._symmetry_fixtures`,
        TOS Phase 5 W5 plan §2 decision 8) reaches the SAME step 6 ``GRANT``/``ADMIT`` as the
        NEW_LONG case, through the real ``EvidencePositionReader`` — position sign flips
        (``SELL`` vs ``BUY``), usage MAGNITUDE (and therefore the decision) does not. Also
        reaches the SAME step 7 ``GRANT``/``ADMIT`` (plan §2 decision 4, TOS action-flow
        observation completion wave, 2026-09-16 — the mirror path exercises the SAME
        :class:`~tos_runtime.riskstate.service.RiskStateService` observation code, so it must
        reach the same outcome as the NEW_LONG case above).

        Also pins DIRECTION/SIDE self-consistency on the INTEGRATED path (code-review MEDIUM,
        2026-09-16): the shared OCP document's own ``DIRECTION`` axis says ``LONG`` (lane A's
        ``ocp_yaml()`` default), yet this composition's ``action_class`` is ``NEW_SHORT`` — the
        exact mismatch ``resolve_construction_direction`` exists to resolve. Before that fix,
        this composition could not derive a SIDE at all; before the envelope self-consistency
        fix, it could derive SIDE=SELL while the envelope's own DIRECTION binding stayed at the
        policy's LONG. Only one hermetic unit test
        (``tests/compose/test_envelope_wiring.py::test_envelope_replaces_the_direction_binding
        _with_the_resolved_direction``) pinned that until now — this asserts the SAME fact on
        the real composed attempt, so deleting the replacement fails here too, not only beside
        the code that implements it."""
        config_dir, data_dir, custody_root = _fresh_risk_state_dirs(tmp_path / "short")
        sfx.write_mirrored_strategy_file(config_dir)
        runtime = compose_paper_runtime(
            config_dir,
            data_dir,
            custody_root,
            "non-live-test",
            construction=sfx.mirrored_construction_config(),
            aggregate_risk_inputs_provider=None,
            action_flow_inputs_provider=None,
            wall_clock=FixedWallClockReference(fx.DEFAULT_WALL_CLOCK_UNIX_MS),
        )
        assert runtime.risk_state is not None

        event = fx.crossing_event()
        verdict_by_step = _drive_two_calls(runtime, custody_root, event)
        are_verdict = verdict_by_step["AGGREGATE_RISK_DECISION"]
        assert are_verdict.outcome.value == "ADMIT", are_verdict.reason
        assert are_verdict.native_verdict_value == "GRANT"

        afg_verdict = verdict_by_step["ACTION_FLOW_DECISION"]
        assert afg_verdict.outcome.value == "ADMIT", afg_verdict.reason
        assert afg_verdict.native_verdict_value == "GRANT"

        construction = runtime.construction_stage.construction
        assert construction is not None and construction.envelope is not None
        direction_bindings = [
            b
            for b in construction.envelope.authorized_axis_bindings
            if b.axis is ConformanceAxis.DIRECTION
        ]
        assert direction_bindings == [
            AxisBinding(axis=ConformanceAxis.DIRECTION, value="SHORT")
        ], (
            "the composed envelope's own DIRECTION binding must match the NEW_SHORT action "
            "class, never the shared policy document's LONG axis left unreplaced"
        )
