"""``tos_runtime.marketfeed.snapshot`` — ``SnapshotIssuer`` derivation + real-gate publication
(TOS tick-source wave, plan §2 decisions 2/5; lane A).

Hermetic (D1.4): every case writes its own policy YAML under ``tmp_path``; no network, no clock
(``now_ms`` is always injected).
"""

from __future__ import annotations

from pathlib import Path

from tos.capsule import AdmissionResult, FieldState
from tos.marketfeed import (
    AdmittedValue,
    ValueRejectionReason,
    ValueViewDisposition,
    publish_context_value_view,
)
from tos_runtime.marketfeed.capsule import CapsuleIssuer
from tos_runtime.marketfeed.snapshot import SnapshotIssuer

from ._fixtures import (
    ACCOUNT,
    BAR_ONE_AS_OF,
    CLOSE_BAR_ONE,
    DECISION_CLASS,
    ENVIRONMENT,
    INSTRUMENT,
    SCHEME,
    loaded_policy,
    observation,
)


def _issuer(tmp_path: Path) -> SnapshotIssuer:
    policy = loaded_policy(tmp_path)
    return SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)


# ===========================================================================
# End-to-end through the REAL kernel gate — the M1/M2/M6 proof surface
# ===========================================================================


def test_fresh_observation_publishes_through_real_gate(tmp_path: Path) -> None:
    """The full path: issued snapshot -> issued capsule -> the kernel's own
    ``publish_context_value_view`` -> a RESOLVED view carrying both declared values.

    Guards mutation M1 (a stamped-constant-VALID FieldEvaluation would let a STALE field through
    the real kernel gate too, not just this module's own report) and M6 (a broken binding would
    never reach RESOLVED at all)."""
    policy = loaded_policy(tmp_path)
    snap_issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    obs = observation()
    issued = snap_issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 500)

    cap_issuer = CapsuleIssuer(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        environment=ENVIRONMENT,
        decision_class=DECISION_CLASS,
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        issuer_principal_id="iss-1",
        critical_input_policy=issued.snapshot.critical_input_policy,
        scheme=SCHEME,
    )
    capsule = cap_issuer.issue(issued.snapshot)

    candidates = tuple(
        AdmittedValue(
            field_key=key,
            observation_ref=obs.raw_event_id,
            preimage=issued.preimages[obs.raw_event_id],
        )
        for key, _ in obs.fields
    )
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=issued.snapshot, candidates=candidates, scheme=SCHEME
    )

    assert resolution.disposition == ValueViewDisposition.RESOLVED
    assert resolution.rejected == ()
    published = {v.field_key: v.value for v in resolution.values}
    assert published == {"close": CLOSE_BAR_ONE, "session": "REGULAR"}


def test_stale_field_is_dropped_by_the_real_gate(tmp_path: Path) -> None:
    """M1's literal proof: a field older than its policy ``max_age_ms`` must be dropped by the
    REAL ``publish_context_value_view`` gate, not merely reported UNKNOWN by this module. A
    mutation stamping ``FieldEvaluation(state=VALID)`` unconditionally would make this pass a
    value the policy's own freshness ceiling forbids."""
    policy = loaded_policy(tmp_path)  # close: max_age_ms=5000
    snap_issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    obs = observation()
    stale_now_ms = BAR_ONE_AS_OF + 10_000  # 10s > 5000ms ceiling
    issued = snap_issuer.issue(obs, now_ms=stale_now_ms)

    cap_issuer = CapsuleIssuer(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        environment=ENVIRONMENT,
        decision_class=DECISION_CLASS,
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        issuer_principal_id="iss-1",
        critical_input_policy=issued.snapshot.critical_input_policy,
        scheme=SCHEME,
    )
    capsule = cap_issuer.issue(issued.snapshot)

    candidate = AdmittedValue(
        field_key="close",
        observation_ref=obs.raw_event_id,
        preimage=issued.preimages[obs.raw_event_id],
    )
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=issued.snapshot,
        candidates=(candidate,),
        scheme=SCHEME,
    )

    assert resolution.disposition == ValueViewDisposition.EXPLICIT_EMPTY
    assert len(resolution.rejected) == 1
    assert resolution.rejected[0].reason == ValueRejectionReason.FIELD_STATE_NOT_VALID


# ===========================================================================
# Per-field derivation — direct on IssuedSnapshot.field_reports
# ===========================================================================


def test_absent_policy_field_derives_unknown(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(
        fields=(("close", CLOSE_BAR_ONE),)
    )  # "session" absent from payload
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    reports = {r.field_key: r for r in issued.field_reports}
    assert reports["close"].state == FieldState.VALID
    assert reports["session"].state == FieldState.UNKNOWN
    assert reports["session"].reason == "absent_from_payload"


def test_now_ms_none_derives_unknown_for_every_declared_field(tmp_path: Path) -> None:
    """An unestablishable freshness bound is never a satisfied one — ``now_ms=None`` must not be
    silently treated as fresh."""
    issuer = _issuer(tmp_path)
    obs = observation()
    issued = issuer.issue(obs, now_ms=None)

    assert all(r.state == FieldState.UNKNOWN for r in issued.field_reports)
    assert all(r.reason == "now_ms_unknown" for r in issued.field_reports)


def test_unprojectable_value_derives_unknown(tmp_path: Path) -> None:
    """A ``float`` is refused by the kernel's own ``project_scalar`` (non-deterministic numeric,
    design #32 §2.5) — this module reuses that rule rather than re-deciding it."""
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", 4512.5), ("session", "REGULAR")))
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    reports = {r.field_key: r for r in issued.field_reports}
    assert reports["close"].state == FieldState.UNKNOWN
    assert reports["close"].reason == "unprojectable"
    assert reports["session"].state == FieldState.VALID


def test_undeclared_field_present_in_payload_drops_only_that_field(
    tmp_path: Path,
) -> None:
    """A key the policy does not declare gets no FieldEvaluation at all (drops via the kernel's
    own UNKNOWN floor), while the declared keys still publish."""
    issuer = _issuer(tmp_path)
    obs = observation(
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR"), ("volume", 100))
    )
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    reported_keys = {r.field_key for r in issued.field_reports}
    assert reported_keys == {"close", "session"}  # "volume" is not policy-declared

    cap_issuer = CapsuleIssuer(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        environment=ENVIRONMENT,
        decision_class=DECISION_CLASS,
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        issuer_principal_id="iss-1",
        critical_input_policy=issued.snapshot.critical_input_policy,
        scheme=SCHEME,
    )
    capsule = cap_issuer.issue(issued.snapshot)
    candidates = (
        AdmittedValue(
            field_key="close",
            observation_ref=obs.raw_event_id,
            preimage=issued.preimages[obs.raw_event_id],
        ),
        AdmittedValue(
            field_key="volume",
            observation_ref=obs.raw_event_id,
            preimage=issued.preimages[obs.raw_event_id],
        ),
    )
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=issued.snapshot, candidates=candidates, scheme=SCHEME
    )
    published = {v.field_key for v in resolution.values}
    assert published == {"close"}
    rejected = {r.field_key: r.reason for r in resolution.rejected}
    assert rejected["volume"] == ValueRejectionReason.FIELD_STATE_NOT_VALID


# ===========================================================================
# Structural distinctness / preimage completeness
# ===========================================================================


def test_one_observation_yields_exactly_one_snapshot_observation(
    tmp_path: Path,
) -> None:
    """Structural guarantee that ``SnapshotIssuer.issue`` can never produce the "two observations
    share one raw_event_id" ambiguity within a single snapshot (one observation in, one
    observation out, by construction — see module docstring)."""
    issuer = _issuer(tmp_path)
    issued = issuer.issue(observation(), now_ms=BAR_ONE_AS_OF + 100)
    assert len(issued.snapshot.observations) == 1
    assert issued.snapshot.observations[0].raw.raw_event_id == "raw-1"


def test_preimage_carries_the_whole_payload_not_just_declared_keys(
    tmp_path: Path,
) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR"), ("volume", 100))
    )
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    preimage = issued.preimages[obs.raw_event_id]
    assert preimage.as_mapping() == {
        "close": CLOSE_BAR_ONE,
        "session": "REGULAR",
        "volume": 100,
    }


def test_payload_digest_matches_scheme_recompute(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation()
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    preimage = issued.preimages[obs.raw_event_id]
    recomputed = SCHEME.compute_digest(preimage.as_mapping())
    assert issued.snapshot.observations[0].raw.payload_digest == recomputed


def test_admission_rejected_for_blank_instrument(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(instrument="")
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)
    assert issued.snapshot.observations[0].admission.result == AdmissionResult.REJECTED


def test_admission_rejected_for_empty_payload(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(fields=())
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)
    assert issued.snapshot.observations[0].admission.result == AdmissionResult.REJECTED


def test_mapping_reflects_first_declared_field_present_in_payload(
    tmp_path: Path,
) -> None:
    """The "primary field" mapping choice (module docstring deviation note): with both ``close``
    and ``session`` present, ``close`` wins (it is declared first); with only ``session``
    present, ``session``'s unit/scale/multiplier/sign are used instead."""
    issuer = _issuer(tmp_path)

    both = issuer.issue(observation(), now_ms=BAR_ONE_AS_OF + 100)
    assert both.snapshot.observations[0].mapping.unit == "KRW"

    session_only = issuer.issue(
        observation(raw_event_id="raw-2", fields=(("session", "REGULAR"),)),
        now_ms=BAR_ONE_AS_OF + 100,
    )
    assert session_only.snapshot.observations[0].mapping.unit == "token"


def test_receipt_trustworthy_time_anchor_is_none_when_collector_recorded_none(
    tmp_path: Path,
) -> None:
    """``received_ms=None`` must stay ``None`` — never silently substituted with ``as_of_ms``
    (module docstring / ports.py's own ``RawObservation.received_ms`` docstring)."""
    issuer = _issuer(tmp_path)
    obs = observation(received_ms=None)
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)
    assert issued.snapshot.observations[0].time.receipt_trustworthy_time_anchor is None


def test_receipt_trustworthy_time_anchor_carries_a_concrete_value(
    tmp_path: Path,
) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(received_ms=BAR_ONE_AS_OF + 50)
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)
    assert issued.snapshot.observations[0].time.receipt_trustworthy_time_anchor == (
        BAR_ONE_AS_OF + 50
    )
