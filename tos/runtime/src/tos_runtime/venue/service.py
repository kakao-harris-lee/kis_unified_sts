"""tos_runtime.venue.service — ``VenueConstraintService`` (snapshot + decision issuance)."""

from __future__ import annotations

from collections.abc import Callable

from tos.canonical import CanonicalizationScheme
from tos.egressgw import fold_venue_admissibility
from tos.ioc import CanonicalBrokerCommand
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderAdmissibilityResult,
    OrderShapeFields,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
    order_shape_admissible,
    session_phase_admits,
)

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.venue.band_source import BandObservation, BandReader
from tos_runtime.venue.config import LoadedOrderConstructionPolicy, LoadedVenuePolicy

__all__ = [
    "VENUE_POLICY_BOUND_KIND",
    "ORDER_CONSTRUCTION_POLICY_BOUND_KIND",
    "VENUE_SNAPSHOT_ISSUED_KIND",
    "ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND",
    "VenueConstraintService",
    "record_order_construction_policy_bound",
]

VENUE_POLICY_BOUND_KIND = "VENUE_POLICY_BOUND"
ORDER_CONSTRUCTION_POLICY_BOUND_KIND = "ORDER_CONSTRUCTION_POLICY_BOUND"
VENUE_SNAPSHOT_ISSUED_KIND = "VENUE_SNAPSHOT_ISSUED"
ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND = "ORDER_ADMISSIBILITY_DECISION_ISSUED"

_SNAPSHOT_ABSENT_FIELD_NAMES: tuple[str, ...] = (
    "critical_input_snapshot_digest",
    "source_continuity_id",
    "max_age",
)


def record_order_construction_policy_bound(
    evidence_store: SqliteEvidenceStore,
    loaded_ocp: LoadedOrderConstructionPolicy,
    activated_member_digest: str,
) -> None:
    """Record ``ORDER_CONSTRUCTION_POLICY_BOUND`` once, at boot (plan §2"""
    evidence_store.append(
        {
            "policy_id": loaded_ocp.policy.policy_id,
            "policy_generation": loaded_ocp.policy.policy_generation,
            "canonical_digest": loaded_ocp.policy.canonical_digest,
            "activated_member_digest": activated_member_digest,
            "wire_codec_kind": loaded_ocp.wire_codec_kind,
        },
        kind=ORDER_CONSTRUCTION_POLICY_BOUND_KIND,
        record_class=ORDER_CONSTRUCTION_POLICY_BOUND_KIND,
    )


def _policy_bound_payload(
    loaded_policy: LoadedVenuePolicy, activated_member_digest: str
) -> dict[str, object]:
    """The one boot-time ``VENUE_POLICY_BOUND`` row (plan §2 decision 8)."""
    payload: dict[str, object] = {
        "policy_id": loaded_policy.policy.policy_id,
        "policy_generation": loaded_policy.policy.policy_generation,
        "canonical_digest": loaded_policy.policy.canonical_digest,
        "activated_member_digest": activated_member_digest,
        "null_shape_bounds": list(loaded_policy.null_shape_bounds),
    }
    if loaded_policy.band_source is not None:
        payload["band_source_digest"] = loaded_policy.band_source_digest
        payload["price_scale"] = loaded_policy.price_scale
    return payload


def _count_prior_rows(evidence_store: SqliteEvidenceStore, kind: str) -> int:
    """The durable count of pre-existing evidence rows of ``kind`` — the"""
    row = evidence_store.connection.execute(
        "SELECT COUNT(*) FROM entries WHERE kind = ?", (kind,)
    ).fetchone()
    return 0 if row is None else int(row[0])


class VenueConstraintService:
    """The runtime owner of ``VenueConstraintSnapshot`` /"""

    def __init__(
        self,
        *,
        loaded_policy: LoadedVenuePolicy,
        scheme: CanonicalizationScheme,
        session_phase_reader: Callable[[], str | None],
        tick_generation_reader: Callable[[], int | None],
        evidence_store: SqliteEvidenceStore,
        environment_label: str,
        route_fields: InstrumentRouteFields,
        broker_capability_profile_version: str | None,
        broker_capability_profile_digest: str | None,
        activated_member_digest: str,
        band_reader: BandReader | None = None,
        trading_date_reader: Callable[[], str | None] | None = None,
    ) -> None:
        """Construct the service and record its one boot-time"""
        self.policy: VenueConstraintPolicy = loaded_policy.policy
        self.quantity_constraint = loaded_policy.quantity_constraint
        self._adopt_band_source(loaded_policy, band_reader, trading_date_reader)
        self._scheme = scheme
        self._session_phase_reader = session_phase_reader
        self._tick_generation_reader = tick_generation_reader
        self._evidence_store = evidence_store
        self._environment_label = environment_label
        self._route_fields = route_fields
        self._broker_capability_profile_version = broker_capability_profile_version
        self._broker_capability_profile_digest = broker_capability_profile_digest

        self._snapshot_generation_base = _count_prior_rows(
            evidence_store, VENUE_SNAPSHOT_ISSUED_KIND
        )
        self._decision_generation_base = _count_prior_rows(
            evidence_store, ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND
        )
        self._snapshot_issue_count = 0
        self._decision_issue_count = 0
        self._cached_tick_generation: int | None = None

        self.last_snapshot: VenueConstraintSnapshot | None = None
        self.last_decision: OrderAdmissibilityDecision | None = None

        evidence_store.append(
            _policy_bound_payload(loaded_policy, activated_member_digest),
            kind=VENUE_POLICY_BOUND_KIND,
            record_class=VENUE_POLICY_BOUND_KIND,
        )

        self._read_band("boot")

    def _adopt_band_source(
        self,
        loaded_policy: LoadedVenuePolicy,
        band_reader: BandReader | None,
        trading_date_reader: Callable[[], str | None] | None,
    ) -> None:
        """Set up this service's band state (module docstring's "the declared band source")."""
        self._policy_shape_constraints: VenueShapeConstraints = (
            loaded_policy.policy.shape_constraints
        )
        self._effective_shape_constraints: VenueShapeConstraints = (
            self._policy_shape_constraints
        )
        self._band_source_declared = loaded_policy.band_source is not None
        self._band_read_on: tuple[str, ...] = (
            ()
            if loaded_policy.band_source is None
            else loaded_policy.band_source.read_on
        )
        self._band_reader = band_reader
        self._trading_date_reader = trading_date_reader
        self._band: BandObservation | None = None
        self._boot_band_read_owed = False

    @property
    def shape_constraints(self) -> VenueShapeConstraints:
        """The EFFECTIVE shape constraints — the policy's own, with ``price_min``/``price_max``"""
        return self._effective_shape_constraints

    def snapshot(self) -> VenueConstraintSnapshot:
        """The current tick generation's ``VenueConstraintSnapshot`` — issued"""
        generation = self._tick_generation_reader()
        band_transition = self._enforce_trading_date_bond()
        if (
            not band_transition
            and self.last_snapshot is not None
            and generation == self._cached_tick_generation
        ):
            return self.last_snapshot
        phase = self._session_phase_reader()
        phase_changed = (
            self.last_snapshot is None
            or self.last_snapshot.observed_session_phase != phase
        )
        if phase_changed and self.last_snapshot is not None:
            self._read_band("phase_change")
        elif self.last_snapshot is None and self._boot_band_read_owed:
            self._read_band("boot")
        if self.last_snapshot is None:
            self._boot_band_read_owed = False
        if not band_transition and not phase_changed:
            assert self.last_snapshot is not None
            self._cached_tick_generation = generation
            return self.last_snapshot
        return self._issue_snapshot(phase, generation)

    def _enforce_trading_date_bond(self) -> bool:
        """Drop a held band whose trading date is not the current one (plan §4.4a)."""
        if self._band is None:
            return False
        current = (
            None if self._trading_date_reader is None else self._trading_date_reader()
        )
        if current is not None and current == self._band.trading_date:
            return False
        self._set_band(None)
        return True

    def _read_band(self, instant: str) -> None:
        """Read the declared band source once, if ``instant`` is one the policy declared."""
        if self._band_reader is None or instant not in self._band_read_on:
            return
        self._set_band(self._band_reader())
        if instant == "boot":
            self._boot_band_read_owed = self._band is None

    def _set_band(self, band: BandObservation | None) -> None:
        self._band = band
        self._effective_shape_constraints = (
            self._policy_shape_constraints
            if band is None
            else self._policy_shape_constraints.model_copy(
                update={"price_min": band.price_min, "price_max": band.price_max}
            )
        )

    def _issue_snapshot(
        self, phase: str | None, generation: int | None
    ) -> VenueConstraintSnapshot:
        self._snapshot_issue_count += 1
        constraint_generation = (
            self._snapshot_generation_base + self._snapshot_issue_count
        )
        snapshot_id = f"vsnap-{self._environment_label}-{constraint_generation}"
        band = self._band
        snapshot = VenueConstraintSnapshot.issue(
            scheme=self._scheme,
            snapshot_id=snapshot_id,
            constraint_generation=constraint_generation,
            policy_id=self.policy.policy_id,
            policy_generation=self.policy.policy_generation,
            policy_digest=self.policy.canonical_digest,
            observed_session_phase=phase,
            action_tradability=(),
            critical_input_snapshot_digest=(
                None if band is None else band.record_digest
            ),
            source_continuity_id=(None if band is None else band.source_continuity_id),
            max_age=(None if band is None else f"trading_date_kst:{band.trading_date}"),
        )
        assert isinstance(snapshot, VenueConstraintSnapshot)
        absent_fields = [
            name
            for name in _SNAPSHOT_ABSENT_FIELD_NAMES
            if getattr(snapshot, name) is None
        ]
        payload: dict[str, object] = {
            "snapshot_id": snapshot.snapshot_id,
            "canonical_digest": snapshot.canonical_digest,
            "constraint_generation": snapshot.constraint_generation,
            "observed_session_phase": snapshot.observed_session_phase,
            "policy_digest": snapshot.policy_digest,
            "absent_fields": absent_fields,
        }
        if self._band_source_declared:
            payload["band_digest"] = None if band is None else band.record_digest
            payload["critical_input_snapshot_digest_role"] = "stand-in"
        self._evidence_store.append(
            payload,
            kind=VENUE_SNAPSHOT_ISSUED_KIND,
            record_class=VENUE_SNAPSHOT_ISSUED_KIND,
        )
        self.last_snapshot = snapshot
        self._cached_tick_generation = generation
        return snapshot

    def decide(
        self,
        *,
        action_class: ActionClass,
        shape: OrderShapeFields | None,
        candidate_command: CanonicalBrokerCommand | None,
    ) -> OrderAdmissibilityDecision:
        """Issue one ``OrderAdmissibilityDecision`` for ``action_class`` /"""
        snapshot = self.snapshot()
        phase_result = session_phase_admits(
            snapshot.observed_session_phase, action_class, snapshot, self.policy
        )
        shape_result = order_shape_admissible(shape, self.shape_constraints)
        result = fold_venue_admissibility(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=action_class,
            snapshot=snapshot,
            policy=self.policy,
            shape=shape,
            constraints=self.shape_constraints,
        )
        failed_predicates, unknown_predicates = _classify_sub_results(
            session_phase_admits=phase_result, order_shape_admissible=shape_result
        )

        self._decision_issue_count += 1
        decision_generation = (
            self._decision_generation_base + self._decision_issue_count
        )
        decision_id = f"vdec-{self._environment_label}-{decision_generation}"
        candidate_command_id = (
            None if candidate_command is None else candidate_command.command_id
        )
        candidate_command_digest = (
            None if candidate_command is None else candidate_command.canonical_digest
        )

        decision = OrderAdmissibilityDecision.issue(
            scheme=self._scheme,
            decision_id=decision_id,
            decision_generation=decision_generation,
            constraint_generation=snapshot.constraint_generation,
            policy_id=self.policy.policy_id,
            policy_generation=self.policy.policy_generation,
            policy_digest=self.policy.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            snapshot_digest=snapshot.canonical_digest,
            decision_context_capsule_id=None,
            decision_context_capsule_digest=None,
            candidate_command_id=candidate_command_id,
            candidate_command_digest=candidate_command_digest,
            broker_capability_profile_version=self._broker_capability_profile_version,
            broker_capability_profile_digest=self._broker_capability_profile_digest,
            bound_instrument_route=self._route_fields,
            action_class=action_class,
            observed_session_phase=snapshot.observed_session_phase,
            result=result,
            failed_predicates=failed_predicates,
            unknown_predicates=unknown_predicates,
        )
        assert isinstance(decision, OrderAdmissibilityDecision)
        self._evidence_store.append(
            {
                "decision_id": decision.decision_id,
                "canonical_digest": decision.canonical_digest,
                "result": result.value,
                "failed_predicates": list(failed_predicates),
                "unknown_predicates": list(unknown_predicates),
                "candidate_command_digest": candidate_command_digest,
                "snapshot_id": snapshot.snapshot_id,
            },
            kind=ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
            record_class=ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND,
        )
        self.last_decision = decision
        return decision


def _classify_sub_results(
    *,
    session_phase_admits: OrderAdmissibilityResult,
    order_shape_admissible: OrderAdmissibilityResult,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Names of the two sub-predicates that failed / were unknown — never a"""
    failed: list[str] = []
    unknown: list[str] = []
    for name, sub_result in (
        ("session_phase_admits", session_phase_admits),
        ("order_shape_admissible", order_shape_admissible),
    ):
        if sub_result in (
            OrderAdmissibilityResult.INADMISSIBLE,
            OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY,
        ):
            failed.append(name)
        elif sub_result is OrderAdmissibilityResult.UNKNOWN:
            unknown.append(name)
    return tuple(failed), tuple(unknown)
