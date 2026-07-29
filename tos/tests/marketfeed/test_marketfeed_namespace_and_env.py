"""§7.2-3/-5/-9 — namespace disjointness, env reachability, and byte-exact backward compatibility.

Three related claims of design #32 §3.2:

1. **disjointness is measured, not declared** (MINOR-3, carried into implementation by the delta
   review). The merge key must be absent from the Capsule's *actual* ``model_dump(mode="json")``
   keys, checked at publication time against the object at hand — not asserted against a
   transcribed seventeen-name list that goes stale the moment a Capsule field is added. A collision
   refuses publication rather than overwriting covered Capsule content.
2. **the merged values are actually reachable** by the shipped interpreter. ``resolve_operand``
   walks dict keys only and demands a scalar leaf (``vocabulary.py:334, 338``), which is exactly why
   the projection is a flat ``{field_key: scalar}`` mapping. A list-shaped exposure would resolve to
   ``UNKNOWN``, i.e. would silently stop working — so reachability is asserted, not assumed.
3. **absence stays restrictive.** No view ⇒ no namespace ⇒ ``UNKNOWN`` ⇒ every comparison ``False``.

Regime tag: authoring evidence only; closes no EV (design #32 §1.1).
"""

from __future__ import annotations

import pytest
from tos.capsule import DecisionContextCapsule
from tos.dsl import (
    UNKNOWN,
    VALUE_NAMESPACE,
    ArtifactIntegrityError,
    Compare,
    CompareOp,
    EvaluationConfig,
    Operand,
    build_environment,
    eval_compare,
    resolve_operand,
)
from tos.marketfeed import (
    ValueViewDisposition,
    capsule_top_level_keys,
    publish_context_value_view,
    value_namespace_is_disjoint,
)

from ._marketfeed_fixtures import CLOSE_BAR_ONE, SCHEME, one_bar

_CONFIG = EvaluationConfig(config_version="cfg-1", bindings={"threshold": CLOSE_BAR_ONE - 1})


def _resolved_env():
    """The environment a resolved bar produces."""
    capsule, snapshot, candidates = one_bar()
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    return capsule, build_environment(capsule, _CONFIG, resolved_context=resolution.view)


# ---------------------------------------------------------------------------
# 1. Disjointness, measured (design #32 §3.2 (1), MINOR-3)
# ---------------------------------------------------------------------------


def test_the_namespace_is_disjoint_from_the_shipped_capsule_key_set() -> None:
    """(§3.2 (1) ★) The check reads the model, so a future Capsule field cannot silently collide."""
    assert value_namespace_is_disjoint() is True
    assert VALUE_NAMESPACE not in capsule_top_level_keys()


def test_disjointness_is_measured_against_the_real_dump_of_the_real_capsule() -> None:
    """(§3.2 (1)) The publication-time check inspects the very mapping the merge writes into."""
    capsule, _, _ = one_bar()
    dumped = set(capsule.model_dump(mode="json"))
    assert capsule_top_level_keys(capsule) == dumped
    assert value_namespace_is_disjoint(capsule) is True


def test_the_class_level_and_instance_level_key_sets_agree_on_the_declared_fields() -> None:
    """(anti-phantom §0.5) The fallback key set is a superset-consistent view, not a guess."""
    capsule, _, _ = one_bar()
    assert set(DecisionContextCapsule.model_fields) <= capsule_top_level_keys(capsule)


def test_a_colliding_namespace_refuses_publication_rather_than_overwriting() -> None:
    """(§3.2 (1) ★ mutation canary) A Capsule that already carries the key blocks the merge.

    Simulated by asking the gate about a Capsule whose dump *does* carry the reserved key — the
    honest way to exercise a branch that a well-formed Capsule can never reach today, without
    mutating the ratified Capsule model.
    """

    class _CollidingCapsule(DecisionContextCapsule):
        """A capsule-shaped stand-in whose dump carries the reserved namespace key."""

        def model_dump(self, **kwargs: object) -> dict[str, object]:  # type: ignore[override]
            dumped = super().model_dump(**kwargs)  # type: ignore[arg-type]
            dumped[VALUE_NAMESPACE] = {"smuggled": 1}
            return dumped

    capsule, snapshot, candidates = one_bar()
    colliding = _CollidingCapsule.model_construct(**dict(capsule))
    assert value_namespace_is_disjoint(colliding) is False
    resolution = publish_context_value_view(
        capsule=colliding, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    assert resolution.disposition is ValueViewDisposition.NAMESPACE_COLLISION
    assert resolution.view is None


def test_build_environment_refuses_to_shadow_a_capsule_key() -> None:
    """(§3.2 (1)) The merge point itself raises rather than overwriting covered content."""

    class _CollidingCapsule(DecisionContextCapsule):
        def model_dump(self, **kwargs: object) -> dict[str, object]:  # type: ignore[override]
            dumped = super().model_dump(**kwargs)  # type: ignore[arg-type]
            dumped[VALUE_NAMESPACE] = {"smuggled": 1}
            return dumped

    capsule, snapshot, candidates = one_bar()
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=candidates, scheme=SCHEME
    )
    colliding = _CollidingCapsule.model_construct(**dict(capsule))
    with pytest.raises(ArtifactIntegrityError, match="collides"):
        build_environment(colliding, _CONFIG, resolved_context=resolution.view)


# ---------------------------------------------------------------------------
# 2. Reachability by the shipped interpreter (design #32 §3.2 (2))
# ---------------------------------------------------------------------------


def test_a_merged_value_is_reachable_as_a_scalar_leaf() -> None:
    """(§3.2 (2) ★) ``("capsule", VALUE_NAMESPACE, "close")`` resolves to the admitted scalar."""
    _, env = _resolved_env()
    operand = Operand(ref=("capsule", VALUE_NAMESPACE, "close"))
    assert resolve_operand(operand, env) == CLOSE_BAR_ONE


def test_the_merge_lands_under_the_capsule_source_not_under_config() -> None:
    """(§3.2, RFC-008 §10:327-331) Market values are Critical Input, never relabelled config."""
    _, env = _resolved_env()
    assert VALUE_NAMESPACE in env["capsule"]
    assert VALUE_NAMESPACE not in env["config"]
    assert set(env) == {"capsule", "config"}, "no third context source is invented"


def test_a_merged_value_participates_in_an_ordering_comparison() -> None:
    """(§2.5) An integer minor-unit value orders against a config-injected threshold."""
    _, env = _resolved_env()
    fired = Compare(
        left=Operand(ref=("capsule", VALUE_NAMESPACE, "close")),
        op=CompareOp.GT,
        right=Operand(ref=("config", "threshold")),
    )
    assert eval_compare(fired, env) is True


def test_an_unpublished_field_resolves_to_unknown_and_compares_false() -> None:
    """(§6, RFC-008 §10:347-350) Absence narrows the action set; it never widens it."""
    _, env = _resolved_env()
    missing = Operand(ref=("capsule", VALUE_NAMESPACE, "lower_band"))
    assert resolve_operand(missing, env) is UNKNOWN
    for op in CompareOp:
        assert (
            eval_compare(Compare(left=missing, op=op, right=Operand(const=0)), env) is False
        ), f"UNKNOWN must be restrictive under {op}"


def test_no_view_means_no_namespace_at_all() -> None:
    """(§6 ∅) With ``resolved_context=None`` the namespace is simply absent — UNKNOWN, restrictive."""
    capsule, _, _ = one_bar()
    env = build_environment(capsule, _CONFIG)
    assert VALUE_NAMESPACE not in env["capsule"]
    assert resolve_operand(Operand(ref=("capsule", VALUE_NAMESPACE, "close")), env) is UNKNOWN


def test_an_explicit_empty_view_is_published_but_reaches_no_value() -> None:
    """(§6 ∅ 양방향) An empty namespace exists and is empty — a defined no-value context."""
    capsule, snapshot, _ = one_bar()
    resolution = publish_context_value_view(
        capsule=capsule, snapshot=snapshot, candidates=(), scheme=SCHEME
    )
    assert resolution.disposition is ValueViewDisposition.EXPLICIT_EMPTY
    env = build_environment(capsule, _CONFIG, resolved_context=resolution.view)
    assert env["capsule"][VALUE_NAMESPACE] == {}
    assert resolve_operand(Operand(ref=("capsule", VALUE_NAMESPACE, "close")), env) is UNKNOWN


# ---------------------------------------------------------------------------
# 3. Backward compatibility (design #32 §7.2-9)
# ---------------------------------------------------------------------------


def test_the_value_free_environment_is_byte_identical_to_the_pre_d_e2_one() -> None:
    """(§7.2-9 ★) ``build_environment(capsule, config)`` is exactly what it always was."""
    capsule, _, _ = one_bar()
    legacy = {
        "capsule": capsule.model_dump(mode="json"),
        "config": dict(_CONFIG.bindings),
    }
    assert build_environment(capsule, _CONFIG) == legacy
    assert build_environment(capsule, _CONFIG, resolved_context=None) == legacy


def test_the_merge_does_not_disturb_any_pre_existing_capsule_key() -> None:
    """(§3.2 (1)) Merging adds one key and changes none — covered content is untouched."""
    capsule, env = _resolved_env()
    baseline = capsule.model_dump(mode="json")
    merged = dict(env["capsule"])
    assert set(merged) - set(baseline) == {VALUE_NAMESPACE}
    merged.pop(VALUE_NAMESPACE)
    assert merged == baseline
