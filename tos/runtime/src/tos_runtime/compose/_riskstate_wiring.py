"""``tos_runtime.compose._riskstate_wiring`` — boots :class:`~tos_runtime.riskstate.service
.RiskStateService` (TOS risk state service wave, lane b; plan §2.4/§4/§4.1).

**Mirrors ``_venue_wiring.py``'s own idiom exactly** (module docstring there): load both
governed policy YAMLs, require BOTH be positively activated
(:mod:`tos_runtime.venue.activation` — new ``AGGREGATE_RISK_POLICY``/``ACTION_FLOW_POLICY``
member kinds), run every boot-time cross-check BEFORE the service is constructed (so a refusal
here surfaces before this function writes any evidence of its own), then construct the service
and let it record its own two ``*_POLICY_BOUND`` boot rows.

**Cross-checks (plan §2.4, all ``RiskPolicyScopeMismatch`` — a governance-authoring bug,
refused at boot, never silently narrowed):**

1. The ARE policy's own ``account_scope``/``instrument_scope`` equal ``construction.account``/
   ``.instrument`` (the SAME scope discipline :func:`~tos_runtime.compose._venue_wiring
   ._cross_check_scope` already applies to the venue policy).
2. Every ARE-governed dimension id is a member of the loaded Hard Safety Envelope's own
   ``governed_dimensions`` — an ARE policy governing a dimension the envelope never bounds
   would let step 6 admit against an ``injected_envelope_max`` this deployment never actually
   ceilinged.
3. ``required_scenario_kinds`` (``risk.yaml``) is a subset of the loaded ``AdverseScenarioSet``'s
   own ``covered_scenario_kinds`` — a required kind the scenario set does not cover would make
   ``tos.are.adverse_increment`` UNKNOWN forever for that kind (dishonest coverage, not merely
   absent).
4. The AFG policy's own ``action_class_map`` contains this composition's fixed
   ``construction.action_class`` — otherwise :meth:`~tos_runtime.riskstate.service
   .RiskStateService.action_flow_inputs_for` would return ``None`` (UNKNOWN) on every single
   attempt this deployment ever drives, a silent permanent gap rather than a boot refusal.
5. The AFG policy's own ``side_tokens`` (both) are members of ``venue_allowed_sides`` (the
   venue policy's own ``VenueShapeConstraints.allowed_sides``) — an unrecognized side token
   would make :class:`~tos_runtime.riskstate.position.EvidencePositionReader` classify every
   sealed send as UNKNOWN-in-both-directions, silently maximizing conservative usage forever.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos.are import AdverseScenarioKind, AdverseScenarioSet
from tos.canonical import CanonicalizationScheme
from tos.egressgw import SizingBound, VenueQuantityConstraint
from tos.egressgw.records import CandidateConstruction
from tos.ioc import EconomicEffectEnvelope
from tos.spg import BundleMemberKind, HardSafetyEnvelope
from tos.venue import ActionClass

from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.riskstate.flow_observation import InboxFlowReader
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
from tos_runtime.venue import load_activation_members, require_member_activated

__all__ = ["RiskPolicyScopeMismatch", "build_risk_state_service"]

#: Duplicated from ``tos_runtime.venue._venue_wiring``'s own module-private constant (a
#: private module symbol, not exported) — the SAME "duplicate the literal" discipline that
#: module already applies to it.
_SAFETY_ACTIVATION_CONFIG_NAME = "safety_activation.yaml"


class RiskPolicyScopeMismatch(RuntimeError):
    """Either governed policy's own declared coordinates disagree with this compose root's
    configured facts, or a governed dimension/scenario/action-class/side token the policy
    names has no counterpart the runtime can actually bound (module docstring's numbered
    cross-check list) — a governance-authoring bug, refused at boot, never silently narrowed
    or worked around."""


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


def _cross_check_hse_dimensions(
    are_policy: LoadedAggregateRiskPolicy, *, hse_envelope: HardSafetyEnvelope
) -> None:
    hse_ids = {gdl.dimension for gdl in hse_envelope.governed_dimensions}
    missing = sorted(set(are_policy.dimension_ids.values()) - hse_ids)
    if missing:
        raise RiskPolicyScopeMismatch(
            f"aggregate risk policy governs dimension id(s) {missing!r} that the Hard Safety "
            f"Envelope's own governed_dimensions {sorted(d for d in hse_ids if d)!r} does not "
            "declare — every ARE-governed dimension must have a real envelope ceiling"
        )


def _cross_check_scenario_coverage(
    are_policy: LoadedAggregateRiskPolicy,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
    *,
    scenario_set: AdverseScenarioSet,
) -> None:
    del are_policy  # required_scenario_kinds is risk.yaml's own floor, not the ARE policy's
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
    """Sibling of :func:`_cross_check_side_tokens`, same subset-and-refuse shape, for the
    Order Construction Policy's own side declarations ((a′) wave, lane B interaction check).

    ``action_class_shape`` makes the OCP a THIRD declarant of the side-token fact ``(b′)``
    already moved to policy declaration (module docstring item 5: the AFG policy's
    ``_runtime.side_tokens`` are already cross-checked against the venue policy's own
    ``allowed_sides``). Every side an OCP ``ActionClassShape`` yields must be a member of that
    same ``allowed_sides`` set, or boot is refused here — never a silent pass-through that lets
    the OCP name a side the venue never declared admissible.
    """
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
    """Sibling of :func:`_cross_check_side_tokens` / :func:`_cross_check_ocp_side_tokens`: the
    OCP's own comment (``order_construction_policy.yaml:120-122``) says its ``sizing``
    ``max_quantity``/``min_quantity``/``lot_size`` are DERIVED from the venue policy's own
    ``lot_size``/``min_quantity`` (and an aggregate-risk effective limit) — a fact nothing
    pins. This checks the SUBSET direction only, never equality (a narrower OCP is legitimate,
    a wider one is a document defect): OCP ``max_quantity`` must not exceed the venue's,
    OCP ``min_quantity`` must not be below the venue's, and OCP's ``lot_size`` must be a whole
    multiple of the venue's (never a finer grain than the venue itself grants). A field left
    ``None`` on either side is skipped — an absent bound is UNKNOWN, not "unlimited", so there
    is nothing to compare it against, not evidence the OCP may claim anything it likes.
    ``derive_order_size`` (``egressgw/construction.py:449-523``) already ANDs both bounds
    independently at every attempt, so a real mismatch here only ever narrows what an attempt
    can do — this check exists to catch the DOCUMENT drift at boot, not a correctness gap.
    """
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
    """Load both policies, require both activated, and return their activated member
    digests — split out of :func:`build_risk_state_service` purely for that function's own
    100-line size budget."""
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
    members = load_activation_members(config_dir / _SAFETY_ACTIVATION_CONFIG_NAME)
    are_member = require_member_activated(
        members,
        kind=BundleMemberKind.AGGREGATE_RISK_POLICY,
        member_id=p.policy_id,
        generation=p.policy_generation,
        digest=p.canonical_digest,
    )
    afg_member = require_member_activated(
        members,
        kind=BundleMemberKind.ACTION_FLOW_POLICY,
        member_id=a.policy_id,
        generation=a.policy_generation,
        digest=a.canonical_digest,
    )
    assert are_member.digest is not None and afg_member.digest is not None
    return are_policy, afg_policy, are_member.digest, afg_member.digest


def build_risk_state_service(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    evidence_store: SqliteEvidenceStore,
    inbox: SqliteEventInbox,
    rcl_log: SqliteCommitLog,
    hse_envelope: HardSafetyEnvelope,
    scenario_set: AdverseScenarioSet,
    required_scenario_kinds: frozenset[AdverseScenarioKind],
    rcl_tip_reader: Callable[[], int | None],
    monotonic_reader: Callable[[], int | None],
    max_attempts_reader: Callable[[], int | None],
    construction_stage_reader: Callable[[], CandidateConstruction | None],
    effect_envelope_reader: Callable[[], EconomicEffectEnvelope | None],
    venue_allowed_sides: frozenset[str],
) -> RiskStateService:
    """Load, activate, cross-check, and construct the production
    :class:`~tos_runtime.riskstate.service.RiskStateService` (module docstring).

    Raises:
        tos_runtime.riskstate.VenuePolicyConfigError: either policy YAML is missing/malformed.
        tos_runtime.venue.ActivationMembersConfigError: ``safety_activation.yaml`` carries no
            explicit ``members:`` list.
        tos_runtime.venue.PolicyNotActivated: either policy has no exactly-one, positively
            resolved+immutable activation member.
        RiskPolicyScopeMismatch: any of the module docstring's five cross-checks fails.
    """
    are_policy, afg_policy, are_digest, afg_digest = _load_and_activate(
        config_dir=config_dir, scheme=scheme
    )
    _cross_check_are_scope(are_policy, construction=construction)
    _cross_check_hse_dimensions(are_policy, hse_envelope=hse_envelope)
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
        hse_envelope=hse_envelope,
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
        activated_member_digests=(are_digest, afg_digest),
    )


def _current_seq_reader_for(inbox: SqliteEventInbox) -> Callable[[], int | None]:
    """The inbox row CURRENTLY being handled, or ``None`` when nothing is pending — the
    engine driver handles exactly one row at a time (module docstring's own "resolved
    structurally" cross-check note), so this is a genuine structural fact, never a guess.
    """

    def _reader() -> int | None:
        pulled = inbox.next_unconsumed()
        return None if pulled is None else pulled[0]

    return _reader
