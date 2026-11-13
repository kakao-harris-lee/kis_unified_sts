"""``tos_runtime.compose`` currentness dimension-reader factories + their late-bound
state cells — split out of ``_currentness_wiring.py`` purely for the size budget
(tools/tos_size_budget.py file-level limit); no behavioural difference from having
them inline there. :func:`_build_dimension_readers` is the ONE assembly point that
builds the full ``dimension_readers`` map
:class:`~tos_runtime.currentness.vector.CurrentnessAssembler` is constructed with —
called from :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`.

Every reader here is a ``Callable[[], DimensionReport | None]`` closure factory:
``None`` in from the underlying stage/service/verdict means "cannot observe yet",
never a fabricated positive (the "구조 파생 > 자기신고" discipline every reader below
follows) — see :class:`~tos_runtime.currentness.vector.DimensionReport`'s own
docstring for the shared field contract (``bound_generation``/``positively_established``/
``restrictive_floor``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.authority import currentness_admissible
from tos.brokercap import environment_binding_ok
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessPolicy,
    DimensionKey,
    policy_covers_mandated_dimensions,
)
from tos.sbr import ReadinessVerdict

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.scopes import BrokerScope, transport_nature
from tos_runtime.compose._monitor_wiring import _MonitorOwners
from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.posttrade.release_consumer import ReleaseConflictReader
from tos_runtime.recovery.barrier import RecoveryVerdict

__all__ = [
    "_DimensionStates",
    "_EnvironmentScopeDimensionState",
    "_PostTradeDimensionState",
    "_RecoveryDimensionState",
    "_ReleaseDimensionState",
    "_authority_dimension_reader_for",
    "_build_dimension_readers",
    "_currentness_policy_dimension_reader_for",
    "_environment_scope_dimension_reader_for",
    "_post_trade_dimension_reader_for",
    "_recovery_dimension_reader_for",
    "_release_dimension_reader_for",
]


def _authority_dimension_reader_for(
    authority_epoch_service: SafetyAuthorityEpochService,
) -> Callable[[], DimensionReport | None]:
    def _reader() -> DimensionReport | None:
        state = authority_epoch_service.current_state()
        if state.current_epoch_floor is None:
            return None
        witness = authority_epoch_service.witness()
        return DimensionReport(
            bound_generation=state.current_epoch_floor,
            positively_established=currentness_admissible(witness),
            restrictive_floor=0,
        )

    return _reader


def _currentness_policy_dimension_reader_for(
    policy: CurrentnessPolicy,
) -> Callable[[], DimensionReport | None]:
    """The CURRENTNESS_POLICY currentness dimension (Phase 5 W3-b, plan §2
    decision 3 — the first of the 9 dimension-owner replacements).

    W3.1 independent review MEDIUM-3: this reader used to ask whether ``policy``
    covers the mandated floor right after ``policy`` had been BUILT from that same
    floor (below, ``required_dimensions=tuple(sorted(MANDATED_DIMENSION_FLOOR, ...))``)
    — a tautology no operator config value could ever change. Fixed: ``policy`` is now
    built from the operator-declared ``required_dimensions`` key
    (:mod:`tos_runtime.currentness.config`'s own module docstring) — a genuinely
    separate, independently-editable source — so the reader's
    :func:`~tos.cur.predicates.policy_covers_mandated_dimensions` call against the
    kernel's own :data:`~tos.cur.MANDATED_DIMENSION_FLOOR` (never
    ``CurrentnessAssembler``'s own narrower ``self._mandated`` — a SEPARATE,
    deliberately smaller floor this class itself is constructed with; see its own
    docstring) now genuinely checks the operator's declared config against the kernel's
    mandated floor, never a comparison this module authors itself (MEDIUM-A
    discipline, module docstring).

    Always returns a report (never ``None``): ``policy`` is always present
    at composition time, so there is no "cannot observe yet" case here,
    unlike the RCL-backed readers above.
    """

    def _reader() -> DimensionReport | None:
        return DimensionReport(
            bound_generation=policy.policy_generation,
            positively_established=policy_covers_mandated_dimensions(
                policy, MANDATED_DIMENSION_FLOOR
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _RecoveryDimensionState:
    """A late-bound cell for the RECOVERY dimension reader (below).

    ``CurrentnessAssembler`` is constructed (in
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`,
    design #40 §5 order 6) strictly BEFORE the TOS Phase 5 W1 recovery barrier ever
    runs (:func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` is the
    LAST call in :func:`~tos_runtime.compose.root.compose_paper_runtime`, after
    ``_finalize``) — so this reader closes over this mutable cell, and
    ``compose_paper_runtime`` fills in :attr:`verdict` right after
    ``apply_recovery_barrier`` returns, before it ever hands the composed runtime to a
    caller that could drive an attempt (the exact same ordering discipline
    :class:`_ActionFlowDimensionState` already relies on for step 9's recorder).
    """

    verdict: RecoveryVerdict | None = None


def _recovery_dimension_reader_for(
    state: _RecoveryDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RECOVERY currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 2/9).

    The owner is W1's own :class:`~tos_runtime.recovery.barrier.RecoveryBarrier` —
    this reader copies its already-decided :attr:`~tos_runtime.recovery.barrier
    .RecoveryVerdict.readiness_verdict` verbatim (the SAME
    ``is ReadinessVerdict.READY`` identity check
    :meth:`~tos_runtime.recovery.barrier.RecoveryVerdict.ready` itself is —
    ``tos.sbr``'s own non-truthy discipline forbids ``if verdict:``), never a second
    judgement of its own (MEDIUM-A discipline, module docstring).

    ``bound_generation=0`` is this reader's own deliberate, explicit statement, not an
    invented placeholder: the recovery barrier is a single boot-time judgement (design
    #17 §3.5), not a versioned/generational artifact, so there is no real generation
    counter to report (the same "an owner reporting 0 is that owner's own choice"
    discipline :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring
    states).

    Returns ``None`` (dimension absent, never a fabricated verdict) until
    :attr:`_RecoveryDimensionState.verdict` is filled in — i.e. for the entire
    composition-time window before ``compose_paper_runtime`` has actually run the
    barrier.
    """

    def _reader() -> DimensionReport | None:
        verdict = state.verdict
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.readiness_verdict is ReadinessVerdict.READY,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _EnvironmentScopeDimensionState:
    """A late-bound cell for the ENVIRONMENT_SCOPE dimension reader (below).

    ``CurrentnessAssembler`` is constructed in
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    (design #40 §5 order 6) strictly BEFORE
    :func:`~tos_runtime.compose._wiring._resolve_strategies_and_attested_inputs` loads
    the broker-scopes config and resolves ``active_scope`` — so this reader closes over
    this mutable cell, and ``_wiring.py``'s ``_boot_services`` fills in
    :attr:`active_scope` right after that resolution returns (the same "constructed
    before its dependency exists" ordering :class:`_RecoveryDimensionState` already
    documents).
    """

    active_scope: BrokerScope | None = None


def _environment_scope_dimension_reader_for(
    environment_label: str,
    state: _EnvironmentScopeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The ENVIRONMENT_SCOPE currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 4/9).

    W3.1 independent review MEDIUM-2: the original reader asked
    :func:`~tos.brokercap.predicates.environment_binding_ok` whether ``environment_label``
    equals ``environment_label`` — a tautology (module docstring, MEDIUM-A discipline
    forbids exactly this). Fixed with three genuinely distinct sources instead of one
    variable read three times, mirroring the SAME broker-reaching / non-broker-reaching
    split :func:`~tos_runtime.brokercap.derive.derive_item6_item12`'s own item 12 already
    applies (never re-derived here — this reader reuses the public
    :func:`~tos_runtime.brokercap.scopes.transport_nature` helper, the SAME structural
    fact that split keys off):

    - A scope whose :func:`~tos_runtime.brokercap.scopes.transport_nature`
      ``reaches_broker`` ``is False`` (``SYNTHETIC``/``NONE`` endpoint classes — an
      explicit identity check, W3.1 independent review LOW-8, never truthiness: the
      field's own type is ``bool | None``, and ``None`` must never silently take this
      vacuous-True branch) has no environment binding evidence to check at all —
      ``positively_established=True`` vacuously, the same "no constraint generation
      exists to be stale" discipline :func:`derive_item6_item12` already documents for
      its own item 12, never a fabricated pass invented for this reader alone.
    - For every other case (``reaches_broker`` is ``True`` OR ``None`` — unknown
      reachability never gets the vacuous pass either), the real three-source check,
      both sides in the SAME
      broker-environment-axis string space (never ``environment_label``, the operator's
      OWN, differently-typed deployment label — D1.1 — which is not what this predicate
      compares at all): ``scope_environment`` is
      ``active_scope.environment_binding[capability_tuples[0].environment]`` — this
      scope's own config-declared axis binding table (independent-review finding F4);
      ``evidence_environment`` is ``active_scope.instance.environment`` — the Broker
      Capability Profile INSTANCE document's OWN declared environment, a file-loaded
      fact from a COMPLETELY SEPARATE source (the loader itself already "refuses when it
      disagrees with ``environment_binding[tuple.environment]``" — :class:`~tos_runtime
      .brokercap.scopes.ScopeInstanceBinding`'s own docstring, so this reader re-confirms
      at read-time what the loader only checked once at boot, exactly the "trust but
      verify" discipline two independently-sourced fields earn), or ``None`` when no
      instance is bound (a broker-reaching scope with no instance is a genuine gap,
      never papered over); ``inherited`` is ``False`` only when that instance binding is
      actually present — a real structural guarantee from the same loader-time
      cross-check, not a hardcoded literal.

    Returns ``None`` (dimension absent, never a fabricated verdict) until
    :attr:`_EnvironmentScopeDimensionState.active_scope` is filled in — the same
    composition-time-window discipline :func:`_recovery_dimension_reader_for` documents.
    """

    def _reader() -> DimensionReport | None:
        active_scope = state.active_scope
        if active_scope is None:
            return None
        if transport_nature(active_scope).reaches_broker is False:
            return DimensionReport(
                bound_generation=0, positively_established=True, restrictive_floor=0
            )
        scope_environment = (
            active_scope.environment_binding.get(
                active_scope.capability_tuples[0].environment
            )
            if active_scope.capability_tuples
            else None
        )
        instance = active_scope.instance
        evidence_environment = instance.environment if instance is not None else None
        inherited = False if instance is not None else None
        return DimensionReport(
            bound_generation=0,
            positively_established=environment_binding_ok(
                evidence_environment=evidence_environment,
                scope_environment=scope_environment,
                inherited=inherited,
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _PostTradeDimensionState:
    """A late-bound cell for the POST_TRADE dimension reader (below).

    TOS Phase 5 W2-R's own :class:`~tos_runtime.posttrade.release_consumer
    .FinalityReleaseConsumer` is built (and possibly never built at all, when
    ``runtime.driver`` did not survive to receive one — see
    :func:`~tos_runtime.compose._release_wiring.apply_release_wiring`'s own docstring)
    strictly AFTER this module's
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness` runs —
    the same "constructed before its dependency exists" ordering every other late-bound
    cell in this module documents, except here the dependency may never arrive at all,
    which is exactly why :attr:`consumer` stays ``None``-typed rather than
    assumed-eventual.
    """

    consumer: ReleaseConflictReader | None = None


def _post_trade_dimension_reader_for(
    state: _PostTradeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The POST_TRADE currentness dimension (Phase 5 W3.2, plan §2 decision 5 —
    dimension-owner replacement 5/6 of this wave's six).

    **A deliberately different axis from every other reader in this module.** Every
    other dimension answers "is it currently safe to SEND this attempt"; POST_TRADE
    answers "did this SCOPE's most recent SEND finish cleanly" — a fact about the past,
    not the present attempt. Sourced from
    :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer
    .latest_release_is_conflict_free`, which scans this consumer's own durable
    ``CAPACITY_RELEASE_INTENT``/``CAPACITY_RELEASE_HELD`` evidence rows for this
    consumer's own reservation scope and reports ``False`` only when the MOST RECENT one
    is a HELD row whose reason is ``ReleaseHoldReason.NOT_CORROBORATED`` — the one HELD
    reason that structurally means gate 3's reconciliation found a genuine conflict
    (an orphan broker order or a non-``MATCHED`` classification) between what this scope
    expected and what actually happened downstream. Every other HELD reason (no witness
    yet, proof not yet reloaded, reconciliation itself unavailable,
    ``WITNESS_NOT_INDEPENDENT`` since #1011 §3.5, ...) is a normal,
    transient "not yet complete" gate, not a conflict this dimension reports on — folding
    them all into ``False`` would permanently block new risk on ordinary pipeline timing,
    which plan §2 decision 5 explicitly rejects.

    **First attempt ⇒ ``True``, never ``None`` (plan §2 decision 5's own correction).** A
    scope with NO recorded post-trade evidence at all has no post-trade fact yet — which
    is the NORMAL state before any attempt has ever sent, not an unknown or absent state
    that should block the very first send. :meth:`FinalityReleaseConsumer
    .latest_release_is_conflict_free` itself returns ``True`` for this case (vacuous
    pass, mirroring :func:`_environment_scope_dimension_reader_for`'s own vacuous-True
    discipline for a non-broker-reaching scope).

    Returns ``None`` (dimension absent, never a fabricated verdict) ONLY when this
    composition never built a consumer at all (:attr:`_PostTradeDimensionState.consumer`
    stays ``None`` — e.g. the W1 recovery barrier detached the driver before release
    wiring could attach one) — a genuinely different case from "no evidence yet",
    which the consumer itself already resolves to ``True``.

    ``bound_generation=0``: no process-wide generation counter exists for a per-scope
    evidence scan (the same explicit-``0`` discipline CONSTRUCTION/CONSTRAINT/
    DECISION_PROOF_INTENT above document — never ``None``, which the kernel's own
    :func:`~tos.cur.predicates.dimension_positively_established` treats as a missing
    coordinate).
    """

    def _reader() -> DimensionReport | None:
        consumer = state.consumer
        if consumer is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=consumer.latest_release_is_conflict_free(),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ReleaseDimensionState:
    """A late-bound cell for the RELEASE dimension reader (below).

    :func:`~tos_runtime.compose._wiring._stage_b_release_probe` runs inside
    :func:`~tos_runtime.compose._wiring._boot_services`, strictly AFTER this module's
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness` — the
    same ordering discipline every other late-bound cell in this module documents.
    """

    release_admitted: bool | None = None


def _release_dimension_reader_for(
    state: _ReleaseDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RELEASE currentness dimension (Phase 5 W3.2, plan §2 decision 6 —
    dimension-owner replacement 6/6 of this wave's six).

    The owner is boot's own STAGE B release probe
    (:func:`~tos_runtime.compose._wiring._stage_b_release_probe`), which already calls
    the kernel's ``tos.sci.predicates.software_deployment_ok_verdict`` and either admits
    (returning ``True``) or raises :class:`~tos_runtime.compose._wiring
    .ReleaseAdmissionRefused` — a composition that reaches THIS reader at all has, by
    construction, already survived that refusal, so :attr:`_ReleaseDimensionState
    .release_admitted` is always ``True`` once filled (never independently re-evaluated
    here). This is a real, kernel-derived fact honestly reported, not a fabricated
    constant — it happens to be constant for this process's entire lifetime because a
    live ``ComposedRuntime`` cannot otherwise exist (the SAME "single boot-time judgement,
    not a versioned counter" shape :func:`_recovery_dimension_reader_for`'s own
    ``bound_generation=0`` documents for a different owner).

    **Disclosed static input (survey §0 RELEASE row).** The probe's own
    ``ReleaseAdmissionConfig.admission_result`` is an OPERATOR-DECLARED STATIC value
    (``tos_runtime/release/config.py``'s own module docstring: "Phase 2 has no live SCI
    admission-decision runtime") — this reader reports the kernel verdict the probe
    already computed over that static input, never claiming the input itself became
    live.

    ``bound_generation=0``: ``ReleaseAdmissionConfig`` carries no Release Generation
    field at all (survey §0) — the same explicit-``0`` discipline every other
    generation-less reader in this module documents (never ``None``, which the kernel's
    own :func:`~tos.cur.predicates.dimension_positively_established` treats as a missing
    coordinate, not an honest absence).

    Returns ``None`` (dimension absent) only during the composition-time window before
    ``_boot_services`` has returned — the same window every other late-bound cell in
    this module documents.
    """

    def _reader() -> DimensionReport | None:
        if state.release_admitted is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=state.release_admitted,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _DimensionStates:
    """Every late-bound dimension-reader cell :func:`_build_dimension_readers` creates —
    bundled so :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    can hand all of them to :class:`~tos_runtime.compose._currentness_wiring
    ._RiskAndCurrentness` in one field, and :func:`~tos_runtime.compose.root
    .compose_paper_runtime` can late-bind each once its own recorder/verdict exists."""

    recovery: _RecoveryDimensionState
    environment_scope: _EnvironmentScopeDimensionState
    post_trade: _PostTradeDimensionState
    release: _ReleaseDimensionState


def _build_dimension_readers(
    *,
    authority_epoch_service: SafetyAuthorityEpochService,
    currentness_policy: CurrentnessPolicy,
    environment_label: str,
    monitor_owners: _MonitorOwners,
) -> tuple[
    dict[DimensionKey, tuple[str, Callable[[], DimensionReport | None]]],
    _DimensionStates,
]:
    """The full ``dimension_readers`` map (module docstring, "Reader map") — split out
    of :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    purely for the size budget. Plan S2-b dropped the six readers that re-read an
    earlier flow step's own verdict (ACTION_FLOW, TRADING_APPROVAL, AGGREGATE_RISK,
    CONSTRUCTION, CONSTRAINT, DECISION_PROOF_INTENT — :data:`tos.cur.RETIRED_DIMENSION_KEYS`).
    """
    dimension_states = _DimensionStates(
        recovery=_RecoveryDimensionState(),
        environment_scope=_EnvironmentScopeDimensionState(),
        post_trade=_PostTradeDimensionState(),
        release=_ReleaseDimensionState(),
    )
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ] = {
        DimensionKey.SAFETY_AUTHORITY: (
            "tos_runtime.authority",
            _authority_dimension_reader_for(authority_epoch_service),
        ),
        DimensionKey.CURRENTNESS_POLICY: (
            "tos_runtime.currentness",
            _currentness_policy_dimension_reader_for(currentness_policy),
        ),
        DimensionKey.RECOVERY: (
            "tos_runtime.recovery",
            _recovery_dimension_reader_for(dimension_states.recovery),
        ),
        DimensionKey.ENVIRONMENT_SCOPE: (
            "tos_runtime.brokercap",
            _environment_scope_dimension_reader_for(
                environment_label, dimension_states.environment_scope
            ),
        ),
        DimensionKey.POST_TRADE: (
            "tos_runtime.posttrade",
            _post_trade_dimension_reader_for(dimension_states.post_trade),
        ),
        DimensionKey.RELEASE: (
            "tos_runtime.release",
            _release_dimension_reader_for(dimension_states.release),
        ),
        **monitor_owners.dimension_readers,
    }
    return dimension_readers, dimension_states
