"""Package surface + constructive-absence canaries for ``tos.sci`` (design #29 §0.2/§6).

The package's identity is as much what it **cannot** do as what it does: there is no deploy, admit,
activate, sign, transmit, arm, mutate, reserve, release, or clear-restriction method anywhere in it
(ADR-002-029 §7 line 221-241 assigns every one of those to another owner). These tests assert that
absence structurally, plus the exported surface and the frozen / extra-forbid model discipline.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; all 12 register rows
carry +Security — the organisational gate is unmet; an EV-L1-complete claim is forbidden.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from pydantic import ValidationError

from ._sci_strategies import clean_decision, clean_policy, clean_scope

#: The nine digest-bound artifacts (design #29 §2.1 — eight template-backed + ReleaseRestriction).
_ARTIFACTS = (
    sci.SoftwareReleasePolicy,
    sci.SourceRevisionManifest,
    sci.DependencyToolchainClosureManifest,
    sci.BuildProvenanceAttestation,
    sci.ReleaseArtifactManifest,
    sci.ArtifactAdmissionDecision,
    sci.AdmittedReleaseSet,
    sci.RuntimeArtifactAttestation,
    sci.ReleaseRestriction,
)

#: The five yolk + five cross-cutting + three supporting predicates (design #29 §0.1-4 / §9.1).
_YOLK_PREDICATES = (
    "source_identity_exact_and_reviewed",
    "provenance_is_not_admission",
    "closure_complete_or_restrictive",
    "admission_admits_only_positive",
    "admitted_set_no_permissive_union",
)
_CROSS_CUTTING_PREDICATES = (
    "supply_chain_artifact_not_authority",
    "release_generation_monotonic",
    "rollback_is_new_generation",
    "restriction_is_monotonic_non_revival",
    "active_currentness_is_negative_gate",
    "software_deployment_ok_verdict",
)
_SUPPORTING_PREDICATES = (
    "mutable_name_is_not_identity",
    "independence_unproven_is_common_mode",
    "release_artifact_identity_exact",
)

#: Verbs §7 assigns to another owner — none may exist as an attribute on any sci model or module.
_FORBIDDEN_OPERATIONS = (
    "deploy",
    "admit",
    "activate",
    "sign",
    "transmit",
    "send",
    "arm",
    "rearm",
    "re_arm",
    "mutate",
    "reserve",
    "release_capacity",
    "clear",
    "clear_restriction",
    "revoke",
    "approve",
    "authorize",
    "commit",
    "issue_authority",
)


def test_nine_artifacts_are_exported_and_independent_id() -> None:
    """(§2.1/§0.4c) Nine digest-bound artifacts, each an IndependentIdArtifact."""
    assert len(_ARTIFACTS) == 9
    for model in _ARTIFACTS:
        assert issubclass(model, sci.IndependentIdArtifact)
        assert isinstance(model._ID_FIELD, str)
        assert (
            model._REQUIRED_COVERED
        ), f"{model.__name__} declares no _REQUIRED_COVERED"


def test_predicate_counts_match_the_contract() -> None:
    """(§0.1-4 / §9.1) Five yolk + five cross-cutting + three supporting are all exported."""
    assert len(_YOLK_PREDICATES) == 5
    # The five cross-cutting structural predicates of §5.6 (a)-(e); (b) ships as two named
    # entry points (`release_generation_monotonic` + `rollback_is_new_generation`, §5.6b).
    assert len(_CROSS_CUTTING_PREDICATES) == 6
    assert len(_SUPPORTING_PREDICATES) == 3
    for name in _YOLK_PREDICATES + _CROSS_CUTTING_PREDICATES + _SUPPORTING_PREDICATES:
        assert callable(getattr(sci, name)), f"{name} is not exported from tos.sci"
        assert name in sci.__all__


def test_every_export_resolves() -> None:
    """Every ``__all__`` name resolves (no phantom export)."""
    for name in sci.__all__:
        assert hasattr(sci, name), f"tos.sci.__all__ names a missing attribute: {name}"


@pytest.mark.parametrize("model", _ARTIFACTS)
def test_models_are_frozen_and_extra_forbid(model: type) -> None:
    """(§2) Every artifact is frozen with ``extra='forbid'`` — append-only by construction."""
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"


def test_frozen_artifact_rejects_mutation() -> None:
    """(§2) A field assignment on an issued artifact raises — there is no mutate path."""
    policy = clean_policy()
    with pytest.raises(ValidationError):
        policy.policy_id = "other"  # type: ignore[misc]


def test_unknown_field_is_rejected() -> None:
    """(§8 line 259) "Unknown fields ... are prohibited" — extra='forbid' realizes it."""
    with pytest.raises(ValidationError):
        sci.SoftwareReleasePolicy(unknown_field="x")


@pytest.mark.parametrize("model", _ARTIFACTS)
def test_no_forbidden_operation_method_on_any_model(model: type) -> None:
    """(§7 / §0.2) No model exposes a deploy / admit / sign / transmit / arm / mutate **method**.

    Field *names* legitimately contain those words (``deployment_plan_digest``,
    ``signer_identity``, ``committed``, ``approved_by_effective_principal_set_digest``) because the
    templates use them; what must not exist is a callable that *performs* the action — §7 line
    221-241 assigns every one of them to another owner.
    """
    field_names = set(model.model_fields)
    for name in dir(model):
        if name.startswith("_") or name in field_names:
            continue
        if not callable(getattr(model, name, None)):
            continue
        for verb in _FORBIDDEN_OPERATIONS:
            assert not name.startswith(verb), (
                f"{model.__name__}.{name}() looks like a {verb!r} operation — ADR-002-029 §7 "
                "assigns every such action to another owner; sci is a pure model/predicate "
                "substrate (design #29 §0.2)"
            )


def test_no_forbidden_operation_callable_on_the_package() -> None:
    """(§7 / §0.2) The module surface exposes no imperative action callable.

    Predicate names are **descriptive** (``admitted_set_no_permissive_union`` answers a question);
    what must not exist is an imperative entry point that *performs* one of the §7 actions, so the
    check is exact-name membership plus the ``<verb>_`` imperative prefix — not a substring match,
    which would false-positive on every descriptive name containing "admit" or "deploy".
    """
    imperative_prefixes = tuple(f"{verb}_" for verb in _FORBIDDEN_OPERATIONS)
    for name in sci.__all__:
        attribute = getattr(sci, name)
        if not callable(attribute) or isinstance(attribute, type):
            continue
        assert (
            name not in _FORBIDDEN_OPERATIONS
        ), f"tos.sci.{name}() is an action verb — ADR-002-029 §7 assigns it to another owner"
        assert not name.startswith(
            imperative_prefixes
        ), f"tos.sci.{name}() reads as an imperative action (design #29 §0.2)"


def test_regime_tag_is_present_in_the_package_docstring() -> None:
    """(§1) The completion-discipline tag is attached — no EV-L1-complete claim."""
    doc = sci.__doc__ or ""
    assert "NOT_IMPLEMENTED" in doc
    assert "+Security" in doc
    assert "EV-L1-complete claim is forbidden" in doc


def test_no_sci_ev_is_claimed_closed() -> None:
    """(§1) The package never claims to close an SCI-EV row."""
    doc = sci.__doc__ or ""
    assert "no SCI-EV is closed by code alone" in doc
    for module_doc in (
        sci.predicates.__doc__,
        sci.records.__doc__,
        sci.vocabulary.__doc__,
        sci.state.__doc__,
        sci._base.__doc__,
    ):
        assert "closes no SCI-EV" in (
            module_doc or ""
        ), "every sci submodule must carry the §1 regime tag"


def test_scope_model_is_a_plain_value_model() -> None:
    """(§2.1) SupplyChainScope carries no id and no digest — it is a value model."""
    fields = set(sci.SupplyChainScope.model_fields)
    assert "canonical_digest" not in fields
    assert not any(name.endswith("_id") for name in fields)
    assert clean_scope().scope_complete is True


def test_decision_exposes_the_mandated_binding_anchor() -> None:
    """(§2.3) The §15 mandated-binding anchor is declared on the decision, not hidden in a helper."""
    anchor = sci.ArtifactAdmissionDecision.MANDATED_ADMIT_BINDINGS
    assert len(anchor) == 10
    decision = clean_decision()
    for path in anchor:
        value: object = decision
        for part in path.split("."):
            value = getattr(value, part, None)
        assert (
            value is not None
        ), f"clean decision leaves the mandated binding {path} unset"
