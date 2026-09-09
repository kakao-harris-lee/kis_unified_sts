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

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``pathlib``, ``yaml``, ``dataclasses``) + ``tos.authority``/``tos.liveauth``/
``tos.egressgw`` + ``tos_runtime.authority.epoch`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.engine import TransportNatureLike
from tos.liveauth import ContinuousValidityInputs, is_live

from tos_runtime.authority.epoch import SafetyAuthorityEpochService

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
    """The one operator-configured Coordinator-precondition governance fact.

    ``live_authorization_state`` is a GOVERNANCE fact the runtime reads, never
    one it computes or self-issues (module docstring; ADR-002-025).
    """

    live_authorization_state: str


def load_coordinator_preconditions_config(path: Path) -> CoordinatorPreconditionsConfig:
    """Load + fail-closed-validate ``coordinator_preconditions.example.yaml``-shaped config.

    Args:
        path: The YAML config file.

    Returns:
        The fully-valued :class:`CoordinatorPreconditionsConfig`.

    Raises:
        CoordinatorPreconditionsConfigError: The file is missing/unreadable/not
            valid YAML/not a mapping, the ``live_authorization_state`` key is
            absent or still ``null`` (named-TBD), or its value is not one of
            :data:`_SUPPORTED_LIVE_AUTHORIZATION_STATES` (no runtime wiring
            exists yet for any other restricted-live governance posture).
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
    return CoordinatorPreconditionsConfig(live_authorization_state=value)


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
    """

    def __init__(
        self,
        *,
        epoch_service: SafetyAuthorityEpochService | None,
        live_authorization_state: str | None,
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
        """
        self._epoch_service = epoch_service
        self._live_authorization_state = live_authorization_state
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

        Composes two independently conservative gates with AND — either one
        alone refusing is enough to refuse the whole check:

        1. **The kernel's own default-non-live judgement.** With this
           runtime's restricted-live governance posture read as
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
        2. **The structural transport check.** ``transport_nature
           .reaches_broker is False`` — an explicit ``is False`` (never a
           falsy check): ``True`` **or** ``None`` (an unestablished nature)
           is conservatively broker-consuming
           (``tos.egressgw.records.TransportNature``'s own docstring) and
           refuses regardless of the governance posture above (structural
           non-live guarantee — a broker-reaching transport can never be
           "live-scope authorized" while restricted-live is
           ``NOT_AUTHORIZED``, matching the CLAUDE.md non-negotiable that the
           real futures account is never funded with margin).

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
            grant); ``False`` if ``transport_nature`` is ``None`` or
            broker-reaching; otherwise ``True`` only for a non-broker-reaching
            transport under the ``NOT_AUTHORIZED`` posture.
        """
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
        return (not currently_live) and (transport_nature.reaches_broker is False)


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
