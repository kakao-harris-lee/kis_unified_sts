"""Global ``CapacityVector.dimension_id`` namespace convention (Gap-1, Phase-0 Variant A)."""

from __future__ import annotations

from typing import Final

import tos.afg
import tos.are
import tos.ioc
import tos.rcl

_CONSUMERS: Final[dict[str, object]] = {
    "rcl": tos.rcl,
    "are": tos.are,
    "ioc": tos.ioc,
    "afg": tos.afg,
}

_GRANDFATHERED_OWNER: Final[str] = "rcl"

_NAMESPACE_EXPORT_SUFFIX: Final[str] = "_DIMENSION_IDS"


def _prefix_of(package: str) -> str:
    """The mandated dimension-id prefix owned by ``package``."""
    return f"{package}."


def _declared_dimension_id_tokens(package: str) -> frozenset[str]:
    """Every concrete dimension-id token ``package`` declares on its public surface."""
    module = _CONSUMERS[package]
    tokens: set[str] = set()
    for name in getattr(module, "__all__", ()):
        if not name.endswith(_NAMESPACE_EXPORT_SUFFIX):
            continue
        value = getattr(module, name)
        assert not isinstance(value, (str, bytes)), (
            f"tos.{package}.{name} must be a collection of dimension-id tokens, "
            f"not a bare string"
        )
        members = tuple(value)
        for member in members:
            assert isinstance(
                member, str
            ), f"tos.{package}.{name} member {member!r} must be a str dimension id"
        tokens.update(members)
    return frozenset(tokens)


def _declared_namespaces() -> dict[str, frozenset[str]]:
    """The discovered namespace registry: owning package -> its declared tokens."""
    return {package: _declared_dimension_id_tokens(package) for package in _CONSUMERS}


def test_the_four_capacity_vector_consumers_share_one_container_type() -> None:
    """(premise) The convention exists *because* all four ids land on one type."""
    assert tos.ioc.EconomicEffectEnvelope is tos.rcl.CapacityVector
    assert tos.afg.ActionFlowVector is tos.rcl.CapacityVector
    assert tos.are.AdverseIncrementResult.model_fields["increment"].annotation is (
        tos.rcl.CapacityVector
    )


def test_every_consumer_owns_a_distinct_prefix() -> None:
    """(premise) Prefix uniqueness is what makes disjointness structural."""
    prefixes = [_prefix_of(package) for package in _CONSUMERS]
    assert len(set(prefixes)) == len(prefixes), "owning prefixes must be unique"
    for outer in prefixes:
        for inner in prefixes:
            if outer != inner:
                assert not outer.startswith(inner)


def test_declared_dimension_ids_carry_their_owning_package_prefix() -> None:
    """(Variant A clause 1) Every declared id is namespaced by the package that owns it."""
    namespaces = _declared_namespaces()
    assert any(namespaces.values()), (
        "no package declares any dimension-id token — the prefix property would be "
        "vacuously true (afg is expected to declare its action-flow namespace)"
    )
    for package, tokens in namespaces.items():
        own_prefix = _prefix_of(package)
        foreign_prefixes = {
            _prefix_of(other) for other in _CONSUMERS if other != package
        }
        for token in tokens:
            if token.startswith(own_prefix):
                assert (
                    token != own_prefix
                ), f"{package}: {token!r} is a bare prefix and names no dimension"
                continue
            assert package == _GRANDFATHERED_OWNER, (
                f"{package} declares dimension id {token!r} without its mandated "
                f"{own_prefix!r} prefix (Phase-0 Variant A); an unprefixed id is "
                f"reserved to {_GRANDFATHERED_OWNER}"
            )
            assert not any(
                token.startswith(p) for p in foreign_prefixes
            ), f"{package} declares {token!r} under a sibling's prefix"


def test_declared_dimension_id_namespaces_are_pairwise_disjoint() -> None:
    """(Gap-1, the safety property) No token is claimed by two consumers."""
    namespaces = _declared_namespaces()
    packages = sorted(namespaces)
    for i, left in enumerate(packages):
        for right in packages[i + 1 :]:
            overlap = namespaces[left] & namespaces[right]
            assert overlap == frozenset(), (
                f"dimension-id collision between {left} and {right} on the shared "
                f"CapacityVector container: {sorted(overlap)}"
            )


def test_no_package_declares_a_token_under_a_siblings_prefix() -> None:
    """(namespace squatting) Owning a prefix means nobody else may write into it."""
    namespaces = _declared_namespaces()
    for package, tokens in namespaces.items():
        for other in _CONSUMERS:
            if other == package:
                continue
            foreign = _prefix_of(other)
            squatted = {token for token in tokens if token.startswith(foreign)}
            assert (
                squatted == set()
            ), f"{package} declares tokens inside {other}'s namespace: {sorted(squatted)}"


def test_packages_without_a_declared_namespace_are_zero() -> None:
    """(drift landmark + auto-enrolment) rcl / are / ioc declare **no** concrete tokens."""
    namespaces = _declared_namespaces()
    for package in ("rcl", "are", "ioc"):
        assert namespaces[package] == frozenset(), (
            f"tos.{package} now declares dimension-id tokens {sorted(namespaces[package])}. "
            f"They are auto-enrolled in the prefix / disjointness properties above; update "
            f"this landmark once you have confirmed they carry the "
            f"{_prefix_of(package)!r} prefix (Phase-0 Variant A)."
        )


def test_afg_namespace_is_non_empty_and_fully_prefixed() -> None:
    """(anti-vacuity) afg is the one package with concrete tokens — it must really bite."""
    afg_tokens = _declared_dimension_id_tokens("afg")
    assert len(afg_tokens) == 13, (
        f"expected the 13 ADR-002-022 §5.6:133 action-flow dimensions, got "
        f"{len(afg_tokens)}: {sorted(afg_tokens)}"
    )
    assert afg_tokens == frozenset(tos.afg.ACTION_FLOW_DIMENSION_IDS)
    assert all(token.startswith("afg.") for token in afg_tokens)


def test_are_risk_axis_does_not_collide_with_any_declared_namespace() -> None:
    """(residual risk) are's ``RiskDimensionKind`` is the likeliest future economic id set."""
    risk_tokens = frozenset(kind.value for kind in tos.are.RiskDimensionKind)
    assert risk_tokens, "the are risk axis must be non-empty for this to bite"
    namespaces = _declared_namespaces()
    for package, tokens in namespaces.items():
        overlap = tokens & risk_tokens
        assert overlap == frozenset(), (
            f"{package} dimension ids collide with the are aggregate-risk axis: "
            f"{sorted(overlap)}"
        )


def test_canary_a_stripped_prefix_would_be_caught() -> None:
    """(canary) Removing the ``afg.`` prefix re-opens the collision the mandate closes."""
    stripped = frozenset(
        token.removeprefix("afg.") for token in _declared_dimension_id_tokens("afg")
    )
    assert all(not token.startswith("afg.") for token in stripped)
    for token in stripped:
        assert tos.afg.is_action_flow_dimension_id(token) is False


def test_canary_a_sibling_prefix_typo_would_be_caught() -> None:
    """(canary) A token mis-filed under a sibling's prefix is detectable as squatting."""
    afg_tokens = _declared_dimension_id_tokens("afg")
    mis_filed = {f"rcl.{token.removeprefix('afg.')}" for token in afg_tokens}
    squatted = {token for token in mis_filed if token.startswith(_prefix_of("rcl"))}
    assert (
        squatted == mis_filed
    ), "the squatting detector must flag every mis-filed token"
    for token in mis_filed:
        assert tos.afg.is_action_flow_dimension_id(token) is False


def test_canary_a_planted_cross_package_collision_would_be_caught() -> None:
    """(canary) The pairwise-disjointness comparison detects a real overlap."""
    afg_tokens = _declared_dimension_id_tokens("afg")
    planted_rcl = frozenset({"rcl.SOMETHING"}) | afg_tokens
    assert planted_rcl & afg_tokens != frozenset()
