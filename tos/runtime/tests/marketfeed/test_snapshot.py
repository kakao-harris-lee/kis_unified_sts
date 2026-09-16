"""``tos_runtime.marketfeed.snapshot`` — ``SnapshotIssuer`` derivation + real-gate publication
(TOS tick-source wave, plan §2 decisions 2/5; lane A).

Hermetic (D1.4): every case writes its own policy YAML under ``tmp_path``; no network, no clock
(``now_ms`` is always injected).
"""

from __future__ import annotations

from pathlib import Path

from tos.capsule import AdmissionResult, FieldState, PolicyRef
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
    policy_yaml,
)


def _issuer(tmp_path: Path) -> SnapshotIssuer:
    policy = loaded_policy(tmp_path)
    return SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)


def _capsule_issuer(policy_ref: PolicyRef) -> CapsuleIssuer:
    return CapsuleIssuer(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        environment=ENVIRONMENT,
        decision_class=DECISION_CLASS,
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        issuer_principal_id="iss-1",
        critical_input_policy=policy_ref,
        scheme=SCHEME,
    )


def _candidate(obs, issued, field_key: str) -> AdmittedValue:
    return AdmittedValue(
        field_key=field_key,
        observation_ref=obs.raw_event_id,
        preimage=issued.preimages[obs.raw_event_id],
    )


# ===========================================================================
# End-to-end through the REAL kernel gate — the M1/M6 proof surface
# ===========================================================================


def test_fresh_observation_publishes_through_real_gate(tmp_path: Path) -> None:
    """The full path: issued snapshot -> issued capsule -> the kernel's own
    ``publish_context_value_view`` -> a RESOLVED view carrying both declared values.

    Guards mutation M1 (a stamped-constant-VALID FieldEvaluation would let a STALE field through
    the real kernel gate too, not just this module's own report) and M6 (a broken binding would
    never reach RESOLVED at all)."""
    issuer = _issuer(tmp_path)
    obs = observation()
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 500)

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    candidates = tuple(_candidate(obs, issued, key) for key, _ in obs.fields)
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
    issuer = _issuer(tmp_path)  # close: max_age_ms=5000
    obs = observation()
    stale_now_ms = BAR_ONE_AS_OF + 10_000  # 10s > 5000ms ceiling
    issued = issuer.issue(obs, now_ms=stale_now_ms)

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=issued.snapshot,
        candidates=(_candidate(obs, issued, "close"),),
        scheme=SCHEME,
    )

    assert resolution.disposition == ValueViewDisposition.EXPLICIT_EMPTY
    assert len(resolution.rejected) == 1
    assert resolution.rejected[0].reason == ValueRejectionReason.FIELD_STATE_NOT_VALID


# ===========================================================================
# Correction 1 (team-lead review) — Observation.field_state must not aggregate
# per-field verdicts. Literal end-to-end reproduction + inverted positive proof.
# ===========================================================================


def test_fresh_field_publishes_when_a_sibling_declared_field_is_absent(
    tmp_path: Path,
) -> None:
    """The literal Correction 1 repro, as a positive assertion: policy declares ``close`` +
    ``session``; payload carries only a fresh ``close``. Before the fix, aggregating
    ``Observation.field_state`` over every declared field dragged a fresh, individually-VALID
    ``close`` down to ``EXPLICIT_EMPTY`` / ``FIELD_STATE_NOT_VALID`` just because ``session`` was
    absent. ``close`` must now publish on its own."""
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", CLOSE_BAR_ONE),))  # "session" absent
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=issued.snapshot,
        candidates=(_candidate(obs, issued, "close"),),
        scheme=SCHEME,
    )

    assert resolution.disposition == ValueViewDisposition.RESOLVED
    published = {v.field_key: v.value for v in resolution.values}
    assert published == {"close": CLOSE_BAR_ONE}


def test_fresh_field_publishes_when_a_sibling_declared_field_is_stale(
    tmp_path: Path,
) -> None:
    """``close`` (max_age_ms=10000) and ``session`` (max_age_ms=2000) both present at age 6000ms:
    ``close`` is individually fresh, ``session`` is individually stale. ``close`` must publish;
    ``session`` alone must be dropped — a pre-fix aggregate would have dropped both."""
    fields_block = (
        "fields:\n"
        "  - field_key: close\n"
        "    unit: KRW\n"
        "    scale: minor\n"
        '    multiplier: "1"\n'
        '    sign: "1"\n'
        "    max_age_ms: 10000\n"
        "  - field_key: session\n"
        "    unit: token\n"
        "    scale: none\n"
        '    multiplier: "1"\n'
        '    sign: "1"\n'
        "    max_age_ms: 2000\n"
    )
    policy = loaded_policy(tmp_path, policy_yaml(fields_block=fields_block))
    issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    obs = observation()  # close + session both present, as_of=BAR_ONE_AS_OF
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 6_000)

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    candidates = (_candidate(obs, issued, "close"), _candidate(obs, issued, "session"))
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=issued.snapshot, candidates=candidates, scheme=SCHEME
    )

    published = {v.field_key: v.value for v in resolution.values}
    assert published == {"close": CLOSE_BAR_ONE}
    rejected = {r.field_key: r.reason for r in resolution.rejected}
    assert rejected["session"] == ValueRejectionReason.FIELD_STATE_NOT_VALID


def test_record_field_state_reflects_only_well_formedness(tmp_path: Path) -> None:
    """Direct check of :func:`tos_runtime.marketfeed.snapshot._derive_observation_state`'s
    contract via its observable effect: a well-formed record is VALID/ADMITTED regardless of
    which declared fields the payload happens to carry."""
    issuer = _issuer(tmp_path)
    only_close = issuer.issue(
        observation(fields=(("close", CLOSE_BAR_ONE),)), now_ms=BAR_ONE_AS_OF + 100
    )
    assert only_close.snapshot.observations[0].field_state == FieldState.VALID
    assert (
        only_close.snapshot.observations[0].admission.result == AdmissionResult.ADMITTED
    )

    both = issuer.issue(observation(raw_event_id="raw-2"), now_ms=BAR_ONE_AS_OF + 100)
    assert both.snapshot.observations[0].field_state == FieldState.VALID
    assert both.snapshot.observations[0].admission.result == AdmissionResult.ADMITTED


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


def test_future_dated_as_of_is_not_refused_at_this_layer(tmp_path: Path) -> None:
    """Review closure (확인 불가 pinned): a future-dated ``as_of_ms`` (negative age,
    ``now_ms < as_of_ms``) must publish VALID through the real kernel gate at this layer.

    This is correct, not a fail-open. The freshness check here is
    ``now_ms - as_of_ms > spec.max_age_ms``, which is ``False`` for a negative age, so this
    layer has no opinion on future-dating by construction. The actual defense lives one layer
    later, on the time-admission path: ``tos.time.freshness_verdict``
    (``tos/src/tos/time/predicates.py:375-408``) treats a negative ``source_age`` as legitimate
    future-dating — never clamped to zero — and returns ``CONFLICTED`` both when there is no
    ``future_tolerance`` at all and when the skew exceeds it. Do NOT "fix" this into a
    fail-closed check here — that would duplicate a bound (``MAX_future_timestamp_tolerance_ms``)
    the kernel already owns, applied at a different layer, which is its own defect class.
    """
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", CLOSE_BAR_ONE),))
    future_now_ms = obs.as_of_ms - 60_000  # now is 60s BEFORE as_of -> negative age
    issued = issuer.issue(obs, now_ms=future_now_ms)

    reports = {r.field_key: r for r in issued.field_reports}
    assert reports["close"].state == FieldState.VALID
    assert reports["close"].reason is None

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    resolution = publish_context_value_view(
        capsule=capsule,
        snapshot=issued.snapshot,
        candidates=(_candidate(obs, issued, "close"),),
        scheme=SCHEME,
    )
    assert resolution.disposition == ValueViewDisposition.RESOLVED
    published = {v.field_key: v.value for v in resolution.values}
    assert published == {"close": CLOSE_BAR_ONE}


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

    capsule = _capsule_issuer(issued.snapshot.critical_input_policy).issue(
        issued.snapshot
    )
    candidates = (_candidate(obs, issued, "close"), _candidate(obs, issued, "volume"))
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
    assert issued.snapshot.observations[0].field_state == FieldState.UNKNOWN


def test_admission_rejected_for_empty_payload(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(fields=())
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)
    assert issued.snapshot.observations[0].admission.result == AdmissionResult.REJECTED
    assert issued.snapshot.observations[0].field_state == FieldState.UNKNOWN


# ===========================================================================
# Correction 2 (team-lead review) — mapping unit/scale/multiplier/sign: filled
# only when unambiguous, never "first field wins".
# ===========================================================================


def test_mapping_slot_is_none_when_present_declared_fields_disagree(
    tmp_path: Path,
) -> None:
    """Default fixture policy: ``close`` (unit=KRW, scale=minor) and ``session`` (unit=token,
    scale=none) disagree on unit/scale but AGREE on multiplier="1"/sign="1" — decided per slot,
    not all-or-nothing."""
    issuer = _issuer(tmp_path)
    issued = issuer.issue(
        observation(), now_ms=BAR_ONE_AS_OF + 100
    )  # close + session present

    mapping = issued.snapshot.observations[0].mapping
    assert mapping.instrument == INSTRUMENT
    assert mapping.unit is None
    assert mapping.scale is None
    assert mapping.multiplier == "1"
    assert mapping.sign == "1"


def test_mapping_filled_when_only_one_declared_field_present(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    issued = issuer.issue(
        observation(fields=(("close", CLOSE_BAR_ONE),)), now_ms=BAR_ONE_AS_OF + 100
    )

    mapping = issued.snapshot.observations[0].mapping
    assert mapping.unit == "KRW"
    assert mapping.scale == "minor"
    assert mapping.multiplier == "1"
    assert mapping.sign == "1"


def test_mapping_filled_when_all_present_declared_fields_agree(tmp_path: Path) -> None:
    fields_block = (
        "fields:\n"
        "  - field_key: bid\n"
        "    unit: KRW\n"
        "    scale: minor\n"
        '    multiplier: "1"\n'
        '    sign: "1"\n'
        "    max_age_ms: 5000\n"
        "  - field_key: ask\n"
        "    unit: KRW\n"
        "    scale: minor\n"
        '    multiplier: "1"\n'
        '    sign: "1"\n'
        "    max_age_ms: 5000\n"
    )
    policy = loaded_policy(tmp_path, policy_yaml(fields_block=fields_block))
    issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    issued = issuer.issue(
        observation(fields=(("bid", 100), ("ask", 101))), now_ms=BAR_ONE_AS_OF + 100
    )

    mapping = issued.snapshot.observations[0].mapping
    assert mapping.unit == "KRW"
    assert mapping.scale == "minor"
    assert mapping.multiplier == "1"
    assert mapping.sign == "1"


def test_mapping_all_none_when_no_declared_field_present(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    issued = issuer.issue(
        observation(fields=(("volume", 100),)), now_ms=BAR_ONE_AS_OF + 100
    )

    mapping = issued.snapshot.observations[0].mapping
    assert mapping.instrument == INSTRUMENT
    assert mapping.unit is None
    assert mapping.scale is None
    assert mapping.multiplier is None
    assert mapping.sign is None


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
