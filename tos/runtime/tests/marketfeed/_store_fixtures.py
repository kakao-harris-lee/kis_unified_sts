"""Shared builders for ``tos_runtime.marketfeed.store`` tests.

Deliberately small — this is NOT the full ``tos.marketfeed`` authoring-evidence suite
(``tos/tests/marketfeed/_marketfeed_fixtures.py``, which this file mirrors the idiom of); it builds
just enough of a real, issuable :class:`~tos.capsule.CriticalInputSnapshot` +
:class:`~tos.marketfeed.RawPayloadPreimage` pair for
:class:`~tos_runtime.marketfeed.store.SqliteSnapshotStore`'s own tests to round-trip and publish
through the real kernel gate.
"""

from __future__ import annotations

from typing import Any

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule import CriticalInputSnapshot, FieldEvaluation, FieldState, Observation
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.capsule.consistency_cut import ConsistencyCut
from tos.capsule.observation import Admission, AdmissionResult, ObservationTime, RawRef
from tos.capsule.snapshot import SnapshotScope
from tos.engine import InstrumentKey
from tos.marketfeed import PreimageEntry, RawPayloadPreimage

#: The one canonicalization scheme this wave rides everywhere (matches
#: ``tos/tests/marketfeed/_marketfeed_fixtures.py``'s own ``SCHEME``).
SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

ACCOUNT = "acct-1"
INSTRUMENT = "ES"
OTHER_INSTRUMENT = "NQ"
DECISION_CLASS = "entry"
ENVIRONMENT = "non-live-test"

AS_OF_MS = 1_700_000_060_000

INSTRUMENT_KEY = InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)


def preimage(**tokens: Any) -> RawPayloadPreimage:
    """Build a raw-payload preimage from keyword field values."""
    return RawPayloadPreimage(
        entries=tuple(
            PreimageEntry(key=key, value=value) for key, value in tokens.items()
        )
    )


def payload_digest_of(payload: RawPayloadPreimage) -> str:
    """The digest the attributed observation must record for ``payload``."""
    return SCHEME.compute_digest(payload.as_mapping())


def observation(
    *,
    raw_event_id: str,
    payload: RawPayloadPreimage,
    as_of: int = AS_OF_MS,
    field_state: FieldState = FieldState.VALID,
) -> Observation:
    """An observation whose ``raw.payload_digest`` attests ``payload``."""
    return Observation(
        raw=RawRef(
            raw_event_id=raw_event_id, payload_digest=payload_digest_of(payload)
        ),
        time=ObservationTime(source_event_time=as_of),
        admission=Admission(result=AdmissionResult.ADMITTED),
        field_state=field_state,
    )


def issue_snapshot(
    *,
    observations: tuple[Observation, ...] = (),
    field_evaluations: tuple[FieldEvaluation, ...] = (),
    instruments: tuple[str, ...] = (INSTRUMENT,),
    **overrides: Any,
) -> CriticalInputSnapshot:
    """Issue a Critical Input Snapshot carrying the given observations/evaluations."""
    base: dict[str, Any] = {
        "issuer_principal_id": "iss-1",
        "critical_input_policy": PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        "scope": SnapshotScope(
            environment=ENVIRONMENT,
            accounts=(ACCOUNT,),
            instruments=instruments,
            decision_class=DECISION_CLASS,
        ),
        "intended_use": DECISION_CLASS,
        "consistency_cut": ConsistencyCut(cut_id="cut-1"),
        "observations": observations,
        "field_evaluations": field_evaluations,
    }
    base.update(overrides)
    return CriticalInputSnapshot.issue(scheme=SCHEME, **base)


def issue_capsule(
    snapshot: CriticalInputSnapshot, **overrides: Any
) -> DecisionContextCapsule:
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
    return DecisionContextCapsule.issue(scheme=SCHEME, **base)


def one_bar(
    *, as_of: int = AS_OF_MS, close: int = 4_512_500, raw_event_id: str = "raw-1"
) -> tuple[DecisionContextCapsule, CriticalInputSnapshot, RawPayloadPreimage]:
    """One bar: a snapshot covering one observation with a ``close`` field, plus its Capsule.

    Returns:
        ``(capsule, snapshot, payload)`` — the Capsule binds the snapshot exactly, and ``payload``
        is the preimage the snapshot's one observation attests.
    """
    payload = preimage(close=close)
    obs = observation(raw_event_id=raw_event_id, payload=payload, as_of=as_of)
    snapshot = issue_snapshot(
        observations=(obs,),
        field_evaluations=(FieldEvaluation(field_ref="close", state=FieldState.VALID),),
    )
    capsule = issue_capsule(snapshot)
    return capsule, snapshot, payload
