"""Builders for the vertical-slice #1 end-to-end integration evidence.

Slice #1 (``docs/plans/2026-07-29-tos-engine-completion-path-assessment.md`` §3-1) is complete
when **one DSL strategy → an event-driven backtest → one paper order** runs through the four
landed lanes using their *public APIs only*:

* D-E1 ``tos.engine`` — the single event core + the 19-step fail-closed sequencer;
* D-E2 ``tos.marketfeed`` — the admitted Critical Input value surface + its
  :class:`~tos.engine.DecisionContextResolver`;
* D-E3 ``tos.backtest`` — the bar model, the causal converter, and the interleaving driver;
* D-E4 ``tos.egressgw`` / ``tos.brokeradapter`` — the send boundary (steps 15-19) and the
  synthetic paper transport.

**The RFC-008 §10-conformant path is the point.** Every value the policy gates on
(``close`` / ``lower_band`` / ``upper_band``) reaches it through
``env["capsule"][VALUE_NAMESPACE]`` — an admitted, digest-bound Critical Input — and
:class:`~tos.dsl.EvaluationConfig` ``bindings`` is **empty**. The DSL spike's
config-relabelling channel (RFC-008 §10:327-331 / RFC-004 §9:251-252) is not used and cannot
be: ``tests/slice`` contains no ``config``-sourced operand at all, which the negative-grep
canary in ``test_slice_conformant_path.py`` asserts mechanically.

**Determinism.** No ``time`` / ``datetime`` / ``random`` / ``secrets`` / ``uuid`` and no I/O
appears anywhere here, mirroring the four suites' own canaries: every identity on the path is
content-addressed or injected, so a replay is byte-identical.

⚠ **Authoring evidence only; closes no EV.** Every lane declares itself provisional
(design #31 §1.1, #32 §1.1, #33 §1.1/§1.2, #34 §1.1): the canonicalization scheme is
``ev-l1-provisional-0``, the authority runtimes are ``NON_AUTHORITATIVE_PROVISIONAL`` stand-ins,
the transport reaches no broker, and a single-run backtest is an ADR-DEV-010 §8:191-192
disqualifier. What this file demonstrates is **wiring**, and nothing else.

Firewall: ``pydantic`` / ``pytest`` + stdlib + ``tos.*`` only. Cross-suite imports are
forbidden (each package's fixtures stay in its own suite), so the builders below are written
against the four packages' public APIs and re-derive what they need locally.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from tos.backtest import (
    BacktestDriver,
    BacktestRun,
    Bar,
    BarTimeProjection,
    CausalBarConverter,
    GatewayResultReinjector,
    validate_bar_stream,
)
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import (
    AdmissionResult,
    ConsistencyCut,
    CriticalInputSnapshot,
    DecisionContextCapsule,
    FieldEvaluation,
    FieldState,
    Observation,
    PolicyRef,
)
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.capsule.observation import Admission, ObservationTime, RawRef
from tos.capsule.snapshot import SnapshotScope
from tos.cur import (
    CurrentnessRevision,
    EgressCurrentnessProof,
    EgressProofCoordinateSet,
    ProofResult,
)
from tos.dsl import (
    FLAT_QUANTITY_BASIS,
    VALUE_NAMESPACE,
    AuthoredStrategy,
    Compare,
    CompareOp,
    Decision,
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
)
from tos.egress import (
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressRequestRecord,
    QuorumCommitCertificate,
    RestrictiveLatchState,
)
from tos.egressgw import (
    AdmittedPriceObservation,
    BrokerEgressGateway,
    CandidateConstruction,
    ConformanceProofStage,
    EconomicEffectStage,
    EffectBasis,
    EffectDimensionSpec,
    LotRoundingPolicy,
    OrderConstructionStage,
    ProposedConstructionEnvelope,
    RecordingGatewayEvidenceSink,
    SendBoundaryContext,
    SizingBound,
    TransportNature,
    VenueConstraintStage,
    VenueQuantityConstraint,
    send_boundary_context,
)
from tos.engine import (
    CAPSULE_CONTEXT_SOURCE,
    AttemptRequest,
    CommitmentStep,
    EngineConfiguration,
    EngineCore,
    InstrumentKey,
    RecordingEvidenceSink,
    Stage,
    StrategyRegistry,
    provisional_stage_map,
)
from tos.ioc import AxisBinding, ConformanceAxis, QuantityUnitKind
from tos.marketfeed import (
    AdmittedValue,
    MarketFeedContextResolver,
    PreimageEntry,
    RawPayloadPreimage,
)
from tos.ordering import OrderingEvent
from tos.rcl import TransmissionCapability
from tos.time import HealthState, SessionContext
from tos.venue import (
    ActionClass,
    ActionPhaseAdmission,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-slice"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
ENVIRONMENT = "non-live-test"
CONTINUITY_ID = "slice-1-stream"
SIDE = "BUY"
SESSION_PHASE = "CONTINUOUS"

#: ⚠ Every number below is **provisional**: the register's Phase-0 bounds approval (P0-1) is
#: incomplete and there is no approved Broker Capability Profile INSTANCE (P0-2), so these are
#: injected slice values, never authorized ones (design #31 §8 / #33 §10 / #34 §9).
PROVISIONAL_BUDGET_STEPS = 64
PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE = 1

PERMIT_IDENTITY = "permit-slice"
PERMIT_NONCE = "permit-nonce-slice"
CAPABILITY_NONCE = "cap-nonce-slice"
PRINCIPAL = "egressgw-slice"
TRANSPORT_PRINCIPAL = "synthetic-paper-slice"
REQUEST_DIGEST = "req-digest-slice"
CAPSULE_EGRESS_REQUEST_DIGEST = "req-bytes-digest-slice"

RISK_BUDGET = Decimal("1000")
PER_UNIT_RISK = Decimal("50")
LOT_SIZE = Decimal("2")
MIN_QUANTITY = Decimal("2")
MAX_QUANTITY = Decimal("100")
PRICE = Decimal("4200")

#: The governed Critical Input field the sizing policy prices against (design #35 §4.2 (4)).
#: It is the **same** ``field_key`` the band comparison gates on, which is the whole point: the
#: number the strategy decided on is now the number the order is sized against.
PRICE_FIELD_KEY = "close"

# ---------------------------------------------------------------------------
# The band-crossing bar profile (§3-1 "일부 bar만 하단 밴드 관통")
# ---------------------------------------------------------------------------

#: The band, in **integer minor/tick units** — the exposed numeric form D-E2 admits
#: (design #32 §2.5: a fractional magnitude is fail-closed until the deterministic-float
#: projection rule is ratified, so an ordering comparison is only ever on exact integers).
LOWER_BAND = 4_500_000
UPPER_BAND = 4_520_000

#: ``(close, expectation)`` per bar. The expectation column is documentation only — every
#: assertion in the suite reads the **engine's own** ``EventResult``, never this table
#: (RFC-010 §6 원칙 1:183-185 — a test is evidence, not authority).
BAND_PROFILE: tuple[tuple[int, str], ...] = (
    (4_510_000, "inside the band — No-Action"),
    (4_499_000, "below the lower band — LONG/OPEN, realized end to end"),
    (4_498_500, "below the lower band again — denied at the capacity stage"),
    (4_511_000, "inside the band — No-Action"),
    (4_521_000, "above the upper band — FLAT proposed"),
)

#: The bar whose crossing is realized end to end (the only order the run produces).
CROSSING_BAR_INDEX = 1
#: The bar whose crossing is denied by the at-most-one exposure retention.
DENIED_BAR_INDEX = 2
#: The bars whose close sits inside the band (No-Action).
INSIDE_BAR_INDEXES = (0, 3)
#: The bar whose close crosses the upper band (the Explicit-Flat branch).
FLAT_BAR_INDEX = 4

_BAR_COORDINATE_STEP = 60
_AS_OF_BASE = 1_700_000_000_000
_AS_OF_STEP = 60_000
_SESSION_TOKEN = "slice-session"
_VOLUME = Decimal(1000)


# ===========================================================================
# D-E2 — the Critical Input value surface, per bar
# ===========================================================================


@dataclass(frozen=True)
class BarContext:
    """One bar's complete Critical Input context (design #32 §2.3/§4.1).

    Distinct bars carry distinct ``as_of`` times and distinct closes, and observations are a
    *covered* snapshot field, so distinct bars yield distinct snapshot digests → distinct Capsule
    digests → distinct outcome identities. That is the D-E1 Gap-1 residue D-E2 closes
    (design #32 §4).
    """

    bar: Bar
    close: int
    snapshot: CriticalInputSnapshot
    capsule: DecisionContextCapsule
    candidates: tuple[AdmittedValue, ...]


def _preimage(**tokens: Any) -> RawPayloadPreimage:
    """The raw payload preimage the observation's ``payload_digest`` addresses."""
    return RawPayloadPreimage(
        entries=tuple(PreimageEntry(key=key, value=value) for key, value in tokens.items())
    )


def _bar(index: int, close: int) -> Bar:
    """One OHLCV bar whose prints bracket the band and the close (design #33 §3.1)."""
    high = Decimal(max(close, UPPER_BAND) + 1)
    low = Decimal(min(close, LOWER_BAND) - 1)
    return Bar(
        bar_index=index,
        timestamp_coordinate=(index + 1) * _BAR_COORDINATE_STEP,
        open_price=Decimal(close),
        high_price=high,
        low_price=low,
        close_price=Decimal(close),
        volume=_VOLUME,
        session_token=_SESSION_TOKEN,
    )


def _bar_context(index: int, close: int) -> BarContext:
    """Assemble one bar's snapshot + Capsule + candidate values."""
    as_of = _AS_OF_BASE + (index + 1) * _AS_OF_STEP
    raw_event_id = f"slice-raw-{index}"
    payload = _preimage(close=close, lower_band=LOWER_BAND, upper_band=UPPER_BAND)
    observation = Observation(
        raw=RawRef(
            raw_event_id=raw_event_id,
            payload_digest=SCHEME.compute_digest(payload.as_mapping()),
        ),
        time=ObservationTime(source_event_time=as_of),
        admission=Admission(result=AdmissionResult.ADMITTED),
        field_state=FieldState.VALID,
    )
    snapshot = CriticalInputSnapshot.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-slice",
        critical_input_policy=PolicyRef(policy_id="pol-slice", canonical_digest="pd-slice"),
        scope=SnapshotScope(
            environment=ENVIRONMENT,
            accounts=(ACCOUNT,),
            instruments=(INSTRUMENT,),
            decision_class=DECISION_CLASS,
        ),
        intended_use=DECISION_CLASS,
        consistency_cut=ConsistencyCut(cut_id=f"cut-slice-{index}"),
        observations=(observation,),
        field_evaluations=(
            FieldEvaluation(field_ref="close", state=FieldState.VALID, blocking=True),
            FieldEvaluation(field_ref="lower_band", state=FieldState.VALID, blocking=True),
            FieldEvaluation(field_ref="upper_band", state=FieldState.VALID, blocking=True),
        ),
    )
    assert isinstance(snapshot, CriticalInputSnapshot)
    capsule = DecisionContextCapsule.issue(
        scheme=SCHEME,
        issuer_principal_id="iss-slice",
        critical_input_policy=PolicyRef(policy_id="pol-slice", canonical_digest="pd-slice"),
        critical_input_snapshot=SnapshotRef(
            snapshot_id=snapshot.snapshot_id, canonical_digest=snapshot.canonical_digest
        ),
        scope=CapsuleScope(
            environment=ENVIRONMENT,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class=DECISION_CLASS,
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )
    assert isinstance(capsule, DecisionContextCapsule)
    candidates = tuple(
        AdmittedValue(field_key=field_key, observation_ref=raw_event_id, preimage=payload)
        for field_key in ("close", "lower_band", "upper_band")
    )
    return BarContext(
        bar=_bar(index, close),
        close=close,
        snapshot=snapshot,
        capsule=capsule,
        candidates=candidates,
    )


class BandBarBook:
    """The slice's injected market history + its per-bar Critical Input contexts.

    It plays the three producer roles D-E2 injects — the per-bar Capsule source (D-E3's
    ``capsule_source``), the content-addressed
    :class:`~tos.marketfeed.SnapshotStore`, and the
    :class:`~tos.marketfeed.ValueCandidateSource` — over one deterministic table. It opens
    nothing: the values are already-admitted observations, exactly the shape RFC-004 §9:242-244
    requires (never an unattributed fetch).
    """

    def __init__(self, profile: Sequence[tuple[int, str]] = BAND_PROFILE) -> None:
        """Build every bar's context from the injected ``(close, note)`` profile."""
        self._contexts = tuple(
            _bar_context(index, close) for index, (close, _note) in enumerate(profile)
        )
        self._by_snapshot_id = {
            context.snapshot.snapshot_id: context for context in self._contexts
        }
        self._by_capsule_id = {
            context.capsule.capsule_id: context for context in self._contexts
        }

    @property
    def contexts(self) -> tuple[BarContext, ...]:
        """Every bar's context, in stream order."""
        return self._contexts

    @property
    def bars(self) -> tuple[Bar, ...]:
        """The validated bar stream (∅ both ways is D-E3's; this profile is non-empty)."""
        return validate_bar_stream([context.bar for context in self._contexts])

    def context_for(self, index: int) -> BarContext:
        """The context for bar ``index``."""
        return self._contexts[index]

    # -- the three injected producer roles -----------------------------------

    def capsule_source(self, bar: Bar) -> DecisionContextCapsule:
        """D-E3's injected per-bar Capsule source (``CapsuleSource``, converter.py:46).

        Unlike the D-E3 suite's own source — which issues the *same* Capsule for every bar
        because slice-1 had no value surface — this issues a **distinct** Capsule per bar,
        because the bar's admitted observations are covered snapshot content (design #32 §4).
        """
        return self._contexts[bar.bar_index].capsule

    def snapshot_store(
        self, *, snapshot_id: str | None, canonical_digest: str | None
    ) -> CriticalInputSnapshot | None:
        """D-E2's injected content-addressed snapshot lookup (resolver.py:56).

        Returns ``None`` — a first-class "this store has no such snapshot" — rather than
        substituting a different body, and re-checks the digest so a store that held a stale
        body under a live id cannot pass one off (ADR-002-018 §15:386).
        """
        if snapshot_id is None:
            return None
        context = self._by_snapshot_id.get(snapshot_id)
        if context is None:
            return None
        if context.snapshot.canonical_digest != canonical_digest:
            return None
        return context.snapshot

    def candidate_source(
        self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey
    ) -> tuple[AdmittedValue, ...]:
        """D-E2's injected candidate supplier (resolver.py:75) — claims, never admissions."""
        if instrument_key.instrument != INSTRUMENT or instrument_key.account != ACCOUNT:
            return ()
        context = self._by_snapshot_id.get(snapshot.snapshot_id)
        return () if context is None else context.candidates


def build_resolver(book: BandBarBook) -> MarketFeedContextResolver:
    """The **real** D-E2 resolver in D-E1's ``DecisionContextResolver`` slot (design #32 §3.3).

    ``time_projection`` is deliberately left ``None``: D-E3's :class:`~tos.backtest.BarTimeProjection`
    owns the bar → time-coordinate projection and the converter applies it after this resolver
    returns (converter.py:119-127), so claiming the coordinates here would be a double authorship.
    """
    return MarketFeedContextResolver(
        snapshot_store=book.snapshot_store,
        candidate_source=book.candidate_source,
        scheme=SCHEME,
    )


# ===========================================================================
# D-E3 — the bar → tick converter and the time projection
# ===========================================================================


def instrument_key() -> InstrumentKey:
    """The single dispatch scope this slice replays."""
    return InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def time_projection(**overrides: Any) -> BarTimeProjection:
    """Injected bar → time-coordinate bounds that positively admit (design #33 §3.3).

    ⚠ Every bound is provisional: the trustworthy-time bounds are register §8-1 new-key
    candidates and P0-1 is incomplete.
    """
    base: dict[str, Any] = {
        "source_age": 10,
        "delay_bounds": (5,),
        "max_age_bound": 1000,
        "future_tolerance": 50,
        "snapshot_age_bound": 20,
        "maximum_consumer_age_ms": 1000,
        "interval_width": 2,
        "boundary_lag": 10,
        "session_template": SessionContext(
            tz_id="tz",
            tz_db_version="tzdb-0",
            trading_calendar_version="cal-0",
            phase=SESSION_PHASE,
            is_open=True,
            tz_version_conflict=False,
            boundary_value=0,
        ),
        "health_state": HealthState.TRUSTED,
    }
    base.update(overrides)
    return BarTimeProjection(**base)


def build_converter(book: BandBarBook, *, resolver: Any = None) -> CausalBarConverter:
    """Wire D-E3's causal converter with the **D-E2 resolver injected** (design #33 §7.4 (a)).

    This is the forward seam D-E3 declared: "착지 시 typed resolver 교체" — the call site is
    unchanged and only the injected resolver differs from
    :class:`~tos.backtest.ProvisionalContextResolver`. The ``resolver`` override exists so the
    suite can run the *negative control* — the same everything with the value surface removed.
    """
    return CausalBarConverter(
        instrument_key=instrument_key(),
        resolver=build_resolver(book) if resolver is None else resolver,
        capsule_source=book.capsule_source,
        time_projection=time_projection(),
    )


# ===========================================================================
# The DSL band-reversion strategy (capsule-sourced operands only)
# ===========================================================================


def _value_ref(field_key: str) -> Operand:
    """A capsule-sourced operand reading one admitted Critical Input value.

    The path is ``("capsule", VALUE_NAMESPACE, field_key)`` — the ``"capsule"`` source, never a
    third invented one and never ``"config"`` (design #32 §3.2; RFC-008 §10:327-331).
    """
    return Operand(ref=("capsule", VALUE_NAMESPACE, field_key))


def band_reversion_policy() -> DecisionPolicy:
    """``close < lower_band → LONG/OPEN``; ``close > upper_band → FLAT``; else hold.

    Both guards compare **two capsule-sourced value operands**, so the D1↔D4 typed-admission
    predicate (``compare_has_capsule_operand``) passes on substance rather than on a decorative
    capsule read placed beside a config-relabelled market value.
    """
    entry = Decision(
        kind=DecisionKind.ACTION,
        rationale="close pierced the lower band — mean-reversion entry",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="band-reversion",
            rationale="close pierced the lower band — mean-reversion entry",
        ),
    )
    exit_flat = Decision(
        kind=DecisionKind.FLAT,
        rationale="close pierced the upper band — explicit flat",
        target=TargetSpec(
            kind=TargetKind.FLAT,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="SHORT",
            position_effect="CLOSE",
            rationale="close pierced the upper band — explicit flat",
        ),
    )
    hold = Decision(
        kind=DecisionKind.NO_ACTION,
        rationale="close is inside the band — hold, no proposal",
    )
    return DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=_value_ref("close"),
                        op=CompareOp.LT,
                        right=_value_ref("lower_band"),
                    ),
                ),
                decision=entry,
            ),
            Rule(
                all_of=(
                    Compare(
                        left=_value_ref("close"),
                        op=CompareOp.GT,
                        right=_value_ref("upper_band"),
                    ),
                ),
                decision=exit_flat,
            ),
        ),
        default=hold,
    )


def band_reversion_strategy() -> AuthoredStrategy:
    """The issued, content-addressed Authored Strategy carrying the band policy."""
    issued = AuthoredStrategy.issue(
        scheme=SCHEME,
        dsl_version="dsl-slice",
        config_binding_version="cfg-bind-slice",
        policy=band_reversion_policy(),
    )
    assert isinstance(issued, AuthoredStrategy)
    return issued


def authored_config() -> EvaluationConfig:
    """The authored constants — **deliberately empty** (design #31 §3.2 (2)).

    An empty ``bindings`` mapping is the mechanical statement that no market-derived value is
    relabelled as configuration in this slice: there is no config key for one to hide in.
    """
    return EvaluationConfig(config_version="cfg-slice", bindings={})


def engine_configuration(**overrides: Any) -> EngineConfiguration:
    """The injected engine configuration (every value provisional — design #31 §8)."""
    base: dict[str, Any] = {
        "dsl_evaluation_budget_steps": PROVISIONAL_BUDGET_STEPS,
        "max_unresolved_send_per_scope": PROVISIONAL_MAX_UNRESOLVED_SEND_PER_SCOPE,
        "canonicalization_version": EV_L1_PROVISIONAL_VERSION,
        "enforcement_mechanism_version": "enf-slice",
    }
    base.update(overrides)
    return EngineConfiguration(**base)


def registry_with_band_strategy() -> tuple[StrategyRegistry, AuthoredStrategy]:
    """A registry holding exactly the band strategy, keyed by its own declared scope."""
    registry = StrategyRegistry()
    strategy = band_reversion_strategy()
    registry.register(strategy, authored_config())
    return registry, strategy


# ===========================================================================
# D-E4 — Order Construction stages + the send-boundary context
# ===========================================================================


def sizing_bound(**overrides: Any) -> SizingBound:
    """The governance-supplied sizing bound the proposed envelope encloses (⚠ provisional)."""
    base: dict[str, Any] = {
        "risk_budget": RISK_BUDGET,
        "per_unit_risk": PER_UNIT_RISK,
        "lot_size": LOT_SIZE,
        "lot_rounding": LotRoundingPolicy.FLOOR_TO_LOT,
        "min_quantity": MIN_QUANTITY,
        "max_quantity": MAX_QUANTITY,
        "quantity_unit": QuantityUnitKind.CONTRACTS,
        # design #35 §5.2 (4): the flat basis is admitted, so the exit half of the band-reversion
        # strategy is *constructable*. It still stops — at the capacity seal (step 8), not at the
        # sizing rule (step 2) — and those are not the same fact (§5.3).
        "admitted_quantity_bases": frozenset({"RISK", FLAT_QUANTITY_BASIS}),
    }
    base.update(overrides)
    return SizingBound(**base)


def proposed_envelope(**overrides: Any) -> ProposedConstructionEnvelope:
    """The proposed Authorized Construction Envelope (ADR-002-002 §11.1:583)."""
    base: dict[str, Any] = {
        "envelope_generation": 1,
        "policy_binding_id": "ocp-slice",
        "authorized_axis_bindings": (
            AxisBinding(axis=ConformanceAxis.ACCOUNT, value=ACCOUNT),
            AxisBinding(axis=ConformanceAxis.INSTRUMENT, value=INSTRUMENT),
            AxisBinding(axis=ConformanceAxis.DIRECTION, value="LONG"),
            AxisBinding(axis=ConformanceAxis.SIDE, value=SIDE),
            AxisBinding(axis=ConformanceAxis.ORDER_TYPE, value="LIMIT"),
            AxisBinding(axis=ConformanceAxis.TIF, value="DAY"),
            AxisBinding(axis=ConformanceAxis.ENVIRONMENT, value=ENVIRONMENT),
        ),
        "sizing_bound": sizing_bound(),
        "effect_dimensions": (
            EffectDimensionSpec(
                dimension_id="notional", basis=EffectBasis.NOTIONAL, unit="KRW", scale="1"
            ),
            EffectDimensionSpec(
                dimension_id="units", basis=EffectBasis.QUANTITY, unit="contract", scale="1"
            ),
        ),
    }
    base.update(overrides)
    return ProposedConstructionEnvelope(**base)


def admitted_price(book: BandBarBook, **overrides: Any) -> AdmittedPriceObservation:
    """The admitted Critical Input price observation the size derivation consumes.

    ⚠ **Seam gap, recorded rather than papered over.** ``snapshot_digest`` is bound to the
    *real* Critical Input Snapshot of the crossing bar, so the price's lineage pointer is
    genuine — but the price ``value`` itself is still an **injected** provisional scalar. There
    is no shipped seam from a :class:`~tos.dsl.ContextValueView` value to
    :class:`~tos.egressgw.AdmittedPriceObservation`, so D-E4's Order Construction does not read
    the D-E2 value surface. See ``test_slice_gaps.py::test_the_construction_price_is_injected_not_value_sourced``.
    """
    crossing = book.context_for(CROSSING_BAR_INDEX)
    base: dict[str, Any] = {
        "source": CAPSULE_CONTEXT_SOURCE,
        "value": PRICE,
        "snapshot_digest": crossing.snapshot.canonical_digest,
    }
    base.update(overrides)
    return AdmittedPriceObservation(**base)


def venue_quantity_constraint(**overrides: Any) -> VenueQuantityConstraint:
    """The injected venue / brokercap quantity constraint."""
    base: dict[str, Any] = {
        "lot_size": LOT_SIZE,
        "min_quantity": MIN_QUANTITY,
        "max_quantity": MAX_QUANTITY,
        "quantity_unit": QuantityUnitKind.CONTRACTS,
    }
    base.update(overrides)
    return VenueQuantityConstraint(**base)


def venue_policy() -> VenueConstraintPolicy:
    """A venue policy admitting the slice's action class in the slice's session phase."""
    issued = VenueConstraintPolicy.issue(
        scheme=SCHEME,
        policy_id="vpol-slice",
        policy_generation=1,
        scope="scope-slice",
        admitting_phase_rules=(
            ActionPhaseAdmission(
                action=ActionClass.NEW_LONG, admitting_phases=frozenset({SESSION_PHASE})
            ),
        ),
    )
    assert isinstance(issued, VenueConstraintPolicy)
    return issued


def venue_snapshot() -> VenueConstraintSnapshot:
    """A venue constraint snapshot bound to the slice's venue policy."""
    issued = VenueConstraintSnapshot.issue(
        scheme=SCHEME,
        snapshot_id="vsnap-slice",
        constraint_generation=1,
        policy_id="vpol-slice",
        policy_generation=1,
        observed_session_phase=SESSION_PHASE,
    )
    assert isinstance(issued, VenueConstraintSnapshot)
    return issued


def venue_decision() -> OrderAdmissibilityDecision:
    """An issued ADMISSIBLE Order Admissibility Decision."""
    issued = OrderAdmissibilityDecision.issue(
        scheme=SCHEME,
        decision_id="vdec-slice",
        decision_generation=1,
        result=OrderAdmissibilityResult.ADMISSIBLE,
    )
    assert isinstance(issued, OrderAdmissibilityDecision)
    return issued


def venue_shape() -> OrderShapeFields:
    """An order shape that is positively **not** silently rounded."""
    return OrderShapeFields(
        price=4200,
        quantity=20,
        order_type="LIMIT",
        tif="DAY",
        side=SIDE,
        position_effect="OPEN",
        silently_rounded=False,
    )


def venue_shape_constraints() -> VenueShapeConstraints:
    """Injected venue shape constraints admitting the slice's shape.

    The price band and tick moved when the shape price became value-sourced (design #36 §3.4):
    the shape now carries a band close, so the old band would have refused it. The design fixes
    only the *condition* a stand-in must satisfy — ``price_min ≤ V ≤ price_max`` and
    ``(V − price_min) mod tick_size == 0`` — never the approved numbers, which are not this
    slice's to choose. The quantity band is untouched: quantity is not value-sourced.

    ``V`` is every close that reaches step 3, not only the realized crossing: 4,499,000
    (realized), 4,498,500 (denied at the capacity stage) and 4,521,000 (the flat). Their pairwise
    differences bound the tick at 500, which is why the tick is 500 and not the coarser 1000 —
    a 1000 tick would refuse 4,498,500 at step 3 and move that bar's recorded halt off the
    capacity seal, i.e. re-source the price and silently rewrite a different lane's evidence.
    The injected 4,200 stand-in is off this grid on purpose (design #36 §8): a value-free tick
    reaching step 3 fails admissibility instead of passing quietly.
    """
    return VenueShapeConstraints(
        # ⚠ provisional (P0-2·register §8-2 candidate·#36 §10-2)
        price_min=1000,
        price_max=9_000_000,
        tick_size=500,
        lot_size=2,
        min_quantity=2,
        max_quantity=100,
        allowed_order_types=frozenset({"LIMIT"}),
        allowed_tifs=frozenset({"DAY"}),
        allowed_sides=frozenset({SIDE}),
        allowed_position_effects=frozenset({"OPEN"}),
    )


def transmission_capability() -> TransmissionCapability:
    """⚠ A provisional single-use Transmission Capability (issuance is the RCL's, deferred)."""
    issued = TransmissionCapability.issue(
        scheme=SCHEME,
        capability_id="txcap-slice",
        nonce=CAPABILITY_NONCE,
        single_use=True,
        reservation_identity="resv-slice",
        attempt_identity="attempt-slice",
        account_scope=ACCOUNT,
        instrument_scope=INSTRUMENT,
        side_action_scope=SIDE,
        ledger_epoch=1,
    )
    assert isinstance(issued, TransmissionCapability)
    return issued


def currentness_proof() -> EgressCurrentnessProof:
    """A structurally complete, admissible, CURRENT Egress Currentness Proof.

    ⚠ Structure and coordinates only: the owner submissions inside the Safety Currentness
    Vector are provisional / D-E2-dependent (design #34 §4.3).
    """
    revision = CurrentnessRevision(revision_id="rev-slice", commit_index=1)
    issued = EgressCurrentnessProof.issue(
        scheme=SCHEME,
        proof_id="ecp-slice",
        nonce="ecp-nonce-slice",
        vector_id="scv-slice",
        vector_digest="scv-digest-slice",
        committed_revision=revision,
        bound_generations=(1,),
        restrictive_floors=(1,),
        capability_claim_command="ClaimCapabilityAndMarkSendStarted",
        claim_committed_result="COMMITTED",
        send_started_revision=revision,
        result=ProofResult.CURRENT,
        single_use_consumed=False,
        is_expired=False,
        egress_coordinates=EgressProofCoordinateSet(
            principal=PRINCIPAL, local_latch_clear=True
        ),
    )
    assert isinstance(issued, EgressCurrentnessProof)
    return issued


def authorized_coordinates() -> EgressCoordinateSet:
    """The authorized egress coordinate set verify item 17 compares against."""
    return EgressCoordinateSet(
        endpoint="synthetic://paper/order",
        account=ACCOUNT,
        environment=ENVIRONMENT,
        action="NEW_ORDER",
        method="SUBMIT",
        route_identity="synthetic-route",
        credential_generation=0,
        broker_session_generation=0,
        egress_generation=1,
        active_principal=PRINCIPAL,
    )


def egress_request(command_digest: str | None) -> EgressRequestRecord:
    """The exact outbound egress request record, coordinate-equal to the authorized set."""
    coordinates = authorized_coordinates()
    issued = EgressRequestRecord.issue(
        scheme=SCHEME,
        request_id="ereq-slice",
        request_bytes_digest=CAPSULE_EGRESS_REQUEST_DIGEST,
        canonical_command_digest=command_digest,
        endpoint=coordinates.endpoint,
        account=coordinates.account,
        environment=coordinates.environment,
        action=coordinates.action,
        method=coordinates.method,
        side=SIDE,
        route_identity=coordinates.route_identity,
        credential_generation=coordinates.credential_generation,
        broker_session_generation=coordinates.broker_session_generation,
        egress_generation=coordinates.egress_generation,
        active_principal=coordinates.active_principal,
    )
    assert isinstance(issued, EgressRequestRecord)
    return issued


def quorum_certificate(command_digest: str | None) -> QuorumCommitCertificate:
    """⚠ A provisional QCC: only its command-digest axis is consumed (quorum runtime deferred)."""
    issued = QuorumCommitCertificate.issue(
        scheme=SCHEME,
        qcc_id="qcc-slice",
        cluster_identity="cluster-slice",
        capacity_domain="domain-slice",
        membership_generation=1,
        restore_generation=1,
        writer_epoch=1,
        committed_revision=1,
        canonical_command_digest=command_digest,
        resulting_state_digest="state-digest-slice",
        egress_generation=1,
        active_egress_principal=PRINCIPAL,
    )
    assert isinstance(issued, QuorumCommitCertificate)
    return issued


def synthetic_nature() -> TransportNature:
    """The synthetic transport's declared nature — every flag an explicit ``False``."""
    return TransportNature(
        principal=TRANSPORT_PRINCIPAL,
        reaches_broker=False,
        credential_bearing=False,
        route_bearing=False,
        risk_relevant_live=False,
    )


def disjoint_inventory() -> tuple[CredentialRouteInventoryEntry, ...]:
    """A credential-route inventory corroborating the synthetic transport **structurally**."""
    return (
        CredentialRouteInventoryEntry(
            principal=TRANSPORT_PRINCIPAL,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
        CredentialRouteInventoryEntry(
            principal=PRINCIPAL,
            usable_credential=False,
            broker_route=False,
            inside_boundary=True,
        ),
    )


def bind_send_boundary_context(
    *,
    attempt: AttemptRequest,
    construction: CandidateConstruction,
    proof: Any,
    reference: OrderingEvent,
    order_shape: OrderShapeFields | None,
    venue_shape_constraints: VenueShapeConstraints | None,
) -> SendBoundaryContext:
    """Partially apply the **shipped** ``send_boundary_context`` factory (design #35 §3.1).

    Everything below is an *injected* fact — the provisional stand-ins, the venue facts, the
    capability nonces, the environment tokens. Everything derived — the reservation identity
    triple, the construction / proof pair, the item-17 artifacts bound to this command's digest,
    the outbound economics — is derived **inside the factory**, from the attempt the sequencer
    just built and the artifacts the step-2 / step-11 stages just produced. That is what keeps
    verify item 2 (reservation identity match) and item 13 (order construction) load-bearing
    instead of self-confirming: no look-alike is rebuilt from the same inputs here.

    ``order_shape`` / ``venue_shape_constraints`` are passed in for the same reason (design #36
    §3.3): the pair ``order_shape_admissible`` compares is step 3's, read off the stage that
    folded it, so item 11's re-fold cannot be handed a second shape that quietly disagrees.
    """
    return send_boundary_context(
        attempt=attempt,
        construction=construction,
        conformance_proof=proof,
        reference=reference,
        egress_request_for_command=egress_request,
        quorum_certificate_for_command=quorum_certificate,
        instrument_key=instrument_key(),
        transport_nature=synthetic_nature(),
        non_live_test_environment_token=ENVIRONMENT,
        scope_environment=ENVIRONMENT,
        evidence_environment=ENVIRONMENT,
        environment_inherited=False,
        credential_route_inventory=disjoint_inventory(),
        transmission_capability=transmission_capability(),
        capability_nonce=CAPABILITY_NONCE,
        action_flow_permit_nonce=PERMIT_NONCE,
        prior_claims=(),
        principal=PRINCIPAL,
        request_digest=REQUEST_DIGEST,
        commitment_epoch_current=True,
        account_instrument_action_allowed=True,
        max_quantity_within_allowance=True,
        venue_session_account_facts_current=True,
        broker_constraint_generation_current=True,
        venue_snapshot=venue_snapshot(),
        venue_policy=venue_policy(),
        venue_decision=venue_decision(),
        observed_session_phase=SESSION_PHASE,
        action_class=ActionClass.NEW_LONG,
        order_shape=order_shape,
        venue_shape_constraints=venue_shape_constraints,
        approval_consumed_for_this_intent=True,
        action_flow_permit_identity=PERMIT_IDENTITY,
        action_flow_commitment_current=True,
        egress_currentness_proof=currentness_proof(),
        egress_currentness_result=ProofResult.CURRENT,
        restrictive_latch_state=RestrictiveLatchState.CLEAR,
        worst_credible_capacity=1,
        authorized_coordinates=authorized_coordinates(),
        capsule_egress_request_digest=CAPSULE_EGRESS_REQUEST_DIGEST,
        outbound_side=SIDE,
    )


def construction_stages(
    book: BandBarBook,
) -> tuple[
    dict[CommitmentStep, Stage],
    OrderConstructionStage,
    VenueConstraintStage,
    ConformanceProofStage,
]:
    """D-E4's four Order Construction stages for steps 2 / 3 / 5 / 11 (design #34 §3.2)."""
    step2 = OrderConstructionStage(
        envelope=proposed_envelope(),
        price=admitted_price(book),
        venue_constraint=venue_quantity_constraint(),
        scheme=SCHEME,
        intent_id="intent-slice",
        intent_version="intent-v1",
        envelope_id="env-slice",
        policy_id="ocp-slice",
        policy_version="ocp-v1",
        policy_generation=1,
        command_id="cmd-slice",
        generation=1,
        price_field_key=PRICE_FIELD_KEY,
    )
    step3 = VenueConstraintStage(
        observed_session_phase=SESSION_PHASE,
        action_class=ActionClass.NEW_LONG,
        snapshot=venue_snapshot(),
        policy=venue_policy(),
        shape=venue_shape(),
        constraints=venue_shape_constraints(),
        decision=venue_decision(),
        shape_price_field_key=PRICE_FIELD_KEY,
    )
    step5 = EconomicEffectStage(construction_stage=step2)
    step11 = ConformanceProofStage(
        construction_stage=step2,
        scheme=SCHEME,
        proof_id="ocp-proof-slice",
        proof_generation=1,
        required_authority_scope=("scope-slice",),
    )
    stages: dict[CommitmentStep, Stage] = provisional_stage_map(
        conformance_proof_digest="unused-provisional-digest",
        action_flow_permit_identity=PERMIT_IDENTITY,
    )
    stages.update(
        {
            CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION: step2,
            CommitmentStep.VENUE_ADMISSIBILITY_DECISION: step3,
            CommitmentStep.ECONOMIC_EFFECT_ENVELOPE: step5,
            CommitmentStep.ORDER_CONFORMANCE_PROOF: step11,
        }
    )
    return stages, step2, step3, step11


# ===========================================================================
# The lazy send-boundary context resolver (design #35 §3.1 (3))
# ===========================================================================


class RecordingContextResolver:
    """The gateway's lazy ``contexts`` resolver — a partial application, plus a log.

    This is **not** the harness-local bridge slice #1 had to write. The two pieces of wiring no
    shipped package owned are now shipped: :func:`~tos.egressgw.send_boundary_context` assembles
    the context, and :class:`~tos.backtest.GatewayResultReinjector` carries the results back to
    the driver. What is left here is the design's own resolver shape (design #35 §3.1 (3)) —
    "injected bundles fixed before the run, flow artifacts derived per attempt" — with the
    produced pairs recorded so the suite can assert against them.

    It assembles nothing itself and judges nothing: the factory builds the context and the
    gateway renders every verdict. Returning ``None`` (no construction or no proof yet) is the
    honest negative path — the gateway records the same ``CONTEXT_MISSING`` stop a missing
    mapping entry has always produced (design #35 §3.1 (1)).
    """

    def __init__(
        self,
        *,
        construction_stage: OrderConstructionStage,
        proof_stage: ConformanceProofStage,
        venue_stage: VenueConstraintStage,
    ) -> None:
        """Bind the resolver to the three live construction stages."""
        self._construction_stage = construction_stage
        self._proof_stage = proof_stage
        self._venue_stage = venue_stage
        self.attempts: tuple[AttemptRequest, ...] = ()
        self.contexts: tuple[SendBoundaryContext, ...] = ()

    def __call__(self, attempt: AttemptRequest) -> SendBoundaryContext | None:
        """Resolve this attempt's send-boundary context from the live flow artifacts."""
        self.attempts += (attempt,)
        construction = self._construction_stage.construction
        proof = self._proof_stage.proof
        if construction is None or proof is None:
            return None
        context = bind_send_boundary_context(
            attempt=attempt,
            construction=construction,
            proof=proof,
            reference=OrderingEvent(
                event_id=f"{CONTINUITY_ID}-send-{len(self.attempts)}",
                source_continuity_id=CONTINUITY_ID,
                source_native_sequence=len(self.attempts),
            ),
            order_shape=self._venue_stage.resolved_shape,
            venue_shape_constraints=self._venue_stage.shape_constraints,
        )
        self.contexts += (context,)
        return context


# ===========================================================================
# The run
# ===========================================================================


@dataclass(frozen=True)
class SliceRun:
    """Everything one slice run produced, plus the live objects each lane owns."""

    run: BacktestRun
    book: BandBarBook
    core: EngineCore
    strategy: AuthoredStrategy
    resolver: RecordingContextResolver
    venue_stage: VenueConstraintStage
    reinjector: GatewayResultReinjector
    gateway: BrokerEgressGateway
    transport: SyntheticPaperTransport
    engine_sink: RecordingEvidenceSink
    gateway_sink: RecordingGatewayEvidenceSink

    def result_for(self, bar_index: int) -> Any:
        """The engine's own ``EventResult`` for the ``DECISION_TICK`` of ``bar_index``."""
        entries = [
            entry
            for entry in self.run.trace.entries
            if entry.bar_index == bar_index and entry.event_kind.value == "DECISION_TICK"
        ]
        assert len(entries) == 1, f"expected one tick for bar {bar_index}, got {len(entries)}"
        return self.run.event_results[entries[0].yield_sequence - 1]


def run_slice(
    *, profile: Sequence[tuple[int, str]] = BAND_PROFILE, resolver: Any = None
) -> SliceRun:
    """Replay the band profile end to end through one core and one send boundary.

    The wiring, in the direction the data flows — every joint a **shipped** symbol
    (design #35)::

        BandBarBook  →  MarketFeedContextResolver  →  CausalBarConverter  →  BacktestDriver
                     →  EngineCore(registry, stages, transmit=BrokerEgressGateway)
                     →  BrokerEgressGateway(contexts=lazy resolver)  →  SyntheticPaperTransport
                     →  GatewayResultReinjector  →  EGRESS_RESULT re-injection
                     →  the same EngineCore

    The gateway now occupies the ``Transmit`` slot **directly** — the substitution design #33
    §7.4 (c) declared — because a lazy ``contexts`` resolver can bind a context to an identity
    that only exists after step 12, and ``GatewayResultReinjector`` presents the gateway's
    retained results on the port the driver drains.
    """
    book = BandBarBook(profile)
    registry, strategy = registry_with_band_strategy()
    stages, step2, step3, step11 = construction_stages(book)

    gateway_sink = RecordingGatewayEvidenceSink()
    transport = SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=LOT_SIZE)
    )
    context_resolver = RecordingContextResolver(
        construction_stage=step2, proof_stage=step11, venue_stage=step3
    )
    gateway = BrokerEgressGateway(
        contexts=context_resolver, transport=transport, sink=gateway_sink
    )
    reinjector = GatewayResultReinjector(source=gateway)

    engine_sink = RecordingEvidenceSink()
    core = EngineCore(
        registry=registry,
        stages=stages,
        configuration=engine_configuration(),
        transmit=gateway,
        sink=engine_sink,
    )
    driver = BacktestDriver(
        converter=build_converter(book, resolver=resolver),
        fill_model=reinjector,
        continuity_id=CONTINUITY_ID,
    )
    run = driver.run(core, book.bars)
    return SliceRun(
        run=run,
        book=book,
        core=core,
        strategy=strategy,
        resolver=context_resolver,
        venue_stage=step3,
        reinjector=reinjector,
        gateway=gateway,
        transport=transport,
        engine_sink=engine_sink,
        gateway_sink=gateway_sink,
    )
