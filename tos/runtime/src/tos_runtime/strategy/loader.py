"""Strategy-file loader — reads every ``*.yaml``/``*.yml`` under a
directory, parses each into an in-process typed
:class:`~tos.dsl.AuthoredStrategy`, and admits it through the kernel's own
typed admission gate (TOS Phase 3 슬라이스 D-R,
``docs/plans/2026-09-09-tos-phase3-event-core-plan.md`` §1.2).

**Injected, not imported, gates.** Both ``parse`` and ``admit`` are injected
callables rather than direct kernel imports:

* ``admit`` is :func:`tos.engine.admission.strategy_admissible` in
  production — injected here (rather than imported) purely so a test can
  substitute a double without monkeypatching the kernel module, matching
  this package's sibling loaders' own injection style
  (``tos_runtime.risk``/``tos_runtime.authority``).
* ``parse`` is :func:`tos.dsl.serialization.parse_strategy` in production
  (design #31 §9-4 / plan §1.2 slice D — kernel lane D-K, landed
  2026-09-09 at ``[D-K-done]``). This loader still makes no assumption
  about which callable it receives — the composition root
  (:mod:`tos_runtime.strategy.resolve`, plan §1.2 ``[D-R-2]``) is the one
  and only production injection site.

**Whole-directory fail-closed refusal (plan §1.2).** An unparseable or
inadmissible file refuses the ENTIRE load — this function never returns a
partial admitted set silently skipping the bad file. "No strategies" (an
empty directory, or a directory that does not exist) is refused too: an
engine with zero admitted strategies is not a defined no-action, it is a
runtime with no configured behavior at all, so it does not start (mirrors
:meth:`~tos.engine.registry.StrategyRegistry` positive-registration
discipline one level up, at the file layer). A **stray file** directly under
``strategies_dir`` that is neither ``*.yaml`` nor ``*.yml`` (2026-09-09
independent-review finding #12) also refuses the whole directory, naming the
stray file — renaming a bad file to make it disappear from the glob would
otherwise silently weaken this discipline instead of tripping it.

**Named-TBD ``null`` leaves (fail-closed).** Every value anywhere in a
strategy file's mapping — including nested rule/target fields — MUST be
concrete; a ``null`` anywhere (the repo's "named-TBD" convention, e.g.
``tos/runtime/config/risk.example.yaml``) refuses that file by name, before
``parse`` ever sees it. This lets an example file such as
``tos/runtime/config/strategies/example.strategy.yaml`` document the exact
shape with every value left as an explicit placeholder, the same way every
other example config in this tree does.

Firewall: this module is ``tos_runtime`` scope — ``tos.*`` (the kernel),
stdlib, and ``pyyaml``/``pydantic`` (already-pinned third parties) only; no
``shared.*`` (``tools/tos_firewall_check.py`` R1 allowlist).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from tos.dsl import ArtifactIntegrityError, AuthoredStrategy
from tos.engine.admission import AdmissionResult
from tos.engine.vocabulary import AdmissionVerdict

__all__ = [
    "AdmitFn",
    "LoadedStrategies",
    "LoadedStrategy",
    "ParseFn",
    "StrategyLoadError",
    "load_strategies",
]

#: The injected parser: raw top-level YAML mapping -> in-process typed
#: Authored Strategy. Production wires :func:`tos.dsl.serialization.parse_strategy`
#: here (this module's own docstring).
ParseFn = Callable[[Mapping[str, Any]], AuthoredStrategy]

#: The injected admission gate. Production wires
#: :func:`tos.engine.admission.strategy_admissible` here.
AdmitFn = Callable[[AuthoredStrategy], AdmissionResult]


class StrategyLoadError(ArtifactIntegrityError):
    """Raised when the strategy directory, or any one file inside it, fails
    to load — refuses the WHOLE load (this module's own docstring: never a
    partial admit). Callers (the composition root) are expected to record an
    ``STRATEGY_REFUSED`` evidence entry naming this error before halting
    (plan §1.2 ``[D-R-2]``)."""


@dataclass(frozen=True)
class LoadedStrategy:
    """One admitted strategy file: its source path, the parsed+admitted
    artifact, and the file's own content digest (feeds the composition
    root's ``OPERATOR_ATTESTED_INPUTS`` evidence record — plan §1.2)."""

    path: Path
    strategy: AuthoredStrategy
    sha256_digest: str


@dataclass(frozen=True)
class LoadedStrategies:
    """The full admitted set from one directory, in sorted-path order (a
    deterministic, filesystem-ordering-independent load — same rationale as
    every other config loader in this tree)."""

    strategies: tuple[LoadedStrategy, ...]


def first_null_leaf(value: Any, path: str) -> str | None:
    """Return the dotted/indexed path of the first ``null`` leaf found by a
    depth-first walk of ``value`` (dict values and list elements only —
    scalars ARE the leaves), or ``None`` if there is none.

    Package-internal (no leading underscore, deliberately — 2026-09-09
    independent-review finding #7): shared verbatim with
    :func:`tos_runtime.strategy.bindings.load_strategy_bindings`, which
    needs the identical null-leaf discipline for its own config file. Not
    part of this module's ``__all__`` — it is an intra-``tos_runtime.
    strategy`` helper, not this package's own public surface.

    Args:
        value: The (sub)value to inspect.
        path: The dotted/indexed path to ``value`` itself, for the message.

    Returns:
        The path of the first ``None`` found, else ``None``.
    """
    if value is None:
        return path or "<root>"
    if isinstance(value, dict):
        for key, sub in value.items():
            found = first_null_leaf(sub, f"{path}.{key}" if path else str(key))
            if found is not None:
                return found
        return None
    if isinstance(value, list):
        for index, sub in enumerate(value):
            found = first_null_leaf(sub, f"{path}[{index}]")
            if found is not None:
                return found
        return None
    return None


#: The only accepted strategy-file suffixes (2026-09-09 independent-review
#: finding #12: ``*.yaml`` alone silently skipped a ``.yml`` file instead of
#: refusing it).
_STRATEGY_FILE_SUFFIXES = (".yaml", ".yml")


def _iter_strategy_paths(strategies_dir: Path) -> Iterator[Path]:
    """Yield every ``*.yaml``/``*.yml`` file directly under
    ``strategies_dir``, in a deterministic (sorted-name) order."""
    yield from sorted(
        path
        for path in strategies_dir.iterdir()
        if path.is_file() and path.suffix in _STRATEGY_FILE_SUFFIXES
    )


def _refuse_stray_files(strategies_dir: Path) -> None:
    """Refuse the whole directory if it contains a regular file directly
    under it that is neither ``*.yaml`` nor ``*.yml`` — a stray file (e.g. a
    renamed-away bad strategy, an editor backup, a README) is never silently
    ignored (module docstring, finding #12)."""
    strays = sorted(
        path
        for path in strategies_dir.iterdir()
        if path.is_file() and path.suffix not in _STRATEGY_FILE_SUFFIXES
    )
    if strays:
        raise StrategyLoadError(
            f"{strategies_dir}: unexpected file {strays[0]!s} is neither "
            "*.yaml nor *.yml — refusing the whole directory rather than "
            "silently ignoring a stray file"
        )


def _load_one(path: Path, *, parse: ParseFn, admit: AdmitFn) -> LoadedStrategy:
    """Load, fail-closed-validate, parse, and admit ONE strategy file.

    Raises:
        StrategyLoadError: The file is unreadable, not valid UTF-8/YAML, not
            a top-level mapping, carries a ``null`` leaf anywhere, cannot be
            parsed into an Authored Strategy, or is INADMISSIBLE.
    """
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise StrategyLoadError(f"{path}: cannot read strategy file: {exc}") from exc
    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrategyLoadError(f"{path}: not valid UTF-8: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StrategyLoadError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise StrategyLoadError(
            f"{path}: strategy file must be a top-level mapping — refusing to load"
        )

    null_leaf = first_null_leaf(raw, "")
    if null_leaf is not None:
        raise StrategyLoadError(
            f"{path}: field {null_leaf!r} is still null (named-TBD) — refusing to "
            "load until an operator attests a concrete value"
        )

    try:
        strategy = parse(raw)
    except (ArtifactIntegrityError, ValidationError) as exc:
        raise StrategyLoadError(
            f"{path}: could not be parsed into an Authored Strategy: {exc}"
        ) from exc

    admission = admit(strategy)
    if admission.verdict is not AdmissionVerdict.ADMISSIBLE:
        raise StrategyLoadError(
            f"{path}: strategy is INADMISSIBLE — refusing to load: "
            + "; ".join(admission.reasons)
        )

    return LoadedStrategy(path=path, strategy=strategy, sha256_digest=digest)


def load_strategies(
    strategies_dir: Path, *, parse: ParseFn, admit: AdmitFn
) -> LoadedStrategies:
    """Load every admissible strategy file under ``strategies_dir``.

    Args:
        strategies_dir: Directory containing ``*.yaml`` strategy files
            (e.g. ``config_dir / "strategies"``).
        parse: Raw-mapping -> :class:`~tos.dsl.AuthoredStrategy` (see this
            module's docstring — injected, not imported).
        admit: :class:`~tos.dsl.AuthoredStrategy` -> :class:`~tos.engine.
            admission.AdmissionResult` (injected, not imported).

    Returns:
        The admitted set, in sorted-path order.

    Raises:
        StrategyLoadError: ``strategies_dir`` does not exist or is not a
            directory, contains a stray non-``*.yaml``/``*.yml`` file,
            contains zero strategy files, or any one file fails to load
            (fail-closed — the WHOLE load is refused, never a partial admit;
            see this module's own docstring).
    """
    if not strategies_dir.is_dir():
        raise StrategyLoadError(
            f"{strategies_dir}: strategies directory does not exist — refusing "
            "to start with no configured strategies"
        )
    _refuse_stray_files(strategies_dir)
    paths = list(_iter_strategy_paths(strategies_dir))
    if not paths:
        raise StrategyLoadError(
            f"{strategies_dir}: no strategy files found — an engine with zero "
            "admitted strategies is not a defined no-action, it does not start"
        )
    loaded = tuple(_load_one(path, parse=parse, admit=admit) for path in paths)
    return LoadedStrategies(strategies=loaded)
