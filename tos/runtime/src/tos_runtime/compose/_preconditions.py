"""``tos_runtime.compose`` Coordinator-precondition wiring — TOS Phase 3 Wave 2 Lane B-R.

Design #31 §9-10 / plan §2.1 ("Coordinator 양성 게이트", RFC-002 §10.7 "verify current
Safety Authority · verify live authorization"). The kernel's own ``engine.core``
gains a ``CoordinatorPreconditions`` Protocol and a REQUIRED ``preconditions``
argument on ``EngineCore`` (kernel lane KW2-B); this module is the runtime-side
implementation of that Protocol, plus the side-effect-free stand-in the
boot-time replay core injects instead. Wired against the landed kernel
Protocol (``authority_epoch_current() -> bool | None``,
``live_scope_authorized(transport_nature: TransportNatureLike | None) -> bool | None``
— note the kernel's own optional ``transport_nature``, wider than the plan's
original non-optional sketch; see :meth:`RuntimeCoordinatorPreconditions
.live_scope_authorized`'s own docstring for the ``None`` treatment).

**Two questions, not one (T2 lane B; plan §2 decision 7 / §7 operator
disposition row 1, ``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md``).**
The kernel Protocol still carries only the two methods above — the kernel
diff for this arc is 0. What changed is what ``live_scope_authorized`` asks
internally: a synthetic (non-broker-reaching) transport is authorized exactly
as before (gate ①/② below, unchanged); a broker-reaching transport is now ALSO
asked a second, independent question — :func:`~tos_runtime.compose
._nonlive_admission.nonlive_broker_consuming_admitted` — which admits it only
under a positively-configured operator posture AND a scope that is
structurally incapable of ever being REAL (see that module's own docstring
for the five required conditions). Neither question ever widens the other:
gate ① (kernel ``is_live`` default-non-live judgement) still gates everything,
and a REAL-shaped scope fails the new question's condition 3 regardless of
posture.

**A third question, broker-reaching only (Phase 5 W3-b; plan §2 decision 5).** The
kernel Protocol still carries only the two methods above — kernel diff 0 again.
``live_scope_authorized`` now ANDs a THIRD, independent question into the
broker-reaching arm only (:meth:`RuntimeCoordinatorPreconditions._mesh_clear`): every
injected Phase 5 W3 safety-mesh service
(:class:`~tos_runtime.safety.ports.SafetyMeshService`) must report
``clear().clear is True``, non-vacuously (an empty mesh is ``False``, never a vacuous
pass). The synthetic (``reaches_broker is False``) path is entirely unaffected — the
mesh question is never even reached there, so a mesh left unwired (``safety_mesh=()``,
the default) never changes synthetic-path behaviour.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``pathlib``, ``yaml``, ``dataclasses``, ``typing``, ``collections.abc``) +
``tos.authority``/``tos.liveauth``/``tos.egressgw`` +
``tos_runtime.authority.epoch``/``tos_runtime.compose._nonlive_admission``/
``tos_runtime.brokercap.instance``/``tos_runtime.brokercap.scopes``/
``tos_runtime.safety.ports`` only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from tos.egressgw import TransportNature
from tos.engine import TransportNatureLike
from tos.liveauth import ContinuousValidityInputs, is_live

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import BrokerScope
from tos_runtime.compose._nonlive_admission import nonlive_broker_consuming_admitted
from tos_runtime.compose._safety_wiring import SafetyMeshSnapshot
from tos_runtime.safety.ports import SafetyMeshService

__all__ = [
    "COORDINATOR_PRECONDITIONS_CONFIG_NAME",
    "CoordinatorPreconditionsConfig",
    "CoordinatorPreconditionsConfigError",
    "RuntimeCoordinatorPreconditions",
    "load_coordinator_preconditions_config",
]

#: The Coordinator-preconditions config file's canonical name under a compose
#: ``config_dir`` (mirrors ``_engine_wiring.ENGINE_DRIVER_CONFIG_NAME``'s own
#: convention).
COORDINATOR_PRECONDITIONS_CONFIG_NAME = "coordinator_preconditions.yaml"

#: The one restricted-live governance posture this module is wired for today —
#: the value ``tos-spec/src/AUTHORITY-STATUS.csv`` records for the
#: ``restricted_live`` row ("No restricted-live grant is recorded; documents
#: tests dashboards and evidence rows are not authority") and ADR-002-025
#: §29's gate table. There is no runtime wiring for any other posture yet — a
#: positively-authorized restricted-live or production posture is Phase 5+
#: territory, gated on a fresh ADR-002-007/015 Live Authorization the spec
#: itself requires before any trial may start (ADR-002-025 line 743). CLAUDE.md
#: non-negotiable: the real futures account is never funded with margin and
#: real-money order paths are permanently policy-blocked, so this module never
#: constructs a path where a broker-reaching transport can be authorized.
_NOT_AUTHORIZED = "NOT_AUTHORIZED"

_SUPPORTED_LIVE_AUTHORIZATION_STATES = frozenset({_NOT_AUTHORIZED})


class CoordinatorPreconditionsConfigError(Exception):
    """Raised when the Coordinator-preconditions config is missing, malformed,
    carries an unfilled (named-TBD) value, or names a governance posture this
    module has no wiring for — fail-closed at load, never a silent default."""


@dataclass(frozen=True)
class CoordinatorPreconditionsConfig:
    """The operator-configured Coordinator-precondition governance facts.

    ``live_authorization_state`` is a GOVERNANCE fact the runtime reads, never
    one it computes or self-issues (module docstring; ADR-002-025).

    ``nonlive_broker_consuming_admitted`` is the T2 lane B posture (plan §2
    decision 7 / §7 operator disposition row 1) — a SEPARATE governance fact
    from ``live_authorization_state``, gating only the new
    non-live-broker-consuming question
    :meth:`RuntimeCoordinatorPreconditions.live_scope_authorized` asks for a
    broker-reaching transport. It is one of five required conditions
    (:mod:`tos_runtime.compose._nonlive_admission` module docstring) — a
    ``True`` posture alone never admits a REAL-shaped scope.
    """

    live_authorization_state: str
    nonlive_broker_consuming_admitted: bool


def load_coordinator_preconditions_config(path: Path) -> CoordinatorPreconditionsConfig:
    """Load + fail-closed-validate ``coordinator_preconditions.example.yaml``-shaped config.

    Args:
        path: The YAML config file.

    Returns:
        The fully-valued :class:`CoordinatorPreconditionsConfig`.

    Raises:
        CoordinatorPreconditionsConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping; the ``live_authorization_state`` key is
            absent or still ``null`` (named-TBD), or its value is not one of
            :data:`_SUPPORTED_LIVE_AUTHORIZATION_STATES` (no runtime wiring
            exists yet for any other restricted-live governance posture); or
            the ``nonlive_broker_consuming.admitted`` key is absent, the
            block itself is not a mapping, the value is still ``null``
            (named-TBD), or the value is not a ``bool``.
    """
    if not path.is_file():
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file not found: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file could not be read: {path}"
        ) from exc
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise CoordinatorPreconditionsConfigError(
            f"coordinator-preconditions config file must be a top-level mapping: {path}"
        )
    value = raw.get("live_authorization_state")
    if value is None:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'live_authorization_state' is missing or still null "
            "(named-TBD) — refusing to start until an operator supplies a "
            "concrete, spec-cited governance value"
        )
    if not isinstance(value, str) or value not in _SUPPORTED_LIVE_AUTHORIZATION_STATES:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'live_authorization_state' {value!r} is not a supported "
            f"posture (supported: {sorted(_SUPPORTED_LIVE_AUTHORIZATION_STATES)}) "
            "— no runtime wiring exists yet for any other restricted-live "
            "governance posture (fail-closed, never silently trusted)"
        )
    nonlive_block = raw.get("nonlive_broker_consuming")
    if not isinstance(nonlive_block, dict):
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming' is missing or not a mapping "
            "— refusing to start until an operator supplies "
            "{admitted: bool} (T2 lane B; plan §2 decision 7)"
        )
    nonlive_admitted = nonlive_block.get("admitted")
    if nonlive_admitted is None:
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming.admitted' is missing or "
            "still null (named-TBD) — refusing to start until an operator "
            "supplies a concrete true/false posture (plan §2 decision 7 / "
            "§7 operator disposition row 1)"
        )
    if not isinstance(nonlive_admitted, bool):
        raise CoordinatorPreconditionsConfigError(
            f"{path}: 'nonlive_broker_consuming.admitted' must be a bool, "
            f"got {nonlive_admitted!r}"
        )
    return CoordinatorPreconditionsConfig(
        live_authorization_state=value,
        nonlive_broker_consuming_admitted=nonlive_admitted,
    )


class RuntimeCoordinatorPreconditions:
    """The runtime implementation of the kernel's ``CoordinatorPreconditions`` Protocol
    (design #31 §9-10; plan §2.1).

    Both methods delegate the actual currentness/liveness judgement to the kernel's
    own pure predicates over injected state — this class authors no currentness or
    authorization comparison of its own, only the plumbing that reads the injected
    ports and hands their state to the kernel.

    **The claimed epoch is bound once, at composition, never re-read per tick
    (2026-09-09 wave-2 review finding #7 fix).** An earlier version re-derived
    the "claimed" epoch from the SAME just-read floor it then compared the
    claim against (``floor >= floor``, a tautology structurally incapable of
    detecting a stale epoch — it could only ever detect an unreadable log).
    This class instead captures :attr:`_bound_epoch` — this runtime's own
    epoch floor at the moment ``RuntimeCoordinatorPreconditions`` is
    constructed (:func:`~tos_runtime.compose._engine_wiring._build_preconditions`
    runs exactly once per boot, inside ``wire_engine_and_driver``) — and holds
    it fixed for the object's lifetime. A later Safety Authority epoch
    transition (:meth:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService.transition`,
    e.g. a failover) then genuinely outdates the bound claim on the very next
    tick, which is what CPL-6 ("a stale epoch SHALL fail closed", ADR-002-005
    §10) requires.

    **New liveness dependency on composition order (re-review finding R4, 2026-09-09).**
    Binding the claim ONCE at construction (rather than re-deriving it, per the fix above) means
    :attr:`_bound_epoch` is ``None`` for this instance's entire lifetime if
    ``epoch_service.current_epoch()`` reads ``None`` at THAT moment — which happens whenever this
    class is constructed BEFORE the epoch service's own first transition ever lands. Every tick
    would then read ``authority_epoch_current() -> False`` forever, refusing every
    ``DECISION_TICK`` for the whole process life (never a boot-time crash — the wave-2 finding #1
    fix already makes a Coordinator-gate refusal receipt ``uncompared`` on replay, so this is a
    LIVENESS regression on the live path, not a boot-availability one). Not reachable TODAY:
    ``tos_runtime.compose._wiring._boot_services`` calls ``authority_epoch_service.transition(...)``
    while acquiring the RCL/authority services, strictly BEFORE ``_finalize`` calls
    ``wire_engine_and_driver`` (which is what constructs this class) — so the bound epoch is never
    ``None`` on the nominal boot path. This is a fact about wiring ORDER, not about this class's
    own logic, so it is recorded here rather than guarded in code: a future reordering of
    ``_boot_services`` relative to ``_finalize`` would silently reintroduce it.
    """

    def __init__(
        self,
        *,
        epoch_service: SafetyAuthorityEpochService | None,
        live_authorization_state: str | None,
        nonlive_admitted: bool | None = None,
        active_scope: BrokerScope | None = None,
        instance_document: InstanceDocument | None = None,
        safety_mesh: Sequence[SafetyMeshService] = (),
        mesh_evidence_recorder: Callable[[Mapping[str, Any]], None] | None = None,
        mesh_snapshot_refresher: Callable[[], SafetyMeshSnapshot] | None = None,
    ) -> None:
        """Wire the preconditions object over its injected ports.

        Args:
            epoch_service: The composed :class:`SafetyAuthorityEpochService` for
                this runtime's authority domain. ``None`` when this instance is
                constructed before authority wiring completes (composition
                ordering) — :meth:`authority_epoch_current` reports ``None``
                (cannot be evaluated yet) rather than raising or guessing.
            live_authorization_state: The loaded
                :class:`CoordinatorPreconditionsConfig`'s governance posture
                (``None`` when not yet configured — same "cannot be evaluated"
                treatment as above).
            nonlive_admitted: The loaded
                :class:`CoordinatorPreconditionsConfig`
                ``.nonlive_broker_consuming_admitted`` posture (T2 lane B;
                plan §2 decision 7). ``None`` (the default) when the caller
                does not wire this path at all — a broker-reaching transport
                is then refused exactly as it was before this posture
                existed (:meth:`live_scope_authorized`'s own docstring).
            active_scope: This runtime's currently-active
                :class:`~tos_runtime.brokercap.scopes.BrokerScope`. ``None``
                (the default) when not wired — same "not available"
                treatment as ``nonlive_admitted``.
            instance_document: The Broker Capability Profile INSTANCE
                document bound to ``active_scope``. ``None`` (the default)
                when not wired — same "not available" treatment.
            safety_mesh: The Phase 5 W3 safety-mesh services (plan §2 decision 5) the
                Coordinator's THIRD question ANDs together for a broker-reaching
                transport (:meth:`live_scope_authorized`'s own docstring). Empty (the
                default) when not wired — a broker-reaching transport is then always
                refused by this question (non-vacuous: an empty mesh is never
                positively clear), while a synthetic transport is unaffected.
            mesh_evidence_recorder: Records ``COORDINATOR_MESH_HELD`` evidence
                (identities + reasons) whenever the mesh question refuses. ``None``
                (the default) records nothing — the refusal itself still holds,
                only the extra evidence trace is skipped.
            mesh_snapshot_refresher: Takes a FRESH per-tick
                :class:`~tos_runtime.compose._safety_wiring.SafetyMeshSnapshot` and
                shares it with the currentness/deferred-fields consumers (team-lead
                disposition, post-HIGH-1/HIGH-2 — see
                :class:`~tos_runtime.compose._safety_wiring.SafetyMeshSnapshot`'s own
                docstring). Called UNCONDITIONALLY, once, at the very top of every
                :meth:`live_scope_authorized` call — regardless of which branch is
                ultimately taken, so the shared snapshot is current before ANY later
                same-tick consumer runs (synthetic transport included). ``None`` (the
                default) falls back to calling ``.clear()`` on each of
                :attr:`_safety_mesh` directly, unchanged from before this disposition.
        """
        self._epoch_service = epoch_service
        self._live_authorization_state = live_authorization_state
        self._nonlive_admitted = nonlive_admitted
        self._active_scope = active_scope
        self._instance_document = instance_document
        self._safety_mesh = tuple(safety_mesh)
        self._mesh_evidence_recorder = mesh_evidence_recorder
        self._mesh_snapshot_refresher = mesh_snapshot_refresher
        #: This runtime's own epoch floor at composition time — the CLAIMED
        #: epoch every later :meth:`authority_epoch_current` call is checked
        #: against. Read exactly once, here, never again per tick (class
        #: docstring). ``None`` when ``epoch_service`` is ``None`` (not wired
        #: yet) or when the service's own floor is not yet established.
        self._bound_epoch: int | None = (
            epoch_service.current_epoch() if epoch_service is not None else None
        )

    def authority_epoch_current(self) -> bool | None:
        """Whether this runtime's bound Safety Authority epoch is still current (§5.1).

        Asks the kernel's ``authority_epoch_current`` predicate (via the
        service's own :meth:`~SafetyAuthorityEpochService.epoch_current`
        wrapper — reused rather than re-authored) whether :attr:`_bound_epoch`
        — the claim fixed at composition time, never re-derived here — is
        still ``>=`` the CURRENT floor. ``epoch_current`` reads the log via
        :meth:`~SafetyAuthorityEpochService.current_state` exactly ONCE per
        call (no separate read to produce the claim, unlike the tautological
        version this replaces — class docstring) so there is no TOCTOU window
        between reading the claim and reading the floor.

        Returns:
            ``None`` if the epoch service has not been wired yet (composition
            ordering — "refusal upstream" per the Coordinator gate's own
            ``is True`` check, never treated as an affirmative grant);
            otherwise the kernel predicate's own ``bool`` — ``False`` for a
            still-unestablished bound epoch, a domain mismatch, or a floor
            that has advanced past the bound claim since composition (a
            stale epoch, CPL-6).
        """
        if self._epoch_service is None:
            return None
        return self._epoch_service.epoch_current(self._bound_epoch)

    def live_scope_authorized(
        self, transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Whether ``transport_nature`` may proceed under the current live-scope
        governance posture (§5-6 liveauth; RFC-002 §10.7).

        Asks TWO independent questions (T2 lane B; plan §2 decision 7 / §7
        operator disposition row 1 — module docstring). Gate ① always gates
        both; ``reaches_broker is False`` OR the new non-live
        broker-consuming admission (never both required) then decides:

        1. **The kernel's own default-non-live judgement (gate ①, unchanged).**
           With this runtime's restricted-live governance posture read as
           ``NOT_AUTHORIZED`` (module docstring; ADR-002-025), no
           :class:`~tos.liveauth.LiveAuthorization` is ever constructed —
           ``authorization=None`` is passed to the kernel's own ``is_live``
           predicate, which is unconditionally ``False`` for an absent
           authorization ("§1 line 17 default non-live", never something this
           module computes). ``not is_live(...)`` is therefore always
           ``True`` today — but it is composed via the real kernel predicate,
           not authored here, so a future change to the governance posture
           (a positively-authorized state this module does not yet
           recognise — see :data:`_SUPPORTED_LIVE_AUTHORIZATION_STATES`)
           flows through this same call rather than silently bypassing it.
           A gate-① refusal short-circuits everything below.
        2. **The structural transport check (gate ②, unchanged).**
           ``transport_nature.reaches_broker is False`` — an explicit ``is
           False`` (never a falsy check) — admits immediately: a
           non-broker-reaching transport never needs the new question below.
        3. **The new non-live broker-consuming admission (only reached when
           gate ② does NOT hold, i.e. ``reaches_broker is True``).** Delegates
           to :func:`~tos_runtime.compose._nonlive_admission
           .nonlive_broker_consuming_admitted` over this instance's own
           ``nonlive_admitted``/``active_scope``/``instance_document`` ports —
           admits only when all five of that function's conditions hold
           (its own module docstring), one of which makes a REAL-shaped
           scope structurally unadmittable regardless of posture. An
           unestablished ``reaches_broker`` (``None``) reaches neither gate ②
           nor this question and refuses (``TransportNature``'s own
           docstring: unknown is conservatively broker-consuming).

        Args:
            transport_nature: The declared nature of the transport this
                Coordinator tick would egress through. The kernel's own
                ``CoordinatorPreconditions.live_scope_authorized`` docstring
                allows ``None`` here (a core wired with no declared transport
                nature at all — e.g. one that never reaches a send boundary)
                and leaves the fail-closed treatment to the implementation:
                this one refuses (``False``), never treats an absent nature
                as conservatively non-broker.

        Returns:
            ``None`` if the governance posture has not been configured yet, or
            names a posture this module has no wiring for (both are
            "cannot be evaluated" — refusal upstream, never an affirmative
            grant); ``False`` if ``transport_nature`` is ``None``, has an
            unestablished ``reaches_broker``, or is broker-reaching without a
            positive non-live broker-consuming admission; otherwise ``True``
            for a non-broker-reaching transport, or a broker-reaching one
            with a positive admission, both under the ``NOT_AUTHORIZED``
            posture.
        """
        # Team-lead disposition (post-HIGH-1/HIGH-2): refresh the shared per-tick
        # SafetyMeshSnapshot UNCONDITIONALLY, before any of the branches below --
        # regardless of which one is ultimately taken, so a LATER same-tick consumer
        # (the currentness dimension readers, the deferred-mesh-fields supply) sees
        # THIS tick's snapshot rather than a stale one from the previous tick. This
        # authors no admission judgement of its own (kernel diff 0; the "synthetic e2e
        # 불변" invariant is unaffected — the refresh is a pure side observation).
        snapshot = (
            self._mesh_snapshot_refresher()
            if self._mesh_snapshot_refresher is not None
            else None
        )
        if self._live_authorization_state is None:
            return None
        if self._live_authorization_state not in _SUPPORTED_LIVE_AUTHORIZATION_STATES:
            return None
        if transport_nature is None:
            return False
        currently_live = is_live(
            authorization=None,
            current_state=None,
            inputs=ContinuousValidityInputs(),
        )
        if currently_live:
            return False
        if transport_nature.reaches_broker is False:
            return True
        if transport_nature.reaches_broker is True:
            verdict = nonlive_broker_consuming_admitted(
                posture_admitted=self._nonlive_admitted,
                # The kernel's own TransportNatureLike Protocol (module
                # docstring) declares only `reaches_broker` — narrower than
                # this class's own construction site, which always receives
                # the real `tos.egressgw.records.TransportNature` (this
                # class's own docstring: "including the real ... TransportNature"
                # satisfies the Protocol structurally). This cast is a
                # static-typing widening only, no runtime check — condition
                # 4 needs `risk_relevant_live`, a field the narrower Protocol
                # never declares.
                transport_nature=cast(TransportNature, transport_nature),
                active_scope=self._active_scope,
                instance_document=self._instance_document,
            )
            return verdict.admitted and self._mesh_clear(snapshot)
        return False

    def _mesh_clear(self, snapshot: SafetyMeshSnapshot | None) -> bool:
        """The Coordinator's THIRD question (T2/W3-b; plan §2 decision 5) — asked ONLY
        on the broker-reaching path reached above (a synthetic transport is admitted
        by gate ② before this method is ever called, unchanged).

        ``True`` only when :attr:`_safety_mesh` is non-empty AND every service's
        clearance reports ``MeshClearance.clear is True`` — an explicit ``is True``
        check (never truthiness) and a non-vacuous requirement (an EMPTY mesh is
        ``False``, never a vacuous pass): a broker-reaching send with no safety-mesh
        wired at all must never be treated as though the mesh had positively cleared
        it.

        **Where each service's clearance comes from (W3.1 independent review
        MEDIUM-8, latent — M17 survives).** This distinguishes two structurally
        different cases, decided ONCE at construction time
        (:attr:`_mesh_snapshot_refresher`), never per-call:

        - :attr:`_mesh_snapshot_refresher` is ``None`` (no per-tick snapshot mechanism
          was ever wired at all — the legacy/unit-test path): each service's
          ``.clear()`` is called directly, exactly as before that mechanism existed.
        - :attr:`_mesh_snapshot_refresher` is wired (not ``None``): ``snapshot`` is
          ALWAYS trusted as-is, even when it is ``None`` this particular call (the
          refresher returned nothing — a no-op/broken refresher, or a genuine gap) —
          NEVER a silent fallback to a direct ``service.clear()`` call, which would
          quietly resurrect the exact per-tick amplification MEDIUM-6 eliminated
          without any signal that the refresher stopped doing its job. A missing
          clearance in this branch is treated as unestablished (held), the same as
          any other non-``True`` clearance.

        Records ``COORDINATOR_MESH_HELD`` evidence (identities + reasons) for every
        non-positive service when the question refuses, via the injected
        :attr:`_mesh_evidence_recorder` (``None`` records nothing — module docstring).
        """
        snapshot_mechanism_wired = self._mesh_snapshot_refresher is not None
        held: list[dict[str, Any]] = []
        for service in self._safety_mesh:
            if snapshot_mechanism_wired:
                clearance = (
                    None if snapshot is None else snapshot.clear_for(service.identity)
                )
            else:
                clearance = service.clear()
            if clearance is None or clearance.clear is not True:
                held.append(
                    {
                        "identity": service.identity,
                        "reasons": () if clearance is None else clearance.reasons,
                    }
                )
        mesh_clear = bool(self._safety_mesh) and not held
        if not mesh_clear and self._mesh_evidence_recorder is not None:
            self._mesh_evidence_recorder(
                {
                    "held_services": held,
                    "mesh_wired": bool(self._safety_mesh),
                }
            )
        return mesh_clear


class _ReplayPreconditions:
    """A ``True``/``True`` stand-in ``CoordinatorPreconditions`` used ONLY by the
    boot-time replay core (design #31 §9-10; plan §2.1's own BR-2 note).

    **Why always True, never the historically-real values.** The replay core
    re-executes an already-admitted event stream to compare
    ``EventResult.outcome_digest`` against what was recorded live (module
    ``_engine_wiring.py``'s own ``_ReplayStage`` docstring). If a
    ``DECISION_TICK`` event has recorded pipeline evidence at all, that is
    only possible because the ORIGINAL live run's own Coordinator gate
    (``authority_epoch_current()`` / ``live_scope_authorized(...)``, evaluated
    against the real epoch service / real transport nature THAT EXISTED AT
    THAT HISTORICAL MOMENT) already returned ``True``/``True`` and let the
    tick proceed far enough to run the decision pipeline — a tick the gate
    refused at the time never produced pipeline evidence to replay in the
    first place. Re-evaluating the gate against TODAY's epoch/authorization
    state during replay would not reconstruct that historical moment (the
    epoch may have advanced since, an authorization may have changed) — it
    would only risk a **false divergence**: the replay path stopping earlier
    than the live path did, for a reason that has nothing to do with the
    pipeline result the digest actually compares (exactly the class of
    "recorded verdicts don't help either" case ``_engine_wiring.py``'s BR-2
    plan note calls out — the gate is evaluated before the digest-determining
    pipeline run, so admitting the same tick again, unconditionally, is what
    "replay compares the same pipeline path the live run took" (plan §2.1)
    means concretely). Always returning ``True`` reproduces exactly the one
    fact replay can rely on: SOME positive gate outcome was recorded, so the
    tick was, in fact, admitted past this gate live. It never revisits
    ``EngineCore._run_entries``'s own already-computed
    ``PipelineResult.outcome_digest`` (untouched by this class), and once past
    the gate the replay core's real side-effect isolation is
    ``_ReplayStage`` — which halts the flow at the very first commitment-flow
    step (restrictive ``UNKNOWN``) with no I/O and no mutation, exactly the
    same as it does for every non-refused replayed tick today.
    """

    def authority_epoch_current(self) -> bool | None:
        """Always ``True`` — see the class docstring for why this is safe."""
        return True

    def live_scope_authorized(
        self, _transport_nature: TransportNatureLike | None
    ) -> bool | None:
        """Always ``True`` — see the class docstring for why this is safe."""
        return True
