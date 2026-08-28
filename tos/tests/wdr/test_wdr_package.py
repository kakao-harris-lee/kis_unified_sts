"""Public-surface + verbatim-count regressions for ``tos.wdr`` (design #26 §2/§9/appendix A-D).

Asserts the package exports the design's promised surface (five artifacts + value models + five
truthy-sealed enums + two closed structural enums + the five yolk predicates + the §6 substrate) and
that the manually-transcribed verbatim counts (§5 ten definitions, §8 fifteen boundary items, §5.7
twenty-one scope dimensions, §26 six gate stages, the state-token counts) hold with over/under both
caught (appendix A-D).

Regime tag: structural substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.wdr as w


def test_five_digest_bound_artifacts_exported() -> None:
    """(§2 / gate-status line 793 "the five deviation templates") The five artifacts are exported."""
    for name in (
        "SafetyDeviationPolicy",
        "SafetyDeviationRequest",
        "SafetyDeviationDecision",
        "ResidualRiskAcceptanceRecord",
        "ActiveDeviationSet",
    ):
        assert hasattr(w, name), name
        assert name in w.__all__


def test_value_models_exported() -> None:
    """(§2.1) The seven value / injected input models are exported."""
    for name in (
        "DeviationScope",
        "CompensatingControl",
        "DeviationDependencyClosure",
        "NonWaivableBoundaryAnchor",
        "WaivedEvidenceItem",
        "GateSeparationLadder",
        "DeviationClassification",
    ):
        assert hasattr(w, name), name


def test_five_truthy_sealed_enums_exported() -> None:
    """(§2.2) The five WDR-axis truthy-sealed enums are exported."""
    for name in (
        "DecisionResult",
        "NonWaivableClassification",
        "RequestState",
        "ActiveDeviationState",
        "WaivedEvidenceStatus",
    ):
        assert hasattr(w, name), name


def test_two_closed_structural_enums_exported() -> None:
    """(§2.2) The two closed structural enums (ScopeDimension / CompensatingControlKind) are exported."""
    assert hasattr(w, "ScopeDimension")
    assert hasattr(w, "CompensatingControlKind")


def test_five_yolk_predicates_exported() -> None:
    """(§5) The five yolk predicates are exported (WDR-EV-001/002/007/010/012 substrate)."""
    for name in (
        "boundary_denies_non_waivable",
        "scope_exact_and_complete",
        "unknown_denies_and_confines",
        "evidence_status_honest",
        "combined_set_no_permissive_union",
        "gate_states_separated",
    ):
        assert hasattr(w, name), name
        assert callable(getattr(w, name))


def test_predicate_only_substrate_exported() -> None:
    """(§6) The predicate-only §6 substrate + §6b not-Phase-1 model are exported."""
    for name in (
        "compensating_control_not_observation",
        "independent_effective_person_approval",
        "deviation_single_use_non_authorizing",
        "broker_finality_unchanged",
        "economic_effect_persists",
        "expiry_recovery_revives_nothing",
        "break_glass_no_authority",
        "deviation_service_no_route",
        "revocation_dominates_send",
        "attempt_potentially_live",
    ):
        assert hasattr(w, name), name


def test_all_exports_are_importable() -> None:
    """(surface) Every name in ``__all__`` is a real attribute (no stale export)."""
    for name in w.__all__:
        assert hasattr(w, name), f"{name} in __all__ but not importable"


def test_verbatim_counts_appendix_a_to_d() -> None:
    """(appendix A-D) The manually-transcribed verbatim counts hold (over/under both caught)."""
    # appendix B — §5.7 twenty-one scope dimensions
    assert len(list(w.ScopeDimension)) == 21
    assert len(w.DeviationScope.model_fields) == 21
    # appendix C — §8 fifteen non-waivable boundary items
    assert len(w.NonWaivableBoundaryAnchor.BOUNDARY_ITEMS) == 15
    assert len(w.NonWaivableBoundaryAnchor.model_fields) == 15
    # §26 six distinct gate stages
    assert len(w.GateSeparationLadder.STAGE_FIELDS) == 6
    # appendix D — state-token counts
    assert len(list(w.DecisionResult)) == 3
    assert len(list(w.NonWaivableClassification)) == 3
    assert len(list(w.RequestState)) == 10
    assert len(list(w.ActiveDeviationState)) == 7
    assert len(list(w.WaivedEvidenceStatus)) == 7
    # WDR-INV-001 — eleven all-false authority flags
    assert len(w.AllFalseDeviationAuthority.model_fields) == 11
    # §5.10 twelve dependency-closure categories
    assert len(w.DeviationDependencyClosure.CLOSURE_CATEGORIES) == 12


def test_mandated_scope_floor_is_full_catalogue() -> None:
    """(§5.2) MANDATED_SCOPE_FLOOR == every ScopeDimension member (caller may add, never subtract)."""
    assert frozenset(w.ScopeDimension) == w.MANDATED_SCOPE_FLOOR


def test_request_binds_all_fifteen_section_10_field_groups() -> None:
    """(§10 line 283-297 drift / MAJOR-1 fix) The request binds all 15 §10 "SHALL bind" field groups.

    ADR §10 "Every request SHALL bind at least:" enumerates exactly 15 field groups. The
    ``REQUEST_FIELD_GROUPS`` anchor maps each group to its representative model fields; every
    representative MUST exist as a model field. Dropping a whole §10 group (the MAJOR-1 defect this fix
    closes) removes its field(s) from the model and breaks this drift regression. Over/under both
    caught: exactly 15 groups, every representative present.
    """
    groups = w.SafetyDeviationRequest.REQUEST_FIELD_GROUPS
    assert len(groups) == 15, f"expected exactly 15 §10 field groups, got {len(groups)}"
    model_fields = set(w.SafetyDeviationRequest.model_fields)
    missing: list[str] = []
    for group, fields in groups.items():
        assert fields, f"group {group!r} has no representative field"
        for field in fields:
            if field not in model_fields:
                missing.append(f"{group}.{field}")
    assert (
        missing == []
    ), f"§10 group representative fields missing from the model: {missing}"


def test_section_10_group_representatives_are_covered_content() -> None:
    """(MAJOR-1) The added §10 groups 9/11/12/13/15 bind immutable request content ⇒ covered digest.

    A material change to any of these request-content fields must change the canonical digest (so a
    same-id / different-bytes substitution is a ``CRITICAL_CONFLICT``). The representative content
    fields of the newly-added groups are therefore in ``_COVERED_FIELDS``.
    """
    covered = w.SafetyDeviationRequest._COVERED_FIELDS
    for field in (
        "assumptions",
        "hard_safety_envelope_ref",
        "capacity_constraints",
        "revocation_behavior",
        "prohibited_inferences",
        "non_waivable_classification_result",
    ):
        assert field in covered, f"{field} (immutable request content) must be covered"
