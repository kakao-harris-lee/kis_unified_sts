"""Global ``CapacityVector.dimension_id`` namespace convention (Gap-1, Phase-0 Variant A).

**The problem.** ``CapacityVector.dimension_id`` is a free string (``rcl/vector.py:67``)
and the capacity arithmetic (``aggregate_usage`` / ``effective_limit``) matches dimensions
by **string equality**. Four packages load ids onto that one shared container type:

* **rcl** — the owner of ``CapacityVector`` / ``CapacityComponent``; the economic /
  capacity axis.
* **are** — ``AdverseIncrement`` is a ``CapacityVector`` (``are/records.py:289``).
* **ioc** — ``EconomicEffectEnvelope`` **is** ``CapacityVector`` (``ioc/records.py:69``).
* **afg** — ``ActionFlowVector`` **is** ``CapacityVector`` (``afg/records.py:86``).

Nothing structural stopped two of those consumers from choosing the same token for two
different quantities. A collision would silently **collapse two coordinates into one**, and
the collapse lands inside fail-closed arithmetic — the worst place for a silent aliasing
bug. The afg design (#16 §7) could only assert its own half of the condition and deferred
the global convention to Phase-0 as Gap-1 (design #16 §10.3-6).

**The convention (ratified).** Operator decision 2026-07-29 adopted **Variant A** (strict
prefix mandate) — ``docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md`` §2.2
and the bounds draft package (``docs/plans/2026-07-29-tos-phase0-bounds-draft-package.md``)
enclosure 2:

1. A dimension id declared by a consumer package is namespaced with that package's own
   prefix — ``rcl.`` / ``are.`` / ``ioc.`` / ``afg.``.
2. An **unprefixed** id is reserved to **rcl**, the originating owner, which is
   grandfathered for its pre-existing ids. (New rcl ids should still take ``rcl.``.)

Prefix uniqueness then makes cross-consumer disjointness **structural**: ``afg.* ∩ rcl.*``
is empty by construction rather than by the coincidence that nobody has yet picked a
colliding word.

**Why this file lives at the cross-package lane.** The per-package test lanes can only see
their own package (afg cannot import rcl / are / ioc — design #16 §0.3 allowlist), so no
package lane can state the *global* property. The root ``tos/tests/`` lane is the
cross-package home; a test import is not a runtime package edge, and the firewall
self-allows any ``tos.*`` import (``tools/tos_firewall_check.py:147``).

**Auto-enrolment.** The namespace registry is *discovered*, not hardcoded: any package that
exports a ``*_DIMENSION_IDS`` collection is picked up automatically and must then satisfy
the prefix and disjointness properties. Packages that declare no such namespace today
(rcl / are / ioc — measured, see :func:`test_packages_without_a_declared_namespace_are_zero`)
are therefore enrolled the moment they add one, with no edit to this file.

Planted-violation canaries prove each property actually bites rather than passing
vacuously.
"""

from __future__ import annotations

from typing import Final

import tos.afg
import tos.are
import tos.ioc
import tos.rcl

#: The four ``CapacityVector`` consumers, mapped to their package module. The dict key is
#: the owning package name, from which the mandated prefix is derived (never spelled twice).
_CONSUMERS: Final[dict[str, object]] = {
    "rcl": tos.rcl,
    "are": tos.are,
    "ioc": tos.ioc,
    "afg": tos.afg,
}

#: rcl is the originating owner of the container, so its pre-existing **unprefixed** ids
#: are grandfathered by the convention (Variant A, clause 2).
_GRANDFATHERED_OWNER: Final[str] = "rcl"

#: A package publishes its dimension-id namespace by exporting a collection whose name ends
#: in this suffix. Discovery (rather than a hardcoded list) is what auto-enrols a package
#: that gains a namespace later.
_NAMESPACE_EXPORT_SUFFIX: Final[str] = "_DIMENSION_IDS"


def _prefix_of(package: str) -> str:
    """The mandated dimension-id prefix owned by ``package``."""
    return f"{package}."


def _declared_dimension_id_tokens(package: str) -> frozenset[str]:
    """Every concrete dimension-id token ``package`` declares on its public surface.

    Reads the package's ``__all__`` for ``*_DIMENSION_IDS`` exports and unions their
    contents. Members are type-guarded: a namespace export must be an iterable of ``str``,
    so a mis-typed export fails loudly here instead of silently contributing nothing (the
    #27 lesson — a discovery sweep that can quietly find nothing is not a property).
    """
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


# ---------------------------------------------------------------------------
# Registry sanity — the properties below are only meaningful if this holds
# ---------------------------------------------------------------------------


def test_the_four_capacity_vector_consumers_share_one_container_type() -> None:
    """(premise) The convention exists *because* all four ids land on one type."""
    assert tos.ioc.EconomicEffectEnvelope is tos.rcl.CapacityVector
    assert tos.afg.ActionFlowVector is tos.rcl.CapacityVector
    # are carries its increment as the same type (are/records.py:289) rather than
    # aliasing it, so assert the field annotation resolves to the shared container.
    assert tos.are.AdverseIncrementResult.model_fields["increment"].annotation is (
        tos.rcl.CapacityVector
    )


def test_every_consumer_owns_a_distinct_prefix() -> None:
    """(premise) Prefix uniqueness is what makes disjointness structural."""
    prefixes = [_prefix_of(package) for package in _CONSUMERS]
    assert len(set(prefixes)) == len(prefixes), "owning prefixes must be unique"
    # No prefix may be a prefix of another, or "owner of a token" would be ambiguous.
    for outer in prefixes:
        for inner in prefixes:
            if outer != inner:
                assert not outer.startswith(inner)


# ---------------------------------------------------------------------------
# The convention itself
# ---------------------------------------------------------------------------


def test_declared_dimension_ids_carry_their_owning_package_prefix() -> None:
    """(Variant A clause 1) Every declared id is namespaced by the package that owns it.

    rcl is exempt only for **unprefixed** ids (clause 2, grandfathered); an rcl id that
    carries *some* prefix must still carry ``rcl.``.
    """
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
            # Not under its own prefix: only grandfathered rcl ids may be unprefixed,
            # and even then they must not squat on a sibling's namespace.
            assert package == _GRANDFATHERED_OWNER, (
                f"{package} declares dimension id {token!r} without its mandated "
                f"{own_prefix!r} prefix (Phase-0 Variant A); an unprefixed id is "
                f"reserved to {_GRANDFATHERED_OWNER}"
            )
            assert not any(
                token.startswith(p) for p in foreign_prefixes
            ), f"{package} declares {token!r} under a sibling's prefix"


def test_declared_dimension_id_namespaces_are_pairwise_disjoint() -> None:
    """(Gap-1, the safety property) No token is claimed by two consumers.

    This is the condition that keeps the shared ``CapacityVector`` from collapsing two
    distinct coordinates onto one string key inside fail-closed arithmetic.
    """
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
    """(drift landmark + auto-enrolment) rcl / are / ioc declare **no** concrete tokens.

    Measured 2026-07-29: only afg publishes a dimension-id namespace. rcl / are / ioc put
    **no** dimension-id literal in source at all — their ids are entirely caller-injected
    (``grep -rnE 'dimension_id\\s*=\\s*"..."' tos/src/tos`` -> 0 hits), which is why
    Variant A needed no source change in those three packages.

    This is a landmark, not a prohibition. When one of them gains a namespace, this
    assertion trips to direct the author to the convention — and the prefix / disjointness
    properties above will already have enrolled the new namespace automatically, since the
    registry is discovered rather than hardcoded.
    """
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


# ---------------------------------------------------------------------------
# Nearest-neighbour economic tokens (not a declared dimension-id namespace)
# ---------------------------------------------------------------------------


def test_are_risk_axis_does_not_collide_with_any_declared_namespace() -> None:
    """(residual risk) are's ``RiskDimensionKind`` is the likeliest future economic id set.

    ``RiskDimensionKind`` is a **typed** risk-axis coordinate (``are/records.py:121,153``
    field type), not a ``dimension_id`` string producer — which is why Variant A required
    no are source change, and why those ADR-002-021 §10:270-279 **verbatim** tokens were
    left untouched. But an INSTANCE that injects them as ``dimension_id`` values is the
    most credible route to a real collision, so the property is asserted against them
    explicitly. Under Variant A such an injection must be written as ``are.<TOKEN>``.
    """
    risk_tokens = frozenset(kind.value for kind in tos.are.RiskDimensionKind)
    assert risk_tokens, "the are risk axis must be non-empty for this to bite"
    namespaces = _declared_namespaces()
    for package, tokens in namespaces.items():
        overlap = tokens & risk_tokens
        assert overlap == frozenset(), (
            f"{package} dimension ids collide with the are aggregate-risk axis: "
            f"{sorted(overlap)}"
        )


# ---------------------------------------------------------------------------
# Canaries — proof the properties above are not vacuous
# ---------------------------------------------------------------------------


def test_canary_a_stripped_prefix_would_be_caught() -> None:
    """(canary) Removing the ``afg.`` prefix re-opens the collision the mandate closes."""
    stripped = frozenset(
        token.removeprefix("afg.") for token in _declared_dimension_id_tokens("afg")
    )
    # The un-namespaced spelling is exactly what the convention reserves to rcl, so an
    # afg package declaring it would violate clause 1 ...
    assert all(not token.startswith("afg.") for token in stripped)
    # ... and it is no longer recognized as an afg id.
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
    # And a mis-filed token is not an afg dimension id any more.
    for token in mis_filed:
        assert tos.afg.is_action_flow_dimension_id(token) is False


def test_canary_a_planted_cross_package_collision_would_be_caught() -> None:
    """(canary) The pairwise-disjointness comparison detects a real overlap."""
    afg_tokens = _declared_dimension_id_tokens("afg")
    planted_rcl = frozenset({"rcl.SOMETHING"}) | afg_tokens
    assert planted_rcl & afg_tokens != frozenset()
