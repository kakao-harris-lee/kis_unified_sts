"""§2 records — digest binding, ``_ID_FIELD`` drift lock, and phantom-field absence.

Covers the four digest-bound citizens and the four value models:

* ``_ID_FIELD`` / ``_REQUIRED_COVERED`` / ``_COVERED_FIELDS`` **drift locks** (design #24
  §9.1-4(b)): the identity field name, the required set, and the covered set are pinned, and
  the covered set is asserted **disjoint** from the self-excluded meta / identity /
  ledger-placement fields, so a later edit cannot quietly pull an id into the digest preimage
  (which would collapse the ``id != f(digest)`` independence the two forgery detections rest
  on) or drop a covered field (which would let content change without changing the digest);
* the §9 line 268-275 **8-group transcription** is asserted field-by-field against the real
  model, so a truncated transcription cannot pass (the #16 M4 lesson);
* the all-false :class:`AllFalsePostTradeConsequence` rejects **every** ``True`` flag at
  construction, on all five flags individually;
* **phantom-field absence** (design #24 §7): no model carries a negative-polarity or
  consequence-bearing field a caller could forge — no ``releases_capacity_flag``, no
  ``favorable_netted``, no ``can_transmit``, no ``title_proven_by_ack``, no
  ``destructive_overwrite``; and no ``PostTradeFinalityProof`` field could carry the global
  ``SETTLED`` / confidence-score / statement-flag / operator-decision substitute PTF-INV-005
  forbids.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tos.canonical import ArtifactStatus
from tos.posttrade import (
    OBLIGATION_RECORD_FIELD_GROUPS,
    STATEMENT_COVERAGE_SET_AXES,
    AllFalsePostTradeConsequence,
    CollateralAllocation,
    EconomicObligationRecord,
    MonetaryLeg,
    ObligationLeg,
    ObligationLegDirection,
    ObligationLegScope,
    PostTradeBreakRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
    post_trade_consequence_all_false,
)

from ._posttrade_strategies import (
    CLEAN_ISSUE_CONTENT,
    SCHEME,
    clean_break_record,
    clean_finality_proof,
    clean_leg,
    clean_obligation_record,
    clean_statement_manifest,
)

#: The four digest-bound citizens with their pinned identity field names (drift lock).
_ID_FIELD_LOCK = (
    (EconomicObligationRecord, "obligation_id"),
    (PostTradeFinalityProof, "proof_id"),
    (StatementCoverageManifest, "manifest_id"),
    (PostTradeBreakRecord, "break_id"),
)

#: The pinned ``_REQUIRED_COVERED`` **contents** of the four digest-bound citizens (design
#: #24 review MINOR-2). The earlier check only asserted the set was a non-empty subset of the
#: covered fields, which a mutation that *dropped* a member passed unchanged — and dropping a
#: member silently makes an incomplete artifact ISSUED-reachable. Two of these sets were
#: deliberately narrowed (``PostTradeFinalityProof`` does not require ``obligation_ref``,
#: ``StatementCoverageManifest`` does not require ``source_identity``) so the §5.6 / §5.7
#: decision guards stay reachable on a genuinely issued artifact — the nontrade
#: ``supersedes_ref`` rationale — and pinning the contents is what stops that deliberate
#: narrowing from drifting into an accidental one.
_REQUIRED_COVERED_LOCK = (
    (
        EconomicObligationRecord,
        (
            "obligation_type",
            "obligation_generation",
            "idempotency_key",
            "lifecycle_state",
        ),
    ),
    (PostTradeFinalityProof, ("bound_generation", "idempotency_key")),
    (StatementCoverageManifest, ("manifest_generation", "idempotency_key")),
    (PostTradeBreakRecord, ("break_scope", "break_generation", "idempotency_key")),
)

#: Exact names that must **never** appear as a field on any posttrade model: a forgeable
#: negative-polarity flag or a consequence a caller could assert (design #24 §7).
_PHANTOM_FIELD_NAMES = (
    "releases_capacity_flag",
    "releases_capacity_on_finality",
    "favorable_netted",
    "netted",
    "can_transmit",
    "credential",
    "route",
    "title_proven_by_ack",
    "destructive_overwrite",
    "released_on_finality",
)

#: **Tokens** that must never appear as an underscore-delimited component of any field name
#: (design #24 review MINOR-1). The exact-name list above is necessary but not sufficient: a
#: suffixed or prefixed variant — ``egress_route``, ``settlement_credential``,
#: ``obligation_send_token`` — would slip straight past an equality check while
#: reintroducing exactly the surface PTF-INV-016 forbids. Splitting on ``_`` and testing
#: token membership matches how the module-level surface scan in ``test_seam_egress`` already
#: works, so the two checks can no longer disagree about what counts as a transmission name.
#:
#: The token set is deliberately chosen not to collide with legitimate vocabulary:
#: ``release_state`` (the §15 line 385 ``MarginCollateralState`` coordinate) and the five
#: all-false consequence flags (``releases_capacity``, ``authorizes_transmission``, ...) name
#: the prohibited acts *on purpose* and must stay constructible, so ``release`` / ``releases``
#: / ``transmission`` / ``title`` are **not** tokens here.
_PHANTOM_FIELD_TOKENS = (
    "credential",
    "credentials",
    "route",
    "routes",
    "endpoint",
    "destination",
    "host",
    "url",
    "channel",
    "send",
    "transmit",
    "submit",
    "dispatch",
    "egress",
    "netted",
    "favorable",
    "overwrite",
    "bypass",
)

#: Names that must never appear on :class:`PostTradeFinalityProof`: the global substitutes
#: PTF-INV-005 forbids ("one global ``SETTLED``, ``CLOSED``, confidence score, statement
#: flag, or operator decision cannot replace exact per-field proof").
_PHANTOM_PROOF_SUBSTITUTES = (
    "global_settled_flag",
    "global_status",
    "settled",
    "closed",
    "confidence_score",
    "statement_flag",
    "operator_decision",
)

_ALL_MODELS = (
    EconomicObligationRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
    PostTradeBreakRecord,
    ObligationLeg,
    ObligationLegScope,
    MonetaryLeg,
    CollateralAllocation,
    AllFalsePostTradeConsequence,
)


@pytest.mark.parametrize(("model", "id_field"), _ID_FIELD_LOCK)
def test_id_field_drift_lock(model: type, id_field: str) -> None:
    """(§3.1 drift lock) Each artifact's ``_ID_FIELD`` is pinned and is a real field."""
    assert id_field == model._ID_FIELD
    assert id_field in model.model_fields


@pytest.mark.parametrize(("model", "id_field"), _ID_FIELD_LOCK)
def test_identity_and_meta_fields_are_excluded_from_the_digest(
    model: type, id_field: str
) -> None:
    """(§2.3 self-exclusion) ``id != f(digest)`` — the identity is out of the preimage.

    If the primary id were covered, two records with the same id would necessarily share
    bytes, and ``classify_record_pair`` could never report ``CRITICAL_CONFLICT``. The whole
    forgery-detection story rests on this exclusion (design #24 §0.4f).
    """
    covered = model._COVERED_FIELDS
    assert id_field not in covered
    assert "canonical_digest" not in covered
    assert "status" not in covered
    assert "canonicalization_version" not in covered
    assert "consequence" not in covered


@pytest.mark.parametrize(("model", "required"), _REQUIRED_COVERED_LOCK)
def test_required_covered_contents_drift_lock(
    model: type, required: tuple[str, ...]
) -> None:
    """(review MINOR-2) The exact ``_REQUIRED_COVERED`` tuple is pinned, order included.

    A dropped member is the dangerous mutation: it makes an artifact missing a
    safety-load-bearing field ISSUED-reachable, and every downstream test that builds a
    *complete* fixture would still pass. An added member is dangerous in the other direction:
    it makes a decision guard unreachable on issued artifacts and thereby vacuous.
    """
    assert required == model._REQUIRED_COVERED


@pytest.mark.parametrize(("model", "required"), _REQUIRED_COVERED_LOCK)
def test_every_required_field_actually_blocks_issuance_when_absent(
    model: type, required: tuple[str, ...]
) -> None:
    """(review MINOR-2, positive canary) Each pinned member really is enforced at ``issue()``.

    The pin above says what the set *is*; this says the set **does** something. Each required
    field is knocked out in turn from an otherwise-complete content dict and the artifact must
    fail to reach ISSUED — notably ``PostTradeFinalityProof.bound_generation``, whose
    requirement is the reason the §5.7 absent-generation guard has to be exercised on a DRAFT.
    """
    complete = CLEAN_ISSUE_CONTENT[model]
    # the control: with everything present the artifact issues cleanly
    issued = model.issue(scheme=SCHEME, **complete)
    assert issued.status is ArtifactStatus.ISSUED
    for field in required:
        knocked_out = dict(complete)
        knocked_out[field] = None
        with pytest.raises(ValueError, match="required safety-load-bearing"):
            model.issue(scheme=SCHEME, **knocked_out)


@pytest.mark.parametrize(("model", "id_field"), _ID_FIELD_LOCK)
def test_required_covered_is_a_subset_of_covered(model: type, id_field: str) -> None:
    """(§3.2) Every required field is itself covered — a required-but-uncovered field
    would be demanded at issuance yet invisible to the digest."""
    del id_field
    assert set(model._REQUIRED_COVERED) <= model._COVERED_FIELDS
    assert model._REQUIRED_COVERED, "an empty required set makes issuance vacuous"


@pytest.mark.parametrize(("model", "id_field"), _ID_FIELD_LOCK)
def test_every_covered_name_is_a_real_field(model: type, id_field: str) -> None:
    """(§3.3) No covered name is a typo — a mistyped covered field silently drops content."""
    del id_field
    missing = sorted(model._COVERED_FIELDS - set(model.model_fields))
    assert missing == [], f"{model.__name__} covers non-existent fields: {missing}"


def test_obligation_record_field_group_transcription_is_complete() -> None:
    """(§2.2-7) Every field named in the 8-group ADR transcription exists on the record."""
    for anchor, field_names in OBLIGATION_RECORD_FIELD_GROUPS:
        for name in field_names:
            assert (
                name in EconomicObligationRecord.model_fields
            ), f"§9 line {anchor} names {name!r}, which is not a field"


def test_obligation_record_covers_every_transcribed_group_field_except_the_identity() -> (
    None
):
    """(§2.2-7) The transcribed content is in the digest preimage — except the primary id.

    The primary ``obligation_id`` is group 1's identity item and is deliberately **outside**
    the preimage (``id != f(digest)``); every other transcribed field is inside it.
    """
    for _anchor, field_names in OBLIGATION_RECORD_FIELD_GROUPS:
        for name in field_names:
            if name == EconomicObligationRecord._ID_FIELD:
                continue
            assert (
                name in EconomicObligationRecord._COVERED_FIELDS
            ), f"transcribed field {name!r} is not covered by the digest"


def test_statement_coverage_axes_are_five_real_field_pairs() -> None:
    """(§19 line 443) The five set axes name real expected / received field pairs."""
    assert len(STATEMENT_COVERAGE_SET_AXES) == 5
    for expected_field, received_field in STATEMENT_COVERAGE_SET_AXES:
        assert expected_field in StatementCoverageManifest.model_fields
        assert received_field in StatementCoverageManifest.model_fields


# --- digest binding ----------------------------------------------------------


def test_issued_records_verify_their_digest() -> None:
    """(§4.1) The four clean fixtures issue and re-verify."""
    for artifact in (
        clean_obligation_record(),
        clean_finality_proof(),
        clean_statement_manifest(),
        clean_break_record(),
    ):
        assert artifact.status is ArtifactStatus.ISSUED
        assert artifact.canonical_digest
        assert artifact.missing_required_fields() == []


def test_changed_covered_content_changes_the_digest() -> None:
    """(§4.1) A covered-content edit is a new artifact — mutation is unconstructable."""
    baseline = clean_obligation_record()
    changed = clean_obligation_record(obligation_type="TAX_LEG")
    assert baseline.canonical_digest != changed.canonical_digest


def test_identity_change_alone_does_not_change_the_digest() -> None:
    """(§3.1) The id is outside the preimage, so two ids over one content share bytes.

    That is precisely what makes a same-**idempotency**-key / different-**id** pair
    classifiable at all: had the id been covered, every such pair would look like different
    bytes and ``DIVERGENT_EMISSION`` could never be distinguished from an honest re-emission.
    """
    first = clean_obligation_record(obligation_id="OBL-1")
    second = clean_obligation_record(obligation_id="OBL-2")
    assert first.canonical_digest == second.canonical_digest


def test_draft_artifact_must_not_carry_a_digest() -> None:
    """(§3.2) A DRAFT is pre-issuance: a forged digest on it is unconstructable."""
    with pytest.raises(ValueError, match="canonical_digest"):
        EconomicObligationRecord(
            obligation_id="OBL-X",
            canonical_digest="forged",
            status=ArtifactStatus.DRAFT,
        )


def test_issued_artifact_requires_a_concrete_independent_id() -> None:
    """(canonical §3.1) An ISSUED artifact with no id is unconstructable."""
    from tos.posttrade import PostTradeObligationLifecycleState

    with pytest.raises(ValueError, match="obligation_id"):
        EconomicObligationRecord.issue(
            scheme=SCHEME,
            obligation_type="SETTLEMENT_LEG",
            obligation_generation=1,
            idempotency_key="IDEM-1",
            lifecycle_state=PostTradeObligationLifecycleState.DUE,
        )


def test_issued_artifact_requires_every_required_covered_field() -> None:
    """(§3.2) A missing required covered field keeps the artifact pre-issuance."""
    with pytest.raises(ValueError, match="required safety-load-bearing"):
        clean_obligation_record(obligation_type=None)


def test_models_forbid_unknown_fields() -> None:
    """(``extra="forbid"``) An unknown field cannot smuggle content past the digest."""
    with pytest.raises(ValueError, match="[Ee]xtra"):
        ObligationLegScope(unknown_component="x")


def test_models_are_frozen() -> None:
    """(§2) No model has a mutation path — append-only is structural."""
    leg = clean_leg()
    with pytest.raises(ValueError, match="frozen|immutable"):
        leg.magnitude = Decimal("1.00")


# --- all-false consequence ---------------------------------------------------


def test_consequence_declares_exactly_the_five_flags() -> None:
    """(§4.7) The four §10 line 312 flags plus the §1 line 31 egress seal."""
    assert set(AllFalsePostTradeConsequence.model_fields) == {
        "releases_capacity",
        "makes_cash_available",
        "proves_legal_title",
        "grants_permission",
        "authorizes_transmission",
    }


@pytest.mark.parametrize("flag", sorted(AllFalsePostTradeConsequence.model_fields))
def test_every_consequence_flag_is_unconstructable_as_true(flag: str) -> None:
    """(§10 line 312) Each of the five flags individually rejects a ``True``."""
    with pytest.raises(ValueError, match=f"{flag} must be false"):
        AllFalsePostTradeConsequence(**{flag: True})


def test_default_consequence_is_all_false_and_passes_the_re_check() -> None:
    """(§5.7) The default block is all-false and the defence-in-depth predicate agrees."""
    assert post_trade_consequence_all_false(AllFalsePostTradeConsequence()) is True


def test_every_record_carries_an_all_false_consequence() -> None:
    """(§4.7) Every artifact grants nothing — including one at ``FINALITY_PROVEN``."""
    from tos.posttrade import PostTradeObligationLifecycleState

    proven = clean_obligation_record(
        lifecycle_state=PostTradeObligationLifecycleState.FINALITY_PROVEN
    )
    for artifact in (
        proven,
        clean_finality_proof(),
        clean_statement_manifest(),
        clean_break_record(),
    ):
        assert post_trade_consequence_all_false(artifact.consequence) is True


# --- phantom-field absence ---------------------------------------------------


@pytest.mark.parametrize("model", _ALL_MODELS)
def test_no_phantom_negative_polarity_or_consequence_field(model: type) -> None:
    """(§7 honest disclosure) The forgeable names stay absent from every model.

    Phase-1 posttrade has **zero** negative-polarity fields: no-netting is the structural
    coexistence of two gross magnitudes, collateral conservation is a magnitude sum, history
    preservation is the positive ``original_retained``, and a capacity release or external
    send is unrepresentable. This asserts that absence so a later edit cannot reintroduce a
    flag a caller could forge.
    """
    present = sorted(set(_PHANTOM_FIELD_NAMES) & set(model.model_fields))
    assert present == [], f"{model.__name__} reintroduced phantom field(s): {present}"


@pytest.mark.parametrize("model", _ALL_MODELS)
def test_no_field_name_contains_a_phantom_token(model: type) -> None:
    """(review MINOR-1) Partial match, so an affixed variant cannot slip past equality.

    ``egress_route`` / ``settlement_credential`` / ``obligation_send_token`` are the same
    surface as ``route`` / ``credential`` / ``send`` wearing a prefix, and an exact-name check
    admits every one of them. Splitting each field name on ``_`` and testing token membership
    is the same rule the ``test_seam_egress`` module-surface scan applies, so the two can no
    longer disagree.
    """
    offenders = sorted(
        name
        for name in model.model_fields
        if set(name.lower().split("_")) & set(_PHANTOM_FIELD_TOKENS)
    )
    assert offenders == [], (
        f"{model.__name__} carries a phantom-token field: {offenders} — a transmission or "
        "netting surface cannot be reintroduced under an affix (PTF-INV-016 / §0.4d)"
    )


@pytest.mark.parametrize(
    "planted",
    [
        "egress_route",
        "settlement_credential",
        "settlement_endpoint",
        "broker_credential",
        "auto_netted",
        "obligation_send_token",
        "favorable_balancing_entry",
        "netted_amount",
        "history_overwrite_allowed",
        "route",
        "bypass_permitted",
        "transfer_destination",
    ],
)
def test_the_phantom_token_scan_catches_an_affixed_plant(planted: str) -> None:
    """(both-ways) The partial-match scan really fires — green means clean, not neutered.

    Every one of these would have passed the exact-name check unchanged; each is caught here.
    """
    assert set(planted.lower().split("_")) & set(
        _PHANTOM_FIELD_TOKENS
    ), f"{planted!r} escaped the token scan"


@pytest.mark.parametrize(
    "legitimate",
    [
        "release_state",
        "releases_capacity",
        "authorizes_transmission",
        "proves_legal_title",
        "makes_cash_available",
        "grants_permission",
        "pledged_obligation_ids",
        "source_revision",
        "does_not_prove",
        "shared_dependencies",
        "missing_intervals",
    ],
)
def test_the_phantom_token_scan_admits_legitimate_vocabulary(legitimate: str) -> None:
    """(both-ways) The scan is not so broad that it condemns the real field names.

    ``release_state`` is the §15 line 385 margin coordinate and the five all-false flags name
    the prohibited acts **on purpose** — a token set that rejected them would have forced the
    seal itself to be deleted.
    """
    assert not set(legitimate.lower().split("_")) & set(_PHANTOM_FIELD_TOKENS)


@pytest.mark.parametrize("name", _PHANTOM_PROOF_SUBSTITUTES)
def test_finality_proof_has_no_global_substitute_field(name: str) -> None:
    """(PTF-INV-005) A global ``SETTLED`` / confidence / statement / operator substitute has
    no field to travel in — the invariant is realized by structural absence, not by a rule
    that tolerates one."""
    assert name not in PostTradeFinalityProof.model_fields


def test_no_model_exposes_a_mutating_or_transmitting_method() -> None:
    """(§4.4 / PTF-INV-008/016) No release / transfer / send / commit method exists."""
    forbidden = (
        "release",
        "release_capacity",
        "transfer",
        "quarantine",
        "send",
        "transmit",
        "commit",
        "apply",
        "mutate",
        "update",
    )
    for model in _ALL_MODELS:
        for name in forbidden:
            assert not hasattr(model, name), (
                f"{model.__name__} exposes a {name!r} operation — capacity mutation is "
                "rcl's (§1 line 21) and transmission is egress's (§1 line 31)"
            )


def test_obligation_leg_direction_set_drops_undirected_legs() -> None:
    """(§9 line 273) An undirected leg proves nothing about coverage and is not counted."""
    record = clean_obligation_record(
        legs=(
            clean_leg(ObligationLegDirection.DEBIT),
            ObligationLeg(direction=None, magnitude=Decimal("1.00")),
        )
    )
    assert record.leg_direction_set() == frozenset({ObligationLegDirection.DEBIT})
