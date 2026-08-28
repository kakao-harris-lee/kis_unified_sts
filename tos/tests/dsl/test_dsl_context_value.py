"""The dsl-side D-E2 extension: the value carrier, the merge, and the signature append (design #32).

This file covers the **additive** ``tos.dsl`` surface design #32 §15.2 ① declares, and it is a *new*
file on purpose: every shipped ``tos/tests/dsl`` test stays byte-for-byte unedited and green, which
is the sanction premise ("committed 테스트 파괴 0", §15.2 ③) demonstrated rather than asserted.

Three claims:

1. **the carrier is a lean, governed container** (§2.2) — primitives only, no ``tos.capsule`` type,
   no re-declared field state, wildcard-free keys, no duplicate keys;
2. **the merge is additive and byte-compatible** (§3.2, §7.2-9) — ``resolved_context=None`` returns
   exactly what ``build_environment`` has always returned;
3. **the recorded signature covers the fourth decision input** (§3.2 (3b), MAJOR-2a) — a view's
   canonical digest is appended to ``captured_external_value_refs``, so two evaluations that differ
   only in their values differ in their signature. Without the append they would be
   indistinguishable on replay while producing different outcomes.

⚠ **Recorded deviation.** Design #32 §3.2 (3) specifies ``evaluate(…, resolved_context=None)``. The
committed canary ``test_dsl_determinism.py:136-146`` asserts ``evaluate``'s parameter set is exactly
its five existing names, so a sixth parameter would break a shipped test — and editing a canary so
new code fits is the neutered-canary defect class. The substance is therefore implemented in
:func:`~tos.dsl.evaluate_resolved`, a separate entry point over a shared body, and both the design's
safety property and the committed canary hold at once. See that function's docstring; the
reconciliation (errata vs. sanctioned canary amendment) is the orchestrator's.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.capsule._base import PolicyRef
from tos.capsule.capsule import (
    CapsuleScope,
    DecisionContextCapsule,
    SafetyCriticalFacts,
    SnapshotRef,
)
from tos.dsl import (
    UNKNOWN,
    VALUE_NAMESPACE,
    ArtifactIntegrityError,
    AuthoredStrategy,
    Compare,
    CompareOp,
    ContextValue,
    ContextValueView,
    Decision,
    DecisionKind,
    DecisionPolicy,
    EvaluationConfig,
    NoActionOutcome,
    Operand,
    Rule,
    TargetKind,
    TargetSpec,
    build_environment,
    evaluate,
    evaluate_resolved,
    is_wildcard_field_key,
    resolve_operand,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)
ENFORCEMENT_VERSION = "esc-0"
_CLOSE = 4_512_500


def _capsule() -> DecisionContextCapsule:
    """An issued Capsule bound to a snapshot reference."""
    return DecisionContextCapsule.issue(  # type: ignore[return-value]
        scheme=SCHEME,
        issuer_principal_id="iss-1",
        critical_input_policy=PolicyRef(policy_id="pol-1", canonical_digest="pd-1"),
        critical_input_snapshot=SnapshotRef(snapshot_id="cis-1", canonical_digest="sd-1"),
        scope=CapsuleScope(
            environment="non-live-test",
            account="acct-1",
            instrument="ES",
            decision_class="entry",
        ),
        safety_critical_facts=SafetyCriticalFacts(
            account="acct-1",
            instrument="ES",
            direction="LONG",
            quantity_basis="RISK",
            unit="contract",
        ),
    )


def _view(*, close: int = _CLOSE, as_of: int = 1_700_000_060_000, digest: str = "view-0") -> ContextValueView:
    """A value view carrying one admitted ``close``."""
    return ContextValueView(
        snapshot_id="cis-1",
        snapshot_canonical_digest="sd-1",
        values=(
            ContextValue(
                field_key="close",
                value=close,
                as_of=as_of,
                payload_digest="pay-1",
                observation_ref="raw-1",
            ),
        ),
        canonical_digest=digest,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )


def _strategy(*, threshold: int) -> AuthoredStrategy:
    """A strategy whose single guard reads a merged value against a config threshold."""
    action = Decision(
        kind=DecisionKind.ACTION,
        rationale="the resolved close cleared the authored threshold",
        target=TargetSpec(
            kind=TargetKind.ACTION,
            account="acct-1",
            instrument="ES",
            direction="LONG",
            position_effect="OPEN",
            quantity_basis="RISK",
            edge_or_confidence="0.7",
            rationale="the resolved close cleared the authored threshold",
        ),
    )
    policy = DecisionPolicy(
        rules=(
            Rule(
                all_of=(
                    Compare(
                        left=Operand(ref=("capsule", VALUE_NAMESPACE, "close")),
                        op=CompareOp.GT,
                        right=Operand(const=threshold),
                    ),
                ),
                decision=action,
            ),
        ),
        default=Decision(kind=DecisionKind.NO_ACTION, rationale="the guard did not fire — hold"),
    )
    return AuthoredStrategy.issue(  # type: ignore[return-value]
        scheme=SCHEME,
        dsl_version="dsl-0",
        config_binding_version="cfg-bind-0",
        policy=policy,
    )


_CONFIG = EvaluationConfig(config_version="cfg-1", bindings={})


# ---------------------------------------------------------------------------
# 1. The carrier (design #32 §2.2)
# ---------------------------------------------------------------------------


def test_the_carrier_fields_are_primitives_only() -> None:
    """(§2.2) A lean container — no ``tos.capsule`` type, and no re-declared field state."""
    annotations = {name: field.annotation for name, field in ContextValue.model_fields.items()}
    assert set(annotations) == {
        "field_key",
        "value",
        "as_of",
        "payload_digest",
        "observation_ref",
    }
    assert "field_state" not in ContextValue.model_fields
    for annotation in annotations.values():
        assert "capsule" not in str(annotation).lower()


def test_the_carrier_module_imports_no_capsule_type() -> None:
    """(§2.2, anti-phantom) The "no capsule import" claim is read off the source, not asserted."""
    import ast
    from pathlib import Path

    import tos.dsl.context_value as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not [name for name in imported if name.startswith("tos.capsule")]


def test_an_absent_as_of_or_provenance_pointer_is_unconstructable() -> None:
    """(§4.2) The publication gate is expressed as a type, not as a check a producer could skip."""
    with pytest.raises(ValidationError):
        ContextValue(
            field_key="close", value=1, as_of=None, payload_digest="p", observation_ref="r"
        )
    with pytest.raises(ValidationError, match="concrete"):
        ContextValue(
            field_key="close", value=1, as_of=1, payload_digest="   ", observation_ref="r"
        )


@pytest.mark.parametrize("wildcard", ["*", "latest", "LATEST", "ALL", "close*"])
def test_a_wildcard_field_key_is_unconstructable(wildcard: str) -> None:
    """(§2.4, RFC-008 §7:239-240) The wildcard prohibition holds on the environment side too."""
    assert is_wildcard_field_key(wildcard) is True
    with pytest.raises(ValidationError, match="wildcard"):
        ContextValue(
            field_key=wildcard, value=1, as_of=1, payload_digest="p", observation_ref="r"
        )


def test_a_legitimate_field_key_is_not_over_rejected() -> None:
    """(#26 WDR MAJOR-1) The wildcard check does not swallow ordinary names."""
    for name in ("close", "lower_band", "session", "latest_close"):
        assert is_wildcard_field_key(name) is False


def test_a_duplicated_field_key_is_unconstructable() -> None:
    """(§6, ADR-002-018 §11:311) Disagreement is refused, never folded onto one arbitrary value."""
    left = ContextValue(
        field_key="close", value=1, as_of=1, payload_digest="p", observation_ref="a"
    )
    right = left.model_copy(update={"value": 2, "observation_ref": "b"})
    with pytest.raises(ValidationError, match="duplicate"):
        ContextValueView(
            snapshot_id="cis-1",
            snapshot_canonical_digest="sd-1",
            values=(left, right),
            canonical_digest="d",
            canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        )


def test_an_explicit_empty_view_is_constructable() -> None:
    """(§6 ∅ 양방향) "resolved and nothing was admissible" is a representable, publishable fact."""
    view = ContextValueView(
        snapshot_id="cis-1",
        snapshot_canonical_digest="sd-1",
        canonical_digest="d",
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
    )
    assert view.values == ()
    assert view.as_environment_mapping() == {}


# ---------------------------------------------------------------------------
# 2. The merge (design #32 §3.2; §7.2-9 backward compatibility)
# ---------------------------------------------------------------------------


def test_build_environment_without_a_view_is_unchanged() -> None:
    """(§7.2-9 ★ backward compatibility) The pre-D-E2 return value, byte for byte."""
    capsule = _capsule()
    legacy = {"capsule": capsule.model_dump(mode="json"), "config": dict(_CONFIG.bindings)}
    assert build_environment(capsule, _CONFIG) == legacy
    assert build_environment(capsule, _CONFIG, resolved_context=None) == legacy


def test_the_resolved_context_parameter_is_keyword_only() -> None:
    """(§3.2 (3)) Additive and keyword-only, so no positional call site can shift meaning."""
    parameter = inspect.signature(build_environment).parameters["resolved_context"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is None


def test_the_merge_lands_under_the_capsule_source() -> None:
    """(§3.2 (1), RFC-008 §10:327-331) Values are Critical Input, never relabelled configuration."""
    env = build_environment(_capsule(), _CONFIG, resolved_context=_view())
    assert env["capsule"][VALUE_NAMESPACE] == {"close": _CLOSE}
    assert env["config"] == {}
    assert set(env) == {"capsule", "config"}


def test_a_merged_value_resolves_as_a_scalar_leaf() -> None:
    """(§3.2 (2)) The flat mapping is what ``resolve_operand``'s dict-walk can actually reach."""
    env = build_environment(_capsule(), _CONFIG, resolved_context=_view())
    assert resolve_operand(Operand(ref=("capsule", VALUE_NAMESPACE, "close")), env) == _CLOSE
    assert resolve_operand(Operand(ref=("capsule", VALUE_NAMESPACE, "absent")), env) is UNKNOWN


def test_the_merge_adds_exactly_one_key_and_changes_none() -> None:
    """(§3.2 (1)) Covered Capsule content is untouched by the merge."""
    capsule = _capsule()
    baseline = capsule.model_dump(mode="json")
    merged = dict(build_environment(capsule, _CONFIG, resolved_context=_view())["capsule"])
    assert set(merged) - set(baseline) == {VALUE_NAMESPACE}
    merged.pop(VALUE_NAMESPACE)
    assert merged == baseline


def test_a_namespace_collision_raises_rather_than_shadowing() -> None:
    """(§3.2 (1) ★) The merge refuses to overwrite a Capsule top-level key."""

    class _CollidingCapsule(DecisionContextCapsule):
        def model_dump(self, **kwargs: object) -> dict[str, object]:  # type: ignore[override]
            dumped = super().model_dump(**kwargs)  # type: ignore[arg-type]
            dumped[VALUE_NAMESPACE] = {"smuggled": 1}
            return dumped

    colliding = _CollidingCapsule.model_construct(**dict(_capsule()))
    with pytest.raises(ArtifactIntegrityError, match="collides"):
        build_environment(colliding, _CONFIG, resolved_context=_view())
    # ...and without a view there is nothing to merge, so nothing to refuse.
    assert VALUE_NAMESPACE in build_environment(colliding, _CONFIG)["capsule"]


# ---------------------------------------------------------------------------
# 3. The recorded signature (design #32 §3.2 (3b), MAJOR-2a)
# ---------------------------------------------------------------------------


def test_evaluate_is_unchanged_and_its_committed_canary_still_describes_it() -> None:
    """(§15.2 ③) ``evaluate``'s parameter set is exactly the five names the shipped canary locks."""
    assert set(inspect.signature(evaluate).parameters) == {
        "strategy",
        "capsule",
        "config",
        "scheme",
        "enforcement_mechanism_version",
    }


def test_evaluate_resolved_has_its_own_locked_signature() -> None:
    """(review MINOR-3) The new entry point gets the same structural lock ``evaluate`` has.

    ``evaluate``'s parameter set is pinned by the committed canary at
    ``test_dsl_determinism.py:136-146``; without a mirror here the *new* entry point would be the
    one place a later change could quietly add an ambient parameter. Same discipline, same shape:
    an exact set, plus the explicit ambient-name exclusion.
    """
    parameters = inspect.signature(evaluate_resolved).parameters
    assert set(parameters) == {
        "strategy",
        "capsule",
        "config",
        "scheme",
        "enforcement_mechanism_version",
        "resolved_context",
    }
    assert not set(parameters) & {
        "clock",
        "now",
        "time",
        "random",
        "rng",
        "network",
        "session",
        "fetch",
        "fetcher",
        "loader",
        "callback",
    }
    assert parameters["resolved_context"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["resolved_context"].default is None
    for name in ("scheme", "enforcement_mechanism_version"):
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_evaluate_resolved_adds_exactly_one_parameter_to_evaluate() -> None:
    """(review MINOR-3) The two entry points differ by ``resolved_context`` and nothing else."""
    resolved = set(inspect.signature(evaluate_resolved).parameters)
    plain = set(inspect.signature(evaluate).parameters)
    assert resolved - plain == {"resolved_context"}
    assert plain - resolved == set()


def test_evaluate_resolved_with_no_view_reproduces_evaluate_exactly() -> None:
    """(§3.2 (3)) The value-free path is the old path — outcome and signature both."""
    capsule = _capsule()
    strategy = _strategy(threshold=_CLOSE - 1)
    plain = evaluate(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    threaded = evaluate_resolved(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=None,
    )
    assert threaded.recorded_input_signature == plain.recorded_input_signature
    assert threaded.outcome.canonical_digest == plain.outcome.canonical_digest


def test_the_view_digest_is_appended_to_the_captured_value_refs() -> None:
    """(§3.2 (3b) ★ the MAJOR-2a seal) The fourth decision input joins the recorded provenance."""
    capsule = _capsule()
    result = evaluate_resolved(
        _strategy(threshold=_CLOSE - 1),
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(digest="view-alpha"),
    )
    refs = result.recorded_input_signature.captured_external_value_refs
    assert refs == (capsule.critical_input_snapshot.canonical_digest, "view-alpha")


def test_two_runs_differing_only_in_their_values_differ_in_their_signature() -> None:
    """(§3.2 (3b) ★ mutation canary) Removing the append makes these two signatures identical.

    Same Capsule, same strategy, same config — different resolved values, and therefore a different
    outcome. If the signature did not move with the values, replay would reconstruct one of these
    two runs and silently disagree with the other (RFC-008 §9:302-306).
    """
    capsule = _capsule()
    strategy = _strategy(threshold=_CLOSE - 1)
    high = evaluate_resolved(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(close=_CLOSE, digest="view-high"),
    )
    low = evaluate_resolved(
        strategy,
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(close=_CLOSE - 100, digest="view-low"),
    )
    assert isinstance(low.outcome, NoActionOutcome)
    assert not isinstance(high.outcome, NoActionOutcome)
    assert (
        high.recorded_input_signature.captured_external_value_refs
        != low.recorded_input_signature.captured_external_value_refs
    )
    assert (
        high.recorded_input_signature.capsule_canonical_digest
        == low.recorded_input_signature.capsule_canonical_digest
    ), "the Capsule really is identical — the values are the only difference"


def test_the_same_view_reproduces_the_same_signature() -> None:
    """(§3.2 (3b)) Determinism: no nonce, no clock, no ordering dependence."""
    capsule = _capsule()
    strategy = _strategy(threshold=_CLOSE - 1)
    kwargs = {
        "scheme": SCHEME,
        "enforcement_mechanism_version": ENFORCEMENT_VERSION,
        "resolved_context": _view(digest="view-alpha"),
    }
    first = evaluate_resolved(strategy, capsule, _CONFIG, **kwargs)  # type: ignore[arg-type]
    second = evaluate_resolved(strategy, capsule, _CONFIG, **kwargs)  # type: ignore[arg-type]
    assert first.recorded_input_signature == second.recorded_input_signature


def test_the_signature_shape_is_unchanged() -> None:
    """(§3.2 (3b)) The digest joins the existing ``tuple[str, ...]``; no new signature field."""
    from tos.dsl import RecordedInputSignature

    assert set(RecordedInputSignature.model_fields) == {
        "capsule_id",
        "capsule_canonical_digest",
        "authored_strategy_version",
        "dsl_version",
        "config_version",
        "enforcement_mechanism_version",
        "captured_external_value_refs",
    }


def test_a_resolved_value_can_actually_gate_a_decision() -> None:
    """(§3.2) The end-to-end point of the whole slice: a market number decides an outcome."""
    capsule = _capsule()
    fires = evaluate_resolved(
        _strategy(threshold=_CLOSE - 1),
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(),
    )
    holds = evaluate_resolved(
        _strategy(threshold=_CLOSE + 1),
        capsule,
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
        resolved_context=_view(),
    )
    assert not isinstance(fires.outcome, NoActionOutcome)
    assert isinstance(holds.outcome, NoActionOutcome)


def test_without_a_view_the_same_guard_is_restrictive() -> None:
    """(§6, RFC-008 §10:347-350) No values ⇒ UNKNOWN ⇒ the guard cannot fire."""
    result = evaluate(
        _strategy(threshold=_CLOSE - 1),
        _capsule(),
        _CONFIG,
        scheme=SCHEME,
        enforcement_mechanism_version=ENFORCEMENT_VERSION,
    )
    assert isinstance(result.outcome, NoActionOutcome)
