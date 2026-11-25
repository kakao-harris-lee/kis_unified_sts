"""Per-strategy config bindings loader — the finding-#9 disposition (TOS"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError
from tos.canonical import ArtifactIntegrityError
from tos.dsl.vocabulary import ScalarValue

from tos_runtime.strategy.loader import first_named_tbd_leaf, first_null_leaf

__all__ = [
    "STRATEGY_BINDINGS_FILE_NAME",
    "LoadedStrategyBindings",
    "OneStrategyBindings",
    "StrategyBindingsLoadError",
    "load_strategy_bindings",
]

STRATEGY_BINDINGS_FILE_NAME = "strategy_bindings.yaml"


class StrategyBindingsLoadError(ArtifactIntegrityError):
    """Raised when the bindings file EXISTS but fails to load — malformed"""


class OneStrategyBindings(BaseModel):
    """One strategy stem's ``config_binding_version`` + flat ``bindings`` —"""

    model_config = ConfigDict(extra="forbid")

    config_binding_version: str
    bindings: dict[str, ScalarValue] = {}


class _StrategyBindingsFile(BaseModel):
    """The whole file's shape: ``strategies: {<stem>: OneStrategyBindings}``."""

    model_config = ConfigDict(extra="forbid")

    strategies: dict[str, OneStrategyBindings] = {}


@dataclass(frozen=True)
class LoadedStrategyBindings:
    """The bindings load result — typed absence is first-class (module"""

    path: Path
    present: bool
    strategies: dict[str, OneStrategyBindings]
    sha256_digest: str | None


def load_strategy_bindings(path: Path) -> LoadedStrategyBindings:
    """Load + fail-closed-validate the strategy-bindings file at ``path``."""
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

    null_leaf = first_null_leaf(raw, "")
    if null_leaf is not None:
        raise StrategyBindingsLoadError(
            f"{path}: field {null_leaf!r} is still null (named-TBD) — "
            "refusing to load until an operator attests a concrete value"
        )

    tbd_leaf = first_named_tbd_leaf(raw, "")
    if tbd_leaf is not None:
        raise StrategyBindingsLoadError(
            f"{path}: field {tbd_leaf!r} is still the template placeholder "
            "'TBD' (named-TBD) — refusing to load until an operator attests a "
            "concrete value"
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
