"""Per-strategy config bindings loader — the finding-#9 disposition (TOS
Phase 3 슬라이스 D-R ``[D-R-3]``, ``docs/plans/2026-09-09-tos-phase3-event-
core-plan.md`` §1.2 / §7.1 편차 ④ / §7.2 #9).

:mod:`tos_runtime.strategy.resolve` (``[D-R-2]``) always constructed every
strategy's :class:`~tos.dsl.EvaluationConfig` with ``bindings={}`` — Wave 1
carried no per-strategy bindings config surface, so a strategy whose policy
read a ``config``-sourced :class:`~tos.dsl.vocabulary.Operand` was refused
outright (an empty-bindings config ref can never resolve, so admitting it
would silently make the rule inert). This module is that surface.

**Location: a SIBLING of ``strategies/``, never inside it.** ``config_dir /
"strategy_bindings.yaml"`` sits directly under ``config_dir``, exactly like
every other single config file this compose root reads (``engine.yaml``,
``risk.yaml``, …) — NOT under ``config_dir / "strategies"``, whose own
stray-file rule (:mod:`tos_runtime.strategy.loader` finding #12) would
otherwise try to parse it as a strategy and refuse the whole directory.

**Absence is typed, not an error.** A compose root with no strategy that
reads a ``config``-sourced ref never needs this file at all — the file not
existing is a normal, first-class ``present=False`` result, distinct from
the file existing but being malformed (which refuses). Positive resolution
against what each strategy actually needs is
:mod:`tos_runtime.strategy.resolve`'s job, not this loader's.

**Flat bindings only — the kernel's own shape, not widened.**
:class:`tos.dsl.EvaluationConfig.bindings` is `dict[str, ScalarValue]` (a
single flat level; :func:`tos.dsl.determinism.build_environment` sets
``env["config"] = dict(config.bindings)`` verbatim) and
:func:`tos.dsl.vocabulary.resolve_operand` walks a ``ref`` tuple over that
environment component-by-component — so a ``config``-sourced ref can only
ever be exactly ``("config", <key>)``; there is no nested ``config`` shape
for a longer ref path to walk into. This loader's ``bindings`` mapping is
therefore flat scalar leaves only (pydantic ``extra="forbid"`` plus the
``dict[str, ScalarValue]`` field type rejects a nested mapping value with a
type error, which the loader's own null/shape checks surface as a refusal
naming the file) — never flattened, remapped, or otherwise widened past what
the kernel already accepts (design #31 §0.3 "커널 재정의 금지" applied one
layer up, to the runtime's own config surface).

**Named-TBD ``null`` leaves (fail-closed) — same walker as strategy files.**
Reuses :func:`tos_runtime.strategy.loader._first_null_leaf` (same package,
kept private/shared rather than duplicated) so a still-``null`` value
anywhere in this file, including a nested ``bindings`` leaf, refuses before
pydantic ever sees it — identical discipline to every strategy file's own
null-leaf gate.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): ``tos.*`` (the
kernel — ``tos.dsl.vocabulary.ScalarValue`` only, a pure type alias, no
kernel behavior invoked), stdlib, and ``pyyaml``/``pydantic`` (already-pinned
third parties) only; no ``shared.*``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from tos.canonical import ArtifactIntegrityError
from tos.dsl.vocabulary import ScalarValue

from tos_runtime.strategy.loader import _first_null_leaf

__all__ = [
    "STRATEGY_BINDINGS_FILE_NAME",
    "LoadedStrategyBindings",
    "OneStrategyBindings",
    "StrategyBindingsLoadError",
    "load_strategy_bindings",
]

#: The bindings file name, directly under ``config_dir`` — a SIBLING of
#: ``strategies/``, never inside it (module docstring).
STRATEGY_BINDINGS_FILE_NAME = "strategy_bindings.yaml"


class StrategyBindingsLoadError(ArtifactIntegrityError):
    """Raised when the bindings file EXISTS but fails to load — malformed
    YAML/shape, a still-null leaf, or an unrecognized key. A MISSING file is
    never this error (module docstring "absence is typed, not an error")."""


class OneStrategyBindings(BaseModel):
    """One strategy stem's ``config_binding_version`` + flat ``bindings`` —
    ``extra="forbid"`` so an unrecognized key at this level refuses rather
    than being silently ignored, matching every DSL-adjacent shape in this
    repo (:class:`tos.canonical.FrozenModel`'s own convention, mirrored here
    with a plain :class:`pydantic.BaseModel` since this is runtime, not
    kernel, scope)."""

    model_config = ConfigDict(extra="forbid")

    #: MUST equal the target strategy file's OWN ``config_binding_version``
    #: — :mod:`tos_runtime.strategy.resolve` checks this; a mismatch refuses
    #: naming both values.
    config_binding_version: str
    #: Flat scalar leaves only (module docstring "flat bindings only") —
    #: fed verbatim into :class:`tos.dsl.EvaluationConfig.bindings`.
    bindings: dict[str, ScalarValue] = {}


class _StrategyBindingsFile(BaseModel):
    """The whole file's shape: ``strategies: {<stem>: OneStrategyBindings}``."""

    model_config = ConfigDict(extra="forbid")

    strategies: dict[str, OneStrategyBindings] = {}


@dataclass(frozen=True)
class LoadedStrategyBindings:
    """The bindings load result — typed absence is first-class (module
    docstring), never conflated with "present but empty"."""

    path: Path
    #: ``False`` iff the file does not exist at all — every other field is
    #: then a degenerate empty/``None`` value, never consulted by a caller
    #: that checks ``present`` first.
    present: bool
    #: Keyed by strategy file STEM (e.g. ``"example.strategy"`` for
    #: ``example.strategy.yaml``) — empty when ``present`` is ``False`` or
    #: the file legitimately declares zero entries.
    strategies: dict[str, OneStrategyBindings]
    #: The file's own sha256 (attestation) — ``None`` iff ``present`` is
    #: ``False`` (nothing was read).
    sha256_digest: str | None


def load_strategy_bindings(path: Path) -> LoadedStrategyBindings:
    """Load + fail-closed-validate the strategy-bindings file at ``path``.

    Args:
        path: ``config_dir / "strategy_bindings.yaml"`` (module docstring —
            never a path under ``config_dir / "strategies"``).

    Returns:
        ``present=False`` (module docstring "absence is typed") if ``path``
        does not exist; otherwise the parsed per-stem map + the file's own
        sha256 digest.

    Raises:
        StrategyBindingsLoadError: The file EXISTS but is not valid
            UTF-8/YAML, is not a top-level mapping, carries a ``null`` leaf
            anywhere, or does not match the expected shape (an unrecognized
            key, a non-flat ``bindings`` value, or a wrong type).
    """
    if not path.is_file():
        return LoadedStrategyBindings(
            path=path, present=False, strategies={}, sha256_digest=None
        )

    raw_bytes = path.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StrategyBindingsLoadError(f"{path}: not valid UTF-8: {exc}") from exc

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise StrategyBindingsLoadError(f"{path}: not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise StrategyBindingsLoadError(
            f"{path}: strategy bindings file must be a top-level mapping — "
            "refusing to load"
        )

    null_leaf = _first_null_leaf(raw, "")
    if null_leaf is not None:
        raise StrategyBindingsLoadError(
            f"{path}: field {null_leaf!r} is still null (named-TBD) — "
            "refusing to load until an operator attests a concrete value"
        )

    try:
        parsed = _StrategyBindingsFile.model_validate(raw)
    except ValidationError as exc:
        raise StrategyBindingsLoadError(
            f"{path}: does not match the expected strategy-bindings shape "
            f"(unrecognized key, non-flat 'bindings' value, or wrong type): {exc}"
        ) from exc

    return LoadedStrategyBindings(
        path=path,
        present=True,
        strategies=parsed.strategies,
        sha256_digest=digest,
    )
