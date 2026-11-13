"""Shared machinery for asserting a shipped ``tos/runtime/config/*.example.yaml`` document is
STRUCTURALLY complete — as opposed to merely "refuses to load", which a document missing an
entire required key ALSO does, identically, to a document that carries the key as an explicit
``null`` (every ``tos_runtime.*``/``tos_runtime.compose._*`` loader treats "key absent" and "key
present but null" as the SAME named-TBD refusal — ``raw.get(key) is None`` does not distinguish
them). A naive ``pytest.raises(SomeConfigError)`` around a shipped example therefore CANNOT catch
a whole required key being missing from the document: the loader refuses either way, for what
looks like the right reason, and the test stays green.

Closes the class ``docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md`` names A-0b:
a shipped example satisfied ONE of its two real readers while silently missing the key a
SECOND, independent reader added later — the same shape of bug W2 hit once already for
``marketfeed.example.yaml``'s missing ``intake_kind`` (commit ``47cf1671``), which is why this
module makes the check itself, not just one more instance fix.

Three independent assertions close this, together:

* :func:`assert_required_paths_present` — the document declared in ``config/EXAMPLE_NAME
  .example.yaml`` must carry every key path any of its real readers require, as an EXPLICIT key
  (value may be ``null`` — that is the correct named-TBD template state) at every level.
* :func:`assert_shipped_example_still_refuses` — the loader must still refuse to load the shipped
  document (a value-leak detector — see its own docstring), for readers whose loader has at least
  one per-field null/TBD check of its own to fail on.
* :func:`assert_shipped_example_is_a_template` — every leaf of the document is ``null``/``[]``
  (a DIFFERENT value-leak detector, for a reader whose kernel record has every field optional,
  so nothing in that loader ever raises on a filled-in leaf; see that function's own docstring
  for why "does it still refuse" cannot substitute here). No shipped example needs it since
  plan S2-a removed the two all-optional spg documents that did.
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
  parametrized test actually iterates and calls — :func:`assert_risk_refuses_on_both_readers`
  is the standalone check ``MULTI_READER_CHECKS`` registers; ``LOADS_SUCCESSFULLY_LOADERS``
  reuses the existing
  ``LoaderSpec`` shape. The ledger sets are now DERIVED (``frozenset(THE_DICT)``), so naming a
  stem "covered" and making it actually get called are the same act.
* :func:`is_template_document`'s leaf-flattener silently dropped an EMPTY MAPPING (``{}``) —
  reproduced by collapsing a nested required block to ``{}``: neither this function nor
  ``assert_required_paths_present`` (registered only one level deep) caught it.
  Fixed generically in :func:`_leaf_values` (an empty mapping is now itself a leaf, exactly like
  an empty list already was) rather than by registering those 7 subfields as explicit required
  paths — the latter would have closed only this one instance, not the class (a different block
  collapsing the same way elsewhere would still slip through a paths-list fix).
"""

from __future__ import annotations

import io
import tokenize
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
RUNTIME_SRC = Path(__file__).resolve().parents[2] / "src"

#: A STRING token right after one of these starts a statement, so it is a docstring or bare prose.
_STATEMENT_START = frozenset(
    {tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENCODING}
)

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


def code_text(path: str | Path) -> str:
    """``path``'s source with comments and docstrings dropped, as joined token text.

    A mention that lives only in prose is not a touch point. The S4 prose strip
    (``docs/plans/2026-11-13-tos-code-halving-plan.md`` §S4) deletes comments and all but the
    first line of every docstring, so a drift signal keyed on prose fires on a documentation
    edit while saying nothing about who reads the config. Narrowing to code only ever REMOVES
    hits — a token's text still carries its own quotes, so the literal search is otherwise
    unchanged (measured 2026-11-13: of the 25 recorded stems, exactly one set changes).
    """
    source = Path(path).read_text(encoding="utf-8")
    kept: list[str] = []
    previous = tokenize.ENCODING
    for token in tokenize.generate_tokens(io.StringIO(source, newline="").readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and previous in _STATEMENT_START:
            # a standalone string statement — a docstring, or bare prose
            previous = tokenize.STRING
            continue
        if token.type != tokenize.NL:
            previous = token.type
        kept.append(token.string)
    return "\n".join(kept)


def touchpoint_files(stem: str) -> frozenset[str]:
    """Live-grep the CODE of every ``*.py`` file under ``tos/runtime/src`` for the literal
    deployed filename (``"{stem}.yaml"``) and return the set of files (paths relative to
    ``tos/runtime/src``) where it appears. A NEW mention is exactly the signal this check exists
    to surface, whether it turns out to be a real new reader or not; a mention in a comment or a
    docstring is not one (see :func:`code_text`).
    """
    literal = f'"{stem}.yaml"'
    found: set[str] = set()
    for path in RUNTIME_SRC.rglob("*.py"):
        if literal in code_text(path):
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
    leaf-flattener itself.

    KNOWN LIMITATION (PR #737 review round 3, LOW — registered, deliberately NOT fixed). The
    empty-list branch is unconditional at EVERY depth, so a NESTED empty list (``[[]]``) still
    flattens to the leaf ``[]`` and passes :func:`is_template_document`. Only the empty-MAPPING
    asymmetry was closed. This is currently unexploitable rather than merely unlikely: the two
    configs in ``EXAMPLE_TEMPLATE_ONLY`` (the only callers of this predicate) have no
    list-of-lists anywhere in their schemas — every field on ``HardSafetyEnvelope``/
    ``RuntimeSafetyProfile`` is a flat optional scalar or a flat tuple. That precondition, not
    the predicate, is what makes it safe; if a config with a nested-list schema is ever added to
    ``EXAMPLE_TEMPLATE_ONLY``, this branch has to be revisited first."""
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
        "validates it via a record whose fields are ALL optional (module docstring), so it "
        "never raises on a filled-in value here; a real, concrete value appears to have "
        "leaked into a file that is supposed to ship as an all-null/empty template."
    )


def assert_risk_refuses_on_both_readers() -> None:
    """Call ALL THREE real reader functions of ``risk.example.yaml`` and assert each still
    refuses.

    A standalone registered check rather than a ``LoaderSpec`` entry because the three readers
    do not share one signature. It is registered in
    ``example_integrity_registry.MULTI_READER_CHECKS`` by name, and that registry IS what a
    parametrized test in ``test_shipped_example_integrity.py`` calls, so there is no way to
    claim coverage without registering something a test actually calls."""
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
    which case ``EXAMPLE_REQUIRED_PATHS`` for this ``stem`` must grow to cover it too, the way
    ``risk``'s entry covers all three of its readers) or just another wiring call site that
    forwards to an
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
