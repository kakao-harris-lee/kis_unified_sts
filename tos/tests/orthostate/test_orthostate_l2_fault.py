"""STATE-EV-001 EV-L2 component-fault suite — ``CompositeState`` (de)serialization.

**Stage**: EV-L2 (VER-002-001 §5 line 146-148 verbatim — "A component is tested with
controlled failure injection and authoritative state inspection"). Catalog: EV-L2 pilot
design ``docs/plans/2026-07-29-tos-ev-l2-pilot-design.md`` §3, **11 faults**
(``ST-01..ST-09``, ``ST-11``, ``ST-12``; ``ST-10`` is merged into ``ST-01`` per design
§3 M6). One ``@pytest.mark.l2_fault`` test per catalog row.

**Covered axis — read this before reading any result as coverage.** This suite covers the
**storage-independent** axis of STATE-EV-001 only: representability, **no silent
derivation** (VER-002-001 line 1024), and structural integrity. The Expected's *durable*
limb — "remains representable and **durable**" (VER:1024), ADR-002-005 §13 line 197 "SHALL
be durable and reconstructable after crash", AC-005-1 line 237 "representable **and
persisted**" — designates a **real persisted authoritative record surviving a real fault**.
That referent does not exist in an in-memory model, is EV-L3 (VER:150-152), and its
persistence technology is undecided (ADR-002-005 §4 line 61). It is therefore **not
evidenced here** and is carried as a §378 residual (design §2.2 / §2.3 alternative C, §9).
Nothing in this file may be read as covering it.

**Component** (the single component under injection): ``tos.orthostate.records.CompositeState``
plus the digest-binding base it inherits (``tos.canonical._base.DigestBoundArtifact``).
**Authoritative state inspected**: the reconstructed composite, or the construction-time
verdict (``ValidationError`` / its ``ArtifactIntegrityError`` cause) — the component's own
authoritative refusal, observed **structurally** and never self-reported (design §0.5-3).

**Both-ways canary** (design §8.4): every fault first constructs the *unmutated* witness
and asserts it is valid, so a rejection is attributable to the single injected mutation and
can never be a vacuous refusal of everything.

**Non-duplication** (design §8.3): ``ST-01/02/03/04/08/11`` re-frame guards that adjacent
EV-L1 nodes already exercise (``test_orthostate_composite.py`` / ``test_orthostate_vocabulary.py``)
as fault-schedule rows with a single mutation on an otherwise-valid witness; they are **not**
a second acceptance of those guards. ``ST-05/06/07/09/12`` are L2-new.

``ST-07`` additionally depends on the design §5 **H-4** hardening (canonicalization-scheme
lookup failure wrapped as ``ArtifactIntegrityError``); before it the same injection escaped
as a raw ``KeyError`` and would have been recorded as a ``DEVIATION`` (design §3 M4 / §5).
"""

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

#: fault id -> the **measured** guard sites, each ``(path, line, token-on-that-line)``.
#:
#: design §3 line 163 (v1.2 N3) makes measuring the *real* guard line an implementation
#: obligation: the design table's own "가드 코드 라인" column is a docstring anchor for
#: five rows and is deliberately NOT reused here. ``token`` is the anti-phantom seal —
#: :func:`test_guard_code_lines_are_measured_not_phantom` re-reads each file and fails if
#: the recorded line no longer carries it, so a later edit cannot leave the fault timeline
#: citing a line that has moved (the citation-drift defect class).
_GUARD_SITES: dict[str, tuple[tuple[str, int, str], ...]] = {
    "ST-01": ((_RECORDS, 94, "intent_state: IntentState"),),
    "ST-02": (
        (_RECORDS, 95, "transmission_attempt_state: TransmissionAttemptState"),
        (_VOCABULARY, 82, 'NONE = "NONE"'),
    ),
    "ST-03": ((_RECORDS, 96, "broker_order_state: BrokerOrderState"),),
    "ST-04": ((_RECORDS, 97, "knowledge_state: KnowledgeState"),),
    "ST-05": ((_BASE, 211, "if digest != expected_digest:"),),
    "ST-06": ((_BASE, 211, "if digest != expected_digest:"),),
    "ST-07": (
        (_CANONICALIZATION, 255, "if version is None or version not in _REGISTRY:"),
        (_BASE, 209, "get_scheme(self.canonicalization_version)"),
    ),
    "ST-08": ((_RECORD_PAIR, 96, "else RecordPairKind.CRITICAL_CONFLICT"),),
    "ST-09": ((_BASE, 205, "if digest is None:"),),
    "ST-11": ((_RECORDS, 102, "observation_revision: int | None = None"),),
    "ST-12": (
        (_BASE, 187, "include=set(self._COVERED_FIELDS)"),
        (_RECORDS, 102, "observation_revision: int | None = None"),
    ),
}

#: The design §3 catalog, in table order. ``ST-10`` is absent by design (merged into
#: ``ST-01``, §3 M6) and its absence is asserted, not assumed.
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


def _guard(fault_id: str) -> str:
    """The measured ``path:line`` guard citation(s) for ``fault_id``."""
    return "; ".join(f"{path}:{line}" for path, line, _ in _GUARD_SITES[fault_id])


def _witness_ref(composite: CompositeState) -> str:
    """A deterministic reference to the otherwise-valid witness a fault mutated."""
    return f"{composite.composite_state_id}@{composite.canonical_digest}"


def _error_disposition(exc: ValidationError) -> str:
    """Structural disposition of a rejection: sorted ``<error-type>@<field path>``.

    Derived from the component's own error surface, so a mutant that stops raising, or
    raises for a *different* field, changes the observed string and turns the fault row
    into a ``DEVIATION`` rather than silently staying ``MET``.
    """
    parts = sorted(
        f"{err['type']}@{'.'.join(str(part) for part in err['loc'])}"
        for err in exc.errors()
    )
    return f"ValidationError[{','.join(parts)}]"


def _integrity_disposition(exc: ValidationError) -> str:
    """Structural disposition naming the wrapped **cause** class (design §3 M3).

    The design §3 Expected column is literally ``ValidationError(cause=ArtifactIntegrityError)``:
    a bare ``ValidationError`` check would also pass for an ordinary type / missing-field
    rejection, so the cause class is read out of pydantic's ``ctx["error"]`` and compared.
    """
    causes = sorted(
        type(err["ctx"]["error"]).__name__
        for err in exc.errors()
        if isinstance(err.get("ctx"), dict) and "error" in err["ctx"]
    )
    return f"ValidationError(cause={','.join(causes) or '<none>'})"


# ---------------------------------------------------------------------------
# anti-phantom: the recorded guard lines are measured, not asserted
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fault_id", sorted(_GUARD_SITES))
def test_guard_code_lines_are_measured_not_phantom(fault_id: str) -> None:
    """Every ``injection_point`` this suite writes still names the real guard line.

    Anti-phantom drift lock (design §0.5-1): a citation is only evidence while the cited
    line still holds the cited code. Without this, a refactor silently converts the whole
    fault timeline into fabricated provenance.
    """
    for path, line, token in _GUARD_SITES[fault_id]:
        lines = (_REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
        assert 1 <= line <= len(lines), f"{fault_id}: {path}:{line} is past EOF"
        assert token in lines[line - 1], (
            f"{fault_id}: guard citation drifted — {path}:{line} no longer contains "
            f"{token!r} (found {lines[line - 1].strip()!r})"
        )


def test_catalog_is_the_design_section_3_table() -> None:
    """The executed catalog is exactly the design §3 table — 11 faults, no ``ST-10``."""
    assert len(_CATALOG) == 11
    assert set(_CATALOG) == set(_GUARD_SITES)
    assert "ST-10" not in _CATALOG, "ST-10 is merged into ST-01 (design §3 M6)"


# ---------------------------------------------------------------------------
# ST-01..ST-04, ST-11 — construction-surface faults (L1-adjacent, re-framed)
# ---------------------------------------------------------------------------


def test_st_01_dropped_dimension_is_not_derived_from_its_neighbours(
    l2_fault_timeline,
) -> None:
    """ST-01 — drop a mandatory dimension + **silent-derivation probe** (§3 M6, ST-10 merged).

    VER-002-001 line 1024: "no dimension is silently derived from another except through an
    explicit CPL invariant and owned transition". The four surviving dimensions of the §14
    row-1 witness are exactly the ones that would *imply* a Broker state under any derivation
    rule, so a component that derived it would construct successfully. The refusal names the
    dropped dimension and **only** it — no default, no neighbour-derived value.
    """
    witness = issue_composite()  # both-ways (b): the unmutated witness is valid
    assert witness.broker_order_state is BrokerOrderState.NONE_OBSERVED

    kwargs = composite_required_kwargs()
    kwargs.pop("broker_order_state")
    with pytest.raises(ValidationError) as caught:
        CompositeState.issue(scheme=SCHEME, **kwargs)

    observed = _error_disposition(caught.value)
    # the silent-derivation probe: refusal is the ONLY outcome, and it is attributed to
    # the dropped dimension alone (a derived default would have produced no error at all).
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
    """ST-02 — substitute ``None`` for the ``NONE`` state (``NONE != None``).

    ``TransmissionAttemptState.NONE`` ("no attempt yet") is a legitimate, load-bearing
    value; a missing / ``None`` field is the absence of knowledge. Collapsing the two would
    let "we never attempted" and "we do not know" share one representation.
    """
    witness = issue_composite(
        transmission_attempt_state=TransmissionAttemptState.NONE
    )  # both-ways (b): the NONE *state* is constructible
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
    """ST-03 — put one dimension's value into another dimension's field.

    Global string-value distinctness across the five dimension enums makes a swap fail
    ``StrEnum`` coercion, so a five-coordinate composite cannot be silently collapsed into
    a single order-status enumeration.
    """
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
    """ST-11 — a non-numeric token in the ledger-placement scalar ``observation_revision``.

    The self-excluded meta field is still schema-checked: a corrupted serial form cannot
    smuggle a non-integer revision past reconstruction.
    """
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


# ---------------------------------------------------------------------------
# ST-05, ST-06, ST-07, ST-09, ST-12 — L2-new reconstruction faults
# ---------------------------------------------------------------------------


def test_st_05_covered_content_tampered_with_a_retained_digest(
    l2_fault_timeline,
) -> None:
    """ST-05 — mutate covered content while retaining the original digest (**L2-new**).

    The serial form of an already-issued observation is edited in one dimension and
    re-presented with its old digest — the classic "same record, quietly changed" forgery.
    Reconstruction recomputes the digest over the covered content and refuses.
    """
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
    """ST-06 — substitute the digest while retaining covered content (**L2-new**).

    The symmetric counterpart of ST-05: an attacker who cannot change the content instead
    re-labels it with another record's digest.
    """
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
    """ST-07 — an unregistered ``canonicalization_version`` (**L2-new; §5 H-4 dependent**).

    A record whose scheme cannot be resolved has an *unverifiable* digest. Before the §5
    H-4 hardening the lookup escaped as a raw ``KeyError`` — an unhandled lookup error, not
    a fail-closed refusal — and this row would have been recorded as a ``DEVIATION``
    (design §3 M4). Post-hardening the failure is an ``ArtifactIntegrityError``, so the
    record is *unconstructable*.
    """
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
    """ST-09 — a lifecycle contradiction: ``ISSUED`` status carrying a null digest (**L2-new**).

    ``DRAFT`` is the only state in which the digest is legitimately absent. An ``ISSUED``
    record with no digest is a ledger citizen whose identity can never be verified, so the
    contradiction is refused at construction rather than represented.
    """
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
    """ST-12 — **positive canary**: a self-excluded field change leaves the record identical.

    The both-ways companion of ST-05/ST-06 (design §2.3 / §8.4): the integrity guard must
    refuse tampering **and** admit a legitimate ledger-placement change. If ``observation_revision``
    leaked into the digest preimage, the same observation committed at two ledger positions
    would produce two different digests — a false ``CRITICAL_CONFLICT`` on every replay.
    A suite that only ever asserts refusals cannot tell a working guard from a broken one.
    """
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


# ---------------------------------------------------------------------------
# ST-08 — same identity, different bytes
# ---------------------------------------------------------------------------


def test_st_08_same_id_different_bytes_is_a_critical_conflict(
    l2_fault_timeline,
) -> None:
    """ST-08 — re-publish the same ``composite_state_id`` with different content.

    Identity is *independent* of the digest, so the append-only log can represent the
    conflict instead of silently letting the later write win. The authoritative state
    inspected here is the classification verdict itself.
    """
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
    # both-ways (b): an identical re-presentation is a duplicate, not a conflict.
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
