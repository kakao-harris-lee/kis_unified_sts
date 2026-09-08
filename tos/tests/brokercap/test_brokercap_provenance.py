"""Provenance-class schema half of upstream plan Phase 4 작업 3 (plan §5-A).

Covers ``tos.brokercap.routing``'s :class:`ProvenanceClass` / :class:`ClaimKind` /
:class:`CapabilityProvenance` / :func:`provenance_admits_claim` per the ratified slice plan
(``docs/plans/2026-09-07-tos-phase4-capability-axes-slice-plan.md`` §5-A): the kernel carries
only the **class names**, not concrete source identities (no ``open-trading-api`` literal, no
``shared.kis`` literal — instance concern). Data-filling from a real P0-2 probe run is **out of
this slice's scope** (§5-A: "데이터 채움(P0-2 캠페인 결속)은 이 슬라이스 밖").

TDD: this file is authored *before* the provenance names exist in
``tos/src/tos/brokercap/routing.py``, so the first run is RED on the import — expected.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pydantic
import pytest
from hypothesis import given, settings
from tos.brokercap.records import BrokerEvidenceRef
from tos.brokercap.routing import (
    CapabilityProvenance,
    ClaimKind,
    ProbeManifest,
    ProvenanceClass,
    provenance_admits_claim,
)

# ---------------------------------------------------------------------------
# enum member-count / verbatim pins (plan §5-A / upstream plan Phase 4 작업 3)
# ---------------------------------------------------------------------------


def test_provenance_class_four_verbatim() -> None:
    """ProvenanceClass carries the upstream plan's four class names verbatim (§5-A): the
    official SDK, official documentation, the internal client, and a controlled GET probe —
    no concrete source identity (e.g. no ``open-trading-api`` / ``shared.kis`` literal).
    """
    assert [p.value for p in ProvenanceClass] == [
        "OFFICIAL_SDK",
        "OFFICIAL_DOCUMENT",
        "INTERNAL_CLIENT",
        "CONTROLLED_GET_PROBE",
    ]


def test_claim_kind_three_verbatim() -> None:
    """ClaimKind is the small closed StrEnum §5-A asks ``provenance_admits_claim`` to gate
    on (e.g. MEASURED_BOUND / DOCUMENTED_LIMIT / REAL_ORDER_CAPABILITY)."""
    assert [c.value for c in ClaimKind] == [
        "MEASURED_BOUND",
        "DOCUMENTED_LIMIT",
        "REAL_ORDER_CAPABILITY",
    ]


# ---------------------------------------------------------------------------
# CapabilityProvenance — combined validator: CONTROLLED_GET_PROBE <=> probe_manifest
# ---------------------------------------------------------------------------


def _manifest() -> ProbeManifest:
    return ProbeManifest(
        allowed_methods=("GET",),
        retention="180d",
        ttl="24h",
        provenance="official-spec",
    )


def test_controlled_get_probe_without_manifest_is_rejected() -> None:
    """(negative, direction 1) CONTROLLED_GET_PROBE requires a probe_manifest."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityProvenance(
            provenance_class=ProvenanceClass.CONTROLLED_GET_PROBE,
            source_ref="probe-endpoint-1",
            captured_at="2026-09-07",
        )


def test_controlled_get_probe_with_manifest_is_accepted() -> None:
    """(positive) CONTROLLED_GET_PROBE + a manifest constructs cleanly."""
    provenance = CapabilityProvenance(
        provenance_class=ProvenanceClass.CONTROLLED_GET_PROBE,
        source_ref="probe-endpoint-1",
        captured_at="2026-09-07",
        probe_manifest=_manifest(),
    )
    assert provenance.probe_manifest is not None


@pytest.mark.parametrize(
    "provenance_class",
    [
        ProvenanceClass.OFFICIAL_SDK,
        ProvenanceClass.OFFICIAL_DOCUMENT,
        ProvenanceClass.INTERNAL_CLIENT,
    ],
)
def test_non_probe_class_with_manifest_is_rejected(
    provenance_class: ProvenanceClass,
) -> None:
    """(negative, direction 2) Only CONTROLLED_GET_PROBE may carry a probe_manifest — the
    other three classes must have it None."""
    with pytest.raises(pydantic.ValidationError):
        CapabilityProvenance(
            provenance_class=provenance_class,
            source_ref="doc-ref-1",
            captured_at="2026-09-07",
            probe_manifest=_manifest(),
        )


@pytest.mark.parametrize(
    "provenance_class",
    [
        ProvenanceClass.OFFICIAL_SDK,
        ProvenanceClass.OFFICIAL_DOCUMENT,
        ProvenanceClass.INTERNAL_CLIENT,
    ],
)
def test_non_probe_class_without_manifest_is_accepted(
    provenance_class: ProvenanceClass,
) -> None:
    """(positive) The other three classes construct cleanly with probe_manifest absent."""
    provenance = CapabilityProvenance(
        provenance_class=provenance_class,
        source_ref="doc-ref-1",
        captured_at="2026-09-07",
    )
    assert provenance.probe_manifest is None


@pytest.mark.parametrize("missing", ["provenance_class", "source_ref", "captured_at"])
def test_capability_provenance_requires_every_identity_field(missing: str) -> None:
    """provenance_class / source_ref / captured_at are required (no ``| None`` default,
    §5-A's typed listing) — a partially-specified provenance is not constructible."""
    kwargs: dict[str, object] = {
        "provenance_class": ProvenanceClass.OFFICIAL_SDK,
        "source_ref": "doc-ref-1",
        "captured_at": "2026-09-07",
    }
    del kwargs[missing]
    with pytest.raises(pydantic.ValidationError):
        CapabilityProvenance(**kwargs)


def test_capability_provenance_is_frozen() -> None:
    provenance = CapabilityProvenance(
        provenance_class=ProvenanceClass.OFFICIAL_SDK,
        source_ref="doc-ref-1",
        captured_at="2026-09-07",
    )
    with pytest.raises(pydantic.ValidationError):
        provenance.source_ref = "changed"  # type: ignore[misc]


def test_capability_provenance_carries_evidence_ref() -> None:
    provenance = CapabilityProvenance(
        provenance_class=ProvenanceClass.OFFICIAL_SDK,
        source_ref="doc-ref-1",
        captured_at="2026-09-07",
        evidence_ref=BrokerEvidenceRef(evidence_id="ev-1"),
    )
    assert provenance.evidence_ref is not None
    assert provenance.evidence_ref.evidence_id == "ev-1"


# ---------------------------------------------------------------------------
# provenance_admits_claim — structural denial + fail-closed None handling
# ---------------------------------------------------------------------------


def _provenance(
    provenance_class: ProvenanceClass,
    *,
    evidence_ref: BrokerEvidenceRef | None = None,
) -> CapabilityProvenance:
    return CapabilityProvenance(
        provenance_class=provenance_class,
        source_ref="ref-1",
        captured_at="2026-09-07",
        evidence_ref=evidence_ref,
        probe_manifest=(
            _manifest()
            if provenance_class is ProvenanceClass.CONTROLLED_GET_PROBE
            else None
        ),
    )


_WITH_EVIDENCE = BrokerEvidenceRef(evidence_id="ev-1")


@pytest.mark.parametrize("provenance_class", list(ProvenanceClass))
def test_real_order_capability_never_admitted(
    provenance_class: ProvenanceClass,
) -> None:
    """(structural) No provenance — even one carrying evidence — ever admits a
    REAL_ORDER_CAPABILITY claim (§5-A: 'REAL_ORDER 관련 claim 을 admit 하지 않는다')."""
    provenance = _provenance(provenance_class, evidence_ref=_WITH_EVIDENCE)
    assert provenance_admits_claim(provenance, ClaimKind.REAL_ORDER_CAPABILITY) is False


@pytest.mark.parametrize(
    "provenance_class",
    [ProvenanceClass.OFFICIAL_DOCUMENT, ProvenanceClass.INTERNAL_CLIENT],
)
def test_document_and_internal_client_never_admit_measured_bound(
    provenance_class: ProvenanceClass,
) -> None:
    """(§5-A) OFFICIAL_DOCUMENT / INTERNAL_CLIENT never admit a MEASURED_BOUND claim — a
    document is not a measurement, even when an evidence_ref happens to be attached."""
    provenance = _provenance(provenance_class, evidence_ref=_WITH_EVIDENCE)
    assert provenance_admits_claim(provenance, ClaimKind.MEASURED_BOUND) is False


@pytest.mark.parametrize(
    "provenance_class",
    [ProvenanceClass.OFFICIAL_SDK, ProvenanceClass.CONTROLLED_GET_PROBE],
)
def test_measured_bound_admitted_only_with_evidence(
    provenance_class: ProvenanceClass,
) -> None:
    """(§5-A 'the rest admit only when evidence_ref is not None') OFFICIAL_SDK /
    CONTROLLED_GET_PROBE can admit MEASURED_BOUND, but only when evidence_ref is present.
    """
    without_evidence = _provenance(provenance_class, evidence_ref=None)
    assert provenance_admits_claim(without_evidence, ClaimKind.MEASURED_BOUND) is False
    with_evidence = _provenance(provenance_class, evidence_ref=_WITH_EVIDENCE)
    assert provenance_admits_claim(with_evidence, ClaimKind.MEASURED_BOUND) is True


@pytest.mark.parametrize("provenance_class", list(ProvenanceClass))
def test_documented_limit_admitted_only_with_evidence(
    provenance_class: ProvenanceClass,
) -> None:
    """(§5-A) DOCUMENTED_LIMIT is not excluded by class, but still fails closed on a missing
    evidence_ref, for every provenance class."""
    without_evidence = _provenance(provenance_class, evidence_ref=None)
    assert (
        provenance_admits_claim(without_evidence, ClaimKind.DOCUMENTED_LIMIT) is False
    )
    with_evidence = _provenance(provenance_class, evidence_ref=_WITH_EVIDENCE)
    assert provenance_admits_claim(with_evidence, ClaimKind.DOCUMENTED_LIMIT) is True


@pytest.mark.parametrize("claim_kind", list(ClaimKind))
def test_none_provenance_fails_closed(claim_kind: ClaimKind) -> None:
    assert provenance_admits_claim(None, claim_kind) is False


@pytest.mark.parametrize("provenance_class", list(ProvenanceClass))
def test_none_claim_kind_fails_closed(provenance_class: ProvenanceClass) -> None:
    provenance = _provenance(provenance_class, evidence_ref=_WITH_EVIDENCE)
    assert provenance_admits_claim(provenance, None) is False


def test_both_none_fails_closed() -> None:
    assert provenance_admits_claim(None, None) is False


# ---------------------------------------------------------------------------
# hypothesis — REAL_ORDER_CAPABILITY universal denial over the full product
# ---------------------------------------------------------------------------

_PROVENANCE_CLASS_ST = st.sampled_from(list(ProvenanceClass))
_HAS_EVIDENCE_ST = st.booleans()


@given(provenance_class=_PROVENANCE_CLASS_ST, has_evidence=_HAS_EVIDENCE_ST)
@settings(max_examples=200)
def test_hypothesis_real_order_capability_denied_over_full_product(
    provenance_class: ProvenanceClass, has_evidence: bool
) -> None:
    """(hypothesis, structural) Over every provenance class x evidence-presence combination,
    a REAL_ORDER_CAPABILITY claim is never admitted."""
    provenance = _provenance(
        provenance_class,
        evidence_ref=_WITH_EVIDENCE if has_evidence else None,
    )
    assert provenance_admits_claim(provenance, ClaimKind.REAL_ORDER_CAPABILITY) is False
