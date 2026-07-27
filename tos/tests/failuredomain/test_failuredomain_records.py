"""§5 / §4.3 / §4.4 record shapes + the §6.4 anchor-drift property (design #27 §6).

Seals, per design #27 §6:

  (i)   frozen immutability — no update / delete path on any record;
  (ii)  the §2.2 all-false authority block — any ``True`` flag makes the record unconstructable;
  (iii) ``isolation_kind is None`` reads fail-closed as ``COMMON_MODE`` (§2.1E);
  (iv)  unknown / undocumented sharing is recorded in ``shared_dependencies`` and independence is
        **structurally unforgeable** — ADR §5 line 130 "It SHALL NOT be recorded as independent
        with an explanatory footnote", realized by there being no independence field at all;
  (v)   the §6.4 anchor-drift property pinning ``SafetyCellScope``'s seven fields to ADR §4.3 line
        92, and the matrix row's eleven fields to the ADR §5 line 116-132 table.

The digest same-id / different-bytes forgery property is deliberately **not** applied: Q1 (design
#27 §0.4b/§3.1) adopts plain frozen records, not digest-bound artifacts.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.failuredomain import (
    ArtifactIntegrityError,
    FailureBehaviorKind,
    FailureDomainAllocationEntry,
    FailureDomainAuthorityEffect,
    FailureDomainKind,
    IsolationClaim,
    IsolationKind,
    SafetyCellScope,
    unproven_isolation_is_common_mode,
)

from ._failuredomain_strategies import (
    CLAIM_FIELDS,
    DOMAIN_SET,
    MATRIX_FIELDS,
    clean_cell,
    clean_claim,
    clean_entry,
)

# --- manually-transcribed regression anchors (design #27 §6.4) ---------------

#: ADR-002-009 §4.3 line 92, transcribed by hand: "A Safety Cell SHALL have an explicit account,
#: portfolio, broker, environment, authority-epoch, writer-epoch, and egress scope."
_ADR_43_CELL_SCOPES: frozenset[str] = frozenset(
    {
        "account",
        "portfolio",
        "broker",
        "environment",
        "authority_epoch",
        "writer_epoch",
        "egress_scope",
    }
)

#: ADR §5 line 116-132 matrix table, transcribed by hand (11 rows, ADR order).
_ADR_5_MATRIX_FIELDS: frozenset[str] = frozenset(MATRIX_FIELDS)

#: ADR §4.4 line 96, transcribed by hand: "Every claim SHALL state assumptions, excluded common
#: modes, enforcement mechanisms, verification cases, and residual risk."
_ADR_44_CLAIM_FIELDS: frozenset[str] = frozenset(CLAIM_FIELDS)

#: Any field name that could express a footnote-qualified independence assertion (ADR §5 line 130).
_FORBIDDEN_INDEPENDENCE_FIELDS: tuple[str, ...] = (
    "independent",
    "is_independent",
    "independence",
    "independent_with_footnote",
    "footnote",
    "exception",
    "waiver",
    "established",
    "isolation_established",
    "proven",
)


# --- (v) §6.4 anchor drift ---------------------------------------------------


def test_safety_cell_scope_matches_the_adr_43_anchor() -> None:
    """(§6.4 anchor drift) SafetyCellScope's seven fields == ADR §4.3 line 92's seven scopes."""
    assert set(SafetyCellScope.model_fields) == _ADR_43_CELL_SCOPES
    assert len(SafetyCellScope.model_fields) == 7


@pytest.mark.parametrize("scope", sorted(_ADR_43_CELL_SCOPES))
def test_each_cell_scope_is_an_opaque_injected_string(scope: str) -> None:
    """(§2.1D) Every §4.3 scope is an opaque ``str | None`` — never interpreted, never numeric."""
    assert SafetyCellScope.model_fields[scope].annotation == (str | None)
    assert getattr(SafetyCellScope(), scope) is None


def test_matrix_row_matches_the_adr_5_anchor_plus_isolation_kind() -> None:
    """(§6.4 anchor drift) The row is exactly ADR §5's 11 + isolation_kind + the §2.2 block."""
    fields = set(FailureDomainAllocationEntry.model_fields)
    assert fields >= _ADR_5_MATRIX_FIELDS
    assert fields - _ADR_5_MATRIX_FIELDS == {"isolation_kind", "authority_effect"}
    assert len(_ADR_5_MATRIX_FIELDS) == 11
    assert len(fields) == 13


def test_claim_matches_the_adr_44_anchor() -> None:
    """(§6.4 anchor drift) The claim is exactly ADR §4.4's five fields + the §2.2 block."""
    fields = set(IsolationClaim.model_fields)
    assert fields >= _ADR_44_CLAIM_FIELDS
    assert fields - _ADR_44_CLAIM_FIELDS == {"authority_effect"}
    assert len(_ADR_44_CLAIM_FIELDS) == 5


# --- (i) frozen immutability -------------------------------------------------


@pytest.mark.parametrize(
    ("record", "field"),
    [
        (clean_entry(), "residual_risk"),
        (clean_claim(), "residual_risk"),
        (clean_cell(), "account"),
        (FailureDomainAuthorityEffect(), "grants_authority"),
    ],
)
def test_records_are_frozen(record: object, field: str) -> None:
    """(i) Frozen is the record-level realization of append-only — no in-place mutation."""
    with pytest.raises(ValueError):
        setattr(record, field, "mutated")


@pytest.mark.parametrize(
    "model",
    [
        FailureDomainAllocationEntry,
        IsolationClaim,
        SafetyCellScope,
        FailureDomainAuthorityEffect,
    ],
)
def test_records_expose_no_update_or_delete_method(model: type) -> None:
    """(i) ``tos.failuredomain`` defines no update / delete / mutate affordance on any record.

    Only attributes this package authors are considered — inherited pydantic machinery (e.g. the
    deprecated v1-compat ``update_forward_refs``) is framework surface, not a mutation path
    ``tos.failuredomain`` offers.
    """
    authored: set[str] = set()
    for klass in model.__mro__:
        if getattr(klass, "__module__", "").startswith("tos.failuredomain"):
            authored |= set(vars(klass))
    for verb in ("update", "delete", "mutate", "apply", "set_", "amend"):
        offenders = sorted(
            name
            for name in authored
            if not name.startswith("__") and name.startswith(verb)
        )
        assert offenders == [], f"{model.__name__} exposes {offenders}"


@pytest.mark.parametrize(
    "model",
    [
        FailureDomainAllocationEntry,
        IsolationClaim,
        SafetyCellScope,
        FailureDomainAuthorityEffect,
    ],
)
def test_records_forbid_extra_fields(model: type) -> None:
    """(extra=forbid) An unknown field cannot be smuggled onto a document-level record."""
    with pytest.raises(ValueError):
        model(unexpected_field="x")


# --- (ii) the §2.2 all-false authority block ---------------------------------


def test_authority_effect_defaults_to_all_false() -> None:
    """(ii / §2.2) Every declared authority flag defaults false — the block grants nothing."""
    effect = FailureDomainAuthorityEffect()
    assert len(FailureDomainAuthorityEffect.model_fields) == 6
    for name in FailureDomainAuthorityEffect.model_fields:
        assert getattr(effect, name) is False


@pytest.mark.parametrize("flag", sorted(FailureDomainAuthorityEffect.model_fields))
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """(ii / §2.2) ADR §1 line 15/32 — a coordinate that granted anything cannot be built."""
    with pytest.raises(ValueError):
        FailureDomainAuthorityEffect(**{flag: True})
    assert issubclass(ArtifactIntegrityError, ValueError)


@pytest.mark.parametrize("flag", sorted(FailureDomainAuthorityEffect.model_fields))
def test_a_record_carrying_a_true_flag_is_unconstructable(flag: str) -> None:
    """(ii / §2.2) The rejection propagates: neither record can wrap a granting block."""
    for builder in (clean_entry, clean_claim):
        with pytest.raises(ValueError):
            builder(authority_effect=FailureDomainAuthorityEffect(**{flag: True}))


def test_the_authority_block_names_the_six_denied_effects() -> None:
    """(§2.2) The six flags are the ADR §1 line 15/30/32 + §4.3 line 92 denials, by name."""
    assert set(FailureDomainAuthorityEffect.model_fields) == {
        "grants_authority",
        "releases_capacity",
        "transmits_to_broker",
        "establishes_permission",
        "proves_isolation",
        "enforces_containment",
    }


# --- (iii) isolation_kind fail-closed ---------------------------------------


def test_unclassified_isolation_kind_reads_as_common_mode() -> None:
    """(iii / §2.1E) ``None`` is never PHYSICAL or LOGICAL — it is COMMON_MODE, fail-closed."""
    entry = clean_entry(isolation_kind=None)
    assert entry.isolation_kind is None
    assert entry.effective_isolation_kind() is IsolationKind.COMMON_MODE


@pytest.mark.parametrize("kind", list(IsolationKind))
def test_declared_isolation_kind_is_returned_verbatim(kind: IsolationKind) -> None:
    """(iii, both-ways) A positively declared classification is passed through unchanged."""
    assert clean_entry(isolation_kind=kind).effective_isolation_kind() is kind


@given(kind=st.sampled_from([*IsolationKind, None]))
def test_property_effective_kind_is_never_physical_or_logical_by_default(
    kind: IsolationKind | None,
) -> None:
    """(iii property) PHYSICAL / LOGICAL are reachable only by explicit declaration."""
    effective = clean_entry(isolation_kind=kind).effective_isolation_kind()
    if kind is None:
        assert effective is IsolationKind.COMMON_MODE
    else:
        assert effective is kind


# --- (iv) unknown sharing / unforgeable independence -------------------------


@pytest.mark.parametrize("forbidden", _FORBIDDEN_INDEPENDENCE_FIELDS)
def test_no_record_can_express_a_footnoted_independence_claim(forbidden: str) -> None:
    """(iv / ADR §5 line 130) There is no independence / footnote / waiver field to set."""
    assert forbidden not in FailureDomainAllocationEntry.model_fields
    assert forbidden not in IsolationClaim.model_fields
    with pytest.raises(ValueError):
        clean_entry(**{forbidden: True})


def test_unknown_sharing_is_recorded_and_stays_common_mode() -> None:
    """(iv / ADR §5 line 130) An undocumented sharing is recorded and never becomes independent.

    The only route to independence is a positively complete ADR §4.4 claim; a row that records
    an unknown sharing but supplies no such claim is common-mode by
    :func:`unproven_isolation_is_common_mode` — there is no second route.
    """
    entry = clean_entry(
        shared_dependencies=frozenset({"undocumented broker session sharing"})
    )
    assert "undocumented broker session sharing" in entry.shared_dependencies
    assert unproven_isolation_is_common_mode(None) is True
    assert unproven_isolation_is_common_mode(IsolationClaim()) is True


def test_the_seven_common_mode_backdrops_are_expressible_as_shared_dependencies() -> (
    None
):
    """(ADR §4.2 line 86) The seven shared-backing kinds fit the free-form dependency field."""
    backdrops = frozenset(
        {
            "one administrator",
            "one credential",
            "one database",
            "one network",
            "one clock",
            "one library",
            "one broker resource",
        }
    )
    entry = clean_entry(shared_dependencies=backdrops)
    assert entry.shared_dependencies == backdrops
    assert len(backdrops) == 7


# --- construction / typing properties ---------------------------------------


@given(domains=DOMAIN_SET)
def test_property_any_taxonomy_subset_builds_a_row(
    domains: frozenset[FailureDomainKind],
) -> None:
    """(§5) Any subset of the closed taxonomy is a legal ``failure_domains`` value."""
    entry = clean_entry(failure_domains=domains)
    assert entry.failure_domains == domains


@pytest.mark.parametrize("behavior", list(FailureBehaviorKind))
def test_every_failure_behavior_is_accepted(behavior: FailureBehaviorKind) -> None:
    """(§5 line 122) All nine behaviors are constructible values of the row's behavior field."""
    assert clean_entry(failure_behavior=behavior).failure_behavior is behavior


def test_unregistered_taxonomy_and_behavior_values_are_rejected() -> None:
    """(closed vocabulary) An unlisted domain / behavior cannot be smuggled into a row."""
    with pytest.raises(ValueError):
        clean_entry(failure_domains=frozenset({"QUANTUM_FLUX"}))
    with pytest.raises(ValueError):
        clean_entry(failure_behavior="SPONTANEOUS_COMBUSTION")
    with pytest.raises(ValueError):
        clean_entry(isolation_kind="AIRGAPPED")


def test_the_clean_row_fixture_is_genuinely_complete() -> None:
    """(#8 fixture discipline) The clean row really fills all 11 ADR §5 fields + the kind."""
    entry = clean_entry()
    for field in MATRIX_FIELDS:
        value = getattr(entry, field)
        assert value is not None, field
        if isinstance(value, (frozenset, str)):
            assert len(value) > 0, field
    assert entry.isolation_kind is not None
