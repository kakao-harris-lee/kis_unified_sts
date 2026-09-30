"""``tos_runtime.marketfeed.snapshot`` — the Critical Input Snapshot issuer (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decisions 2/3/5).

:class:`SnapshotIssuer` turns one :class:`~tos_runtime.marketfeed.ports.RawObservation` into one
kernel-issued :class:`~tos.capsule.CriticalInputSnapshot` — **one observation, one snapshot**
(design #32 §4.1 distinct-as-of-per-bar; this is what makes a distinct as-of yield a distinct
snapshot digest, so per-observation distinctness — the obligation
``tos/tests/marketfeed/test_marketfeed_cis_port.py:46-49`` leaves upstream — is discharged by
construction rather than by a separate check). It never stamps ``FieldState.VALID``: every
declared field's state is **derived** from the loaded :class:`~tos_runtime.marketfeed.policy
.LoadedCriticalInputPolicy` (plan §2 decision 2) — see :func:`_derive_field_state`.

**No transformation lineage.** This wave ships direct observations only (plan §1 비범위 — derived/
indicator values need :class:`~tos.capsule.TransformationLineage` + parent causality, a separate
design). A value with no lineage node inherits ``VALID`` from the kernel's own lineage gate
(``tos/src/tos/marketfeed/value.py:309-311`` — "a value with no lineage node is a *direct*
observation... there is no derivation to be unreproducible about"), which is exactly the shape a
direct observation has, so this module constructs no :class:`~tos.capsule.TransformationLineage`
node at all.

**Correction 1 (team-lead review of the initial cut) — ``Observation.field_state`` must not
aggregate per-field verdicts.** The first cut set ``Observation.field_state = worst(over every
declared field's FieldEvaluation)``. That double-counts: ``tos/src/tos/marketfeed/value.py:216-230``
(``value_field_state``) already folds the snapshot's own ``field_evaluations`` in *per matching
field_ref*, and separately folds ``observation.field_state`` in for **every** field key regardless
of which one it was "about". A per-field verdict placed on the observation therefore counted twice
against its own key and once, wrongly, against every other key. Reproduced against the real kernel
gate: policy declares ``close`` + ``session``; payload carries only a fresh ``close``. With the
aggregating cut, ``observation.field_state`` came out ``UNKNOWN`` (because ``session`` was absent),
which then dragged ``close`` down too — ``publish_context_value_view`` returned
``EXPLICIT_EMPTY`` with ``close`` itself rejected ``FIELD_STATE_NOT_VALID``, even though ``close``
was individually fresh and valid. Any deployment whose policy declares more keys than a given
payload happens to carry would silently publish an empty value surface. Fixed:
:func:`_derive_observation_state` computes ``field_state``/``admission.result`` from
**observation-level** facts only — is the record well-formed (instrument concrete, payload
non-empty) — never from per-field presence or freshness; those stay exactly where the kernel folds
them, in ``field_evaluations``. (``as_of_ms`` is always concrete — ``RawObservation.as_of_ms: int``,
not ``int | None`` — and the payload digest is always computable by the time this function runs,
since an un-computable preimage would already have raised at :class:`~tos.marketfeed
.RawPayloadPreimage` construction, so neither needs an explicit re-check here.) Declared-but-absent
keys still get their own ``FieldEvaluation(state=UNKNOWN)`` (see :func:`_derive_field_state`) — a
deliberate decision, not a leftover: with the aggregation removed, an absent key's ``UNKNOWN`` now
affects only that key's own gate, which is informative (a future evidence row can see *why* that
one field was dropped) and no longer contaminates the record-level verdict.

**Correction 2 (team-lead review) — ``Observation.mapping``'s unit/scale/multiplier/sign: filled
only when unambiguous, never "first field wins".** The first cut's ``_primary_field_spec`` picked
one policy-declared field's unit/scale/multiplier/sign to represent the whole observation even when
several *different* declared fields, with *different* values for those slots, were present in the
same payload (this module's own fixture: ``close`` unit ``KRW`` vs. ``session`` unit ``token``) —
a false statement written into a covered, digest-bound artifact. It is not inert either:
``tos/src/tos/capsule/predicates.py:212-236`` compares exactly these four ``mapping`` fields
against an injected expectation, and ``observed != expected`` is folded into
:func:`~tos.capsule.predicates.admitted_field_state` as ``REJECTED`` -> ``INVALID`` — the
strongest, *proven-bad* verdict the lattice has — for a fact this module invented, not observed.
Fixed: :func:`_mapping_slot_values` fills each of the four slots **independently**, and only when
every policy-declared field actually present in this payload agrees on that slot's value (a single
present field trivially agrees with itself); otherwise the slot is left ``None``. A field's
``unit`` may be ambiguous while its ``sign`` is shared, so this is decided per slot, not
all-or-nothing. ``None`` degrades correctly at the predicate above — ``observed is None`` is
folded as *uncertain* (``UNCERTAIN`` -> ``UNKNOWN``), never a mismatch — which is the "absence is
restrictive, never permissive" discipline this codebase applies everywhere else.

**Review closure — a future-dated ``as_of_ms`` (negative age) is deliberately not refused here.**
``_derive_field_state``'s freshness check is ``now_ms - as_of_ms > spec.max_age_ms``, which is
``False`` for a negative age, so a future-dated observation reads ``VALID`` at this layer. That is
not a fail-open: the future-dating defense is owned one layer later, on the time-admission path —
``tos.time.freshness_verdict`` (``tos/src/tos/time/predicates.py:375-408``) treats a negative
``source_age`` as legitimate future-dating, never clamps it to zero, and returns ``CONFLICTED``
both with no ``future_tolerance`` at all and when the skew exceeds it. This layer has no
future-date opinion by design — duplicating that bound here would be its own defect class, a
runtime-owned copy of a kernel-owned bound that can drift out of sync with it.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.marketfeed.ports`` only — no
``shared.*``, no network, no clock (the caller supplies ``now_ms``; this module never reads one).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tos.canonical import CanonicalizationScheme
from tos.capsule import (
    AdmissionResult,
    ConsistencyCut,
    CriticalInputSnapshot,
    FieldEvaluation,
    FieldState,
    Observation,
    PolicyRef,
)
from tos.capsule.observation import (
    Admission,
    ObservationTime,
    RawRef,
    SourceIdentity,
)
from tos.capsule.observation import (
    Mapping as ObservationMapping,
)
from tos.capsule.snapshot import SnapshotScope
from tos.marketfeed import RawPayloadPreimage, project_scalar
from tos.marketfeed.records import PreimageEntry

from tos_runtime.marketfeed.policy import (
    CriticalInputFieldPolicy,
    LoadedCriticalInputPolicy,
)
from tos_runtime.marketfeed.ports import RawObservation

__all__ = [
    "FieldEvaluationReport",
    "IssuedSnapshot",
    "SnapshotIssuer",
]


@dataclass(frozen=True)
class FieldEvaluationReport:
    """Why one policy-declared field landed at the state it did (module docstring — so tests and
    a future evidence row can read the reason without re-deriving it)."""

    field_key: str
    state: FieldState
    #: ``None`` iff ``state is FieldState.VALID``; otherwise one of ``"absent_from_payload"``,
    #: ``"now_ms_unknown"``, ``"stale"``, ``"unprojectable"``.
    reason: str | None


@dataclass(frozen=True)
class IssuedSnapshot:
    """One issued snapshot plus what a durable store needs to keep it reproducible (plan §2
    decision 3) and what an evidence consumer needs to read why (module docstring)."""

    snapshot: CriticalInputSnapshot
    #: ``raw_event_id -> preimage`` — exactly the one entry this snapshot's single observation
    #: addresses (one observation per snapshot, module docstring).
    preimages: Mapping[str, RawPayloadPreimage]
    field_reports: tuple[FieldEvaluationReport, ...]


_MAPPING_SLOTS: tuple[str, ...] = ("unit", "scale", "multiplier", "sign")


def _mapping_slot_values(
    policy: LoadedCriticalInputPolicy, payload: RawPayloadPreimage
) -> dict[str, str | None]:
    """Fill each of ``Observation.mapping``'s unit/scale/multiplier/sign slots only when
    unambiguous (module docstring "Correction 2"): every policy-declared field actually present
    in ``payload`` must agree on that slot's value, or the slot is left ``None``. Decided
    independently per slot — two present fields may disagree on ``unit`` while agreeing on
    ``sign``."""
    present_specs = [
        spec for spec in policy.fields if payload.lookup(spec.field_key) is not None
    ]
    slots: dict[str, str | None] = {}
    for slot in _MAPPING_SLOTS:
        values = {getattr(spec, slot) for spec in present_specs}
        slots[slot] = values.pop() if len(values) == 1 else None
    return slots


def _derive_field_state(
    field_key: str,
    spec: CriticalInputFieldPolicy,
    payload: RawPayloadPreimage,
    *,
    now_ms: int | None,
    as_of_ms: int,
) -> tuple[FieldState, str | None]:
    """The worst of three derived checks (plan §2 decision 2): present in this payload, fresh as
    of ``now_ms``, and scalar-projectable — never a declared/constant ``VALID`` (mutation M1).
    """
    token = payload.lookup(field_key)
    if token is None:
        return FieldState.UNKNOWN, "absent_from_payload"
    if now_ms is None:
        # An unestablishable freshness bound is never a satisfied one (module docstring).
        return FieldState.UNKNOWN, "now_ms_unknown"
    if now_ms - as_of_ms > spec.max_age_ms:
        return FieldState.UNKNOWN, "stale"
    value, projection_reason = project_scalar(token)
    if value is None or projection_reason is not None:
        # Reuse the kernel's own projection rule (module docstring) — a value the kernel gate
        # would refuse at publication is not VALID here either.
        return FieldState.UNKNOWN, "unprojectable"
    return FieldState.VALID, None


def _derive_observation_state(
    observation: RawObservation,
) -> tuple[FieldState, AdmissionResult]:
    """Record-level well-formedness only (module docstring "Correction 1") — instrument
    concrete, payload non-empty. Never reads per-field presence or freshness; those stay in
    ``field_evaluations``, the slot the kernel folds per key (``value.py:216-230``)."""
    well_formed = bool(observation.instrument.strip()) and bool(observation.fields)
    if well_formed:
        return FieldState.VALID, AdmissionResult.ADMITTED
    return FieldState.UNKNOWN, AdmissionResult.REJECTED


class SnapshotIssuer:
    """Issues one :class:`~tos.capsule.CriticalInputSnapshot` per
    :class:`~tos_runtime.marketfeed.ports.RawObservation` (module docstring)."""

    def __init__(
        self,
        *,
        policy: LoadedCriticalInputPolicy,
        scheme: CanonicalizationScheme,
        account: str,
    ) -> None:
        self._policy = policy
        self._scheme = scheme
        self._account = account

    def issue(
        self, observation: RawObservation, *, now_ms: int | None
    ) -> IssuedSnapshot:
        """Issue a snapshot covering exactly ``observation`` (module docstring).

        Args:
            observation: The raw observation to snapshot.
            now_ms: The wall-clock reading to evaluate freshness against, or ``None`` when no
                trustworthy time is available (every declared field then derives ``UNKNOWN`` —
                an unestablished bound is never satisfied).

        Returns:
            The issued snapshot, its one preimage, and the per-field derivation report.
        """
        payload = RawPayloadPreimage(
            entries=tuple(
                PreimageEntry(key=key, value=value) for key, value in observation.fields
            )
        )
        payload_digest = self._scheme.compute_digest(payload.as_mapping())

        field_evaluations: list[FieldEvaluation] = []
        field_reports: list[FieldEvaluationReport] = []
        for field_key, spec in self._policy.fields_by_key.items():
            state, reason = _derive_field_state(
                field_key, spec, payload, now_ms=now_ms, as_of_ms=observation.as_of_ms
            )
            field_evaluations.append(
                FieldEvaluation(field_ref=field_key, state=state, blocking=True)
            )
            field_reports.append(
                FieldEvaluationReport(field_key=field_key, state=state, reason=reason)
            )
        record_field_state, admission_result = _derive_observation_state(observation)
        mapping_slots = _mapping_slot_values(self._policy, payload)

        observation_record = Observation(
            source=SourceIdentity(provider=observation.source_id),
            raw=RawRef(
                raw_event_id=observation.raw_event_id, payload_digest=payload_digest
            ),
            time=ObservationTime(
                source_event_time=observation.as_of_ms,
                receipt_trustworthy_time_anchor=observation.received_ms,
            ),
            mapping=ObservationMapping(
                instrument=observation.instrument,
                unit=mapping_slots["unit"],
                scale=mapping_slots["scale"],
                multiplier=mapping_slots["multiplier"],
                sign=mapping_slots["sign"],
            ),
            admission=Admission(result=admission_result),
            field_state=record_field_state,
        )

        snapshot = CriticalInputSnapshot.issue(
            scheme=self._scheme,
            issuer_principal_id=self._policy.issuer_principal_id,
            critical_input_policy=PolicyRef(
                policy_id=self._policy.policy_id,
                policy_generation=self._policy.policy_generation,
                canonical_digest=self._policy.canonical_digest,
            ),
            scope=SnapshotScope(
                environment=self._policy.environment,
                accounts=(self._account,),
                instruments=(observation.instrument,),
                decision_class=self._policy.decision_class,
            ),
            intended_use=self._policy.intended_use,
            consistency_cut=ConsistencyCut(
                cut_id=f"cut-{observation.instrument}-{observation.as_of_ms}"
            ),
            observations=(observation_record,),
            field_evaluations=tuple(field_evaluations),
        )
        assert isinstance(snapshot, CriticalInputSnapshot)

        return IssuedSnapshot(
            snapshot=snapshot,
            preimages={observation.raw_event_id: payload},
            field_reports=tuple(field_reports),
        )
