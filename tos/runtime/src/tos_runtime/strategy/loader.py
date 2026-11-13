"""Strategy-file loader — reads every ``*.yaml``/``*.yml`` under a"""

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

from tos_runtime._named_tbd import first_named_tbd_leaf

__all__ = [
    "AdmitFn",
    "LoadedStrategies",
    "LoadedStrategy",
    "ParseFn",
    "StrategyLoadError",
    "load_strategies",
]

ParseFn = Callable[[Mapping[str, Any]], AuthoredStrategy]

AdmitFn = Callable[[AuthoredStrategy], AdmissionResult]


class StrategyLoadError(ArtifactIntegrityError):
    """Raised when the strategy directory, or any one file inside it, fails"""


@dataclass(frozen=True)
class LoadedStrategy:
    """One admitted strategy file: its source path, the parsed+admitted"""

    path: Path
    strategy: AuthoredStrategy
    sha256_digest: str


@dataclass(frozen=True)
class LoadedStrategies:
    """The full admitted set from one directory, in sorted-path order (a"""

    strategies: tuple[LoadedStrategy, ...]


def first_null_leaf(value: Any, path: str) -> str | None:
    """Return the dotted/indexed path of the first ``null`` leaf found by a"""
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


_STRATEGY_FILE_SUFFIXES = (".yaml", ".yml")


def _iter_strategy_paths(strategies_dir: Path) -> Iterator[Path]:
    """Yield every ``*.yaml``/``*.yml`` file directly under"""
    yield from sorted(
        path
        for path in strategies_dir.iterdir()
        if path.is_file() and path.suffix in _STRATEGY_FILE_SUFFIXES
    )


def _refuse_stray_files(strategies_dir: Path) -> None:
    """Refuse the whole directory if it contains a regular file directly"""
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
    """Load, fail-closed-validate, parse, and admit ONE strategy file."""
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

    tbd_leaf = first_named_tbd_leaf(raw, "")
    if tbd_leaf is not None:
        raise StrategyLoadError(
            f"{path}: field {tbd_leaf!r} is still the template placeholder "
            "'TBD' (named-TBD) — refusing to load until an operator attests a "
            "concrete value"
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
    """Load every admissible strategy file under ``strategies_dir``."""
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
