"""Package surface + completion-discipline regression for ``tos.sir`` (design #28 §0.1/§1/§9.1).

Locks the design #28 §9.1 Phase-1 deliverable list (six digest-bound artifacts, the value models, the
six enums, the three yolks, the nine §6 substrate predicates and the §6b thin models), the export
surface's internal consistency, and the **completion discipline**: SIR closes **zero** SIR-EV rows and
the package must not grow a surface that implies otherwise.

Regime tag: restrictive-declaration / exact-scope-combined / evidence-honesty predicate substrate only;
``SIR-EV-001..012`` all remain NOT_IMPLEMENTED; **EV-L1-complete claim forbidden**.
"""

from __future__ import annotations

import tos.sir as s

#: design #28 §9.1 item 2 — the six digest-bound artifacts.
_DIGEST_BOUND_ARTIFACTS = (
    "SafetyIncidentPolicy",
    "SafetyIncidentRecord",
    "ActiveSafetyIncidentSet",
    "IncidentContainmentPlan",
    "IncidentRecoveryHandoffPackage",
    "IncidentClosureDecision",
)

#: design #28 §9.1 item 2 — the value / injected input models.
_VALUE_MODELS = (
    "SafetySignal",
    "ActiveSetMember",
    "IncidentDependencyClosure",
    "IncidentScope",
    "ControlledShutdownProcedure",
    "ShutdownStep",
    "OngoingSafetyObligation",
    "CommunicationHonestyLadder",
    "ClosureIndependenceLadder",
    "IncidentClassificationInput",
    "AnalysisClaim",
    "ContainmentAction",
    "IncidentUnknownState",
    "BrokerFinalityTokens",
    "RecoveryRevivalInputs",
    "ExternalActivityClaim",
)

#: design #28 §9.1 item 2 — the six enums, with their mandated cardinalities.
_ENUM_CARDINALITY = {
    "IncidentLifecycleState": 8,
    "ClosureDecisionResult": 3,
    "IncidentRecordState": 4,
    "CommunicationAssertionKind": 9,
    "SignalClassificationClass": 8,
    "ClosureDimension": 22,
}

#: design #28 §9.1 item 3 — the three yolk predicates.
_YOLK_PREDICATES = (
    "restrictive_declaration_non_authorizing",
    "scope_exact_combined_no_favorable_subset",
    "evidence_communication_status_honest",
)

#: design #28 §6.1-§6.9 — the nine predicate-only substrate predicates (each closes **no** SIR-EV).
_SUBSTRATE_PREDICATES = (
    "containment_uses_normal_authority",
    "controlled_shutdown_not_broker_finality",
    "recovery_revives_nothing",
    "obligations_survive_shutdown",
    "unknown_remains_conservative",
    "broker_finality_unchanged",
    "economic_effect_outlives_incident_state",
    "closure_administrative_non_permissive",
    "closure_independence_non_self_exemption",
)

#: design #28 §6b — the not-Phase-1 thin models.
_THIN_MODELS = (
    "restriction_dominates_send",
    "attempt_potentially_live",
    "external_activity_conservative",
)


def test_every_declared_export_resolves() -> None:
    """(surface) Every name in ``__all__`` is actually importable from the package."""
    missing = sorted(name for name in s.__all__ if not hasattr(s, name))
    assert missing == [], f"declared but absent from tos.sir: {missing}"


def test_export_list_has_no_duplicates() -> None:
    """(surface) ``__all__`` carries each name exactly once."""
    assert len(s.__all__) == len(set(s.__all__))


def test_six_digest_bound_artifacts_are_exported() -> None:
    """(§9.1 item 2) The six §5 ledger citizens are all present and id-independent."""
    for name in _DIGEST_BOUND_ARTIFACTS:
        artifact = getattr(s, name)
        assert issubclass(artifact, s.IndependentIdArtifact)
        assert isinstance(artifact._ID_FIELD, str)
        assert artifact._REQUIRED_COVERED
        assert artifact._COVERED_FIELDS


def test_self_digest_field_is_excluded_from_the_covered_preimage() -> None:
    """(§2.3 digest rule) Each artifact's own ``*_digest`` field is self-excluded; externals are covered."""
    for name in _DIGEST_BOUND_ARTIFACTS:
        artifact = getattr(s, name)
        own_digest_fields = [
            field
            for field in artifact.model_fields
            if field.endswith("_digest") and field != "active_set_digest"
        ]
        for field in own_digest_fields:
            assert field not in artifact._COVERED_FIELDS, (
                f"{name}.{field} is its own digest and must be excluded from the preimage "
                "(design #28 §2.3 self-exclusion)"
            )
    # the external reference digest IS covered, on both artifacts that carry one.
    assert "active_set_digest" in s.IncidentContainmentPlan._COVERED_FIELDS
    assert "active_set_digest" in s.IncidentClosureDecision._COVERED_FIELDS


def test_value_models_are_exported_and_id_free() -> None:
    """(§2.1) The value models carry no independent id — only the six artifacts are ledger citizens."""
    for name in _VALUE_MODELS:
        model = getattr(s, name)
        assert not issubclass(model, s.IndependentIdArtifact)


def test_every_model_is_frozen_and_extra_forbid() -> None:
    """(§2.3) Every model is immutable and rejects unknown fields — "omission is restrictive"."""
    for name in (*_DIGEST_BOUND_ARTIFACTS, *_VALUE_MODELS, "AllFalseIncidentAuthority"):
        config = getattr(s, name).model_config
        assert config.get("frozen") is True, f"{name} is not frozen"
        assert config.get("extra") == "forbid", f"{name} does not forbid extra fields"


def test_six_enums_carry_their_mandated_cardinality() -> None:
    """(§2.2 / §7.2 drift) Each enum is present with exactly the ADR-transcribed member count."""
    for name, cardinality in _ENUM_CARDINALITY.items():
        assert len(list(getattr(s, name))) == cardinality, f"{name} cardinality drifted"


def test_three_yolks_and_nine_substrate_predicates_are_exported() -> None:
    """(§9.1 item 3) The three yolks, the nine §6 substrate predicates and the §6b thin models exist."""
    for name in (*_YOLK_PREDICATES, *_SUBSTRATE_PREDICATES, *_THIN_MODELS):
        assert callable(getattr(s, name)), f"{name} is missing from the tos.sir surface"


def test_every_predicate_returns_a_plain_bool() -> None:
    """(§4.2) No predicate returns a sentinel-bearing value — every result is a plain ``bool``.

    A predicate returning an enum would re-open the truthy-sentinel fail-open at the *call site*; the
    package deliberately keeps its enums as inputs and its verdicts as plain booleans.
    """
    from ._sir_strategies import (
        CLEAN_APPLICABLE_INCIDENTS,
        CLEAN_APPLICABLE_SHARED_CAUSES,
        clean_active_set,
        clean_analysis_claim,
        clean_communication_ladder,
        clean_dependency_closure,
        clean_record,
        clean_signal,
    )

    results = (
        s.restrictive_declaration_non_authorizing(clean_record(), clean_signal()),
        s.scope_exact_combined_no_favorable_subset(
            clean_active_set(),
            clean_dependency_closure(),
            CLEAN_APPLICABLE_INCIDENTS,
            CLEAN_APPLICABLE_SHARED_CAUSES,
            frozenset(),
        ),
        s.evidence_communication_status_honest(
            clean_communication_ladder(), clean_analysis_claim()
        ),
        s.dominating_open_incident_present(clean_active_set()),
    )
    for result in results:
        assert type(result) is bool


def test_package_declares_no_ev_completion_surface() -> None:
    """(§1 completion discipline) Nothing in the surface implies a closed SIR-EV."""
    for forbidden in (
        "SIR_EV_001",
        "SIR_AC_001",
        "EV_L1_COMPLETE",
        "closes_sir_ev",
        "accepted",
        "acceptance",
    ):
        assert not hasattr(s, forbidden)


def test_module_docstrings_carry_the_regime_tag() -> None:
    """(§1 regime tag) Every sir module states that it closes no SIR-EV."""
    import tos.sir._base
    import tos.sir.predicates
    import tos.sir.records
    import tos.sir.state
    import tos.sir.vocabulary

    for module in (
        s,
        tos.sir._base,
        tos.sir.predicates,
        tos.sir.records,
        tos.sir.state,
        tos.sir.vocabulary,
    ):
        doc = module.__doc__ or ""
        assert (
            "EV-L1-complete" in doc
        ), f"{module.__name__} does not carry the design #28 §1 regime tag"
