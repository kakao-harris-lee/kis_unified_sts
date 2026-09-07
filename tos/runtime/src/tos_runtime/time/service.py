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
    TimeContinuityIdentity,
    TimeHealthSnapshot,
    anchor_valid,
    freshness_verdict,
    health_transition_allowed,
    independent_reference_count,
    recovery_generation_revives_nothing,
    snapshot_age_admissible,
    source_disagreement_within_bound,
    transition_to_trusted_requires_new_generation,
)
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.generation import GenerationCounter
from tos_runtime.time.sources import MonotonicSource, ReferenceSourceReader

__all__ = ["TimeServiceNotStarted", "TrustworthyTimeService"]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_STARTUP_KIND = "TIME_SERVICE_STARTUP"
_STARTUP_RECORD_CLASS = "TIME_STARTUP"
_SNAPSHOT_KIND = "TIME_HEALTH_SNAPSHOT"
_SNAPSHOT_RECORD_CLASS = "TIME_HEALTH_SNAPSHOT"


class TimeServiceNotStarted(RuntimeError):
    """Raised when a method requiring ``start()`` is called before it, or
    ``start()`` is called twice on the same service instance."""


class TrustworthyTimeService:
    """Composition root for one process's Trustworthy Time health-check cycle.

    Args:
        monotonic: The injected monotonic-clock port.
        references: The injected reference-source ports (Phase 2 wires exactly
            one — :class:`~tos_runtime.time.sources.LocalSystemClockReader` —
            but the service accepts a sequence so a later profile can add a
            second independent source without a service-shape change).
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
        """Kernel ``anchor_valid`` call: is ``anchor`` still continuous at ``now_ms``?"""
        continuity_now = anchor.model_copy(update={"monotonic_anchor_value": now_ms})
        return anchor_valid(
            continuity_now,
            anchor,
            suspension_ms=0,
            max_suspension_ms=self._config.max_process_suspension_ms,
        )

    def _read_reference_sources(self) -> tuple[tuple[ReferenceSource, ...], bool]:
        """Read every injected reference source; return the kernel-shaped
        records plus whether at least one is reachable+healthy this cycle."""
        observations = [reader.read() for reader in self._references]
        reachable = any(obs.reachable and obs.healthy for obs in observations)
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
        return kernel_sources, reachable

    def _required_ok(
        self,
        anchor_ok: bool,
        kernel_sources: tuple[ReferenceSource, ...],
        reachable: bool,
    ) -> bool:
        """Fold every kernel predicate this cycle's observations feed into the
        single "may this be TRUSTED" gate (fault contracts ⑥/⑦)."""
        reference_count = (
            independent_reference_count(kernel_sources) if reachable else 0
        )

        # Phase 2 wires at most one physical reader (module docstring residual
        # note): with zero or one reachable source there is nothing to disagree
        # with, so the disagreement observation is trivially 0; an unreachable
        # source reports no disagreement observation at all (None -> UNKNOWN,
        # fail-closed, never silently "in bound").
        disagreement_ms = 0 if reachable else None
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
            assert recovery_generation_revives_nothing(
                invalidated_under_generation=generation.current,
                new_generation=generation.current,
            )
            next_anchor = self._build_anchor(now_ms, generation.current)
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
        kernel_sources, reachable = self._read_reference_sources()
        required_ok = self._required_ok(anchor_ok, kernel_sources, reachable)

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

        if commit_generation != generation.current:
            generation.next()
        self._anchor = next_anchor
        self._health_state = applied_state
        self._last_transition_reason = reason
        self._snapshot = snapshot
        return snapshot
