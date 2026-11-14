"""§7.1/§0.3 import-closure + determinism canaries for every kernel package, table-driven."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from . import _closure_children
from ._closure_policy import (
    CLEARED_NON_TOS_PROBES,
    DENIED_NON_TOS_PROBES,
    OPTIONAL_DENIED_PROBES,
    PLANTED_SOURCE,
    SRC_ROOT,
    ClosurePolicy,
    canary_of,
    closure_of,
    closure_of_module,
    scan_offenders,
    statically_imported_modules,
    tos_top_level,
)
from ._closure_table import POLICIES


def _load_all() -> dict[str, dict[str, object]]:
    """Run every package's importer in this process, then bind the modules it loaded."""
    loaded: dict[str, dict[str, object]] = {}
    for name, policy in POLICIES.items():
        _closure_children.IMPORTERS[name]()
        loaded[name] = {module: sys.modules[module] for module in policy.child_imports}
    return loaded


_LOADED = _load_all()


def _importer_imports(key: str) -> tuple[str, ...]:
    """The modules ``_closure_children.IMPORTERS[key]`` really names, read from its source."""
    source = Path(_closure_children.__file__).read_text(encoding="utf-8")
    wanted = _closure_children.IMPORTERS[key].__name__
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == wanted:
            body = node.body[1:] if ast.get_docstring(node) else node.body
            offenders = [
                ast.dump(stmt) for stmt in body if not isinstance(stmt, ast.Import)
            ]
            assert offenders == [], (
                f"{wanted} holds a statement that is not a plain ``import`` — the measured "
                f"closure would not be the one this test reads: {offenders}"
            )
            names = tuple(
                alias.name for stmt in body for alias in stmt.names  # type: ignore[attr-defined]
            )
            assert names, f"{wanted} imports nothing — its canary would be vacuous"
            return names
    raise AssertionError(f"{wanted} is not defined in _closure_children.py")


def _params(predicate) -> list:
    """Parametrize over the policies ``predicate`` selects, keeping the package name as the id."""
    return [
        pytest.param(policy, id=name)
        for name, policy in sorted(POLICIES.items())
        if predicate(policy)
    ]


ALL = _params(lambda _policy: True)
WITH_ALLOWLIST = _params(lambda p: p.allowed_tos is not None)
WITH_EDGES = _params(lambda p: bool(p.edges()))
WITH_SIBLINGS = _params(lambda p: bool(p.forbidden_siblings))
WITH_PLANTED = _params(lambda p: bool(p.planted))
WITH_SCAN = _params(lambda p: p.scan is not None)
WITH_STATIC_SCAN = _params(lambda p: p.static_scan)
WITH_SUITE = _params(lambda p: p.suite_dir is not None)
WITH_SUBMODULE_DIR = _params(lambda p: p.submodule_dir is not None)
WITH_NAMESPACE = _params(lambda p: bool(p.namespace_forbidden))
WITH_BOUND = _params(lambda p: bool(p.bounded_by))
WITH_EVERY_EDGE = _params(lambda p: p.every_edge_is_taken)

_FAMILIES = {
    "allowlist": WITH_ALLOWLIST,
    "edges": WITH_EDGES,
    "siblings": WITH_SIBLINGS,
    "planted": WITH_PLANTED,
    "scan": WITH_SCAN,
    "static_scan": WITH_STATIC_SCAN,
    "suite": WITH_SUITE,
    "submodule_dir": WITH_SUBMODULE_DIR,
    "namespace": WITH_NAMESPACE,
    "bound": WITH_BOUND,
    "every_edge": WITH_EVERY_EDGE,
}


def test_the_table_is_populated_and_no_family_is_empty() -> None:
    """∅-seal: a predicate that selects nothing would make its whole test silently not run."""
    assert (
        len(POLICIES) == 24
    ), f"the closure table holds {len(POLICIES)} policies, not 24"
    assert {param.values[0].name for param in ALL} == set(POLICIES)
    empty = sorted(name for name, family in _FAMILIES.items() if not family)
    assert empty == [], f"parametrized families select no policy at all: {empty}"


def _bound(policy: ClosurePolicy) -> set[str]:
    """The declared allowlist widened by the closure of each package it may consume."""
    assert policy.allowed_tos is not None
    bound = set(policy.allowed_tos)
    for module in policy.bounded_by:
        bound |= set(closure_of_module(policy, module)["tos_tops"])
    return bound


@pytest.mark.parametrize("policy", ALL)
def test_closure_has_no_forbidden_package(policy: ClosurePolicy) -> None:
    """(§7.1 items 1-4) A fresh import of the package pulls no denied package into the closure."""
    result = closure_of(policy)
    assert (
        result["forbidden"] == []
    ), f"forbidden packages reached the tos.{policy.name} closure: {result['forbidden']}"


@pytest.mark.parametrize("policy", WITH_ALLOWLIST)
def test_closure_is_within_the_declared_allowlist(policy: ClosurePolicy) -> None:
    """(§0.3 allowlist) The tos closure stays inside the declared packages (plus any consumed one)."""
    result = closure_of(policy)
    extra = sorted(set(result["tos_tops"]) - _bound(policy))
    assert extra == [], f"tos.{policy.name} closure escaped its declared bound: {extra}"


@pytest.mark.parametrize("policy", WITH_EDGES)
def test_closure_contains_every_declared_edge(policy: ClosurePolicy) -> None:
    """(anti-phantom) Every declared edge is really taken — the allowlist is not padded."""
    present = closure_of(policy)["present"]
    missing = sorted(name for name in policy.edges() if not present[name])
    assert (
        missing == []
    ), f"declared edges missing from the tos.{policy.name} closure: {missing}"


@pytest.mark.parametrize("policy", WITH_SIBLINGS)
def test_closure_excludes_every_forbidden_sibling(policy: ClosurePolicy) -> None:
    """(§0.3/§4.5/§5.4) Send-boundary, downstream and unrelated siblings stay outside the closure."""
    tops = set(closure_of(policy)["tos_tops"])
    leaked = sorted(name for name in policy.forbidden_siblings if name in tops)
    assert leaked == [], f"siblings leaked into the tos.{policy.name} closure: {leaked}"


@pytest.mark.parametrize("policy", WITH_PLANTED)
def test_leak_canary_is_detected(policy: ClosurePolicy) -> None:
    """(both-ways) The spawn+scan pipeline catches every planted leak — it is not vacuously green."""
    result = canary_of(policy)
    if policy.allowed_tos is not None:
        extra = set(result["tos_tops"]) - _bound(policy)
        for expected in policy.planted_tos():
            assert expected in extra, f"planted {expected} leak was NOT detected"
        for expected in policy.planted_non_tos():
            assert (
                expected in result["forbidden"]
            ), f"planted {expected} was NOT detected"
        return
    for expected in policy.planted:
        assert expected in result["forbidden"], f"planted {expected} was NOT detected"


@pytest.mark.parametrize("policy", ALL)
def test_denylist_classifier_canaries(policy: ClosurePolicy) -> None:
    """The denylist flags every operational package and every named sibling, and clears the rest."""
    for name in DENIED_NON_TOS_PROBES:
        assert policy.denies(name) is True, f"{name} is not denied by {policy.name}"
    for name in OPTIONAL_DENIED_PROBES:
        if name in policy.deny_exact:
            assert policy.denies(name) is True
            assert policy.denies(f"{name}.sub") is True
    for sibling in policy.denied_tos_siblings():
        assert policy.denies(sibling) is True
        assert policy.denies(f"{sibling}.predicates") is True
        assert policy.denies(f"{sibling}.records") is True
    for name in CLEARED_NON_TOS_PROBES + policy.cleared_canaries:
        assert (
            policy.denies(name) is False
        ), f"{name} is wrongly denied by {policy.name}"


@pytest.mark.parametrize("policy", WITH_ALLOWLIST)
def test_allowlist_classifier_canaries(policy: ClosurePolicy) -> None:
    """The declared allowlist admits every allowed module and rejects every sibling, born or not."""
    for name in policy.allowed_canaries:
        assert policy.admits(name) is True, f"{name} is not admitted by {policy.name}"
    for sibling in policy.rejected_tos_siblings():
        assert policy.admits(sibling) is False
        assert policy.admits(f"{sibling}.predicates") is False
    for name in policy.indirect_only:
        assert policy.admits(name) is True
        assert policy.admits_directly(name) is False


@pytest.mark.parametrize("policy", WITH_SCAN)
def test_source_has_no_escape_env_clock_rng_or_network(policy: ClosurePolicy) -> None:
    """(§7.1 item 6) No shipped source reaches for a dynamic escape, ambient env, clock, RNG or net."""
    assert policy.scan is not None
    sources = policy.sources()
    assert sources, f"no tos.{policy.name} source files found under {policy.src_dirs}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(scan_offenders(path, policy.scan))
    assert (
        offenders == []
    ), f"forbidden construct found in tos.{policy.name} sources: {offenders}"


@pytest.mark.parametrize("policy", WITH_SUITE)
def test_the_test_suite_is_held_to_the_same_rule(policy: ClosurePolicy) -> None:
    """(§9) The suite models nothing the shipped package forbids — including here."""
    assert policy.scan is not None and policy.suite_dir is not None
    suite = sorted((Path(__file__).resolve().parent / policy.suite_dir).rglob("*.py"))
    assert suite, f"no suite files found for tos.{policy.name}"
    offenders: list[str] = []
    for path in suite:
        offenders.extend(scan_offenders(path, policy.scan))
    assert (
        offenders == []
    ), f"forbidden construct found in the {policy.name} suite: {offenders}"


@pytest.mark.parametrize("policy", WITH_SCAN)
def test_the_ast_scan_detects_planted_constructs(
    policy: ClosurePolicy, tmp_path: Path
) -> None:
    """The AST scan really catches planted escapes, clocks, RNG, network and nondeterminism."""
    assert policy.scan is not None
    planted = tmp_path / "planted.py"
    planted.write_text(PLANTED_SOURCE, encoding="utf-8")
    joined = " ".join(scan_offenders(planted, policy.scan))
    for expected in policy.scan.planted_markers():
        assert expected in joined, f"the AST scan missed a planted {expected}"


@pytest.mark.parametrize("policy", WITH_STATIC_SCAN)
def test_source_imports_no_module_outside_the_allowlist(policy: ClosurePolicy) -> None:
    """(§0.3 static mirror) No source statically names a ``tos.*`` module off the declared list."""
    offenders: list[str] = []
    for path in policy.sources():
        for name, lineno in statically_imported_modules(path):
            if not policy.admits_directly(name):
                offenders.append(f"{path.name}:{lineno} import {name}")
    assert offenders == [], f"forbidden sibling import in source: {offenders}"


@pytest.mark.parametrize("policy", WITH_EVERY_EDGE)
def test_every_declared_edge_is_really_imported(policy: ClosurePolicy) -> None:
    """(anti-phantom) No allowlist entry is a dead name, and no deferred edge has been taken early."""
    assert policy.allowed_tos is not None
    imported: set[str] = set()
    for path in policy.sources():
        for name, _lineno in statically_imported_modules(path):
            top = tos_top_level(name)
            if top is not None:
                imported.add(top)
    unused = policy.allowed_tos - imported - {"tos"}
    assert unused == set(), f"allowlist entries are never imported: {sorted(unused)}"
    taken = policy.declared_but_not_taken & imported
    assert taken == set(), f"{sorted(taken)} is now imported — add it to the allowlist"


@pytest.mark.parametrize("policy", WITH_SUBMODULE_DIR)
def test_every_submodule_is_covered_by_the_closure_child(policy: ClosurePolicy) -> None:
    """Anti-phantom: the closure child imports **every** shipped submodule, not a stale subset."""
    assert policy.submodule_dir is not None
    package = f"tos.{policy.submodule_dir}"
    src = SRC_ROOT / policy.submodule_dir
    on_disk = {
        f"{package}.{path.stem}" if path.stem != "__init__" else package
        for path in src.glob("*.py")
    }
    assert (
        on_disk == set(policy.declared_submodules) == set(_LOADED[policy.name])
    ), f"the shipped submodule set and the child's import list have drifted: {sorted(on_disk)}"


@pytest.mark.parametrize("policy", WITH_NAMESPACE)
def test_namespace_exposes_no_sibling_or_mutation_symbol(policy: ClosurePolicy) -> None:
    """(author-level lock) No mutation, construction or other authority's symbol is reachable."""
    root = sys.modules[f"tos.{policy.name}"]
    for name in policy.namespace_forbidden:
        assert not hasattr(root, name), f"tos.{policy.name} exposes {name!r}"
    if not policy.namespace_all_submodules:
        return
    for module_name, module in _LOADED[policy.name].items():
        for name in policy.namespace_forbidden:
            assert name not in vars(module), f"{module_name} exposes {name!r}"


@pytest.mark.parametrize("policy", WITH_BOUND)
def test_the_consumed_package_edge_is_real(policy: ClosurePolicy) -> None:
    """(anti-phantom) The widening package really has a closure — the bound is not a free pass."""
    for name in policy.bounded_by:
        tops = set(closure_of_module(policy, name)["tos_tops"])
        assert name in tops, f"{name} reports no closure of its own"


@pytest.mark.parametrize("policy", ALL)
def test_the_closure_child_imports_exactly_the_declared_modules(
    policy: ClosurePolicy,
) -> None:
    """Anti-phantom: the child's real ``import`` statements are the policy's declared edge set."""
    assert _importer_imports(policy.name) == policy.child_imports, (
        f"_closure_children.import_{policy.name} and POLICIES[{policy.name!r}].child_imports "
        "have drifted — the measured closure would not be the declared one"
    )
    assert _importer_imports(f"{policy.name}:root") == policy.canary_imports
    for module in policy.bounded_by:
        assert _importer_imports(f"module:{module}") == (module,), (
            f"the importer for module:{module} names more than {module} — the bound it widens "
            "the allowlist by would be measured too wide, and no other test would notice"
        )


_PINNED_SHAPES: dict[str, tuple[int, int, int, int, int, int]] = {
    "afg": (14, 13, 5, 0, 6, 7),
    "are": (25, 24, 0, 0, 6, 7),
    "authority": (17, 16, 0, 0, 9, 5),
    "backtest": (15, 14, 17, 18, 12, 9),
    "brokeradapter": (14, 13, 6, 17, 3, 5),
    "brokercap": (23, 22, 0, 0, 6, 5),
    "capsule": (12, 11, 0, 0, 11, 2),
    "cur": (14, 13, 4, 28, 6, 8),
    "dsl": (14, 13, 0, 0, 11, 3),
    "egress": (14, 13, 4, 28, 6, 8),
    "egressgw": (14, 13, 12, 16, 9, 6),
    "engine": (14, 13, 15, 17, 14, 8),
    "evidence": (13, 12, 0, 0, 14, 2),
    "iap": (29, 28, 0, 0, 6, 6),
    "ioc": (26, 25, 0, 0, 6, 7),
    "marketfeed": (14, 13, 16, 19, 6, 7),
    "orthostate": (20, 19, 0, 0, 6, 7),
    "posttrade": (14, 13, 4, 23, 5, 25),
    "rcl": (16, 15, 0, 0, 11, 4),
    "recon": (22, 21, 0, 0, 6, 5),
    "staterestore": (20, 19, 0, 0, 5, 4),
    "time": (15, 14, 0, 0, 8, 4),
    "venue": (14, 13, 4, 18, 6, 6),
    "workload": (20, 19, 0, 0, 4, 4),
}

_NO_SOURCE_SCAN = frozenset({"brokeradapter"})
_NO_DETERMINISM_DENIAL = frozenset({"capsule", "evidence"})
_NO_YAML_DENIAL = frozenset({"capsule", "dsl", "evidence", "time"})


def _shape(policy: ClosurePolicy) -> tuple[int, int, int, int, int, int]:
    """The declared-fact sizes this package is pinned to."""
    return (
        len(policy.deny_exact),
        len(policy.deny_prefixes),
        len(policy.allowed_tos or ()),
        len(policy.forbidden_siblings),
        len(policy.child_imports),
        len(policy.planted),
    )


def test_the_declared_facts_are_pinned() -> None:
    """A floor the canaries cannot move: they read the table, so the table's size is pinned here."""
    measured = {name: _shape(policy) for name, policy in POLICIES.items()}
    assert measured == _PINNED_SHAPES, (
        "a declared fact was added or removed. Every canary above reads the same table, so a "
        "deletion there would make them agree with themselves and stay green — this pin is what "
        "goes red instead. Update it in the same commit, with the reason in the PR body."
    )


def test_the_scan_and_denial_exceptions_are_pinned() -> None:
    """The three families that are deliberately scanned or denied less are named, not inferred."""
    assert {n for n, p in POLICIES.items() if p.scan is None} == _NO_SOURCE_SCAN
    assert {
        n for n, p in POLICIES.items() if "shared.determinism" not in p.deny_exact
    } == _NO_DETERMINISM_DENIAL
    assert {
        n for n, p in POLICIES.items() if "yaml" not in p.deny_exact
    } == _NO_YAML_DENIAL
    starved = sorted(
        n
        for n, p in POLICIES.items()
        if p.scan is not None and "env" not in p.scan.categories
    )
    assert starved == [], f"these packages no longer scan for ambient env: {starved}"
