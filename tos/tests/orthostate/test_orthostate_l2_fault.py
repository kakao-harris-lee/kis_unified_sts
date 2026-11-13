"""STATE-EV-001 EV-L2 component-fault suite — ``CompositeState`` (de)serialization."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from tos.canonical import (
    ArtifactStatus,
    RecordPairKind,
    classify_record_pair,
)
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    TransmissionAttemptState,
)

from ._orthostate_strategies import SCHEME, composite_required_kwargs, issue_composite

pytestmark = pytest.mark.l2_fault

_EVIDENCE_ID = "STATE-EV-001"
_COMPONENT = "tos.orthostate.records.CompositeState (serialization / reconstruction)"

_REPO_ROOT = Path(__file__).resolve().parents[3]

_RECORDS = "tos/src/tos/orthostate/records.py"
_VOCABULARY = "tos/src/tos/orthostate/vocabulary.py"
_BASE = "tos/src/tos/canonical/_base.py"
_CANONICALIZATION = "tos/src/tos/canonical/canonicalization.py"
_RECORD_PAIR = "tos/src/tos/canonical/record_pair.py"

_GUARD_SITES: dict[str, tuple[tuple[str, str], ...]] = {
    "ST-01": ((_RECORDS, "intent_state: IntentState"),),
    "ST-02": (
        (_RECORDS, "transmission_attempt_state: TransmissionAttemptState"),
        (_VOCABULARY, 'NONE = "NONE"'),
    ),
    "ST-03": ((_RECORDS, "broker_order_state: BrokerOrderState"),),
    "ST-04": ((_RECORDS, "knowledge_state: KnowledgeState"),),
    "ST-05": ((_BASE, "if digest != expected_digest:"),),
    "ST-06": ((_BASE, "if digest != expected_digest:"),),
    "ST-07": (
        (_CANONICALIZATION, "if version is None or version not in _REGISTRY:"),
        (_BASE, "get_scheme(self.canonicalization_version)"),
    ),
    "ST-08": ((_RECORD_PAIR, "else RecordPairKind.CRITICAL_CONFLICT"),),
    "ST-09": ((_BASE, "if digest is None:"),),
    "ST-11": ((_RECORDS, "observation_revision: int | None = None"),),
    "ST-12": (
        (_BASE, "include=set(self._COVERED_FIELDS)"),
        (_RECORDS, "observation_revision: int | None = None"),
    ),
}

_CATALOG: tuple[str, ...] = (
    "ST-01",
    "ST-02",
    "ST-03",
    "ST-04",
    "ST-05",
    "ST-06",
    "ST-07",
    "ST-08",
    "ST-09",
    "ST-11",
    "ST-12",
)


def _guard_line(path: str, token: str) -> int:
    """The 1-based line of the first line in ``path`` holding ``token``."""
    lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if token in line:
            return number
    raise AssertionError(
        f"guard citation is phantom — {path} no longer holds {token!r}"
    )


def _guard(fault_id: str) -> str:
    """The measured ``path:line`` guard citation(s) for ``fault_id``."""
    return "; ".join(
        f"{path}:{_guard_line(path, token)}" for path, token in _GUARD_SITES[fault_id]
    )


def _witness_ref(composite: CompositeState) -> str:
    """A deterministic reference to the otherwise-valid witness a fault mutated."""
    return f"{composite.composite_state_id}@{composite.canonical_digest}"


def _error_disposition(exc: ValidationError) -> str:
    """Structural disposition of a rejection: sorted ``<error-type>@<field path>``."""
    parts = sorted(
        f"{err['type']}@{'.'.join(str(part) for part in err['loc'])}"
        for err in exc.errors()
    )
    return f"ValidationError[{','.join(parts)}]"


def _integrity_disposition(exc: ValidationError) -> str:
    """Structural disposition naming the wrapped **cause** class (design §3 M3)."""
    causes = sorted(
        type(err["ctx"]["error"]).__name__
        for err in exc.errors()
        if isinstance(err.get("ctx"), dict) and "error" in err["ctx"]
    )
    return f"ValidationError(cause={','.join(causes) or '<none>'})"


@pytest.mark.parametrize("fault_id", sorted(_GUARD_SITES))
def test_guard_code_lines_are_measured_not_phantom(fault_id: str) -> None:
    """Every ``injection_point`` this suite writes still names the real guard line."""
    citation = _guard(fault_id)
    for path, token in _GUARD_SITES[fault_id]:
        lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
        hits = [number for number, line in enumerate(lines, 1) if token in line]
        assert hits, f"{fault_id}: {path} no longer holds {token!r}"
        assert f"{path}:{hits[0]}" in citation, (
            f"{fault_id}: the written injection_point {citation!r} does not carry the "
            f"measured line {path}:{hits[0]} for {token!r}"
        )


def test_catalog_is_the_design_section_3_table() -> None:
    """The executed catalog is exactly the design §3 table — 11 faults, no ``ST-10``."""
    assert len(_CATALOG) == 11
    assert set(_CATALOG) == set(_GUARD_SITES)
    assert "ST-10" not in _CATALOG, "ST-10 is merged into ST-01 (design §3 M6)"


def test_st_01_dropped_dimension_is_not_derived_from_its_neighbours(
    l2_fault_timeline,
) -> None:
    """ST-01 — drop a mandatory dimension + **silent-derivation probe** (§3 M6, ST-10 merged)."""
    witness = issue_composite()
    assert witness.broker_order_state is BrokerOrderState.NONE_OBSERVED

    kwargs = composite_required_kwargs()
    kwargs.pop("broker_order_state")
    with pytest.raises(ValidationError) as caught:
        CompositeState.issue(scheme=SCHEME, **kwargs)

    observed = _error_disposition(caught.value)
    assert {err["type"] for err in caught.value.errors()} == {"missing"}

    l2_fault_timeline.record(
        fault_id="ST-01",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-01"),
        fault_kind="mandatory_dimension_dropped+silent_derivation_probe",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[missing@broker_order_state]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[missing@broker_order_state]"


def test_st_02_none_is_not_the_none_state(l2_fault_timeline) -> None:
    """ST-02 — substitute ``None`` for the ``NONE`` state (``NONE != None``)."""
    witness = issue_composite(transmission_attempt_state=TransmissionAttemptState.NONE)
    assert witness.transmission_attempt_state.value == "NONE"

    with pytest.raises(ValidationError) as caught:
        issue_composite(transmission_attempt_state=None)

    observed = _error_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-02",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-02"),
        fault_kind="none_substituted_for_NONE_state",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[enum@transmission_attempt_state]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[enum@transmission_attempt_state]"


def test_st_03_dimension_swap_is_unconstructable(l2_fault_timeline) -> None:
    """ST-03 — put one dimension's value into another dimension's field."""
    witness = issue_composite()
    with pytest.raises(ValidationError) as caught:
        issue_composite(broker_order_state=IntentState.APPROVED)

    observed = _error_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-03",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-03"),
        fault_kind="dimension_swap_value_contamination",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[enum@broker_order_state]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[enum@broker_order_state]"


def test_st_04_out_of_vocabulary_token_is_rejected(l2_fault_timeline) -> None:
    """ST-04 — a token outside the dimension's closed vocabulary."""
    witness = issue_composite()
    with pytest.raises(ValidationError) as caught:
        issue_composite(knowledge_state="NOT_A_STATE")

    observed = _error_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-04",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-04"),
        fault_kind="out_of_enum_token",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[enum@knowledge_state]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[enum@knowledge_state]"


def test_st_11_scalar_meta_type_contamination(l2_fault_timeline) -> None:
    """ST-11 — a non-numeric token in the ledger-placement scalar ``observation_revision``."""
    witness = issue_composite(observation_revision=3)
    with pytest.raises(ValidationError) as caught:
        issue_composite(observation_revision="two")

    observed = _error_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-11",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-11"),
        fault_kind="scalar_meta_type_contamination",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError[int_parsing@observation_revision]",
        observed_disposition=observed,
    )
    assert observed == "ValidationError[int_parsing@observation_revision]"


def test_st_05_covered_content_tampered_with_a_retained_digest(
    l2_fault_timeline,
) -> None:
    """ST-05 — mutate covered content while retaining the original digest (**L2-new**)."""
    witness = issue_composite()
    with pytest.raises(ValidationError) as caught:
        CompositeState(
            **composite_required_kwargs(intent_state=IntentState.ACTIVE),
            canonical_digest=witness.canonical_digest,
            status=witness.status,
            canonicalization_version=witness.canonicalization_version,
        )

    observed = _integrity_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-05",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-05"),
        fault_kind="covered_content_tampered_digest_retained",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError(cause=ArtifactIntegrityError)",
        observed_disposition=observed,
    )
    assert observed == "ValidationError(cause=ArtifactIntegrityError)"


def test_st_06_digest_substituted_with_covered_content_retained(
    l2_fault_timeline,
) -> None:
    """ST-06 — substitute the digest while retaining covered content (**L2-new**)."""
    witness = issue_composite()
    other = issue_composite(intent_state=IntentState.ACTIVE)
    assert other.canonical_digest != witness.canonical_digest

    with pytest.raises(ValidationError) as caught:
        CompositeState(
            **composite_required_kwargs(),
            canonical_digest=other.canonical_digest,
            status=witness.status,
            canonicalization_version=witness.canonicalization_version,
        )

    observed = _integrity_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-06",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-06"),
        fault_kind="digest_substituted_covered_retained",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError(cause=ArtifactIntegrityError)",
        observed_disposition=observed,
    )
    assert observed == "ValidationError(cause=ArtifactIntegrityError)"


def test_st_07_unregistered_canonicalization_version(l2_fault_timeline) -> None:
    """ST-07 — an unregistered ``canonicalization_version`` (**L2-new; §5 H-4 dependent**)."""
    witness = issue_composite()
    with pytest.raises(ValidationError) as caught:
        CompositeState(
            **composite_required_kwargs(),
            canonical_digest=witness.canonical_digest,
            status=witness.status,
            canonicalization_version="no-such-scheme-0",
        )

    observed = _integrity_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-07",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-07"),
        fault_kind="unregistered_canonicalization_version",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError(cause=ArtifactIntegrityError)",
        observed_disposition=observed,
    )
    assert observed == "ValidationError(cause=ArtifactIntegrityError)"


def test_st_09_issued_status_with_a_null_digest(l2_fault_timeline) -> None:
    """ST-09 — a lifecycle contradiction: ``ISSUED`` status carrying a null digest (**L2-new**)."""
    witness = issue_composite()
    assert witness.status is ArtifactStatus.ISSUED and witness.canonical_digest

    with pytest.raises(ValidationError) as caught:
        CompositeState(
            **composite_required_kwargs(),
            canonical_digest=None,
            status=ArtifactStatus.ISSUED,
            canonicalization_version=witness.canonicalization_version,
        )

    observed = _integrity_disposition(caught.value)
    l2_fault_timeline.record(
        fault_id="ST-09",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-09"),
        fault_kind="lifecycle_contradiction_issued_null_digest",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="ValidationError(cause=ArtifactIntegrityError)",
        observed_disposition=observed,
    )
    assert observed == "ValidationError(cause=ArtifactIntegrityError)"


def test_st_12_self_excluded_field_round_trip_is_stable(l2_fault_timeline) -> None:
    """ST-12 — **positive canary**: a self-excluded field change leaves the record identical."""
    witness = issue_composite()
    replaced = issue_composite(observation_revision=7)

    stable = (
        replaced.canonical_digest == witness.canonical_digest
        and replaced.covered_content() == witness.covered_content()
        and replaced.observation_revision != witness.observation_revision
    )
    observed = "DIGEST_STABLE_RECONSTRUCTION_IDENTICAL" if stable else "DIGEST_UNSTABLE"

    l2_fault_timeline.record(
        fault_id="ST-12",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-12"),
        fault_kind="self_excluded_field_changed_positive_canary",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="DIGEST_STABLE_RECONSTRUCTION_IDENTICAL",
        observed_disposition=observed,
    )
    assert observed == "DIGEST_STABLE_RECONSTRUCTION_IDENTICAL"


def test_st_08_same_id_different_bytes_is_a_critical_conflict(
    l2_fault_timeline,
) -> None:
    """ST-08 — re-publish the same ``composite_state_id`` with different content."""
    witness = issue_composite()
    forged = issue_composite(intent_state=IntentState.ACTIVE)
    assert forged.composite_state_id == witness.composite_state_id
    assert forged.canonical_digest != witness.canonical_digest

    kind = classify_record_pair(
        witness.composite_state_id,
        witness.canonical_digest,
        forged.composite_state_id,
        forged.canonical_digest,
    )
    assert (
        classify_record_pair(
            witness.composite_state_id,
            witness.canonical_digest,
            witness.composite_state_id,
            witness.canonical_digest,
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )

    l2_fault_timeline.record(
        fault_id="ST-08",
        evidence_id=_EVIDENCE_ID,
        target_component=_COMPONENT,
        guard_code_line=_guard("ST-08"),
        fault_kind="same_identity_different_bytes",
        input_witness_ref=_witness_ref(witness),
        expected_disposition="CRITICAL_CONFLICT",
        observed_disposition=kind.value,
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT
