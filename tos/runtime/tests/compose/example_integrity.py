"""Shared machinery for asserting a shipped ``tos/runtime/config/*.example.yaml`` document is
STRUCTURALLY complete — as opposed to merely "refuses to load", which a document missing an
entire required key ALSO does, identically, to a document that carries the key as an explicit
``null`` (every ``tos_runtime.*``/``tos_runtime.compose._*`` loader treats "key absent" and "key
present but null" as the SAME named-TBD refusal — ``raw.get(key) is None`` does not distinguish
them). A naive ``pytest.raises(SomeConfigError)`` around a shipped example therefore CANNOT catch
a whole required key being missing from the document: the loader refuses either way, for what
looks like the right reason, and the test stays green.

Closes the class ``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md`` names A-0b:
``safety_activation.example.yaml`` satisfied ONE of its two real readers
(``tos_runtime.safety.profile``'s ``activation:``/``not_expired:`` schema) while silently missing
the key a SECOND, independent reader added later (``tos_runtime.venue.activation
.load_activation_members``'s ``members:`` key) — the exact same shape of bug W2 hit once already
for ``marketfeed.example.yaml``'s missing ``intake_kind`` (commit ``47cf1671``), which is why this
module makes the check itself, not just one more instance fix.

Three independent assertions close this, together:

* :func:`assert_required_paths_present` — the document declared in ``config/EXAMPLE_NAME
  .example.yaml`` must carry every key path any of its real readers require, as an EXPLICIT key
  (value may be ``null`` — that is the correct named-TBD template state) at every level.
* :func:`assert_shipped_example_still_refuses` — the loader must still refuse to load the shipped
  document (a value-leak detector — see its own docstring), for readers whose loader has at least
  one per-field null/TBD check of its own to fail on.
* :func:`assert_shipped_example_is_a_template` — every leaf of the document is ``null``/``[]``
  (a DIFFERENT value-leak detector, for a reader — ``tos_runtime.safety.profile._load_documents``'s
  ``HardSafetyEnvelope``/``RuntimeSafetyProfile`` halves — whose kernel record has every field
  optional, so nothing in that loader ever raises on a filled-in leaf; see that function's own
  docstring for why "does it still refuse" cannot substitute here. A PR #737 review caught this
  exact gap: the module comment above ``EXAMPLE_LOADERS`` in ``example_integrity_registry.py``
  once claimed ``safety_envelope``/``safety_profile`` "get their own targeted test", but the only
  test touching them (``test_safety_activation_still_refuses_on_both_independent_readers``) only
  ever raises via ``activation``'s ``not_expired`` — replacing either file's content wholesale
  with concrete-looking values left the whole suite green.
* :func:`assert_touchpoints_match` — a live grep of ``tos_runtime`` for the config's own deployed
  filename literal (``f'"{stem}.yaml"'``) must match a RECORDED set of touch-point files exactly.
  A new file referencing that literal (a new wiring call site, or a genuinely new independent
  schema reader) flips this red until a human looks — this is what makes the check follow a NEW
  loader being added later, rather than rotting the moment ``EXAMPLE_REQUIRED_PATHS`` goes stale
  (the "레지스트리 + 고정 안 된 위성" class this repo has already hit once at the kernel layer).

PR #737 review round 2 found TWO further gaps, both closed here rather than by instance:

* The coverage LEDGER itself (``test_shipped_example_integrity.test_every_registered_example_has
  _value_leak_coverage``, added to close the first round's gap) tracked which of the four checks
  above applies to each config via two hand-typed ``frozenset``s that named stems but called
  nothing — reproduced by removing ``backtest_calibration`` from ``EXAMPLE_LOADERS`` (deleting
  its REAL check) and adding its name to the bogus set instead: the whole suite stayed green.
  Fixed by making those two categories real dicts of callables
  (``example_integrity_registry.LOADS_SUCCESSFULLY_LOADERS``/``MULTI_READER_CHECKS``) that a
  parametrized test actually iterates and calls — :func:`assert_safety_activation_refuses_on_both
  _readers` and :func:`assert_risk_refuses_on_both_readers` are the two standalone checks
  ``MULTI_READER_CHECKS`` registers; ``LOADS_SUCCESSFULLY_LOADERS`` reuses the existing
  ``LoaderSpec`` shape. The ledger sets are now DERIVED (``frozenset(THE_DICT)``), so naming a
  stem "covered" and making it actually get called are the same act.
* :func:`is_template_document`'s leaf-flattener silently dropped an EMPTY MAPPING (``{}``) —
  reproduced by collapsing ``safety_envelope.example.yaml``'s ``envelope_version:`` block (7
  required ``null`` subfields) to ``envelope_version: {}``: neither this function nor
  ``assert_required_paths_present`` (registered only one level deep for this config) caught it.
  Fixed generically in :func:`_leaf_values` (an empty mapping is now itself a leaf, exactly like
  an empty list already was) rather than by registering those 7 subfields as explicit required
  paths — the latter would have closed only this one instance, not the class (a different block
  collapsing the same way elsewhere would still slip through a paths-list fix).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"

#: A key path into a nested mapping, e.g. ``("activation", "not_expired")``.
KeyPath = tuple[str, ...]

#: A statically-imported loader callable plus its own extra keyword arguments (never sourced from
#: the example file itself — see each ``EXAMPLE_LOADERS`` entry's own comment in
#: ``example_integrity_registry.py``). Deliberately a plain callable, not a
#: ``(module_name, func_name)`` string pair resolved via ``importlib.import_module`` at test time
#: — the tos import firewall (``tools/tos_firewall_check.py`` rule TOS-FW-D) forbids dynamic
#: import/``getattr``-chain dispatch precisely to close that static-analysis escape hatch, and
#: this test tree is scanned by that same firewall (module docstring's own §2.4 note: "a test
#: that imports a forbidden module breaks the hermetic claim").
LoaderSpec = tuple[Callable[..., Any], dict[str, Any]]


def load_example_document(stem: str) -> Any:
    """Parse ``config/{stem}.example.yaml`` and return the raw YAML value (a ``dict`` for every
    config this module knows about)."""
    path = CONFIG_DIR / f"{stem}.example.yaml"
    assert path.is_file(), f"fixture assumption: {path} ships in this repo"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def has_key_path(document: Any, path: KeyPath) -> bool:
    """``True`` iff every key in ``path`` is an EXPLICIT key of ``document`` at its own nesting
    level — the value at the final key may be ``null`` (the named-TBD template convention this
    whole codebase uses) and this still returns ``True``. Returns ``False`` the moment a key is
    absent from a mapping at any level, which is the one thing ``dict.get`` cannot tell apart
    from "present and null" — exactly the gap this module exists to check independently of the
    loaders themselves."""
    node = document
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def assert_required_paths_present(stem: str, required_paths: list[KeyPath]) -> None:
    """Assert every path in ``required_paths`` is an explicit key of ``config/{stem}
    .example.yaml`` at every nesting level (see :func:`has_key_path`). Raising here means a copy
    of this template would refuse to boot for a STRUCTURAL reason — a key genuinely missing from
    the document — never because a leaf still needs an operator-filled value."""
    document = load_example_document(stem)
    assert isinstance(
        document, dict
    ), f"{stem}.example.yaml must be a top-level mapping"
    missing = [
        ".".join(path) for path in required_paths if not has_key_path(document, path)
    ]
    assert not missing, (
        f"{stem}.example.yaml is missing required key path(s) {missing} that its own reader(s) "
        "demand. A deployment config copied from this template would refuse to boot for a "
        "STRUCTURAL reason (the key is not there at all), not because a named-TBD placeholder "
        "needs filling. Add the key in named-TBD form (null, matching every other leaf in this "
        "file) — do not invent a concrete value (docs/plans/2026-09-18-tos-config-adoption-and-"
        "carryover-plan.md §0.1.4)."
    )


def touchpoint_files(stem: str) -> frozenset[str]:
    """Live-grep every ``*.py`` file under ``tos/runtime/src`` for the literal deployed filename
    (``"{stem}.yaml"``) and return the set of files (paths relative to ``tos/runtime/src``) where
    it appears — comments and docstrings included on purpose: a NEW mention is exactly the signal
    this check exists to surface, whether it turns out to be a real new reader or not.
    """
    literal = f'"{stem}.yaml"'
    found: set[str] = set()
    for path in RUNTIME_SRC.rglob("*.py"):
        if literal in path.read_text(encoding="utf-8"):
            found.add(str(path.relative_to(RUNTIME_SRC)))
    return frozenset(found)


def call_loader(spec: LoaderSpec, path: Path) -> Any:
    """Call ``spec``'s statically-imported loader callable with ``path`` as the sole positional
    argument plus ``spec``'s own keyword arguments."""
    loader, kwargs = spec
    return loader(path, **kwargs)


def assert_shipped_example_still_refuses(stem: str, spec: LoaderSpec) -> None:
    """Call ``spec``'s loader against ``config/{stem}.example.yaml`` and assert it raises.

    Every shipped example in ``EXAMPLE_LOADERS`` is an all-``null`` template (module docstrings
    across this codebase say so explicitly) — it must still refuse to load as-is. A loader that
    unexpectedly SUCCEEDS on the shipped example means a real, filled-in value leaked into a file
    that is supposed to ship as a template — a different bug from the structural one
    :func:`assert_required_paths_present` targets, but one this same sweep should still catch.
    """
    example_path = CONFIG_DIR / f"{stem}.example.yaml"
    loader, _ = spec
    try:
        result = call_loader(spec, example_path)
    except Exception:  # noqa: BLE001 - any refusal is the expected outcome here
        return
    raise AssertionError(
        f"{stem}.example.yaml loaded successfully via {loader.__module__}.{loader.__qualname__} "
        f"instead of refusing (got {result!r}) — this file is supposed to ship as an all-null "
        "template; a concrete value appears to have leaked into it."
    )


def _leaf_values(node: Any) -> list[Any]:
    """Flatten ``node`` into its leaf values — recursing through NON-EMPTY mappings and lists,
    but treating an EMPTY mapping OR an empty list as itself a leaf.

    An empty list IS a valid named-TBD leaf value this codebase's loaders already accept (the
    "explicit empty list" convention, e.g. ``scope: []``/``members: []``) — but an empty mapping
    is NOT: a real ``{...}`` block collapsed to ``{}`` is a required sub-structure gone missing
    (PR #737 review, second HIGH finding — a re-review confirmed ``safety_envelope.example
    .yaml``'s ``envelope_version:`` block, 7 required ``null`` subfields, collapses to
    ``envelope_version: {}`` completely undetected: the ORIGINAL version of this function
    recursed into an empty dict exactly like a non-empty one, found zero leaves under it, and
    contributed nothing to :func:`is_template_document`'s ``all(...)`` — which is vacuously
    ``True`` over zero elements. Both ``{}`` and ``[]`` are therefore returned AS leaves here so
    :func:`is_template_document` can tell them apart — ``[]`` passes, ``{}`` fails (neither
    ``None`` nor ``[]``) — instead of the empty-mapping case silently vanishing from the walk.
    This mirrors the exact class of bug this whole module exists to catch at the loader layer
    (a required key/block gone missing, not merely unfilled) — just one level lower, inside the
    leaf-flattener itself."""
    if isinstance(node, dict):
        if not node:
            return [node]
        leaves: list[Any] = []
        for value in node.values():
            leaves.extend(_leaf_values(value))
        return leaves
    if isinstance(node, list):
        if not node:
            return [node]
        leaves = []
        for item in node:
            leaves.extend(_leaf_values(item))
        return leaves
    return [node]


def is_template_document(document: Any) -> bool:
    """``True`` iff every leaf of ``document`` (see :func:`_leaf_values`) is ``None`` or an empty
    list — i.e. the document is STILL the all-placeholder template, never a concrete instance. An
    empty MAPPING (``{}``) is never a valid leaf here (see :func:`_leaf_values`'s own docstring)
    — no example this module registers uses one legitimately (confirmed by grep across every
    shipped ``*.example.yaml`` before this predicate was tightened, PR #737 review round 2).

    Exists for readers whose loader has NO per-field null/TBD check of its own to fail on (e.g.
    ``tos_runtime.safety.profile._load_documents``'s ``HardSafetyEnvelope``/``RuntimeSafetyProfile``
    halves — every field on both kernel records is ``X | None = None``, so
    ``model_validate`` accepts an all-``null`` mapping AND an all-filled-in one identically;
    nothing in that path ever raises on the envelope/profile leaves themselves). For those,
    :func:`assert_shipped_example_still_refuses` cannot detect a real value leaking into the
    shipped example — there is nothing left in the loader to refuse it — so this checks the
    document directly instead."""
    return all(leaf is None or leaf == [] for leaf in _leaf_values(document))


def assert_shipped_example_is_a_template(stem: str) -> None:
    """Assert every leaf of ``config/{stem}.example.yaml`` is ``None``/``[]`` (see
    :func:`is_template_document`).

    Use this — INSTEAD OF, never in addition to expecting a raise from,
    :func:`assert_shipped_example_still_refuses` — for a config whose loader validates via a
    kernel record with universally-optional fields (module docstring's own note): such a loader
    genuinely never refuses a filled-in example, so "does it still refuse" cannot catch a real
    value leaking in; asserting the document's own leaves directly is the only check left that
    can.
    """
    document = load_example_document(stem)
    assert is_template_document(document), (
        f"{stem}.example.yaml has at least one non-null, non-empty leaf — its loader "
        "(tos_runtime.safety.profile._load_documents) validates this half via a kernel record "
        "whose fields are ALL optional (module docstring), so it never raises on a filled-in "
        "value here; a real, concrete value appears to have leaked into a file that is supposed "
        "to ship as an all-null/empty template."
    )


def assert_safety_activation_refuses_on_both_readers() -> None:
    """Call BOTH real readers of ``safety_activation.example.yaml`` and assert each still
    refuses — the A-0b defect this whole module exists because of (module docstring): the file
    has two independent schemas, and a value leaking into either one's leaves must be caught.

    A standalone function (not a data-driven ``LoaderSpec``, unlike :func:`assert_shipped_example
    _still_refuses`) because the second reader (``_load_documents``) takes three paths, not one —
    but still a REAL, directly-callable check, not a bookkeeping label: registered in
    ``example_integrity_registry.MULTI_READER_CHECKS`` by name, and that registry IS what a
    parametrized test in ``test_shipped_example_integrity.py`` calls (PR #737 review round 2,
    first HIGH finding: a hand-typed ``frozenset`` of stem names claiming coverage, with nothing
    tying it to an actual test, let a real coverage gap through — ``backtest_calibration``
    reproduced it: removed from ``EXAMPLE_LOADERS`` and its name added to the OLD bookkeeping set
    instead, the whole suite stayed green). Making the "is this stem covered" set equal to
    ``MULTI_READER_CHECKS.keys()`` — the SAME dict this function is registered in and the
    parametrized test iterates — closes that gap structurally: there is no longer a way to claim
    coverage without also registering something a test actually calls.
    """
    from tos_runtime.safety.profile import SafetyProfileConfigError, _load_documents
    from tos_runtime.venue.activation import (
        ActivationMembersConfigError,
        load_activation_members,
    )

    example_path = CONFIG_DIR / "safety_activation.example.yaml"
    try:
        result = load_activation_members(example_path)
    except ActivationMembersConfigError:
        pass
    else:
        raise AssertionError(
            f"{example_path.name} loaded successfully via load_activation_members instead of "
            f"refusing (got {result!r}) — a real value appears to have leaked into the "
            "members: schema."
        )
    try:
        result = _load_documents(
            CONFIG_DIR / "safety_envelope.example.yaml",
            CONFIG_DIR / "safety_profile.example.yaml",
            example_path,
        )
    except SafetyProfileConfigError:
        pass
    else:
        raise AssertionError(
            f"{example_path.name} loaded successfully via _load_documents instead of refusing "
            f"(got {result!r}) — a real value appears to have leaked into the activation:/"
            "not_expired: schema."
        )


def assert_risk_refuses_on_both_readers() -> None:
    """Call ALL THREE real reader functions of ``risk.example.yaml`` and assert each still
    refuses — see :func:`assert_safety_activation_refuses_on_both_readers`'s own docstring for
    why this is a standalone registered check rather than a ``LoaderSpec`` entry, and for the
    PR #737 review round 2 finding this closes."""
    from tos_runtime.compose._currentness_wiring import _load_action_flow_envelope
    from tos_runtime.risk.aggregate import (
        AggregateRiskConfigError,
        load_adverse_scenario_set,
        load_required_scenario_kinds,
    )

    example_path = CONFIG_DIR / "risk.example.yaml"
    for loader in (
        load_adverse_scenario_set,
        load_required_scenario_kinds,
        _load_action_flow_envelope,
    ):
        try:
            result = loader(example_path)
        except AggregateRiskConfigError:
            continue
        raise AssertionError(
            f"{example_path.name} loaded successfully via {loader.__qualname__} instead of "
            f"refusing (got {result!r}) — a real value appears to have leaked in."
        )


def assert_touchpoints_match(stem: str, expected_files: frozenset[str]) -> None:
    """Assert the LIVE set of files referencing ``"{stem}.yaml"`` (see :func:`touchpoint_files`)
    equals ``expected_files`` exactly.

    This is the drift guard ``EXAMPLE_REQUIRED_PATHS`` alone cannot provide: a hand-maintained
    required-paths registry only stays correct as long as nobody adds a NEW file that reads this
    same config for a NEW purpose. When one does, this test goes red — pointing at exactly which
    file is new/gone — until a human decides whether it is a real independent schema reader (in
    which case ``EXAMPLE_REQUIRED_PATHS`` for this ``stem`` must grow to cover it too, mirroring
    how ``safety_activation``'s entry covers BOTH ``tos_runtime.safety.profile`` and
    ``tos_runtime.venue.activation``) or just another wiring call site that forwards to an
    already-covered canonical loader (in which case the recorded set is simply updated).
    """
    found = touchpoint_files(stem)
    assert found == expected_files, (
        f"{stem}.yaml touch points drifted from the recorded set in EXAMPLE_TOUCHPOINTS.\n"
        f"  now:      {sorted(found)}\n"
        f"  recorded: {sorted(expected_files)}\n"
        "A file was added to (or removed from) the set of tos_runtime source files that "
        "reference this config's deployed filename literal. Update EXAMPLE_TOUCHPOINTS in "
        "example_integrity_registry.py to match, and — if the new file is a genuinely "
        "independent schema reader rather than another wiring call site forwarding to an "
        "already-covered canonical loader — extend EXAMPLE_REQUIRED_PATHS for this config too. "
        "This is exactly the class docs/plans/2026-09-18-tos-config-adoption-and-carryover-"
        "plan.md §0.1.4 (A-0b) closed: one file, multiple schemas, only one covered."
    )
