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
"""

from __future__ import annotations

from collections.abc import Sequence

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
    "TimeServiceNotStarted",
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

    def _anchor_ok(self, anchor: TimeContinuityIdentity, now_ms: int) -> bool:
        """Kernel ``anchor_valid`` call: is ``anchor`` still continuous at ``now_ms``?

        ``suspension_ms=0`` here is a **known, documented literal**, not an
        observed value (survey ``scratchpad/ep-survey-wiring.md` §1b`` and
        runtime operations wiring plan §2 decision 2's own parenthetical
        anticipated exactly this finding). It is deliberately left
        UNCHANGED by this wave: replacing it with the honest per-cycle
        observation (:meth:`_observed_suspension_ms`, which is ``None``
        whenever ``expected_evaluate_cadence_ms`` is unset — the config
        state of every shipped example and, as surveyed, every existing test
        fixture across this distribution) makes kernel ``anchor_valid``
        return ``False`` unconditionally (``tos/src/tos/time/predicates.py``
        :143-145: ``suspension_ms is None`` => invalid), which makes
        ``HealthState.TRUSTED`` permanently unreachable anywhere this literal
        currently lets it be reached — including the ~30 ``_reach_trusted()``
        call sites across ``tests/compose/test_compose_root.py`` and every
        downstream compose e2e file (owned by other lanes/shared infra, not
        this lane), plus this lane's own ``tests/time/test_service.py`` /
        ``tests/authority/*`` TRUSTED-reaching tests. This is a real,
        confirmed finding (not a guess) reported back to the team lead rather
        than applied unilaterally, since fixing the fallout crosses lane
        ownership boundaries and only a real ``expected_evaluate_cadence_ms``
        value (still named-TBD, plan §6 confirmation point ②) resolves it
        honestly. Decision 2's OTHER half — exposing the observation on the
        issued snapshot's ``suspension_status`` when a cadence IS configured
        — is implemented below (:meth:`_observed_suspension_ms`,
        :meth:`evaluate`) and does not touch this literal.
        """
        continuity_now = anchor.model_copy(update={"monotonic_anchor_value": now_ms})
        return anchor_valid(
            continuity_now,
            anchor,
            suspension_ms=0,
            max_suspension_ms=self._config.max_process_suspension_ms,
        )

    def _observed_suspension_ms(
        self, anchor: TimeContinuityIdentity, now_ms: int
    ) -> tuple[bool, int | None]:
        """Compute this cycle's ``(suspended, suspension_ms)`` observation for
        the issued snapshot's ``suspension_status`` (G-1, runtime operations
        wiring plan §2 decision 2) — independent of :meth:`_anchor_ok`'s own
        (unchanged, see its docstring) literal.

        Returns ``(False, None)`` unchanged — the kernel default, exactly as
        before this method existed — whenever
        ``expected_evaluate_cadence_ms`` is unset (``None``). When set, the
        elapsed monotonic gap since the anchor's last-ratcheted value is
        compared against the configured cadence:
        ``suspension_ms = max(0, elapsed - cadence)``, and ``suspended`` is
        whether the RAW elapsed gap itself exceeds
        ``max_process_suspension_ms`` (an absolute bound, independent of the
        cadence-relative magnitude).
        """
        cadence = self._config.expected_evaluate_cadence_ms
        if cadence is None:
            return False, None
        anchor_value = anchor.monotonic_anchor_value or now_ms
        elapsed = max(0, now_ms - anchor_value)
        suspension_ms = max(0, elapsed - cadence)
        suspended = elapsed > self._config.max_process_suspension_ms
        return suspended, suspension_ms

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
        # DigestBoundArtifact.issue() is annotated to return the BASE class
        # (no Self/TypeVar — tos/src/tos/canonical/_base.py:232), even though
        # at runtime a classmethod call always binds `cls` to the class it was
        # called on (TimeHealthSnapshot here). The isinstance check below
        # narrows the static type to match that real runtime behavior; it is
        # not a suppression — it will always hold, and mypy would flag a
        # regression if TimeHealthSnapshot.issue ever stopped constructing a
        # TimeHealthSnapshot.
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
        assert isinstance(snapshot, TimeHealthSnapshot)
        return snapshot

    def evaluate(self) -> TimeHealthSnapshot:
        """Run one health-check cycle: read sources, call kernel predicates,
        derive the next state, issue + durably evidence a snapshot, and only
        then expose it.

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

        anchor_ok = self._anchor_ok(anchor, now_ms)
        kernel_sources, reachable_count, wall_clock_observation = (
            self._read_reference_sources()
        )
        required_ok = self._required_ok(anchor_ok, kernel_sources, reachable_count)
        suspended, suspension_ms = self._observed_suspension_ms(anchor, now_ms)

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

        # "영수증 없으면 일어나지 않았다" — durable commit BEFORE any of the
        # state below becomes observable. If this raises, nothing past this
        # point executes: no state/anchor/generation mutation, no snapshot
        # exposed via current_snapshot().
        self._evidence.append(
            snapshot.model_dump(mode="json"),
            kind=_SNAPSHOT_KIND,
            record_class=_SNAPSHOT_RECORD_CLASS,
        )

        # G-1 taking-effect announcement (runtime operations wiring plan §2
        # decision 8): exactly once per service instance, the first time a
        # TRUSTED snapshot carries a real wall-clock observation. A SEPARATE
        # evidence append from the snapshot's own row above — ordered after
        # it, per the same "receipt before observable state" discipline (if
        # THIS append raises, the snapshot itself was already durably
        # committed and IS exposed; only the exposure flag below would not
        # yet be set, so a retry-from-caller would correctly re-attempt this
        # announcement on the next evaluate() rather than silently losing it).
        if (
            applied_state is HealthState.TRUSTED
            and wall_clock_observation is not None
            and not self._wall_clock_exposed
        ):
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

        if commit_generation != generation.current:
            generation.next()
        self._anchor = next_anchor
        self._health_state = applied_state
        self._last_transition_reason = reason
        self._snapshot = snapshot
        return snapshot

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
