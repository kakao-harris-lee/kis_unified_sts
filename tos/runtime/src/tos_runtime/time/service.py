"""``TrustworthyTimeService`` — Phase 2 runtime composition of the ``tos.time``"""

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
from tos_runtime.time.judged_content import judged_content
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
_WALL_CLOCK_EXPOSED_KIND = "TIME_WALL_CLOCK_EXPOSED"
_WALL_CLOCK_EXPOSED_RECORD_CLASS = "TIME_WALL_CLOCK_EXPOSED"


class TimeServiceNotStarted(RuntimeError):
    """Raised when a method requiring ``start()`` is called before it, or"""


class RecoveryGenerationNotAdvanced(RuntimeError):
    """Raised when a recovery out of ``UNTRUSTED`` would not carry a strictly"""


class TimeSnapshotReader(Protocol):
    """The narrow read surface most :class:`TrustworthyTimeService` consumers actually need —"""

    def current_snapshot(self) -> TimeHealthSnapshot:
        """Return the current :class:`~tos.time.TimeHealthSnapshot` (raises"""
        ...


class TimeHealthReader(Protocol):
    """The narrower read surface :class:`~tos_runtime.posttrade.release_consumer"""

    @property
    def health_state(self) -> HealthState:
        """The service's current :class:`~tos.time.HealthState`."""
        ...


class TrustworthyTimeService:
    """Composition root for one process's Trustworthy Time health-check cycle."""

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
        self._wall_clock_exposed = False
        self._previous_monotonic_ms: int | None = None
        self._previous_wall_clock_unix_ms: int | None = None
        self._cycle_previous_monotonic_ms: int | None = None
        self._cycle_suspension_ms: int | None = None
        self._evidenced_content: dict[str, Any] | None = None
        self._evidenced_monotonic_ms: int | None = None

    @property
    def health_state(self) -> HealthState:
        """The last successfully-applied ``HealthState`` (never a refused one)."""
        return self._health_state

    @property
    def last_transition_reason(self) -> str | None:
        """Why the most recent ``evaluate()`` did not change state, or ``None``"""
        return self._last_transition_reason

    def start(self) -> None:
        """Issue this process's ``TimeContinuityIdentity`` anchor + generation 0,"""
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
        """Return the most recently evaluated + durably-evidenced snapshot."""
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
        """Propose a conservative next state (validated + possibly refused by"""
        if from_state is HealthState.UNINITIALIZED:
            return HealthState.SYNCHRONIZING
        if from_state is HealthState.UNTRUSTED:
            return HealthState.SYNCHRONIZING
        if not anchor_ok:
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
        """Kernel ``anchor_valid`` call: is ``anchor`` still continuous at ``now_ms``?"""
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
        """This cycle's observed process-suspension magnitude (team-lead"""
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
        """Read every injected reference source; return the kernel-shaped"""
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
        """Fold every kernel predicate this cycle's observations feed into the"""
        reachable = reachable_count > 0
        reference_count = (
            independent_reference_count(kernel_sources) if reachable else 0
        )

        disagreement_ms: int | None = 0 if reachable_count == 1 else None
        disagreement_ok = source_disagreement_within_bound(
            disagreement_ms, self._config.max_time_source_disagreement_ms
        )

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
        """Propose + gate one FSM transition (never applied if the kernel"""
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
        """Advance the anchor's high-water mark forward when it held valid"""
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

    def _re_establishes_freshness(self, now_ms: int) -> bool:
        """Whether this cycle is the one that makes an AGED-OUT exposed reading fresh again."""
        previous = self._snapshot
        if previous is None:
            return False
        issued = previous.issue_monotonic_value
        if issued is None:
            return True
        age_ms = now_ms - issued
        return (
            age_ms < 0 or age_ms > self._config.max_time_conservative_freshness_age_ms
        )

    def _snapshot_evidence_due(self, judged: Mapping[str, Any], now_ms: int) -> bool:
        """Whether this cycle's ``TIME_HEALTH_SNAPSHOT`` row must be appended: the judged"""
        if self._evidenced_content is None or judged != self._evidenced_content:
            return True
        if self._re_establishes_freshness(now_ms):
            return True
        last_ms = self._evidenced_monotonic_ms
        if last_ms is None or now_ms < last_ms:
            return True
        return now_ms - last_ms >= self._config.time_health_snapshot_heartbeat_ms

    def _announce_wall_clock_exposed(
        self, snapshot: TimeHealthSnapshot, wall_clock_observation: int
    ) -> None:
        """G-1 taking-effect announcement (runtime operations wiring plan §2 decision 8):"""
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
        """Run one health-check cycle: read sources, call kernel predicates,"""
        generation, anchor = self._require_started()
        now_ms = self._monotonic.now_ms()
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
        judged = judged_content(payload, reason)
        announce_ms: int | None = (
            wall_clock_observation
            if applied_state is HealthState.TRUSTED and not self._wall_clock_exposed
            else None
        )
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
        self._previous_monotonic_ms = now_ms
        self._previous_wall_clock_unix_ms = wall_clock_observation
        self._capture_cycle(previous_monotonic_ms, suspension_ms)
        return snapshot

    def _capture_cycle(
        self, previous_monotonic_ms: int | None, suspension_ms: int | None
    ) -> None:
        """Record the two facts :meth:`wall_clock_at_monotonic` needs about the cycle that"""
        self._cycle_previous_monotonic_ms = previous_monotonic_ms
        self._cycle_suspension_ms = suspension_ms

    def wall_clock_now(self) -> int | None:
        """The current wall-clock reading, or ``None`` (G-1, runtime"""
        if self._health_state is not HealthState.TRUSTED or self._snapshot is None:
            return None
        return self._snapshot.wall_clock_observation

    def wall_clock_now_if_fresh(self, max_age_ms: int) -> int | None:
        """:meth:`wall_clock_now`, but only while the snapshot it comes from is at most"""
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
        """The wall-clock time that a PAST monotonic instant of this process corresponds to,"""
        issue_wall_ms = self.wall_clock_now()
        if issue_wall_ms is None or self._snapshot is None:
            return None
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
