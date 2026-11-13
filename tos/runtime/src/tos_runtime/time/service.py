"""``TrustworthyTimeService`` — Phase 2 runtime composition of the ``tos.time``
kernel predicate substrate (design #40 D1/D4; slice plan §1 item 2).

**This service does not judge.** It collects inputs — a monotonic reading, one
or more reference-source observations, and injected config bounds — and calls
the kernel's own conservative, fail-closed predicates
(``tos/src/tos/time/predicates.py``) to derive the next ``HealthState`` and a
``TimeHealthSnapshot``. Any transition the kernel's own
``health_transition_allowed``/``transition_to_trusted_requires_new_generation``
refuses is never applied — the service falls back to leaving the state
unchanged and recording why (slice plan §0: "런타임은 판정하지 않고 입력을
모아 커널 술어를 호출").

Fault-contract table (slice plan §1 "장애 계약" — the two this lane owns):

| # | contract | how this service satisfies it |
| - | -------- | ------------------------------ |
| ⑥ | clock regression/distortion | Every ``evaluate()`` call re-derives ``anchor_valid`` against the process's own high-water-mark anchor. A regression (or an unresolvable suspension) makes ``anchor_valid`` false, which can only route the FSM toward ``UNTRUSTED`` — never toward, or held at, ``TRUSTED`` (see ``_propose_transition``). |
| ⑦ | source unavailable | An unreachable/unhealthy reference observation feeds ``freshness_verdict`` a ``source_age=None`` (kernel: unknown source time), which the kernel predicate returns as ``FreshnessVerdict.UNKNOWN`` — never ``FRESH`` — so ``required_ok`` cannot hold and the service cannot claim freshness on a source it could not reach. |
| ⑤ | restart / recovery | A fresh process's ``start()`` mints a brand-new anchor + a brand-new :class:`~tos_runtime.time.generation.GenerationCounter` seeded at 0 — sharing no provable relationship with whatever an earlier process's snapshots asserted (``tos.time.recovery_generation_revives_nothing`` documents this is by design). Within one process, the only edge out of ``UNTRUSTED`` re-baselines the anchor at the recovery instant, and any subsequent return to ``TRUSTED`` still requires a strictly-new generation via ``transition_to_trusted_requires_new_generation``. |

Anchor-validity is a **high-water-mark** check, not merely "the value at
process start": every cycle that finds the anchor still valid ratchets its
recorded ``monotonic_anchor_value`` forward to the latest reading (never
backward), so a later reading has to beat the *highest* value ever
legitimately observed, not just the value recorded at boot — otherwise a
single injected regression followed by an unrelated later high reading could
look "valid again" by accident. Recovery out of ``UNTRUSTED`` deliberately
resets this high-water mark at the recovery instant (a fresh anchor, not a
revival of the old one).

Evidence cadence is NOT evaluation cadence
------------------------------------------
:meth:`TrustworthyTimeService.evaluate` runs, and exposes a fresh snapshot,
exactly as often as its caller calls it (the marketfeed pass loop: measured
~408 ms, p90 411). That cadence is what every freshness consumer reads
(:meth:`~TrustworthyTimeService.wall_clock_now_if_fresh`,
``FreshTrustedWallClockReference``) and this module does not touch it.

What IS bounded is how often the ``TIME_HEALTH_SNAPSHOT`` evidence ROW is
appended: on a change of judged content, and otherwise no more often than
``time_health_snapshot_heartbeat_ms`` (see that config key's own YAML comment
for the incident). Measured 2026-11-13 over every live evidence store
(``~/.local/state/tos/{paper-data,cp3-setup-d-*-data}/*/evidence.sqlite3``):
2.9 M of 3.45 M rows — 84.4 %, 8.3 GB — were this one kind, re-appending the
same judgement every ~400 ms, and on 2026-11-10 the host disk filled and
sessions were LOST.

**The receipt discipline is unchanged where it means something.** Every
*judgement* still reaches a durable receipt before it is observable: the
fingerprint below covers ``health_state``, ``generation``, the refusal
``reason``, the reference sources, the bounds, the versions, the continuity
identity and the ``suspended`` verdict, so no state/generation/anchor-identity
move can be skipped. What a skipped cycle leaves un-evidenced is only this
cycle's monotonic bookkeeping — the ratcheted high-water mark, the snapshot's
own id/instant, and the previous-reading pair. None of those is a judgement,
none is read back out of evidence by anything in this runtime, and none
survives a restart anyway (``tos.time.recovery_generation_revives_nothing``:
a fresh process mints a brand-new anchor and generation regardless).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.time import (
    Bounds,
    EvaluatedMonotonicAnchor,
    FreshnessVerdict,
    HealthState,
    ReferenceSource,
    SuspensionStatus,
    TimeContinuityIdentity,
    TimeHealthSnapshot,
    anchor_valid,
    freshness_verdict,
    health_transition_allowed,
    independent_reference_count,
    snapshot_age_admissible,
    source_disagreement_within_bound,
    transition_to_trusted_requires_new_generation,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.generation import GenerationCounter
from tos_runtime.time.sources import MonotonicSource, ReferenceSourceReader

__all__ = [
    "RecoveryGenerationNotAdvanced",
    "TimeHealthReader",
    "TimeServiceNotStarted",
    "TimeSnapshotReader",
    "TrustworthyTimeService",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_STARTUP_KIND = "TIME_SERVICE_STARTUP"
_STARTUP_RECORD_CLASS = "TIME_STARTUP"
_SNAPSHOT_KIND = "TIME_HEALTH_SNAPSHOT"
_SNAPSHOT_RECORD_CLASS = "TIME_HEALTH_SNAPSHOT"
#: G-1 taking-effect announcement (runtime operations wiring plan §2
#: decision 8) — appended exactly once per service instance.
_WALL_CLOCK_EXPOSED_KIND = "TIME_WALL_CLOCK_EXPOSED"
_WALL_CLOCK_EXPOSED_RECORD_CLASS = "TIME_WALL_CLOCK_EXPOSED"

#: Top-level dumped-snapshot fields that carry THIS CYCLE'S INSTANT, not its judgement, and so
#: are excluded from the on-change fingerprint (module docstring "Evidence cadence is NOT
#: evaluation cadence"). ``canonical_digest`` is ``f(covered content)`` and the covered content
#: includes the instants, so it moves every cycle by construction.
#: ``wall_clock_observation`` is the raw reference reading; the kernel's own
#: :class:`~tos.time.TimeHealthSnapshot` docstring records that it is **audit-only** ("no
#: predicate reads it for expiry/freshness/ordering"), so its VALUE is not a judgement — but
#: its PRESENCE is (see :func:`_judged_content`).
_INSTANT_FIELDS: frozenset[str] = frozenset(
    {
        "snapshot_id",
        "canonical_digest",
        "issue_monotonic_value",
        "wall_clock_observation",
    }
)

#: ``(section, field)`` pairs of the same kind, one level down. The two anchor values are this
#: cycle's monotonic reading and the ratcheted high-water mark; ``suspension_status
#: .suspension_ms`` is the raw ``max(0, Δwall - Δmono)`` magnitude, which jitters by a
#: millisecond on a quiet host — its JUDGEMENT, the sibling ``suspended`` bool the kernel's
#: ``anchor_valid`` actually turns on, stays in the fingerprint.
_INSTANT_SUBFIELDS: tuple[tuple[str, str], ...] = (
    ("evaluated_monotonic_anchor", "monotonic_anchor_value"),
    ("time_continuity_identity", "monotonic_anchor_value"),
    ("suspension_status", "suspension_ms"),
)


def _judged_content(payload: Mapping[str, Any], reason: str | None) -> dict[str, Any]:
    """The part of a dumped snapshot a consumer judges on, plus this cycle's refusal reason.

    Built by SUBTRACTION, never by listing what to keep: a field added to
    :class:`~tos.time.TimeHealthSnapshot` later counts as judged content automatically and
    fails toward writing a row, rather than being silently dropped from the comparison by an
    allowlist nobody updated.

    ``reason`` is :attr:`TrustworthyTimeService.last_transition_reason` — a refused
    transition is a real change a consumer reads, and it is not carried on the snapshot at
    all, so comparing only the dump would miss a cycle that newly started refusing.
    """
    judged: dict[str, Any] = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in payload.items()
        if key not in _INSTANT_FIELDS
    }
    for section, field_name in _INSTANT_SUBFIELDS:
        block = judged.get(section)
        if isinstance(block, dict):
            block.pop(field_name, None)
    # Presence, not value: a cycle that first acquires (or loses) a wall-clock reading has
    # changed what it can attest, and the TIME_WALL_CLOCK_EXPOSED announcement below cites the
    # snapshot_id of exactly such a cycle — it must not cite a row that was never written.
    judged["wall_clock_observed"] = payload.get("wall_clock_observation") is not None
    judged["last_transition_reason"] = reason
    return judged


class TimeServiceNotStarted(RuntimeError):
    """Raised when a method requiring ``start()`` is called before it, or
    ``start()`` is called twice on the same service instance."""


class RecoveryGenerationNotAdvanced(RuntimeError):
    """Raised when a recovery out of ``UNTRUSTED`` would not carry a strictly
    greater generation than the last exposed snapshot (LOW-5, review of
    ba7d438f). ``tos.time.recovery_generation_revives_nothing`` documents the
    rule this enforces, but the kernel predicate itself is an unconditional
    ``True`` for any input — it cannot detect a violation, only describe one.
    This exception is the real, falsifiable guard at the one place a
    violation would actually matter."""


class TimeSnapshotReader(Protocol):
    """The narrow read surface most :class:`TrustworthyTimeService` consumers actually need —
    the FSM's current health snapshot only (mypy stage 3 §1.3 rule 3 port introduction).

    Introduced because five independently-named test doubles
    (``FakeTimeService`` / ``_TrustedTimeService`` / ``_NeverStartedTimeService`` /
    ``_NotStartedTimeService`` / ``_BrokenTimeService``) each stood in for the FULL service
    while implementing only :meth:`current_snapshot` — the signal that every one of these
    consumers never touches :meth:`TrustworthyTimeService.start`,
    :meth:`~TrustworthyTimeService.evaluate`, :meth:`~TrustworthyTimeService.wall_clock_now`,
    or :attr:`~TrustworthyTimeService.last_transition_reason`. Narrowing the parameter type to
    this Protocol lets each test inject its own double directly, structurally, instead of every
    test needing to drive the full real FSM to get a typed value in.
    """

    def current_snapshot(self) -> TimeHealthSnapshot:
        """Return the current :class:`~tos.time.TimeHealthSnapshot` (raises
        :class:`TimeServiceNotStarted`, or an implementation's own equivalent, before the first
        successful ``start()``/``evaluate()``)."""
        ...


class TimeHealthReader(Protocol):
    """The narrower read surface :class:`~tos_runtime.posttrade.release_consumer
    .FinalityReleaseConsumer` needs (mypy stage 3 §1.3 rule 3 port introduction) — only the
    current :class:`~tos.time.HealthState`, read directly as a property
    (``_check_obligation_expiry`` reads ``health_state`` itself, never through
    :meth:`TimeSnapshotReader.current_snapshot`)."""

    @property
    def health_state(self) -> HealthState:
        """The service's current :class:`~tos.time.HealthState`."""
        ...


class TrustworthyTimeService:
    """Composition root for one process's Trustworthy Time health-check cycle.

    Args:
        monotonic: The injected monotonic-clock port.
        references: The injected reference-source ports. The typical Phase 2
            wiring is exactly one —
            :class:`~tos_runtime.time.sources.LocalSystemClockReader` — but
            this constructor does NOT itself enforce "at most one": a caller
            may inject any number. Multiple instances of the same reader kind
            still collapse to one independent contribution (every
            ``LocalSystemClockReader`` declares the same
            ``common_mode_group``), and with more than one genuinely
            independent reachable source, ``_required_ok`` reports
            disagreement as UNKNOWN rather than asserting agreement it never
            measured (HIGH-2 fix, review of ba7d438f) — see
            :meth:`_required_ok`.
        config: The fully-valued, fail-closed-loaded config
            (:func:`tos_runtime.time.config.load_time_config`).
        identity: This process's :class:`tos.workload.RuntimeIdentity`
            (design #40 D4) — binds every snapshot's continuity identity to
            the same workload instance every other evidence/RCL record this
            process produces carries.
        evidence: The durable append port (:class:`tos_runtime.evidence.ports.
            EvidenceAppendPort`) every snapshot (and the one startup record)
            is committed through before it is ever exposed.
    """

    def __init__(
        self,
        monotonic: MonotonicSource,
        references: Sequence[ReferenceSourceReader],
        config: TrustworthyTimeConfig,
        identity: RuntimeIdentity,
        evidence: EvidenceAppendPort,
    ) -> None:
        self._monotonic = monotonic
        self._references = tuple(references)
        self._config = config
        self._identity = identity
        self._evidence = evidence
        self._monotonic_anchor_id = f"mono-{identity.process_nonce}"

        self._generation: GenerationCounter | None = None
        self._anchor: TimeContinuityIdentity | None = None
        self._health_state: HealthState = HealthState.UNINITIALIZED
        self._snapshot: TimeHealthSnapshot | None = None
        self._snapshot_seq = 0
        self._last_transition_reason: str | None = None
        #: G-1 (decision 8): whether the TIME_WALL_CLOCK_EXPOSED announcement
        #: has already been appended for this service instance.
        self._wall_clock_exposed = False
        #: G-1 (team-lead follow-up, 2026-09-13): the previous cycle's
        #: ``(now_ms, wall_clock_unix_ms)`` reading pair — ``None`` until the
        #: first ``evaluate()`` completes. Feeds :meth:`_observed_suspension_ms`
        #: on the NEXT cycle; updated only after a cycle's own evidence append
        #: succeeds (same "no state moves before the receipt" discipline as
        #: every other mutation in :meth:`evaluate`).
        self._previous_monotonic_ms: int | None = None
        self._previous_wall_clock_unix_ms: int | None = None
        #: #810 (plan ``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.2):
        #: the two facts :meth:`wall_clock_at_monotonic` needs about the CYCLE the currently
        #: exposed snapshot came from — the monotonic reading the PREVIOUS cycle took (the
        #: mapping's domain floor) and the suspension THIS cycle observed. Captured in
        #: :meth:`evaluate` alongside every other post-receipt mutation, because
        #: :attr:`_previous_monotonic_ms` is overwritten there and neither value can be
        #: recovered from the snapshot afterwards. ``None`` until a cycle supplies them.
        self._cycle_previous_monotonic_ms: int | None = None
        self._cycle_suspension_ms: int | None = None
        #: The judged content (:func:`_judged_content`) of the last cycle whose
        #: ``TIME_HEALTH_SNAPSHOT`` row actually got a receipt, and the monotonic reading that
        #: cycle took. ``None`` until the first ``evaluate()`` commits one — which is why the
        #: first cycle of every process always writes. Updated only inside the post-receipt
        #: block of :meth:`evaluate`, with every other mutation there.
        self._evidenced_content: dict[str, Any] | None = None
        self._evidenced_monotonic_ms: int | None = None

    @property
    def health_state(self) -> HealthState:
        """The last successfully-applied ``HealthState`` (never a refused one)."""
        return self._health_state

    @property
    def last_transition_reason(self) -> str | None:
        """Why the most recent ``evaluate()`` did not change state, or ``None``
        when it either changed state or made no transition attempt at all."""
        return self._last_transition_reason

    def start(self) -> None:
        """Issue this process's ``TimeContinuityIdentity`` anchor + generation 0,
        together, then durably evidence the startup event.

        Design #40 D1.1: "``runtime_generation`` 은 D2 epoch 와 같은 트랜잭션에서
        증가" — Phase 2 realizes "same transaction" for this axis as "issued in
        the same startup call", with durable RCL-epoch binding deferred to
        slice order 3.

        Raises:
            TimeServiceNotStarted: If called more than once on the same
                instance (a service is started exactly once per process).
        """
        if self._generation is not None:
            raise TimeServiceNotStarted("start() has already been called")

        self._generation = GenerationCounter(start=0)
        now_ms = self._monotonic.now_ms()
        self._anchor = self._build_anchor(now_ms, self._generation.current)

        payload = {
            "event": _STARTUP_KIND,
            "cell_id": self._identity.cell_id,
            "process_nonce": self._identity.process_nonce,
            "runtime_generation": self._identity.runtime_generation,
            "tts_generation": self._generation.current,
            "monotonic_anchor_id": self._anchor.monotonic_anchor_id,
            "monotonic_anchor_value": self._anchor.monotonic_anchor_value,
        }
        self._evidence.append(
            payload, kind=_STARTUP_KIND, record_class=_STARTUP_RECORD_CLASS
        )

    def current_snapshot(self) -> TimeHealthSnapshot:
        """Return the most recently evaluated + durably-evidenced snapshot.

        Raises:
            TimeServiceNotStarted: If ``start()`` has not run, or no
                ``evaluate()`` call has yet completed successfully (a snapshot
                is exposed only after its evidence append returned a receipt —
                see the module docstring and :meth:`evaluate`).
        """
        self._require_started()
        if self._snapshot is None:
            raise TimeServiceNotStarted("no TimeHealthSnapshot has been evaluated yet")
        return self._snapshot

    def _require_started(self) -> tuple[GenerationCounter, TimeContinuityIdentity]:
        if self._generation is None or self._anchor is None:
            raise TimeServiceNotStarted("start() must be called first")
        return self._generation, self._anchor

    def _build_anchor(
        self, monotonic_value: int, tts_generation: int
    ) -> TimeContinuityIdentity:
        return TimeContinuityIdentity(
            host_or_runtime_id=self._identity.cell_id,
            boot_id=self._identity.process_nonce,
            process_id=self._identity.process_nonce,
            monotonic_anchor_id=self._monotonic_anchor_id,
            monotonic_anchor_value=monotonic_value,
            tts_generation=tts_generation,
        )

    def _next_snapshot_id(self) -> str:
        self._snapshot_seq += 1
        return f"ths-{self._identity.process_nonce}-{self._snapshot_seq}"

    @staticmethod
    def _propose_transition(
        from_state: HealthState, anchor_ok: bool, required_ok: bool
    ) -> HealthState:
        """Propose a conservative next state (validated + possibly refused by
        :meth:`evaluate` before ever being applied — see the module
        docstring's fault-contract table)."""
        if from_state is HealthState.UNINITIALIZED:
            return HealthState.SYNCHRONIZING
        if from_state is HealthState.UNTRUSTED:
            # The FSM's only edge out of UNTRUSTED — always re-attempt sync;
            # evaluate() re-baselines the anchor when this is actually applied.
            return HealthState.SYNCHRONIZING
        if not anchor_ok:
            # TRUSTED/DEGRADED_HOLDOVER lose all trust the instant the anchor
            # cannot be proven continuous — never merely "less fresh" (kernel
            # anchor_valid docstring; fault contract ⑥). A proposal from
            # SYNCHRONIZING here is shape-illegal (no SYNCHRONIZING->UNTRUSTED
            # edge) and is safely refused by evaluate()'s health_transition_
            # allowed gate, leaving SYNCHRONIZING in place.
            return HealthState.UNTRUSTED
        if from_state is HealthState.SYNCHRONIZING:
            return HealthState.TRUSTED if required_ok else HealthState.SYNCHRONIZING
        if from_state is HealthState.TRUSTED:
            return HealthState.TRUSTED if required_ok else HealthState.DEGRADED_HOLDOVER
        if from_state is HealthState.DEGRADED_HOLDOVER:
            return (
                HealthState.SYNCHRONIZING
                if required_ok
                else HealthState.DEGRADED_HOLDOVER
            )
        return from_state

    def _anchor_ok(
        self, anchor: TimeContinuityIdentity, now_ms: int, *, suspension_ms: int | None
    ) -> bool:
        """Kernel ``anchor_valid`` call: is ``anchor`` still continuous at ``now_ms``?

        ``suspension_ms`` is the REAL per-cycle observation from
        :meth:`_observed_suspension_ms` (team-lead follow-up, 2026-09-13,
        superseding an earlier ``suspension_ms=0`` literal this method used
        to pass unconditionally — see git history for that finding). ``None``
        on the very first ``evaluate()`` cycle (no previous reading to diff
        against) makes the kernel's own ``anchor_valid`` refuse (``tos/src/
        tos/time/predicates.py`` :143-145: ``suspension_ms is None`` =>
        invalid) — harmless there, since the first cycle's own
        ``UNINITIALIZED -> SYNCHRONIZING`` transition never consults
        ``anchor_ok`` in the first place (:meth:`_propose_transition`).
        """
        continuity_now = anchor.model_copy(update={"monotonic_anchor_value": now_ms})
        return anchor_valid(
            continuity_now,
            anchor,
            suspension_ms=suspension_ms,
            max_suspension_ms=self._config.max_process_suspension_ms,
        )

    def _observed_suspension_ms(
        self, now_ms: int, wall_clock_unix_ms: int | None
    ) -> int | None:
        """This cycle's observed process-suspension magnitude (team-lead
        follow-up, 2026-09-13, runtime operations wiring plan §2 decision 2):
        ``max(0, Δwall_clock_ms - Δmonotonic_ms)`` between the PREVIOUS
        ``evaluate()`` cycle's ``(monotonic, wall_clock)`` reading pair and
        THIS cycle's — a real system suspend/sleep stops the monotonic clock
        while the wall clock keeps advancing (an NTP step shows up the same
        way), so a wall delta that outruns the monotonic delta is an honest,
        conservative signal of exactly what the anchor predicate is meant to
        protect against. Clamped at 0 (never negative — the monotonic clock
        running AHEAD of the wall clock is not "negative suspension").

        Returns ``None`` — never a fabricated ``0`` — whenever no comparison
        is possible: the first ``evaluate()`` cycle ever (no previous
        reading), or either the previous or current cycle's reference
        reader(s) supplied no wall-clock value at all
        (:attr:`~tos_runtime.time.sources.ReferenceObservation.
        wall_clock_unix_ms` was ``None`` that cycle).
        """
        prev_mono = self._previous_monotonic_ms
        prev_wall = self._previous_wall_clock_unix_ms
        if prev_mono is None or prev_wall is None or wall_clock_unix_ms is None:
            return None
        delta_wall = wall_clock_unix_ms - prev_wall
        delta_mono = now_ms - prev_mono
        return max(0, delta_wall - delta_mono)

    def _read_reference_sources(
        self,
    ) -> tuple[tuple[ReferenceSource, ...], int, int | None]:
        """Read every injected reference source; return the kernel-shaped
        records, how many are reachable+healthy this cycle, and this cycle's
        wall-clock observation (G-1, runtime operations wiring plan §2
        decision 1).

        The count — not just a bool — matters as of the HIGH-2 fix (review of
        ba7d438f): whether disagreement can be honestly asserted as 0 depends
        on whether there is exactly one reachable source (nothing to disagree
        with) or more than one (a real comparison would be needed, and Phase 2
        performs none) — see :meth:`_required_ok`.

        The wall-clock value is the first reachable+healthy observation that
        actually carries one (Phase 2 wires exactly one reader kind,
        :class:`~tos_runtime.time.sources.LocalSystemClockReader`, so in
        practice there is at most one candidate) — never fabricated when no
        injected reader supplies one.
        """
        observations = [reader.read() for reader in self._references]
        reachable_count = sum(
            1 for obs in observations if obs.reachable and obs.healthy
        )
        wall_clock_unix_ms = next(
            (
                obs.wall_clock_unix_ms
                for obs in observations
                if obs.reachable and obs.healthy and obs.wall_clock_unix_ms is not None
            ),
            None,
        )
        kernel_sources = tuple(
            ReferenceSource(
                common_mode_group=obs.common_mode_group,
                quality=obs.quality,
                reachable=obs.reachable,
                healthy=obs.healthy,
                offset_bound_ms=obs.offset_bound_ms,
                drift_bound_ppm=obs.drift_bound_ppm,
                uncertainty_bound_ms=obs.uncertainty_bound_ms,
            )
            for obs in observations
        )
        return kernel_sources, reachable_count, wall_clock_unix_ms

    def _required_ok(
        self,
        anchor_ok: bool,
        kernel_sources: tuple[ReferenceSource, ...],
        reachable_count: int,
    ) -> bool:
        """Fold every kernel predicate this cycle's observations feed into the
        single "may this be TRUSTED" gate (fault contracts ⑥/⑦)."""
        reachable = reachable_count > 0
        reference_count = (
            independent_reference_count(kernel_sources) if reachable else 0
        )

        # HIGH-2 fix (review of ba7d438f): the precondition "at most one
        # reachable source" is NOT enforced by the constructor — a caller can
        # wire any number of ReferenceSourceReaders (module docstring
        # "accepts a sequence so a later profile can add a second independent
        # source"). So disagreement is asserted as 0 ONLY in the genuinely
        # single-source case (exactly one reachable source — nothing to
        # disagree with); with MORE than one reachable source, Phase 2
        # performs no pairwise comparison at all (no comparator exists yet),
        # so the disagreement observation is UNKNOWN (``None``), which
        # source_disagreement_within_bound fails closed on — never silently
        # asserted as "in bound". An earlier cut asserted 0 for any reachable
        # count, which let un-measured multi-source agreement pass as
        # measured agreement.
        # reachable_count == 0 -> None (no observation at all); == 1 -> 0
        # (nothing to disagree with); > 1 -> None (unmeasured, fail-closed).
        disagreement_ms: int | None = 0 if reachable_count == 1 else None
        disagreement_ok = source_disagreement_within_bound(
            disagreement_ms, self._config.max_time_source_disagreement_ms
        )

        # A locally-read observation's source_age is ~0 by construction (read
        # and evaluated in the same cycle, no transport hop yet exists in
        # Phase 2); an unreachable source reports no age at all (fail-closed).
        source_age = 0 if reachable else None
        freshness = freshness_verdict(
            source_age=source_age,
            delay_bounds=(
                self._config.max_time_transport_and_queue_uncertainty_ms,
                self._config.max_time_source_precision_ms,
            ),
            max_age_bound=self._config.max_time_conservative_freshness_age_ms,
            future_tolerance=self._config.max_future_timestamp_tolerance_ms,
        )

        # Defense-in-depth self-check: even a FRESH instantaneous read must
        # still fall within the same conservative freshness bound when framed
        # as a consumer age (Phase 2's own service is its own sole consumer
        # here — a cross-continuity consumer would instead compose
        # effective_snapshot_age_bound_from_continuity, out of this slice).
        snapshot_admissible = snapshot_age_admissible(
            0 if reachable else None,
            self._config.max_time_conservative_freshness_age_ms,
        )

        return (
            anchor_ok
            and reachable
            and reference_count >= self._config.min_time_independent_reference_count
            and disagreement_ok
            and freshness is FreshnessVerdict.FRESH
            and snapshot_admissible
        )

    def _decide_transition(
        self,
        from_state: HealthState,
        anchor_ok: bool,
        required_ok: bool,
        generation: GenerationCounter,
        anchor: TimeContinuityIdentity,
        now_ms: int,
    ) -> tuple[HealthState, str | None, int, TimeContinuityIdentity]:
        """Propose + gate one FSM transition (never applied if the kernel
        refuses it). Returns ``(applied_state, refusal_reason, commit_
        generation, next_anchor)`` — ``next_anchor`` is only replaced here on
        an UNTRUSTED->SYNCHRONIZING recovery; the caller still ratchets it
        afterward when the anchor held valid this cycle."""
        to_state = self._propose_transition(from_state, anchor_ok, required_ok)
        applied_state = from_state
        reason: str | None = None
        next_anchor = anchor
        commit_generation = generation.current

        if to_state == from_state:
            return applied_state, reason, commit_generation, next_anchor

        if not health_transition_allowed(from_state, to_state):
            return (
                from_state,
                f"health_transition_allowed refused {from_state} -> {to_state}",
                commit_generation,
                next_anchor,
            )

        if to_state is HealthState.TRUSTED:
            candidate_generation = generation.peek_next()
            if transition_to_trusted_requires_new_generation(
                generation.current, candidate_generation
            ):
                return to_state, None, candidate_generation, next_anchor
            return (
                from_state,
                "transition_to_trusted_requires_new_generation refused "
                f"({generation.current} -> {candidate_generation})",
                commit_generation,
                next_anchor,
            )

        if (
            to_state is HealthState.SYNCHRONIZING
            and from_state is HealthState.UNTRUSTED
        ):
            # tos.time.recovery_generation_revives_nothing is the kernel rule
            # this enforces ("a new generation does not revive what an
            # earlier one invalidated") — but that predicate is an
            # unconditional True for any input (LOW-5, review of ba7d438f):
            # it documents the rule, it cannot detect a violation of it. The
            # REAL, falsifiable guard is this explicit generation-advance
            # check: recovery must mint a generation strictly greater than
            # whatever the last exposed snapshot carried. A plain `assert`
            # here would (a) vanish entirely under `python -O` and (b) never
            # fail regardless of -O, since both of its would-be arguments
            # were the same value — this `if ... raise` cannot be stripped
            # and is genuinely falsifiable.
            last_generation = (
                self._snapshot.generation
                if self._snapshot is not None
                else generation.current
            )
            new_generation = generation.peek_next()
            if last_generation is None or new_generation <= last_generation:
                raise RecoveryGenerationNotAdvanced(
                    "recovery from UNTRUSTED must mint a strictly-new "
                    f"generation (last exposed snapshot generation="
                    f"{last_generation!r}, candidate={new_generation!r})"
                )
            next_anchor = self._build_anchor(now_ms, new_generation)
            commit_generation = new_generation
        return to_state, None, commit_generation, next_anchor

    @staticmethod
    def _ratchet_anchor(
        anchor: TimeContinuityIdentity,
        next_anchor: TimeContinuityIdentity,
        anchor_ok: bool,
        now_ms: int,
    ) -> TimeContinuityIdentity:
        """Advance the anchor's high-water mark forward when it held valid
        this cycle (module docstring "high-water-mark" note); leave it
        untouched on a regression, and never overwrite a fresh recovery
        rebuild (``next_anchor is not anchor`` already)."""
        if next_anchor is not anchor or not anchor_ok:
            return next_anchor
        ratcheted = max(anchor.monotonic_anchor_value or now_ms, now_ms)
        return anchor.model_copy(update={"monotonic_anchor_value": ratcheted})

    def _issue_snapshot(
        self,
        *,
        generation_value: int,
        health_state: HealthState,
        anchor: TimeContinuityIdentity,
        now_ms: int,
        kernel_sources: tuple[ReferenceSource, ...],
        wall_clock_observation: int | None,
        suspension_status: SuspensionStatus,
    ) -> TimeHealthSnapshot:
        snapshot = TimeHealthSnapshot.issue(
            scheme=_SCHEME,
            snapshot_id=self._next_snapshot_id(),
            generation=generation_value,
            health_state=health_state,
            time_continuity_identity=anchor,
            evaluated_monotonic_anchor=EvaluatedMonotonicAnchor(
                monotonic_anchor_id=anchor.monotonic_anchor_id,
                monotonic_anchor_value=now_ms,
            ),
            reference_sources=kernel_sources,
            bounds=Bounds(
                source_disagreement_bound_ms=self._config.max_time_source_disagreement_ms
            ),
            wall_clock_observation=wall_clock_observation,
            suspension_status=suspension_status,
            issuer_continuity_id=anchor.monotonic_anchor_id,
            issue_monotonic_value=now_ms,
            maximum_consumer_age_ms=self._config.max_time_conservative_freshness_age_ms,
            tz_db_version=self._config.tz_db_version,
            trading_calendar_version=self._config.trading_calendar_version,
            verification_profile_version=self._config.verification_profile_version,
            safety_profile_version=self._config.safety_profile_version,
        )
        return snapshot

    def _snapshot_evidence_due(self, judged: Mapping[str, Any], now_ms: int) -> bool:
        """Whether this cycle's ``TIME_HEALTH_SNAPSHOT`` row must be appended: the judged
        content moved, or the heartbeat interval has elapsed since the last row that got one.

        Fails toward writing. The first cycle of a process has nothing to compare against and
        writes; a monotonic reading that went BACKWARD since the last written row is exactly
        the regression the anchor predicate exists for and writes rather than silently
        deferring on a negative age.
        """
        if self._evidenced_content is None or judged != self._evidenced_content:
            return True
        last_ms = self._evidenced_monotonic_ms
        if last_ms is None or now_ms < last_ms:
            return True
        return now_ms - last_ms >= self._config.time_health_snapshot_heartbeat_ms

    def _announce_wall_clock_exposed(
        self, snapshot: TimeHealthSnapshot, wall_clock_observation: int
    ) -> None:
        """G-1 taking-effect announcement (runtime operations wiring plan §2 decision 8):
        exactly once per service instance, the first time a TRUSTED snapshot carries a real
        wall-clock observation.

        A SEPARATE evidence append from the snapshot's own row — ordered after it, per the
        same "receipt before observable state" discipline (if THIS append raises, the snapshot
        itself was already durably committed and IS exposed; only the exposure flag below
        would not yet be set, so a retry-from-caller would correctly re-attempt this
        announcement on the next ``evaluate()`` rather than silently losing it).

        The cited ``snapshot_id`` always names a row that exists: the cycle that satisfies
        this condition is by construction one :meth:`evaluate` forces due (``announce_ms is
        not None or ...``), so the snapshot row above was appended on this very cycle.
        """
        self._evidence.append(
            {
                "event": _WALL_CLOCK_EXPOSED_KIND,
                "snapshot_id": snapshot.snapshot_id,
                "wall_clock_observation": wall_clock_observation,
                "unit": "unix_ms",
                "source_label": "LOCAL_SYSTEM_CLOCK",
            },
            kind=_WALL_CLOCK_EXPOSED_KIND,
            record_class=_WALL_CLOCK_EXPOSED_RECORD_CLASS,
        )
        self._wall_clock_exposed = True

    def evaluate(self) -> TimeHealthSnapshot:
        """Run one health-check cycle: read sources, call kernel predicates,
        derive the next state, issue a snapshot, durably evidence it when it is
        due, and only then expose it.

        The cycle itself is unconditional — every call reads the clock, calls
        every predicate and exposes a fresh snapshot, which is what the
        freshness consumers read. The ``TIME_HEALTH_SNAPSHOT`` evidence ROW is
        written on a change of judged content or once per
        ``time_health_snapshot_heartbeat_ms``, never per cycle (module
        docstring "Evidence cadence is NOT evaluation cadence").

        Returns:
            The freshly issued, digest-verified :class:`TimeHealthSnapshot`.

        Raises:
            TimeServiceNotStarted: If ``start()`` has not run.
            Exception: Whatever the injected evidence port raises on a failed
                append — propagated unchanged; no internal state (health
                state, anchor, generation) is mutated and no snapshot is
                exposed when this happens (see the module docstring).
        """
        generation, anchor = self._require_started()
        now_ms = self._monotonic.now_ms()
        # Read before the post-receipt block below overwrites it (:meth:`_capture_cycle`).
        previous_monotonic_ms = self._previous_monotonic_ms

        kernel_sources, reachable_count, wall_clock_observation = (
            self._read_reference_sources()
        )
        suspension_ms = self._observed_suspension_ms(now_ms, wall_clock_observation)
        suspended = (
            suspension_ms is not None
            and suspension_ms > self._config.max_process_suspension_ms
        )
        anchor_ok = self._anchor_ok(anchor, now_ms, suspension_ms=suspension_ms)
        required_ok = self._required_ok(anchor_ok, kernel_sources, reachable_count)

        applied_state, reason, commit_generation, next_anchor = self._decide_transition(
            self._health_state, anchor_ok, required_ok, generation, anchor, now_ms
        )
        next_anchor = self._ratchet_anchor(anchor, next_anchor, anchor_ok, now_ms)

        snapshot = self._issue_snapshot(
            generation_value=commit_generation,
            health_state=applied_state,
            anchor=next_anchor,
            now_ms=now_ms,
            kernel_sources=kernel_sources,
            wall_clock_observation=wall_clock_observation,
            suspension_status=SuspensionStatus(
                suspended=suspended, suspension_ms=suspension_ms
            ),
        )

        payload = snapshot.model_dump(mode="json")
        judged = _judged_content(payload, reason)
        # The reading to announce (G-1 decision 8), or None when this is not that cycle.
        announce_ms: int | None = (
            wall_clock_observation
            if applied_state is HealthState.TRUSTED and not self._wall_clock_exposed
            else None
        )
        # "영수증 없으면 일어나지 않았다" — durable commit BEFORE any of the
        # state below becomes observable. If this raises, nothing past this
        # point executes: no state/anchor/generation mutation, no snapshot
        # exposed via current_snapshot(). A cycle that is NOT due appends no
        # row and therefore has no receipt to wait on — see the module
        # docstring for exactly which mutations that leaves un-evidenced and
        # why none of them is a judgement.
        due = announce_ms is not None or self._snapshot_evidence_due(judged, now_ms)
        if due:
            self._evidence.append(
                payload, kind=_SNAPSHOT_KIND, record_class=_SNAPSHOT_RECORD_CLASS
            )
        if announce_ms is not None:
            self._announce_wall_clock_exposed(snapshot, announce_ms)

        if due:
            self._evidenced_content = judged
            self._evidenced_monotonic_ms = now_ms
        if commit_generation != generation.current:
            generation.next()
        self._anchor = next_anchor
        self._health_state = applied_state
        self._last_transition_reason = reason
        self._snapshot = snapshot
        # Feeds the NEXT cycle's _observed_suspension_ms — captured
        # unconditionally (regardless of this cycle's health-state outcome),
        # same as every other post-receipt mutation above.
        self._previous_monotonic_ms = now_ms
        self._previous_wall_clock_unix_ms = wall_clock_observation
        self._capture_cycle(previous_monotonic_ms, suspension_ms)
        return snapshot

    def _capture_cycle(
        self, previous_monotonic_ms: int | None, suspension_ms: int | None
    ) -> None:
        """Record the two facts :meth:`wall_clock_at_monotonic` needs about the cycle that
        just issued the exposed snapshot (#810, plan
        ``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.2): the PREVIOUS
        cycle's monotonic reading — the mapping's domain floor, which
        :attr:`_previous_monotonic_ms` has by now been overwritten with this cycle's — and the
        suspension this cycle observed.

        Called from :meth:`evaluate` with the other post-receipt mutations, never before the
        durable append returns: a mapping that survived a failed commit would describe a cycle
        whose snapshot was never exposed.
        """
        self._cycle_previous_monotonic_ms = previous_monotonic_ms
        self._cycle_suspension_ms = suspension_ms

    def wall_clock_now(self) -> int | None:
        """The current wall-clock reading, or ``None`` (G-1, runtime
        operations wiring plan §2 decision 1).

        Gated on ``HealthState.TRUSTED``: a ``SYNCHRONIZING``/``DEGRADED_
        HOLDOVER``/``UNTRUSTED`` cycle — even one whose snapshot happens to
        carry a wall-clock observation — never exposes it through this
        method. This is the ONE read
        :class:`~tos_runtime.calendar.ports.TrustedWallClockReference` calls;
        it never reads ``current_snapshot().wall_clock_observation`` directly
        (which would skip this gate).
        """
        if self._health_state is not HealthState.TRUSTED or self._snapshot is None:
            return None
        return self._snapshot.wall_clock_observation

    def wall_clock_now_if_fresh(self, max_age_ms: int) -> int | None:
        """:meth:`wall_clock_now`, but only while the snapshot it comes from is at most
        ``max_age_ms`` old on this service's own monotonic clock; ``None`` otherwise.

        :meth:`wall_clock_now` serves the observation captured at the last ``evaluate()`` — in a
        composed runtime that is the boot cycle, so its value can be hours or days old. A consumer
        that turns the reading into an identity (the egress trading date — plan 2026-09-26 egress
        trading date, review finding 1) must not use a stale instant as "now": an ACK on day D+1
        stamped with day D would pair a fresh ODNO with the wrong day. A snapshot with no
        ``issue_monotonic_value``, or one from the future, is not fresh.
        """
        observation = self.wall_clock_now()
        if observation is None or self._snapshot is None:
            return None
        issued = self._snapshot.issue_monotonic_value
        if issued is None:
            return None
        age_ms = self._monotonic.now_ms() - issued
        if age_ms < 0 or age_ms > max_age_ms:
            return None
        return observation

    def wall_clock_at_monotonic(self, mono_ms: int) -> int | None:
        """The wall-clock time that a PAST monotonic instant of this process corresponds to,
        or ``None`` (#810, plan
        ``docs/plans/2026-09-28-tos-kis-quote-request-anchor-plan.md`` §2.2).

        The value is::

            S'_wall - (S'_mono - mono_ms) - (the suspension THIS cycle observed)

        where ``S'`` is the freshly evaluated, exposed snapshot: ``S'_wall`` is its
        ``wall_clock_observation`` (served through :meth:`wall_clock_now`, so the
        ``TRUSTED`` gate is the same one) and ``S'_mono`` its ``issue_monotonic_value``.

        **This is NOT the rejected "extrapolate now" (plan 2026-09-26 §3).** That proposal
        read a cached wall-clock value and added elapsed monotonic time to MANUFACTURE a
        present instant no reference source ever attested — a reading with no evaluation
        behind it. This maps only BACKWARD, from a reading that has just been evaluated and
        found trustworthy, onto an instant that lies inside the very interval that evaluation
        covers. Subtracting the observed suspension moves the answer EARLIER, which makes any
        age derived from it LARGER — the conservative direction. (During a suspension the
        monotonic clock stops while the wall clock runs on, so the elapsed-monotonic gap
        understates the elapsed wall time; charging the whole observed suspension to the gap
        can only over-age the mapped instant, never under-age it.)

        **The domain is this cycle only.** ``mono_ms`` must lie between the PREVIOUS
        evaluation's monotonic reading and ``S'_mono``: outside that interval there is no
        measured suspension covering the span, so the mapping would be an extrapolation past
        what was evaluated. The floor also stays honest about what the suspension figure
        actually measures — it is ``max(0, Δwall - Δmono)`` across exactly those two readings
        (:meth:`_observed_suspension_ms`).

        Returns ``None`` — never a fabricated instant — when:

        * the service is not ``TRUSTED``, or has no exposed snapshot, or that snapshot carries
          no wall-clock observation / no ``issue_monotonic_value``;
        * this cycle observed no suspension magnitude at all (the first ``evaluate()``, or a
          cycle with no wall-clock reading on either side) — an unknown term is not a zero;
        * ``mono_ms`` is outside the domain above.

        **The unknown-suspension branch is defense in depth: no ``TRUSTED`` path in a real run
        reaches it** (PR #812 review, LOW). :meth:`_observed_suspension_ms` answers ``None`` on
        exactly three inputs — no previous monotonic reading, no previous wall-clock reading, no
        current one — and a real run closes all three before this line: the first
        ``evaluate()`` (the only one with no previous reading) is still ``SYNCHRONIZING``, so
        the ``TRUSTED`` gate above has already returned ``None``; and Phase 2 wires exactly one
        reference-reader kind (:class:`~tos_runtime.time.sources.LocalSystemClockReader`), which
        always carries a wall-clock value, so neither the previous nor the current observation
        can be absent while the service is ``TRUSTED``. The branch is kept — and pinned by
        ``tests/time/test_service.py`` — because folding the unknown to a zero (``suspension_ms
        or 0``) would silently un-age every mapped instant on the day a future reader kind, or
        a degraded read, does expose a trusted reading with no suspension behind it.

        Args:
            mono_ms: A reading taken from THIS service's own injected
                :class:`~tos_runtime.time.sources.MonotonicSource` — monotonic readings are
                comparable only within one source instance, so a caller injected with a
                different source has no meaningful argument to pass here.

        Returns:
            The mapped wall-clock time in epoch milliseconds, or ``None``.
        """
        issue_wall_ms = self.wall_clock_now()
        if issue_wall_ms is None or self._snapshot is None:
            return None
        # Annotated, not inferred: the snapshot field's own declared type is what this
        # arithmetic must be checked against (an inferred ``Any`` here would silently accept
        # a non-numeric mapping).
        issue_mono_ms: int | None = self._snapshot.issue_monotonic_value
        if issue_mono_ms is None:
            return None
        domain_floor_ms = self._cycle_previous_monotonic_ms
        suspension_ms = self._cycle_suspension_ms
        if domain_floor_ms is None or suspension_ms is None:
            return None
        if mono_ms < domain_floor_ms or mono_ms > issue_mono_ms:
            return None
        return issue_wall_ms - (issue_mono_ms - mono_ms) - suspension_ms
