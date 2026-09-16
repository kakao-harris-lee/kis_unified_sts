"""``tos_runtime.compose._venue_wiring`` — boots the governed venue-constraint service and
step 3's real, per-attempt fold (TOS venue constraint service wave, plan §2 decisions 4/5/6/7,
``docs/plans/2026-09-15-tos-venue-constraint-service-plan.md``).

**Replaces ``compose/_venue_phase.py::VenuePhaseStage``.** The old stage folded venue facts the
caller had already hand-issued onto ``ConstructionConfig`` (``venue_snapshot``/``venue_policy``/
``venue_decision`` — a test fixture literally calling ``.issue()``, plan §0 "발행 아티팩트 3").
:class:`VenueServiceStage` instead reads a live :class:`~tos_runtime.venue.VenueConstraintService`
— the governed policy loader plus the runtime's own snapshot/decision issuance
(:mod:`tos_runtime.venue`) — so step 3 folds against a real per-tick snapshot and issues a real
per-attempt decision, never a test-authored stand-in.

**Two folds, deliberately.** :meth:`VenueServiceStage.__call__` builds a kernel
``tos.egressgw.VenueConstraintStage`` TWICE: once with ``decision=None`` purely to obtain
``resolved_shape`` (the kernel's own value-view projection of the injected order shape — this
module never re-derives that projection itself), and once more with the REAL
``OrderAdmissibilityDecision`` :meth:`~tos_runtime.venue.VenueConstraintService.decide` issues
from that same resolved shape, so the returned :class:`~tos.engine.records.StageVerdict` binds
the real decision's digest/identity. Both folds are pure and deterministic over the same inputs,
so they agree by construction (plan §2 decision 4; pinned by
``tos/runtime/tests/compose/test_venue_wiring.py``).

**Boot-time wiring (``build_venue_service``).** Loads the two governed policy YAMLs
(:mod:`tos_runtime.venue.config`), requires BOTH be positively activated
(:mod:`tos_runtime.venue.activation` — ``safety_activation.yaml``'s own ``members:`` list;
``PolicyNotActivated`` propagates as a boot refusal), cross-checks the venue policy's own
``scope`` against this compose root's configured coordinates and its ``admitting_phase_rules``
phase tokens against what ``calendar.yaml`` can actually produce for that instrument class
(:class:`VenuePolicyScopeMismatch` on any mismatch — a policy that scopes or admits outside what
this deployment can ever observe is a governance-authoring bug, refused at boot, never silently
narrowed), and cross-checks the Order Construction Policy's own ``wire_codec`` declaration against
the active transport (plan §2 decision 6). Builds the
:class:`~tos.venue.InstrumentRouteFields` this service's every decision binds from real sources
only — the venue policy's own scope coordinates, this compose root's account/instrument/
environment, and the egress route identity; ``contract_month``/``expiration``/``multiplier``/
``settlement_method`` have no runtime source yet (plan §5 "정직 상태") and stay at their
``InstrumentRouteFields`` ``None`` default, never invented.

**Order of boot refusals.** The two ``require_member_activated`` calls (and the scope/calendar/
wire-codec cross-checks that follow them) all run BEFORE :class:`~tos_runtime.venue
.VenueConstraintService` is ever constructed — so an activation or scope refusal here surfaces
before this function writes ANY evidence of its own (the only evidence that could already exist
at this point in ``compose_paper_runtime`` is whatever ``_boot_services`` itself wrote, earlier).
``VENUE_POLICY_BOUND`` (service construction) and ``ORDER_CONSTRUCTION_POLICY_BOUND``
(:func:`~tos_runtime.venue.record_order_construction_policy_bound`, called last) are this
function's own first two evidence rows, and both only ever get written past every refusal check
above.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path

from tos.canonical import CanonicalizationScheme
from tos.egressgw import OrderConstructionStage, VenueConstraintStage
from tos.engine import StageRequest, StageVerdict
from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
from tos.spg import BundleMemberKind, BundleMemberRef
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

from tos_runtime.brokercap import InstanceDocument
from tos_runtime.calendar.config import CalendarConfig
from tos_runtime.compose._egress_coordinates import EgressCoordinatesConfig
from tos_runtime.compose._envelope_wiring import (
    SideDerivationRefused,
    resolve_construction_direction,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS
from tos_runtime.venue import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    VENUE_POLICY_CONFIG_NAME,
    LoadedOrderConstructionPolicy,
    LoadedVenuePolicy,
    VenueConstraintService,
    load_activation_members,
    load_order_construction_policy,
    load_venue_constraint_policy,
    record_order_construction_policy_bound,
    require_member_activated,
)
from tos_runtime.venue.construction_rules import ConstructionRules

__all__ = [
    "VenuePolicyScopeMismatch",
    "VenueServiceStage",
    "build_venue_service",
]

#: Duplicated from ``tos_runtime.compose._safety_wiring``'s own private
#: ``_SAFETY_ACTIVATION_CONFIG_NAME`` (module-private there, not exported) — the SAME
#: "duplicate the literal, do not reach into another module's private surface" discipline
#: ``compose/cli.py`` already applies to its own duplicated constants.
_SAFETY_ACTIVATION_CONFIG_NAME = "safety_activation.yaml"

#: The KIS wire-codec kind the Order Construction Policy's ``_runtime.wire_codec.kind`` must
#: name for a ``kis-mock`` transport (``tos_runtime.transport.kis_mock.codec`` names the codec
#: itself this way nowhere as a string constant, so this module owns the one literal).
_KIS_ORDER_CASH_WIRE_CODEC_KIND = "kis-order-cash-v1"


class VenuePolicyScopeMismatch(RuntimeError):
    """The loaded Venue Constraint Policy's own ``scope`` does not match this compose root's
    configured coordinates, one of its ``admitting_phase_rules`` names a phase token
    ``calendar.yaml`` cannot produce for that instrument class, or the loaded Order Construction
    Policy's own ``wire_codec`` declaration does not match the active transport — a
    governance-authoring bug, refused at boot (module docstring), never silently narrowed or
    worked around."""


def _cross_check_scope(
    loaded_policy: LoadedVenuePolicy,
    *,
    construction: ConstructionConfig,
    environment_label: str,
) -> None:
    scope = loaded_policy.scope
    if scope.instrument != construction.instrument:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.instrument {scope.instrument!r} != configured "
            f"construction.instrument {construction.instrument!r}"
        )
    if scope.account != construction.account:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.account {scope.account!r} != configured "
            f"construction.account {construction.account!r}"
        )
    if scope.environment != environment_label:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.environment {scope.environment!r} != this compose root's "
            f"environment_label {environment_label!r}"
        )
    if scope.instrument_class != construction.instrument_class:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.instrument_class {scope.instrument_class!r} != configured "
            f"construction.instrument_class {construction.instrument_class!r}"
        )


def _calendar_phase_tokens(
    calendar_config: CalendarConfig, instrument_class: str
) -> frozenset[str]:
    """Every session-phase token ``calendar_config`` can produce for ``instrument_class`` —
    its own session windows' ``phase``, the calendar-wide ``closed_phase`` (always reachable,
    every instrument class can be observed closed), and its own futures-expiry
    ``expired_phase`` when one is declared for that class."""
    tokens = {calendar_config.closed_phase}
    tokens.update(
        window.phase for window in calendar_config.sessions.get(instrument_class, ())
    )
    rule = calendar_config.futures_expiry.get(instrument_class)
    if rule is not None:
        tokens.add(rule.expired_phase)
    return frozenset(tokens)


def _cross_check_admitting_phase_tokens(
    policy: VenueConstraintPolicy,
    *,
    calendar_config: CalendarConfig,
    instrument_class: str,
) -> None:
    allowed = _calendar_phase_tokens(calendar_config, instrument_class)
    for rule in policy.admitting_phase_rules:
        unknown = rule.admitting_phases - allowed
        if unknown:
            raise VenuePolicyScopeMismatch(
                f"venue policy admitting_phase_rules names phase token(s) "
                f"{sorted(unknown)!r} for action {rule.action!r} that calendar.yaml does not "
                f"declare for instrument class {instrument_class!r} (declared: "
                f"{sorted(allowed)!r}) — an admit over a phase the calendar can never produce "
                "is a vacuous admit, refused at boot"
            )


def _cross_check_wire_codec(
    loaded_ocp: LoadedOrderConstructionPolicy, *, transport_kind: TransportKind
) -> None:
    if transport_kind is TransportKind.SYNTHETIC:
        if loaded_ocp.wire_codec_kind is not None:
            raise VenuePolicyScopeMismatch(
                f"Order Construction Policy _runtime.wire_codec is "
                f"{loaded_ocp.wire_codec_kind!r} but the active transport is 'synthetic' — "
                "a synthetic (non-broker-reaching) transport requires wire_codec: null"
            )
        return
    if (
        loaded_ocp.wire_codec_kind != _KIS_ORDER_CASH_WIRE_CODEC_KIND
        or loaded_ocp.wire_fields != KIS_ORDER_CASH_WIRE_FIELDS
    ):
        raise VenuePolicyScopeMismatch(
            f"Order Construction Policy _runtime.wire_codec (kind="
            f"{loaded_ocp.wire_codec_kind!r}, wire_fields={sorted(loaded_ocp.wire_fields)!r}) "
            f"does not exactly declare kind={_KIS_ORDER_CASH_WIRE_CODEC_KIND!r} and "
            f"wire_fields={sorted(KIS_ORDER_CASH_WIRE_FIELDS)!r} — required for the active "
            "'kis-mock' transport"
        )


def _broker_capability_profile_facts(
    instance_document: InstanceDocument | None,
) -> tuple[str | None, str | None]:
    """``(broker_capability_profile_version, broker_capability_profile_digest)`` — real values
    only, never invented (plan §2 decision 3): ``None``/``None`` when no INSTANCE document is
    bound to the active scope at all (e.g. the SYNTHETIC scope), the version string off the
    document's own ``profile.profile_version.profile_version`` when a version block is present,
    and the digest off the document's own ``profile.canonical_digest`` — ``None`` while that
    profile is still DRAFT (:mod:`tos_runtime.brokercap.instance`'s own module docstring).
    """
    if instance_document is None:
        return None, None
    profile_version = instance_document.profile.profile_version
    version = None if profile_version is None else profile_version.profile_version
    digest = instance_document.profile.canonical_digest
    return version, digest


def _load_and_activate_policies(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    calendar_config: CalendarConfig,
    transport_kind: TransportKind,
) -> tuple[
    LoadedVenuePolicy, LoadedOrderConstructionPolicy, BundleMemberRef, BundleMemberRef
]:
    """Load both governed policy YAMLs, require both be activated, and run every boot-time
    cross-check (module docstring "Order of boot refusals") — split out of
    :func:`build_venue_service` purely for the function-length budget (no behavioural
    difference from having this inline there)."""
    loaded_policy = load_venue_constraint_policy(
        config_dir / VENUE_POLICY_CONFIG_NAME, scheme=scheme
    )
    loaded_ocp = load_order_construction_policy(
        config_dir / ORDER_CONSTRUCTION_POLICY_CONFIG_NAME, scheme=scheme
    )
    # Narrows the kernel model's Optional field types for mypy — both loaders always fill
    # these (require_filled_str/require_int at load, check_canonical_digest at issue) — never
    # a real absence past a successful load.
    p, o = loaded_policy.policy, loaded_ocp.policy
    assert p.policy_id is not None and p.policy_generation is not None
    assert p.canonical_digest is not None and o.canonical_digest is not None
    assert o.policy_id is not None and o.policy_generation is not None
    members = load_activation_members(config_dir / _SAFETY_ACTIVATION_CONFIG_NAME)
    # Activation refusal (PolicyNotActivated) surfaces here, before any evidence this
    # module itself writes (module docstring "Order of boot refusals").
    venue_member = require_member_activated(
        members,
        kind=BundleMemberKind.VENUE_CONSTRAINT_POLICY,
        member_id=p.policy_id,
        generation=p.policy_generation,
        digest=p.canonical_digest,
    )
    ocp_member = require_member_activated(
        members,
        kind=BundleMemberKind.ORDER_CONSTRUCTION_POLICY,
        member_id=o.policy_id,
        generation=o.policy_generation,
        digest=o.canonical_digest,
    )
    # require_member_activated only returns a ref whose digest matched the exact
    # (non-None) canonical_digest passed above — non-None here by construction.
    assert venue_member.digest is not None
    assert ocp_member.digest is not None
    _cross_check_scope(
        loaded_policy, construction=construction, environment_label=environment_label
    )
    _cross_check_admitting_phase_tokens(
        loaded_policy.policy,
        calendar_config=calendar_config,
        instrument_class=loaded_policy.scope.instrument_class,
    )
    _cross_check_wire_codec(loaded_ocp, transport_kind=transport_kind)
    return loaded_policy, loaded_ocp, venue_member, ocp_member


def build_venue_service(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    session_phase_reader: Callable[[], str | None],
    tick_generation_reader: Callable[[], int | None],
    evidence_store: SqliteEvidenceStore,
    instance_document: InstanceDocument | None,
    egress_coordinates: EgressCoordinatesConfig,
    transport_kind: TransportKind,
    calendar_config: CalendarConfig,
) -> tuple[VenueConstraintService, LoadedOrderConstructionPolicy]:
    """Load, activate, cross-check, and construct the governed venue-constraint service
    (module docstring).

    Raises:
        tos_runtime.venue.VenuePolicyConfigError: either policy YAML is missing/malformed.
        tos_runtime.venue.ActivationMembersConfigError: ``safety_activation.yaml`` carries no
            explicit ``members:`` list.
        tos_runtime.venue.PolicyNotActivated: either policy has no exactly-one, positively
            resolved+immutable activation member.
        VenuePolicyScopeMismatch: the venue policy's scope/admitting-phase tokens, or the
            Order Construction Policy's wire-codec declaration, disagree with this compose
            root's own configured facts.
    """
    loaded_policy, loaded_ocp, venue_member, ocp_member = _load_and_activate_policies(
        config_dir=config_dir,
        scheme=scheme,
        construction=construction,
        environment_label=environment_label,
        calendar_config=calendar_config,
        transport_kind=transport_kind,
    )
    # Re-narrowed at this function boundary (the assert inside _load_and_activate_policies
    # does not carry across a function return) — both members matched a non-None digest.
    assert venue_member.digest is not None and ocp_member.digest is not None
    profile_version, profile_digest = _broker_capability_profile_facts(
        instance_document
    )
    route_fields = InstrumentRouteFields(
        canonical_instrument_id=construction.instrument,
        venue_listing=loaded_policy.scope.venue,
        market_segment=loaded_policy.scope.market_segment,
        # contract_month / product_type / multiplier / expiration / settlement_method: no
        # runtime source exists yet (module docstring) — left at their InstrumentRouteFields
        # None default, never invented.
        currency=loaded_policy.scope.currency,
        account_mapping=construction.account,
        environment=environment_label,
        broker=loaded_policy.scope.broker,
        route=egress_coordinates.route_identity,
    )
    service = VenueConstraintService(
        loaded_policy=loaded_policy,
        scheme=scheme,
        session_phase_reader=session_phase_reader,
        tick_generation_reader=tick_generation_reader,
        evidence_store=evidence_store,
        environment_label=environment_label,
        route_fields=route_fields,
        broker_capability_profile_version=profile_version,
        broker_capability_profile_digest=profile_digest,
        activated_member_digest=venue_member.digest,
    )
    record_order_construction_policy_bound(
        evidence_store, loaded_ocp, ocp_member.digest
    )
    return service, loaded_ocp


def _derived_shape_quantity(
    candidate_command: CanonicalBrokerCommand | None,
) -> int | None:
    """The QUANTITY axis value ``construct_candidate_command`` already bound onto the command
    (``_derived_axis_bindings``, ``egressgw/construction.py:544-553``), parsed to the ``int``
    :class:`~tos.venue.OrderShapeFields.quantity` needs.

    (a′) wave (``construction_rules.py`` module docstring "the asymmetry this wave also
    closes"): the kernel refuses an envelope that re-declares a ``DERIVED_AXES`` member as
    ambiguous, but nothing reconciled the derived quantity against ``OrderShapeFields.quantity``
    — a caller-declared literal — before this. This function is the ONE place that reads the
    derived value back out; it never re-derives a quantity itself (``derive_order_size`` stays
    the sole source) and never falls back to the caller's literal.

    A denied attempt (``candidate_command is None``), an absent QUANTITY axis binding, or a
    bound value that does not parse as an exact whole number all fail closed to ``None`` — the
    same structural UNKNOWN ``_shape_for`` already returns for an unprojectable price
    (``egressgw/construction.py:1074-1098``), never a guess and never the injected literal.
    """
    if candidate_command is None:
        return None
    raw = candidate_command.axis_value(ConformanceAxis.QUANTITY)
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if value != value.to_integral_value():
        return None
    return int(value)


def _authorized_axis_value(
    authorized_axes: tuple[AxisBinding, ...], axis: ConformanceAxis
) -> str | None:
    """The single bound value for ``axis`` in ``authorized_axes`` — ``None`` if absent. The one
    place both :func:`_shape_order_type_and_tif` and :func:`_shape_side_and_position_effect`
    read a governed axis value, so "absent is a refusal, never a default" is not a rule
    duplicated across call sites."""
    for binding in authorized_axes:
        if binding.axis == axis:
            return binding.value
    return None


def _shape_side_and_position_effect(
    construction_rules: ConstructionRules,
    action_class: ActionClass | None,
) -> tuple[str | None, str | None]:
    """``(side, position_effect)`` for ``action_class``, sourced from the OCP's own
    ``ConstructionRules.action_class_shape`` mapping — never ``ConstructionConfig``'s
    caller-declared literal.

    Keyed by ``(ActionClass, direction)`` (contract amended 2026-09-16, commit ``7e79f00c``):
    ``ActionClass`` has a single ``CLOSE`` member, so a long-close and a short-close arm would
    otherwise collapse onto one key. ``direction`` is resolved through
    :func:`~tos_runtime.compose._envelope_wiring.resolve_construction_direction` — the ONE
    place direction is resolved (that function's own docstring), never a second, independent
    read of ``construction_rules.authorized_axes`` here: a direction-NAMED action class
    (``NEW_LONG``/``NEW_SHORT``) resolves from the class itself, never the policy's own
    ``DIRECTION`` axis alone — reading the axis unconditionally, as an earlier version of this
    function did, gave every action class the SAME answer regardless of which one actually
    fired, silently wrong for whichever side the axis did not name (the same
    per-composition-constant defect :func:`build_construction_envelope` already fixed for the
    envelope's own SIDE derivation).

    No direction resolvable (a direction-agnostic class with no ``DIRECTION`` axis binding), an
    ``(action_class, direction)`` pair absent from the mapping, or ``action_class is None``
    outright are all the SAME refusal — ``(None, None)`` — never a default
    (``ConstructionRules.action_class_shape`` docstring: "absent from this mapping is
    unauthorized for this generation, not defaulted"; the "no derivation ⇒ None" discipline
    this wave already applies to quantity, applied here to direction)."""
    if action_class is None:
        return None, None
    try:
        direction = resolve_construction_direction(
            construction_rules, action_class=action_class
        )
    except SideDerivationRefused:
        return None, None
    mapped = construction_rules.action_class_shape.get((action_class, direction))
    if mapped is None:
        return None, None
    return mapped.side, mapped.position_effect


def _shape_order_type_and_tif(
    construction_rules: ConstructionRules,
) -> tuple[str | None, str | None]:
    """``(order_type, tif)`` sourced from ``ConstructionRules.authorized_axes`` (a′) wave
    decision 3) — never a caller literal. An axis this generation does not authorize is
    ``None`` (fail-closed), never a default."""
    return (
        _authorized_axis_value(
            construction_rules.authorized_axes, ConformanceAxis.ORDER_TYPE
        ),
        _authorized_axis_value(construction_rules.authorized_axes, ConformanceAxis.TIF),
    )


def _observed_silently_rounded() -> bool:
    """``False``, always — an observation of the RUNTIME's own behaviour, not a relayed
    caller claim, and (round 3 correction, team-lead review, PR #718, 2026-09-16) not a
    re-derivation of the kernel's own grid verdict.

    ``OrderShapeFields.silently_rounded`` does not ask "is this shape off the tick/lot grid" —
    ``order_shape_admissible`` already judges exactly that, completely, itself, from the SAME
    injected :class:`~tos.venue.VenueShapeConstraints` a first and second cut of this function
    tried to re-check (price band + tick divisibility at
    ``tos/src/tos/venue/predicates.py:281-284``, quantity range + lot divisibility at
    ``:286-291``). The field is a question about PROVENANCE, not grid membership — the
    kernel's own comment at ``predicates.py:252``: "a silently-rounded / normalized shape is a
    NEW shape — never admissible here". It asks whether whoever handed this exact shape over
    quietly normalized it FIRST, after it was decided, before it reached the gate.

    Two rounds of review each found this function's grid re-derivation missing one more of
    ``order_shape_admissible``'s own precondition fields (round 1: ``shape.price``/
    ``shape.quantity``/``constraints`` absent; round 2: ``price_max``/``min_quantity``/
    ``max_quantity`` absent) — because re-deriving a verdict the kernel owns means predicting
    every precondition it will ever check, and nothing bounds that list. That approach is
    DELETED here, not patched a fourth time — the grid arithmetic that lived in this function
    (a second, unpinned copy of ``predicates.py:281-291``) is gone.

    **The structural answer: this runtime never rounds a shape after it has been decided.**
    :meth:`VenueServiceStage._sourced_shape` takes ``derive_order_size``'s own output quantity
    AS-IS (:func:`_derived_shape_quantity` parses the bound axis value back to ``int`` and
    REFUSES — returns ``None`` — a value that is not already an exact whole number, rather
    than rounding it). ``derive_order_size`` itself, under
    :attr:`~tos.egressgw.vocabulary.LotRoundingPolicy.EXACT_MULTIPLE_REQUIRED`, DENIES a raw
    size that is not already an exact lot multiple rather than rounding it — never reaches
    ``DERIVED``, never reaches this runtime at all. Under ``FLOOR_TO_LOT`` the derivation DOES
    floor the raw size to a lot multiple — but that floor IS the authored policy computing the
    decision, not a caller normalizing an already-decided shape: the floored quantity is the
    ONE value that ever exists in this runtime's path (the axis binding, the command, this
    shape), so there is no second, differently-valued "decided" shape for a later step to have
    quietly altered. Nothing between ``derive_order_size`` and the judged shape (this module)
    rounds, clamps, or widens a value. So the honest answer is ``False`` — always, structurally
    true rather than computed per attempt.

    This is true only for as long as it stays true. ``tos/runtime/tests/compose
    /test_venue_wiring.py::TestSilentlyRoundedIsNeverIntroduced`` pins the underlying
    INVARIANT this constant relies on — that the sourced shape's quantity always equals
    ``derive_order_size``'s own output exactly, unaltered, including under a genuine
    ``FLOOR_TO_LOT`` floor — never this constant itself (asserting ``is False`` on a hardcoded
    ``False`` would be exactly the tautology this project has been bitten by before). If this
    runtime ever grows a normalization step, that test goes red and THIS field must be
    revisited then, never left at ``False`` by inertia.
    """
    return False


class VenueServiceStage:
    """Step 3, folded against a live :class:`~tos_runtime.venue.VenueConstraintService`
    (module docstring — replaces ``compose/_venue_phase.py::VenuePhaseStage``).

    Exposes the same read surface :class:`~tos_runtime.compose.context.ComposeContextResolver`
    (item 11) and :class:`~tos_runtime.compose._types.ComposedRuntime` already read off the old
    stage — ``resolved_shape``/``shape_constraints``/``policy``/``last_snapshot``/
    ``last_decision`` — so those call sites change only what they read FROM, not how.

    **(a′) wave — order-shape field sourcing.** ``shape`` is keyword-only and defaults to an
    empty :class:`~tos.venue.OrderShapeFields` skeleton when omitted (``__init__`` below) — the
    real compose call site (``compose/_wiring.py``) passes none at all, since every field gets
    sourced downstream regardless; only a unit test that wants to pin a specific literal
    surviving (or not) supplies one explicitly. :meth:`__call__` never folds that shape
    unchanged: ``quantity`` is ALWAYS replaced with the derivation's own quantity
    (:func:`_derived_shape_quantity`) and ``silently_rounded`` is ALWAYS the structural
    ``False`` this runtime's own behaviour justifies (:func:`_observed_silently_rounded` — its
    own docstring explains why this is not a grid re-derivation) — neither ever falls back
    to the caller's literal, construction_rules or not. ``side``/``position_effect``/
    ``order_type``/``tif`` are sourced from ``construction_rules`` (decisions 2/3) when one is
    supplied. **Lane D wires this in production** (``compose/_wiring.py``'s
    ``_build_construction_stages`` passes ``loaded_ocp.construction_rules`` — the SAME loaded
    OCP generation step 2's envelope already came from), so all seven ``OrderShapeFields``
    fields are policy/derivation-sourced on the real boot path; ``construction_rules`` stays an
    optional constructor argument purely so a unit test may construct this stage directly
    without a full compose boot (e.g. :func:`_derived_shape_quantity`'s own unit tests) — when
    omitted there, those four fields fall back to the injected literal rather than a
    fail-closed refusal.
    """

    def __init__(
        self,
        service: VenueConstraintService,
        construction_stage: OrderConstructionStage,
        action_class: ActionClass,
        shape_price_field_key: str | None,
        *,
        shape: OrderShapeFields | None = None,
        construction_rules: ConstructionRules | None = None,
    ) -> None:
        self._service = service
        self._construction_stage = construction_stage
        self._action_class = action_class
        # A caller with no literal shape to inject (the real compose path, since (a′) lane D —
        # every field gets sourced below regardless) never needs to know OrderShapeFields
        # exists just to build an empty one; this stage owns that default itself. `None` here
        # is "no literal supplied", never "fold nothing" — a caller that genuinely wants the
        # kernel's "no shape at all" behaviour has no route to it through this constructor
        # (module docstring: no real or test call site has ever needed that degenerate case).
        self._shape = shape if shape is not None else OrderShapeFields()
        self._shape_price_field_key = shape_price_field_key
        self._construction_rules = construction_rules
        #: The last, decision-bound kernel stage this call built — never read for judgement,
        #: only for the read-surface properties below (mirrors the retired
        #: ``VenuePhaseStage``'s own ``_last_stage`` discipline).
        self._last_stage: VenueConstraintStage | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        snapshot = self._service.snapshot()
        # Fold #1 (decision=None): purely to obtain the kernel's own resolved_shape (its
        # value-view price projection) — this module never re-derives that projection itself
        # (module docstring "Two folds, deliberately").
        stage0 = VenueConstraintStage(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=self._action_class,
            snapshot=snapshot,
            policy=self._service.policy,
            shape=self._shape,
            constraints=self._service.shape_constraints,
            decision=None,
            shape_price_field_key=self._shape_price_field_key,
        )
        stage0(request)
        resolved = stage0.resolved_shape
        construction = self._construction_stage.construction
        candidate_command = None if construction is None else construction.command
        # (a′) wave: the quantity judged here is the DERIVED one — never the caller-declared
        # literal on ``self._shape`` — the same discipline the kernel already applies to the
        # other two DERIVED_AXES members (module docstring; ``_derived_shape_quantity``).
        # ``silently_rounded`` is likewise always the OBSERVED grid fact, never the injected
        # attestation. ``resolved is None`` (no shape was ever injected) leaves nothing to
        # source any field onto — stays ``None``, not a stand-in.
        shape_for_decision = self._sourced_shape(resolved, candidate_command)
        decision = self._service.decide(
            action_class=self._action_class,
            shape=shape_for_decision,
            candidate_command=candidate_command,
        )
        # Fold #2: the real per-attempt decision now bound onto the returned StageVerdict
        # (venue_admissibility_verdict records decision.canonical_digest/decision_id). Folded
        # against the SAME ``shape_for_decision`` ``decide()`` just judged — not ``self._shape``
        # — so the returned StageVerdict's outcome (computed locally by this fold, module
        # docstring "Two folds, deliberately") agrees with ``decision.result`` on the quantity
        # that was actually judged, not a stale literal.
        stage = VenueConstraintStage(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=self._action_class,
            snapshot=snapshot,
            policy=self._service.policy,
            shape=shape_for_decision,
            constraints=self._service.shape_constraints,
            decision=decision,
            shape_price_field_key=self._shape_price_field_key,
        )
        self._last_stage = stage
        return stage(request)

    def _sourced_shape(
        self,
        resolved: OrderShapeFields | None,
        candidate_command: CanonicalBrokerCommand | None,
    ) -> OrderShapeFields | None:
        """Build the exact shape both folds judge — ``resolved`` (fold #1's price-projected
        shape) with every (a′)-owned field replaced (class docstring "order-shape field
        sourcing"). ``None`` in, ``None`` out — no shape at all means no field to source
        anything onto."""
        if resolved is None:
            return None
        updates: dict[str, object] = {
            "quantity": _derived_shape_quantity(candidate_command),
            "silently_rounded": _observed_silently_rounded(),
        }
        if self._construction_rules is not None:
            side, position_effect = _shape_side_and_position_effect(
                self._construction_rules, self._action_class
            )
            order_type, tif = _shape_order_type_and_tif(self._construction_rules)
            updates["side"] = side
            updates["position_effect"] = position_effect
            updates["order_type"] = order_type
            updates["tif"] = tif
        return resolved.model_copy(update=updates)

    @property
    def resolved_shape(self) -> OrderShapeFields | None:
        return None if self._last_stage is None else self._last_stage.resolved_shape

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:
        return self._service.shape_constraints

    @property
    def policy(self) -> VenueConstraintPolicy:
        return self._service.policy

    @property
    def last_snapshot(self) -> VenueConstraintSnapshot | None:
        return self._service.last_snapshot

    @property
    def last_decision(self) -> OrderAdmissibilityDecision | None:
        return self._service.last_decision
