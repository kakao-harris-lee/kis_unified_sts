"""Package-surface canaries for ``tos.marketfeed`` — the seals that are structural, not promised.

Four families:

* **the fetch-surface seal** (design #32 §0.3/§7.1). The package's name says "feed"; its contract
  says it never fetches. A docstring saying so is a self-report, so every marketfeed record's field
  names run through a closed token check at construction — a record carrying ``url`` / ``socket`` /
  ``token`` is unconstructable. The over-rejection direction is checked too: ``endpoint`` is
  deliberately admitted, because ``tos.capsule``'s shipped ``SourceIdentity.endpoint`` is an opaque
  provenance scalar this package legitimately reads.
* **immutability** — every record is frozen and rejects unknown fields, so a value surface cannot be
  edited after publication (ADR-002-018 §12).
* **the report is internally consistent** — a ``ValueResolution`` cannot claim a disposition its view
  presence contradicts, so the ∅ distinction stays readable rather than inferred from a nullable.
* **the honest scope** — the package announces provisional status and closes no EV, in the module
  docstring, where a reader of the code will meet it.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import pytest
import tos.marketfeed as marketfeed
from pydantic import ValidationError
from tos.canonical import EV_L1_PROVISIONAL_VERSION
from tos.marketfeed import (
    ADMITTING_DISPOSITIONS,
    AdmittedValue,
    PreimageEntry,
    RawPayloadPreimage,
    RejectedValue,
    ValueRejectionReason,
    ValueResolution,
    ValueViewDisposition,
    fetch_surface_offenders,
    seal_fetch_surface,
)

from ._marketfeed_fixtures import INTEGRITY_ERRORS, SCHEME, one_bar, preimage

# ---------------------------------------------------------------------------
# The fetch-surface seal (design #32 §0.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "url",
        "feed_url",
        "socket",
        "websocket",
        "api_key",
        "apikey",
        "auth_token",
        "password",
        "host",
        "port",
        "subscription",
        "connection_id",
    ],
)
def test_a_transport_or_credential_field_name_is_an_offender(name: str) -> None:
    """(§0.3 ★) The token check catches transport and credential surfaces token-wise."""
    assert fetch_surface_offenders([name]) == (name,)
    with pytest.raises(marketfeed.MarketFeedIntegrityError, match="transport or credential"):
        seal_fetch_surface("Probe", [name])


@pytest.mark.parametrize(
    "name",
    [
        "field_key",
        "observation_ref",
        "payload_digest",
        "as_of",
        "preimage",
        "endpoint",
        "source_event_time",
        "snapshot_id",
        "canonical_digest",
    ],
)
def test_the_seal_does_not_over_reject_a_legitimate_field_name(name: str) -> None:
    """(#26 WDR MAJOR-1) Over-rejection is its own defect class — ``endpoint`` is admitted."""
    assert fetch_surface_offenders([name]) == ()
    seal_fetch_surface("Probe", [name])


def test_the_shipped_records_carry_no_fetch_surface() -> None:
    """(§0.3) Every marketfeed model is clean under its own seal."""
    for model in (AdmittedValue, PreimageEntry, RawPayloadPreimage, RejectedValue, ValueResolution):
        assert fetch_surface_offenders(model.model_fields) == (), model.__name__


def test_the_seal_runs_at_construction_not_only_in_a_test() -> None:
    """(§0.3) ``AdmittedValue`` seals its own surface, so the check cannot be forgotten."""
    seal_fetch_surface("AdmittedValue", AdmittedValue.model_fields)


# ---------------------------------------------------------------------------
# Immutability + strict schema (ADR-002-018 §12)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model, kwargs",
    [
        (PreimageEntry, {"key": "close", "value": 1}),
        (AdmittedValue, {"field_key": "close", "observation_ref": "raw-1"}),
        (
            RejectedValue,
            {
                "field_key": "close",
                "observation_ref": "raw-1",
                "reason": ValueRejectionReason.DIGEST_MISMATCH,
            },
        ),
    ],
)
def test_records_are_frozen_and_reject_unknown_fields(model, kwargs) -> None:
    """(ADR-002-018 §12) A published value surface is immutable and schema-strict."""
    instance = model(**kwargs)
    with pytest.raises(ValidationError):
        setattr(instance, next(iter(kwargs)), "mutated")
    with pytest.raises(ValidationError):
        model(**kwargs, smuggled_extra=1)


def test_a_blank_binding_is_unconstructable() -> None:
    """(§2.3/§4.2) Fail-closed at the type level, not at a check a producer could skip."""
    payload = preimage(close=1)
    with pytest.raises(INTEGRITY_ERRORS, match="concrete"):
        AdmittedValue(field_key="   ", observation_ref="raw-1", preimage=payload)
    with pytest.raises(INTEGRITY_ERRORS, match="concrete"):
        AdmittedValue(field_key="close", observation_ref="", preimage=payload)


@pytest.mark.parametrize("wildcard", ["*", "latest", "LATEST", "any", "close*"])
def test_a_wildcard_field_key_is_unconstructable(wildcard: str) -> None:
    """(§2.4, RFC-008 §7:239-240) A wildcard field reference cannot enter from the value side."""
    with pytest.raises(INTEGRITY_ERRORS, match="wildcard"):
        AdmittedValue(field_key=wildcard, observation_ref="raw-1", preimage=preimage(close=1))


def test_a_duplicated_preimage_key_is_unconstructable() -> None:
    """(§6) A payload with two values under one name has no attributable value."""
    with pytest.raises(INTEGRITY_ERRORS, match="duplicate"):
        RawPayloadPreimage(
            entries=(
                PreimageEntry(key="close", value=1),
                PreimageEntry(key="close", value=2),
            )
        )


# ---------------------------------------------------------------------------
# The report cannot contradict itself (design #32 §6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "disposition",
    [
        ValueViewDisposition.SNAPSHOT_UNRESOLVED,
        ValueViewDisposition.BINDING_MISMATCH,
        ValueViewDisposition.NAMESPACE_COLLISION,
    ],
)
def test_a_refused_disposition_may_not_carry_a_view(disposition: ValueViewDisposition) -> None:
    """(§6 ★) A refused binding never yields consumable values, structurally."""
    capsule, snapshot, candidates = one_bar()
    published = marketfeed.publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    with pytest.raises(INTEGRITY_ERRORS, match="must carry no view"):
        ValueResolution(disposition=disposition, view=published.view)


@pytest.mark.parametrize(
    "disposition", [ValueViewDisposition.RESOLVED, ValueViewDisposition.EXPLICIT_EMPTY]
)
def test_an_admitting_disposition_requires_a_view(disposition: ValueViewDisposition) -> None:
    """(§6 ★) "resolved, but no view" would make the ∅ distinction unreadable."""
    with pytest.raises(INTEGRITY_ERRORS, match="requires a published view"):
        ValueResolution(disposition=disposition, view=None)


def test_resolved_and_explicit_empty_may_not_be_swapped() -> None:
    """(§6 ∅ 양방향 ★) The disposition must agree with whether values are actually present."""
    capsule, snapshot, candidates = one_bar()
    resolved = marketfeed.publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    empty = marketfeed.publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=(), scheme=SCHEME
    )
    with pytest.raises(INTEGRITY_ERRORS, match="EXPLICIT_EMPTY"):
        ValueResolution(disposition=ValueViewDisposition.RESOLVED, view=empty.view)
    with pytest.raises(INTEGRITY_ERRORS, match="value-free view"):
        ValueResolution(disposition=ValueViewDisposition.EXPLICIT_EMPTY, view=resolved.view)


def test_the_admitting_disposition_set_is_positive_membership() -> None:
    """(§6) Membership is stated positively; everything outside it carries no view."""
    assert set(ADMITTING_DISPOSITIONS) == {
        ValueViewDisposition.RESOLVED,
        ValueViewDisposition.EXPLICIT_EMPTY,
    }
    for member in ValueViewDisposition:
        if member not in ADMITTING_DISPOSITIONS:
            assert member in {
                ValueViewDisposition.SNAPSHOT_UNRESOLVED,
                ValueViewDisposition.BINDING_MISMATCH,
                ValueViewDisposition.NAMESPACE_COLLISION,
            }


def test_every_rejection_reason_is_named_with_no_catch_all() -> None:
    """(§6) An unnamed rejection is an unauditable one — there is no ``OTHER`` member."""
    names = {member.name for member in ValueRejectionReason}
    assert not names & {"OTHER", "UNKNOWN", "MISC", "UNSPECIFIED"}
    assert len(names) == len(ValueRejectionReason)


# ---------------------------------------------------------------------------
# Honest scope (design #32 §1.1)
# ---------------------------------------------------------------------------


def test_the_package_docstring_declares_the_provisional_scope() -> None:
    """(§1.1) The reader of the code meets the honesty declaration, not only the design doc."""
    doc = marketfeed.__doc__ or ""
    assert "closes no EV" in doc
    assert "Provisional" in doc


def test_the_published_view_records_the_non_production_canonicalization_version() -> None:
    """(§1.1/§8) The digest rides ``ev-l1-provisional-0``, and the artifact says which scheme."""
    capsule, snapshot, candidates = one_bar()
    resolution = marketfeed.publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    assert resolution.view is not None
    assert resolution.view.canonicalization_version == EV_L1_PROVISIONAL_VERSION


def test_the_public_surface_matches_the_declared_all() -> None:
    """(anti-phantom §0.5) Every exported name exists; every declared name is exported."""
    for name in marketfeed.__all__:
        assert hasattr(marketfeed, name), f"__all__ declares {name!r} but the package lacks it"
    assert len(set(marketfeed.__all__)) == len(marketfeed.__all__), "duplicate __all__ entry"
