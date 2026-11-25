"""``tos_runtime.marketfeed.snapshot`` — ``SnapshotIssuer`` derivation + real-gate publication"""

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


def test_fresh_observation_publishes_through_real_gate(tmp_path: Path) -> None:
    """The full path: issued snapshot -> issued capsule -> the kernel's own"""
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
    """M1's literal proof: a field older than its policy ``max_age_ms`` must be dropped by the"""
    issuer = _issuer(tmp_path)
    obs = observation()
    stale_now_ms = BAR_ONE_AS_OF + 10_000
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


def test_fresh_field_publishes_when_a_sibling_declared_field_is_absent(
    tmp_path: Path,
) -> None:
    """The literal Correction 1 repro, as a positive assertion: policy declares ``close`` +"""
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", CLOSE_BAR_ONE),))
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
    """``close`` (max_age_ms=10000) and ``session`` (max_age_ms=2000) both present at age 6000ms:"""
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
    obs = observation()
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
    """Direct check of :func:`tos_runtime.marketfeed.snapshot._derive_observation_state`'s"""
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


def test_absent_policy_field_derives_unknown(tmp_path: Path) -> None:
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", CLOSE_BAR_ONE),))
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    reports = {r.field_key: r for r in issued.field_reports}
    assert reports["close"].state == FieldState.VALID
    assert reports["session"].state == FieldState.UNKNOWN
    assert reports["session"].reason == "absent_from_payload"


def test_now_ms_none_derives_unknown_for_every_declared_field(tmp_path: Path) -> None:
    """An unestablishable freshness bound is never a satisfied one — ``now_ms=None`` must not be"""
    issuer = _issuer(tmp_path)
    obs = observation()
    issued = issuer.issue(obs, now_ms=None)

    assert all(r.state == FieldState.UNKNOWN for r in issued.field_reports)
    assert all(r.reason == "now_ms_unknown" for r in issued.field_reports)


def test_future_dated_as_of_is_not_refused_at_this_layer(tmp_path: Path) -> None:
    """Review closure (확인 불가 pinned): a future-dated ``as_of_ms`` (negative age,"""
    issuer = _issuer(tmp_path)
    obs = observation(fields=(("close", CLOSE_BAR_ONE),))
    future_now_ms = obs.as_of_ms - 60_000
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
    """A ``float`` is refused by the kernel's own ``project_scalar`` (non-deterministic numeric,"""
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
    """A key the policy does not declare gets no FieldEvaluation at all (drops via the kernel's"""
    issuer = _issuer(tmp_path)
    obs = observation(
        fields=(("close", CLOSE_BAR_ONE), ("session", "REGULAR"), ("volume", 100))
    )
    issued = issuer.issue(obs, now_ms=BAR_ONE_AS_OF + 100)

    reported_keys = {r.field_key for r in issued.field_reports}
    assert reported_keys == {"close", "session"}

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


def test_one_observation_yields_exactly_one_snapshot_observation(
    tmp_path: Path,
) -> None:
    """Structural guarantee that ``SnapshotIssuer.issue`` can never produce the "two observations"""
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


def test_mapping_slot_is_none_when_present_declared_fields_disagree(
    tmp_path: Path,
) -> None:
    """Default fixture policy: ``close`` (unit=KRW, scale=minor) and ``session`` (unit=token,"""
    issuer = _issuer(tmp_path)
    issued = issuer.issue(observation(), now_ms=BAR_ONE_AS_OF + 100)

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
    """``received_ms=None`` must stay ``None`` — never silently substituted with ``as_of_ms``"""
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
