#!/usr/bin/env python3
"""Render the COMMITTED CP-3 stock tenant trees from one declared tenant list.

Upper plan: ``docs/plans/2026-11-27-tos-p4-position-fields-plan.md`` §4 row S6 — "주식 트리를
종목 목록에서 렌더 (`scripts/tos/render_paper_config.py` 재사용) — 종목 추가 = 목록 한 줄".
The list is ``config/tos_stock_tenants/TENANTS.yaml``.

Why this is a second entry point rather than a flag on ``render_paper_config.py``
--------------------------------------------------------------------------------
The two renderers have OPPOSITE output rules, and the difference is a safety rule in each:

* ``render_paper_config.py`` is the DEPLOYMENT renderer. It fills this host's coordinates
  (the mock account number, the front month) into a copy of a committed tree and REFUSES to
  write inside the repository — ``_refuse_output_inside_repo``, "one missing .gitignore line
  would be a committed account number".
* this script is the AUTHORING generator. Its output IS the committed tree, so it writes
  into the repository, and it reads no account, no ``.env*`` file and no host fact at all.

One command cannot hold both rules. What they DO share is the substitution engine: every
patch below is a :class:`render_paper_config.Rule` executed by
:func:`render_paper_config.apply_rules`, so the "anchor matches EXACTLY ONCE" invariant has
one implementation. The coordinate renderer's ``_validate_replacement_template`` (rules ①-④)
is deliberately NOT reused: it exists to stop a coordinate slot from smuggling a literal
value, and a tenant-tree patch is nothing BUT literal content (a rule, a comment, a policy
id), so those rules would reject every patch here.

The model: one base tree, declared layers, one symbol literal
-------------------------------------------------------------
``cp3-setup-d-stock-005930`` (the canary) IS the base — not a fourth copy of it. Every
shipped stock tree is that tree with

1. the base symbol/name/strategy-path literals replaced by the tenant's, in exactly the
   files and counts the list declares (an occurrence anywhere else refuses — that is what
   keeps a short count table honest), and
2. the tenant's ROLE layers applied in order, then the layers its own list line declares:
   every file in a layer directory replaces the base's copy whole, and
   ``LAYER.yaml::patches`` replaces single anchored lines. A role layer must be true of
   EVERY symbol that takes the role, so a fact about one tenant (its decision-generation
   history) goes in a per-tenant layer rather than being hand-edited into the output.

Layer content is written with ``{{SYMBOL}}`` / ``{{SYMBOL_NAME}}`` tokens; a BARE ``005930``
inside a layer is kept as-is, because there it means the canary tenant the prose points at,
not this tenant. Rendering is pure text — no YAML round-trip — so every header comment and
provenance citation survives byte-for-byte.

Nothing here reads or writes anything outside the repository, and no runtime loads this file
or the list: ``--check`` is the gate (``tests/tools/test_tos_stock_tenant_render.py``), and
``--write`` is what an operator runs after adding a line to the list.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:  # direct-script invocation and test imports alike
    sys.path.insert(0, str(_SCRIPT_DIR))

from render_paper_config import RenderError, Rule, apply_rules  # noqa: E402

__all__ = [
    "DEFAULT_LIST",
    "LAYER_MANIFEST_NAME",
    "Layer",
    "Patch",
    "RenderError",
    "Role",
    "StockTenants",
    "Tenant",
    "check",
    "load_tenants",
    "main",
    "render_all",
    "render_tenant",
    "tree_name",
    "write",
]

#: The declared list this script renders from, relative to the repository root.
DEFAULT_LIST = Path("config/tos_stock_tenants/TENANTS.yaml")

#: The one schema token the list may carry.
SCHEMA = "tos-stock-tenants/1"

#: The optional per-layer manifest. A layer needs one only for ``patches``; its ordinary
#: files are discovered, so a file list cannot drift from the directory.
LAYER_MANIFEST_NAME = "LAYER.yaml"

#: The closed set of tokens layer content may carry, and where each value comes from.
_TOKENS: tuple[str, ...] = ("SYMBOL", "SYMBOL_NAME")

_TOKEN_RE = re.compile(r"\{\{([A-Za-z_]+)\}\}")

#: A KRX stock code as every stock tree already writes it (``RENDER.yaml::instrument.pattern``).
_SYMBOL_RE = re.compile(r"[0-9]{6}")

#: Characters a tenant NAME may not carry.
_NAME_REFUSED_RE = re.compile(r'["\\\x00-\x1f\x7f]')

#: The literal kinds the base tree is retargeted on, in application order.
_OCCURRENCE_KINDS: tuple[str, ...] = ("symbol", "symbol_name", "strategy_file")


@dataclass(frozen=True)
class Tenant:
    """One declared stock tenant — one line of ``TENANTS.yaml::tenants``."""

    symbol: str
    name: str
    role: str
    #: Layers applied AFTER the role's, declared on the tenant's own line. The one place a
    #: fact about THIS tenant may live without the role layer claiming it of every symbol
    #: that shares the role (its decision-generation history, for instance).
    layers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Patch:
    """One anchored line replacement a layer applies to a base file."""

    file: str
    key: str
    anchor: str
    replacement: str


@dataclass(frozen=True)
class Layer:
    """One overlay directory: whole files plus anchored patches."""

    name: str
    directory: Path
    files: tuple[str, ...]
    patches: tuple[Patch, ...]


@dataclass(frozen=True)
class Role:
    """A tenant role — the ordered layers it applies and the strategy file it ships."""

    name: str
    layers: tuple[str, ...]
    strategy_file: str


@dataclass(frozen=True)
class StockTenants:
    """``TENANTS.yaml``, validated against the base tree and the layer directories."""

    list_path: Path
    base_tree: Path
    base_symbol: str
    base_symbol_name: str
    base_strategy_file: str
    occurrences: dict[str, dict[str, int]]
    layers: dict[str, Layer]
    roles: dict[str, Role]
    tenants: tuple[Tenant, ...]

    def literals(self, tenant: Tenant) -> tuple[tuple[str, str, str], ...]:
        """``(kind, base literal, tenant literal)`` in application order."""
        role = self.roles[tenant.role]
        return (
            ("symbol", self.base_symbol, tenant.symbol),
            ("symbol_name", self.base_symbol_name, tenant.name),
            ("strategy_file", self.base_strategy_file, role.strategy_file),
        )


# ---------------------------------------------------------------------------
# Reading the declaration
# ---------------------------------------------------------------------------


def _require(raw: Any, *, where: str, kind: type = str) -> Any:
    if not isinstance(raw, kind) or (kind is str and not raw):
        raise RenderError(f"{where}: expected a non-empty {kind.__name__}, got {raw!r}")
    return raw


def _within(path: Path, root: Path, *, where: str) -> Path:
    """``path`` resolved, refused unless it stays inside ``root``.

    # SAFETY: every path in the list and in a layer manifest is DATA. Without this, a
    # `base.tree`, `layers_root`, layer name or `patch.file` holding `../` reads files from
    # outside the checkout into a committed tree, and `--write` then writes outside it.
    """
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise RenderError(
            f"{where}: {path} resolves outside {root} ({resolved}) — every path in the "
            "list and in a layer manifest stays inside the checkout it is relative to"
        )
    return resolved


def _refuse_symlinks(root: Path, *, where: str) -> None:
    """Refuse any symlink under ``root``.

    # SAFETY: `_relative_files` admits a symlink as an ordinary file, so a link inside the
    # base tree or a layer would be READ THROUGH — content from outside the checkout copied
    # into a committed tree, with every containment check above seeing only the link's path.
    """
    links = sorted(
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_symlink()
    )
    if links:
        raise RenderError(f"{where}: symlink(s) refused: {links}")


def _relative_files(root: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
        )
    )


def _load_yaml(path: Path, *, where: str) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RenderError(f"{where}: cannot read {path} ({exc})") from exc
    if not isinstance(raw, dict):
        raise RenderError(f"{where}: {path} must hold a mapping, got {type(raw)}")
    return raw


def _load_layer(name: str, layers_root: Path, *, base_tree: Path) -> Layer:
    directory = _within(layers_root / name, layers_root, where=f"layer {name!r}")
    if not directory.is_dir():
        raise RenderError(f"layer {name!r}: directory not found: {directory}")
    _refuse_symlinks(directory, where=f"layer {name!r}")
    files = tuple(
        rel for rel in _relative_files(directory) if rel != LAYER_MANIFEST_NAME
    )
    manifest = directory / LAYER_MANIFEST_NAME
    patches: list[Patch] = []
    if manifest.is_file():
        raw = _load_yaml(manifest, where=f"layer {name!r}")
        entries = raw.get("patches", [])
        if not isinstance(entries, list):
            raise RenderError(f"layer {name!r}: patches must be a list")
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            where = f"layer {name!r}: patches[{index}]"
            if not isinstance(entry, dict):
                raise RenderError(f"{where}: expected a mapping, got {entry!r}")
            patch = Patch(
                file=_require(entry.get("file"), where=f"{where}.file"),
                key=_require(entry.get("key"), where=f"{where}.key"),
                anchor=_require(entry.get("anchor"), where=f"{where}.anchor"),
                replacement=_lines(
                    entry.get("replacement"), where=f"{where}.replacement"
                ),
            )
            if patch.key in seen:
                raise RenderError(f"{where}: duplicate patch key {patch.key!r}")
            # The rendered tree has the base tree's layout, so containment holds there too.
            _within(base_tree / patch.file, base_tree, where=f"{where}.file")
            seen.add(patch.key)
            patches.append(patch)
    if not files and not patches:
        raise RenderError(
            f"layer {name!r}: holds neither a file nor a patch — an empty layer silently "
            "makes every role that applies it identical to the base tree"
        )
    return Layer(name=name, directory=directory, files=files, patches=tuple(patches))


def _lines(raw: Any, *, where: str) -> str:
    """A replacement: one string, or a list of lines joined with newlines.

    The list form exists so a multi-line replacement whose lines carry leading spaces (a YAML
    list item, an indented key) needs no block-scalar indentation indicator to stay exact.
    """
    if isinstance(raw, str) and raw:
        return raw
    if isinstance(raw, list) and raw:
        for index, line in enumerate(raw):
            if not isinstance(line, str):
                raise RenderError(f"{where}[{index}]: expected a string, got {line!r}")
        return "\n".join(raw)
    raise RenderError(f"{where}: expected a non-empty string or list of strings")


def load_tenants(path: Path, *, repo_root: Path = _REPO_ROOT) -> StockTenants:
    """Read and validate the tenant list; every path in it is ``repo_root``-relative.

    Raises:
        RenderError: any refusal — an unknown schema, a malformed entry, a role or layer that
            does not exist, a declared occurrence table that does not match the base tree, or
            a role whose strategy file no layer provides.
    """
    raw = _load_yaml(path, where="tenant list")
    if raw.get("schema") != SCHEMA:
        raise RenderError(
            f"{path}: schema refused: {raw.get('schema')!r} — expected {SCHEMA!r}"
        )

    base_raw = raw.get("base")
    if not isinstance(base_raw, dict):
        raise RenderError(f"{path}: base must be a mapping")
    base_tree = _within(
        repo_root / _require(base_raw.get("tree"), where=f"{path}: base.tree"),
        repo_root,
        where=f"{path}: base.tree",
    )
    if not base_tree.is_dir():
        raise RenderError(f"{path}: base.tree not found: {base_tree}")
    _refuse_symlinks(base_tree, where=f"{path}: base.tree")
    base_symbol = _require(base_raw.get("symbol"), where=f"{path}: base.symbol")
    if not _SYMBOL_RE.fullmatch(base_symbol):
        raise RenderError(f"{path}: base.symbol refused: {base_symbol!r}")
    base_symbol_name = _require(
        base_raw.get("symbol_name"), where=f"{path}: base.symbol_name"
    )
    base_strategy_file = _require(
        base_raw.get("strategy_file"), where=f"{path}: base.strategy_file"
    )
    if not (base_tree / base_strategy_file).is_file():
        raise RenderError(
            f"{path}: base.strategy_file not in the base tree: {base_strategy_file}"
        )
    if base_tree.name.count(base_symbol) != 1:
        raise RenderError(
            f"{path}: base.tree directory name {base_tree.name!r} must carry the base symbol "
            f"{base_symbol!r} exactly once — the rendered tree's name comes from it"
        )

    occurrences = _occurrence_table(
        base_raw.get("occurrences"),
        base_tree=base_tree,
        where=f"{path}: base.occurrences",
    )

    layers_root = _within(
        repo_root / _require(raw.get("layers_root"), where=f"{path}: layers_root"),
        repo_root,
        where=f"{path}: layers_root",
    )
    roles_raw = raw.get("roles")
    if not isinstance(roles_raw, dict) or not roles_raw:
        raise RenderError(f"{path}: roles must be a non-empty mapping")
    layers: dict[str, Layer] = {}
    roles: dict[str, Role] = {}
    for name, entry in roles_raw.items():
        where = f"{path}: roles.{name}"
        if not isinstance(entry, dict):
            raise RenderError(f"{where}: expected a mapping, got {entry!r}")
        declared = entry.get("layers", [])
        if not isinstance(declared, list) or any(
            not isinstance(item, str) for item in declared
        ):
            raise RenderError(f"{where}.layers: expected a list of layer names")
        for layer_name in declared:
            if layer_name not in layers:
                layers[layer_name] = _load_layer(
                    layer_name, layers_root, base_tree=base_tree
                )
        strategy_file = entry.get("strategy_file", base_strategy_file)
        _require(strategy_file, where=f"{where}.strategy_file")
        _within(
            base_tree / str(strategy_file), base_tree, where=f"{where}.strategy_file"
        )
        if strategy_file != base_strategy_file and not any(
            strategy_file in layers[layer_name].files for layer_name in declared
        ):
            raise RenderError(
                f"{where}.strategy_file: {strategy_file!r} is not the base tree's and no "
                f"layer of this role provides it — the rendered tree would have no strategy"
            )
        roles[str(name)] = Role(
            name=str(name), layers=tuple(declared), strategy_file=str(strategy_file)
        )

    tenants_raw = raw.get("tenants")
    if not isinstance(tenants_raw, list) or not tenants_raw:
        raise RenderError(f"{path}: tenants must be a non-empty list")
    tenants: list[Tenant] = []
    seen: set[str] = set()
    for index, entry in enumerate(tenants_raw):
        where = f"{path}: tenants[{index}]"
        if not isinstance(entry, dict):
            raise RenderError(f"{where}: expected a mapping, got {entry!r}")
        stray = sorted(set(entry) - {"symbol", "name", "role", "layers"})
        if stray:
            raise RenderError(
                f"{where}: unknown key(s) {stray!r} — a misspelled one would be silently "
                "ignored (the line's keys are symbol, name, role, layers)"
            )
        declared_layers = entry.get("layers", [])
        if not isinstance(declared_layers, list) or any(
            not isinstance(item, str) for item in declared_layers
        ):
            raise RenderError(f"{where}.layers: expected a list of layer names")
        tenant = Tenant(
            symbol=_require(entry.get("symbol"), where=f"{where}.symbol"),
            name=_require(entry.get("name"), where=f"{where}.name"),
            role=_require(entry.get("role"), where=f"{where}.role"),
            layers=tuple(declared_layers),
        )
        refused = _NAME_REFUSED_RE.search(tenant.name)
        if refused is not None:
            # SAFETY: the name is substituted into DOUBLE-QUOTED YAML strings (the `derived`
            # layer's approval line), where a quote or a backslash ends or re-escapes the
            # string and a newline or a control character breaks the document — the render
            # would commit a policy file that no longer parses, or parses to something else.
            raise RenderError(
                f"{where}.name refused: {tenant.name!r} carries {refused.group()!r} — a "
                "name is substituted into double-quoted YAML strings, so a quote, a "
                "backslash, a newline or a control character is not allowed in it"
            )
        for layer_name in tenant.layers:
            if layer_name not in layers:
                layers[layer_name] = _load_layer(
                    layer_name, layers_root, base_tree=base_tree
                )
        if not _SYMBOL_RE.fullmatch(tenant.symbol):
            raise RenderError(
                f"{where}.symbol refused: {tenant.symbol!r} — a KRX stock code is six digits"
            )
        if tenant.symbol in seen:
            raise RenderError(
                f"{where}.symbol: {tenant.symbol!r} is declared twice — one tenant per "
                "symbol is what keeps each tenant's broker reads about its own orders"
            )
        seen.add(tenant.symbol)
        if tenant.role not in roles:
            raise RenderError(
                f"{where}.role refused: {tenant.role!r} — declared roles are "
                f"{sorted(roles)!r}"
            )
        tenants.append(tenant)
    if base_symbol not in seen:
        raise RenderError(
            f"{path}: the base symbol {base_symbol!r} is not in the list — the base tree "
            "must be rendered like every other tree, or nothing checks it"
        )
    return StockTenants(
        list_path=path,
        base_tree=base_tree,
        base_symbol=base_symbol,
        base_symbol_name=base_symbol_name,
        base_strategy_file=base_strategy_file,
        occurrences=occurrences,
        layers=layers,
        roles=roles,
        tenants=tuple(tenants),
    )


def _occurrence_table(
    raw: Any, *, base_tree: Path, where: str
) -> dict[str, dict[str, int]]:
    if not isinstance(raw, dict):
        raise RenderError(f"{where}: must be a mapping")
    unknown = sorted(set(raw) - set(_OCCURRENCE_KINDS))
    if unknown:
        raise RenderError(
            f"{where}: unknown literal kinds {unknown!r} — the set is "
            f"{list(_OCCURRENCE_KINDS)!r}"
        )
    table: dict[str, dict[str, int]] = {kind: {} for kind in _OCCURRENCE_KINDS}
    for kind in _OCCURRENCE_KINDS:
        entry = raw.get(kind, {})
        if not isinstance(entry, dict):
            raise RenderError(f"{where}.{kind}: must be a mapping of file -> count")
        for name, count in entry.items():
            spot = f"{where}.{kind}.{name}"
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                raise RenderError(f"{spot}: must be a positive integer, got {count!r}")
            if not (base_tree / str(name)).is_file():
                raise RenderError(f"{spot}: not a file of the base tree")
            table[kind][str(name)] = count
    return table


def verify_base_occurrences(spec: StockTenants) -> None:
    """Refuse unless every base file carries exactly the declared number of each literal.

    # SAFETY: this scan is what makes the short occurrence table safe — without it a literal
    # that appeared in an UNDECLARED base file (a new comment naming the canary's symbol, a
    # second strategy path) would be copied into every sibling unchanged, and the sibling
    # would quietly carry the canary's symbol in a policy id or a freshness declaration.
    """
    literals = {
        "symbol": spec.base_symbol,
        "symbol_name": spec.base_symbol_name,
        "strategy_file": spec.base_strategy_file,
    }
    problems: list[str] = []
    for rel in _relative_files(spec.base_tree):
        text = (spec.base_tree / rel).read_text(encoding="utf-8")
        for kind, literal in literals.items():
            found = text.count(literal)
            declared = spec.occurrences[kind].get(rel, 0)
            if found != declared:
                problems.append(
                    f"{rel}: carries the base {kind} {literal!r} {found} time(s), the list "
                    f"declares {declared} — re-measure and update "
                    f"{spec.list_path}::base.occurrences.{kind}"
                )
    if problems:
        raise RenderError(
            "the base tree and the declared occurrence table disagree:\n  "
            + "\n  ".join(problems)
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _expand(text: str, tenant: Tenant, *, where: str) -> str:
    values = {"SYMBOL": tenant.symbol, "SYMBOL_NAME": tenant.name}
    unknown = sorted(set(_TOKEN_RE.findall(text)) - set(_TOKENS))
    if unknown:
        raise RenderError(
            f"{where}: unknown token(s) {unknown!r} — the set is {list(_TOKENS)!r}"
        )
    for token, value in values.items():
        text = text.replace("{{" + token + "}}", value)
    return text


def tree_name(spec: StockTenants, symbol: str) -> str:
    """The directory name a tenant's rendered tree takes."""
    return spec.base_tree.name.replace(spec.base_symbol, symbol)


def render_tenant(spec: StockTenants, tenant: Tenant, out_root: Path) -> Path:
    """Render one tenant's whole tree into ``out_root/<tree name>`` and return that path."""
    role = spec.roles[tenant.role]
    out = out_root / tree_name(spec, tenant.symbol)
    # SAFETY: the base tree is READ file by file below, so rendering on top of it would
    # delete the canary tenant's committed tree and then copy from the hole it left —
    # every render goes to a staging directory and :func:`write` swaps it in.
    if out.resolve() == spec.base_tree.resolve():
        raise RenderError(
            f"refusing to render {tenant.symbol} over the base tree itself ({out}) — render "
            "into a staging directory and swap (see write())"
        )
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for rel in _relative_files(spec.base_tree):
        text = (spec.base_tree / rel).read_text(encoding="utf-8")
        for _kind, base_literal, tenant_literal in spec.literals(tenant):
            text = text.replace(base_literal, tenant_literal)
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    if role.strategy_file != spec.base_strategy_file:
        (out / spec.base_strategy_file).unlink()

    for layer_name in (*role.layers, *tenant.layers):
        layer = spec.layers[layer_name]
        for rel in layer.files:
            text = _expand(
                (layer.directory / rel).read_text(encoding="utf-8"),
                tenant,
                where=f"layer {layer_name!r} file {rel}",
            )
            target = out / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        apply_rules(
            out,
            [
                Rule(
                    patch.file,
                    f"{layer_name}::{patch.key}",
                    _expand(
                        patch.anchor,
                        tenant,
                        where=f"layer {layer_name!r} patch {patch.key} anchor",
                    ),
                    _expand(
                        patch.replacement,
                        tenant,
                        where=f"layer {layer_name!r} patch {patch.key} replacement",
                    ),
                )
                for patch in layer.patches
            ],
        )

    _verify_output(spec, tenant, out)
    return out


def _verify_output(spec: StockTenants, tenant: Tenant, out: Path) -> None:
    role = spec.roles[tenant.role]
    problems: list[str] = []
    if not (out / role.strategy_file).is_file():
        problems.append(f"the role's strategy file is missing: {role.strategy_file}")
    for rel in _relative_files(out):
        text = (out / rel).read_text(encoding="utf-8")
        left = sorted(set(_TOKEN_RE.findall(text)))
        if left:
            problems.append(f"{rel}: unexpanded token(s) {left!r}")
    if problems:
        raise RenderError(
            f"tenant {tenant.symbol} rendered wrong:\n  " + "\n  ".join(problems)
        )


def render_all(spec: StockTenants, out_root: Path) -> dict[str, Path]:
    """Render every declared tenant into ``out_root``; keys are tree directory names."""
    # SAFETY: the base tree is READ file by file, so an output root ANYWHERE inside it (not
    # only equal to it — `--out config/tos_runtime/cp3-setup-d-stock-005930/sub` too) would
    # have `render_tenant` rmtree a directory the later reads need.
    if out_root.resolve().is_relative_to(spec.base_tree.resolve()):
        raise RenderError(
            f"refusing to render into {out_root} — it is inside the base tree "
            f"({spec.base_tree}), whose files every render reads"
        )
    verify_base_occurrences(spec)
    return {
        tree_name(spec, tenant.symbol): render_tenant(spec, tenant, out_root)
        for tenant in spec.tenants
    }


def write(spec: StockTenants, *, committed_root: Path) -> dict[str, Path]:
    """Render every tenant into a staging directory, then replace the committed trees.

    Staged first because the canary's committed tree IS the base this render reads
    (:func:`render_tenant`'s refusal), and because a render that refuses halfway must leave
    the committed trees exactly as they were.
    """
    written: dict[str, Path] = {}
    with tempfile.TemporaryDirectory(prefix="tos-stock-tenants-") as temp:
        rendered = render_all(spec, Path(temp))
        for name, source in rendered.items():
            target = committed_root / name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
            written[name] = target
    return written


# ---------------------------------------------------------------------------
# Checking the committed trees against the render
# ---------------------------------------------------------------------------


def check(spec: StockTenants, *, committed_root: Path) -> list[str]:
    """Return the problems between the render and the committed trees — empty means equal.

    Both directions are reported: a hand edit of a generated tree, a list or layer edit
    nobody re-rendered, a file that only one side has, and a committed
    ``cp3-setup-d-stock-*`` directory the list does not declare.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory(prefix="tos-stock-tenants-") as temp:
        try:
            rendered = render_all(spec, Path(temp))
        except RenderError as exc:
            return [str(exc)]
        pattern = spec.base_tree.name.replace(spec.base_symbol, "*")
        committed = {
            path.name for path in sorted(committed_root.glob(pattern)) if path.is_dir()
        }
        for extra in sorted(committed - set(rendered)):
            problems.append(
                f"{extra}: a committed tree the list does not declare — add its line to "
                f"{spec.list_path} (or delete the tree)"
            )
        for name, source in rendered.items():
            target = committed_root / name
            if not target.is_dir():
                problems.append(f"{name}: declared but not committed — run --write")
                continue
            problems.extend(_diff_trees(name, source, target))
    return problems


def _diff_trees(name: str, rendered: Path, committed: Path) -> Iterable[str]:
    want = set(_relative_files(rendered))
    have = set(_relative_files(committed))
    for rel in sorted(want - have):
        yield f"{name}/{rel}: rendered but not committed"
    for rel in sorted(have - want):
        yield f"{name}/{rel}: committed but not rendered"
    for rel in sorted(want & have):
        left = (rendered / rel).read_bytes()
        right = (committed / rel).read_bytes()
        if left == right:
            continue
        hunk = "".join(
            list(
                difflib.unified_diff(
                    left.decode("utf-8").splitlines(keepends=True),
                    right.decode("utf-8").splitlines(keepends=True),
                    fromfile=f"rendered/{rel}",
                    tofile=f"committed/{rel}",
                    n=0,
                )
            )[:12]
        )
        yield f"{name}/{rel}: committed bytes differ from the render\n{hunk}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        type=Path,
        default=_REPO_ROOT / DEFAULT_LIST,
        help=f"the tenant list (default: {DEFAULT_LIST})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="the checkout every path in the list is relative to",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the rendered trees over the committed ones (default: --check only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="render into this directory instead of the committed config tree",
    )
    args = parser.parse_args(argv)

    try:
        spec = load_tenants(args.list, repo_root=args.repo_root)
        if args.out is not None:
            rendered = render_all(spec, args.out)
            for name in sorted(rendered):
                print(f"rendered {args.out / name}")
            return 0
        committed_root = spec.base_tree.parent
        if args.write:
            for name in sorted(write(spec, committed_root=committed_root)):
                print(f"wrote {committed_root / name}")
            return 0
        problems = check(spec, committed_root=committed_root)
    except RenderError as exc:
        print(f"render-stock-tenant-trees: refused — {exc}", file=sys.stderr)
        return 1
    if problems:
        print("render-stock-tenant-trees: the committed trees are NOT the render:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        f"render-stock-tenant-trees: {len(spec.tenants)} committed stock tenant tree(s) are "
        "byte-identical to the render"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
