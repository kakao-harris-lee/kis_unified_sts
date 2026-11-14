"""``tos_runtime.compose._riskstate_wiring`` — boots :class:`~tos_runtime.riskstate.service"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import CanonicalizationScheme
from tos.egressgw import SizingBound, VenueQuantityConstraint
from tos.egressgw.records import CandidateConstruction
from tos.engine.records import StageRequest
from tos.ioc import EconomicEffectEnvelope
from tos.venue import ActionClass

from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    EntryCloseBound,
)
from tos_runtime.riskstate.flow_observation import InboxFlowReader
from tos_runtime.riskstate.held_position import (
    HeldPositionCurrentness,
    HeldPositionProof,
)
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
    LoadedActionFlowPolicy,
    LoadedAggregateRiskPolicy,
    load_action_flow_policy,
    load_aggregate_risk_policy,
)
from tos_runtime.riskstate.position import EvidencePositionReader
from tos_runtime.riskstate.service import RiskStateService

__all__ = ["RiskPolicyScopeMismatch", "build_risk_state_service"]


class RiskPolicyScopeMismatch(RuntimeError):
    """Either governed policy's own declared coordinates disagree with this compose root's"""


def _cross_check_are_scope(
    are_policy: LoadedAggregateRiskPolicy, *, construction: ConstructionConfig
) -> None:
    if are_policy.account_scope != construction.account:
        raise RiskPolicyScopeMismatch(
            f"aggregate risk policy account_scope {are_policy.account_scope!r} != configured "
            f"construction.account {construction.account!r}"
        )
    if are_policy.instrument_scope != construction.instrument:
        raise RiskPolicyScopeMismatch(
            f"aggregate risk policy instrument_scope {are_policy.instrument_scope!r} != "
            f"configured construction.instrument {construction.instrument!r}"
        )


def _cross_check_scenario_coverage(
    are_policy: LoadedAggregateRiskPolicy,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
    *,
    scenario_set: AdverseScenarioSet,
) -> None:
    del are_policy
    covered = set(scenario_set.covered_scenario_kinds)
    missing = sorted(k.value for k in required_scenario_kinds - covered)
    if missing:
        raise RiskPolicyScopeMismatch(
            f"required_scenario_kinds names {missing!r}, which the loaded AdverseScenarioSet's "
            f"own covered_scenario_kinds {sorted(k.value for k in covered)!r} does not cover — "
            "a required-but-uncovered kind is permanently UNKNOWN, never a real floor"
        )


def _cross_check_action_class(
    afg_policy: LoadedActionFlowPolicy, *, action_class: ActionClass
) -> None:
    if action_class not in afg_policy.action_class_map:
        raise RiskPolicyScopeMismatch(
            f"action flow policy action_class_map does not cover this composition's fixed "
            f"construction.action_class {action_class!r} — every attempt would return UNKNOWN "
            "step 7 inputs forever"
        )


def _cross_check_side_tokens(
    afg_policy: LoadedActionFlowPolicy, *, venue_allowed_sides: frozenset[str]
) -> None:
    unknown = sorted(set(afg_policy.side_tokens) - venue_allowed_sides)
    if unknown:
        raise RiskPolicyScopeMismatch(
            f"action flow policy _runtime.side_tokens names {unknown!r}, which the venue "
            f"policy's own allowed_sides {sorted(venue_allowed_sides)!r} does not declare"
        )


def _cross_check_ocp_side_tokens(
    ocp_sides: frozenset[str], *, venue_allowed_sides: frozenset[str]
) -> None:
    """Sibling of :func:`_cross_check_side_tokens`, same subset-and-refuse shape, for the"""
    unknown = sorted(ocp_sides - venue_allowed_sides)
    if unknown:
        raise RiskPolicyScopeMismatch(
            f"order construction policy action_class_shape names side token(s) {unknown!r}, "
            f"which the venue policy's own allowed_sides {sorted(venue_allowed_sides)!r} does "
            "not declare"
        )


def _cross_check_ocp_sizing_bound(
    sizing_bound: SizingBound, *, venue_quantity_constraint: VenueQuantityConstraint
) -> None:
    """Sibling of :func:`_cross_check_side_tokens` / :func:`_cross_check_ocp_side_tokens`: the"""
    offenses: list[str] = []
    ocp_max, venue_max = (
        sizing_bound.max_quantity,
        venue_quantity_constraint.max_quantity,
    )
    if ocp_max is not None and venue_max is not None and ocp_max > venue_max:
        offenses.append(f"max_quantity: OCP {ocp_max} > venue {venue_max}")
    ocp_min, venue_min = (
        sizing_bound.min_quantity,
        venue_quantity_constraint.min_quantity,
    )
    if ocp_min is not None and venue_min is not None and ocp_min < venue_min:
        offenses.append(f"min_quantity: OCP {ocp_min} < venue {venue_min}")
    ocp_lot, venue_lot = sizing_bound.lot_size, venue_quantity_constraint.lot_size
    if (
        ocp_lot is not None
        and venue_lot is not None
        and venue_lot > 0
        and ocp_lot % venue_lot != 0
    ):
        offenses.append(
            f"lot_size: OCP {ocp_lot} is not a whole multiple of venue {venue_lot}"
        )
    if offenses:
        raise RiskPolicyScopeMismatch(
            "order construction policy sizing bound is WIDER than the venue quantity "
            f"constraint it claims to derive from ({'; '.join(offenses)})"
        )


def _load_and_activate(
    *, config_dir: Path, scheme: CanonicalizationScheme
) -> tuple[LoadedAggregateRiskPolicy, LoadedActionFlowPolicy, str, str]:
    """Load both policies and return their canonical digests — split out of"""
    are_policy = load_aggregate_risk_policy(
        config_dir / AGGREGATE_RISK_POLICY_CONFIG_NAME, scheme=scheme
    )
    afg_policy = load_action_flow_policy(
        config_dir / ACTION_FLOW_POLICY_CONFIG_NAME, scheme=scheme
    )
    p, a = are_policy.policy, afg_policy.policy
    assert p.policy_id is not None and p.policy_generation is not None
    assert p.canonical_digest is not None and a.canonical_digest is not None
    assert a.policy_id is not None and a.policy_generation is not None
    return are_policy, afg_policy, p.canonical_digest, a.canonical_digest


def build_risk_state_service(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    scenario_set: AdverseScenarioSet,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
    rcl_tip_reader: Callable[[], int | None],
    monotonic_reader: Callable[[], int | None],
    max_attempts_reader: Callable[[], int | None],
    construction_stage_reader: Callable[[], CandidateConstruction | None],
    effect_envelope_reader: Callable[[], EconomicEffectEnvelope | None],
    venue_allowed_sides: frozenset[str],
    action_class_reader: Callable[[], ActionClass] | None = None,
    attempt_arm_direction_reader: Callable[[], str | None] | None = None,
    held_position_proof_reader: (
        Callable[[StageRequest, str], HeldPositionProof | None] | None
    ) = None,
    held_position_currentness_reader: (
        Callable[[HeldPositionProof], HeldPositionCurrentness | None] | None
    ) = None,
    close_authority: CloseAuthoritySource = CloseAuthoritySource.BROKER_HELD_PROOF,
    entry_close_bound_reader: Callable[[], EntryCloseBound] | None = None,
) -> RiskStateService:
    """Load, activate, cross-check, and construct the production"""
    are_policy, afg_policy, are_digest, afg_digest = _load_and_activate(
        config_dir=config_dir, scheme=scheme
    )
    _cross_check_are_scope(are_policy, construction=construction)
    _cross_check_scenario_coverage(
        are_policy, required_scenario_kinds, scenario_set=scenario_set
    )
    _cross_check_action_class(afg_policy, action_class=construction.action_class)
    _cross_check_side_tokens(afg_policy, venue_allowed_sides=venue_allowed_sides)

    buy_token, sell_token = afg_policy.side_tokens
    position_reader = EvidencePositionReader(
        evidence_store,
        account=construction.account,
        instrument=construction.instrument,
        buy_side_token=buy_token,
        sell_side_token=sell_token,
    )
    flow_reader = InboxFlowReader(inbox, evidence_store, rcl_log, scheme=scheme)

    return RiskStateService(
        are_policy=are_policy,
        afg_policy=afg_policy,
        scheme=scheme,
        scenario_set=scenario_set,
        required_scenario_kinds=required_scenario_kinds,
        position_reader=position_reader,
        flow_reader=flow_reader,
        rcl_log=rcl_log,
        construction_stage_reader=construction_stage_reader,
        effect_envelope_reader=effect_envelope_reader,
        rcl_tip_reader=rcl_tip_reader,
        monotonic_reader=monotonic_reader,
        max_attempts_reader=max_attempts_reader,
        current_seq_reader=_current_seq_reader_for(inbox),
        evidence_store=evidence_store,
        environment_label=environment_label,
        action_class=construction.action_class,
        action_class_reader=action_class_reader,
        attempt_arm_direction_reader=attempt_arm_direction_reader,
        held_position_proof_reader=held_position_proof_reader,
        held_position_currentness_reader=held_position_currentness_reader,
        close_authority=close_authority,
        entry_close_bound_reader=entry_close_bound_reader,
        activated_member_digests=(are_digest, afg_digest),
    )


def _current_seq_reader_for(inbox: SqliteEventInbox) -> Callable[[], int | None]:
    """The inbox row CURRENTLY being handled, or ``None`` when nothing is pending — the"""

    def _reader() -> int | None:
        pulled = inbox.next_unconsumed()
        return None if pulled is None else pulled[0]

    return _reader
