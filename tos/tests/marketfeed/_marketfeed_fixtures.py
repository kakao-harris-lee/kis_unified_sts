"""Shared builders for the ``tos.marketfeed`` authoring-evidence suite (design #32 §7).

Every builder is deterministic and clock-free: no ``time`` / ``datetime`` / ``random`` / ``uuid``
appears anywhere, including here, because the §7.1 canary scans the sources and the tests must not
model something the shipped package forbids.

The whole suite is **authoring evidence**, not acceptance: design #32 §1.1 declares the slice
provisional and closes no EV.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import (
    AdmissionResult,
    CriticalInputSnapshot,
    DecisionContextCapsule,
    FieldEvaluation,
    FieldState,
    Observation,
    TransformationLineage,
)
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.lineage import ParentRef
from tos.capsule.observation import Admission, ObservationTime, RawRef
from tos.capsule.snapshot import SnapshotScope
from tos.marketfeed import (
    AdmittedValue,
    MarketFeedIntegrityError,
    PreimageEntry,
    RawPayloadPreimage,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: A construction-time seal breach surfaces either as the marketfeed error itself (when raised from
#: a plain function) or wrapped by pydantic as a ``ValidationError`` (when raised from a validator).
#: Both mean "unconstructable", which is the property under test — the shipped ``tos.backtest``
#: suite's ``INTEGRITY_ERRORS`` precedent.
INTEGRITY_ERRORS = (MarketFeedIntegrityError, ValidationError)

ACCOUNT = "acct-1"
INSTRUMENT = "ES"
DECISION_CLASS = "entry"
ENVIRONMENT = "non-live-test"

#: Two bar coordinates, distinct by construction (design #32 §4.1 — distinct as-of per bar).
BAR_ONE_AS_OF = 1_700_000_060_000
BAR_TWO_AS_OF = 1_700_000_120_000

#: The exposed numeric form is an **integer** in minor/tick units (design #32 §2.5), never a float.
CLOSE_BAR_ONE = 4_512_500
CLOSE_BAR_TWO = 4_513_000


def preimage(**tokens: Any) -> RawPayloadPreimage:
    """Build a raw-payload preimage from keyword field values (order-independent by construction)."""
    return RawPayloadPreimage(
        entries=tuple(PreimageEntry(key=key, value=value) for key, value in tokens.items())
    )


def payload_digest_of(payload: RawPayloadPreimage) -> str:
    """The digest the attributed observation must record for ``payload`` (design #32 §2.3)."""
    return SCHEME.compute_digest(payload.as_mapping())


def observation(
    *,
    raw_event_id: str,
    payload: RawPayloadPreimage,
    as_of: int,
    admission: AdmissionResult = AdmissionResult.ADMITTED,
    field_state: FieldState = FieldState.VALID,
    payload_digest: str | None = None,
) -> Observation:
    """An observation whose ``raw.payload_digest`` attests ``payload`` unless overridden."""
    return Observation(
        raw=RawRef(
            raw_event_id=raw_event_id,
            payload_digest=(
                payload_digest if payload_digest is not None else payload_digest_of(payload)
            ),
        ),
        time=ObservationTime(source_event_time=as_of),
        admission=Admission(result=admission),
        field_state=field_state,
    )


def evaluation(
    field_ref: str, state: FieldState = FieldState.VALID, *, blocking: bool = True
) -> FieldEvaluation:
    """A field evaluation naming ``field_ref`` — the snapshot governance a value must ride."""
    return FieldEvaluation(field_ref=field_ref, state=state, blocking=blocking)


def lineage_node(
    *,
    output_id: str,
    parents: tuple[str, ...],
    reproducible: bool = True,
    field_state: FieldState = FieldState.VALID,
) -> TransformationLineage:
    """A transformation-lineage node with exact, digest-bound parents (design #32 §5.2)."""
    return TransformationLineage(
        output_id=output_id,
        parents=tuple(
            ParentRef(parent_id=parent, digest=f"digest-of-{parent}") for parent in parents
        ),
        reproducible=reproducible,
        field_state=field_state,
    )


def issue_snapshot(
    *,
    observations: tuple[Observation, ...] = (),
    field_evaluations: tuple[FieldEvaluation, ...] = (),
    transformation_lineage: tuple[TransformationLineage, ...] = (),
    **overrides: Any,
) -> CriticalInputSnapshot:
    """Issue a Critical Input Snapshot carrying the given observations/evaluations/lineage."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "scope": SnapshotScope(
            environment=ENVIRONMENT,
            accounts=(ACCOUNT,),
            instruments=(INSTRUMENT,),
            decision_class=DECISION_CLASS,
        ),
        "intended_use": DECISION_CLASS,
        "consistency_cut": ConsistencyCut(cut_id="cut-1"),
        "observations": observations,
        "field_evaluations": field_evaluations,
        "transformation_lineage": transformation_lineage,
    }
    base.update(overrides)
    return CriticalInputSnapshot.issue(scheme=SCHEME, **base)  # type: ignore[return-value]


def issue_capsule(snapshot: CriticalInputSnapshot, **overrides: Any) -> DecisionContextCapsule:
    """Issue a Capsule whose ``SnapshotRef`` binds ``snapshot`` exactly."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "critical_input_snapshot": SnapshotRef(
            snapshot_id=snapshot.snapshot_id, canonical_digest=snapshot.canonical_digest
        ),
        "scope": CapsuleScope(
            environment=ENVIRONMENT,
            account=ACCOUNT,
            instrument=INSTRUMENT,
            decision_class=DECISION_CLASS,
        ),
        "safety_critical_facts": SafetyCriticalFacts(
            account=ACCOUNT,
            instrument=INSTRUMENT,
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    }
    base.update(overrides)
    return DecisionContextCapsule.issue(scheme=SCHEME, **base)  # type: ignore[return-value]


def candidate(field_key: str, observation_ref: str, payload: RawPayloadPreimage) -> AdmittedValue:
    """One producer-supplied candidate claim."""
    return AdmittedValue(
        field_key=field_key, observation_ref=observation_ref, preimage=payload
    )


def one_bar(
    *,
    as_of: int = BAR_ONE_AS_OF,
    close: int = CLOSE_BAR_ONE,
    raw_event_id: str = "raw-1",
    session: str = "REGULAR",
) -> tuple[DecisionContextCapsule, CriticalInputSnapshot, tuple[AdmittedValue, ...]]:
    """The canonical happy path: one bar, two admitted values (``close`` + ``session``).

    Returns:
        ``(capsule, snapshot, candidates)`` — the Capsule binds the snapshot exactly, and both
        candidates pass every gate.
    """
    payload = preimage(close=close, session=session)
    obs = observation(raw_event_id=raw_event_id, payload=payload, as_of=as_of)
    snapshot = issue_snapshot(
        observations=(obs,),
        field_evaluations=(evaluation("close"), evaluation("session")),
    )
    capsule = issue_capsule(snapshot)
    candidates = (
        candidate("close", raw_event_id, payload),
        candidate("session", raw_event_id, payload),
    )
    return capsule, snapshot, candidates
