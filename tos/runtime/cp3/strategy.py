"""Strategy content loaded + admitted + bound through the PRODUCTION loader path."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.dsl import AuthoredStrategy, DecisionKind
from tos.dsl.serialization import parse_strategy
from tos.engine import InstrumentKey, StrategyRegistry
from tos.engine.admission import (
    derive_instrument_key,
    policy_work_steps,
    strategy_admissible,
)
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import load_strategies
from tos_runtime.strategy.resolve import (
    STRATEGIES_DIRNAME,
    _register_all,
    _resolve_bindings_or_refuse,
)

from ._base import Cp3RunnerRefusal

__all__ = ["LoadedStrategyContent", "load_strategy_content"]


@dataclass(frozen=True)
class LoadedStrategyContent:
    """The admitted strategy plus everything the lineage block needs from it."""

    strategy: AuthoredStrategy
    registry: StrategyRegistry
    instrument_key: InstrumentKey
    direction: str
    strategy_path: Path
    strategy_sha256: str
    bindings_path: Path
    bindings_sha256: str | None
    bindings: Mapping[str, Any]
    work_steps: int
    rule_index: Mapping[str, tuple[str, DecisionKind]]


def _rule_id(rationale: str) -> str:
    """The rule id a Decision's rationale declares — the token before the colon."""
    head, _, _ = rationale.partition(":")
    return head.strip()


def _build_rule_index(
    strategy: AuthoredStrategy, *, strategy_path: Path
) -> dict[str, tuple[str, DecisionKind]]:
    """Map each reachable Decision's rationale onto ``(rule id, kind)``."""
    policy = strategy.policy
    if policy is None:  # pragma: no cover - admission already refused this
        raise Cp3RunnerRefusal(f"{strategy_path}: strategy carries no policy")
    index: dict[str, tuple[str, DecisionKind]] = {}

    def register(rationale: str | None, kind: DecisionKind, where: str) -> None:
        if rationale is None or not rationale.strip():
            raise Cp3RunnerRefusal(
                f"{strategy_path}: {where} has no rationale — the rule id is read "
                "from it"
            )
        rule_id = _rule_id(rationale)
        if not rule_id:
            raise Cp3RunnerRefusal(
                f"{strategy_path}: {where} rationale {rationale!r} declares no "
                "'<rule-id>: <why>' prefix"
            )
        existing = index.get(rationale)
        if existing is not None and existing != (rule_id, kind):
            raise Cp3RunnerRefusal(
                f"{strategy_path}: rationale {rationale!r} is shared by two "
                "decisions with different ids/kinds — rule attribution would be "
                "ambiguous"
            )
        index[rationale] = (rule_id, kind)

    for position, rule in enumerate(policy.rules, start=1):
        where = f"rule #{position}"
        register(rule.decision.rationale, rule.decision.kind, where)
        if rule.decision.target is not None:
            register(
                rule.decision.target.rationale, rule.decision.kind, f"{where} target"
            )
    register(policy.default.rationale, policy.default.kind, "default decision")
    return index


def _single_direction(strategy: AuthoredStrategy, *, strategy_path: Path) -> str:
    """The one direction this deployment's ACTION targets declare."""
    policy = strategy.policy
    assert policy is not None
    directions: set[str] = set()
    for rule in policy.rules:
        if rule.decision.kind is not DecisionKind.ACTION:
            continue
        target = rule.decision.target
        if target is None or target.direction is None:
            continue
        directions.add(target.direction)
    if len(directions) != 1:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: expected exactly one ACTION direction, found "
            f"{sorted(directions)} — direction is a per-deployment fact and "
            "SHORT is a separate render (kickoff §4 결정 4)"
        )
    return directions.pop()


def _refuse_path_shape(*, strategy_path: Path, bindings_path: Path) -> Path:
    """Refuse paths a boot could not have produced; return the strategies dir."""
    strategies_dir = strategy_path.parent
    if bindings_path.name != STRATEGY_BINDINGS_FILE_NAME:
        raise Cp3RunnerRefusal(
            f"{bindings_path}: the bindings file must be named "
            f"{STRATEGY_BINDINGS_FILE_NAME!r} — that name is the loader's own "
            "contract (tos_runtime.strategy.bindings), and a differently-named "
            "file would be invisible to a boot"
        )
    if strategies_dir.name != STRATEGIES_DIRNAME:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: its parent directory is {strategies_dir.name!r}, "
            f"not {STRATEGIES_DIRNAME!r} — a boot reads strategies from "
            f"config_dir / {STRATEGIES_DIRNAME!r}, so a file outside such a "
            "directory is not content a deployment could load"
        )
    if bindings_path.resolve().parent != strategies_dir.resolve().parent:
        raise Cp3RunnerRefusal(
            f"{bindings_path}: must sit in the SAME config_dir as the "
            f"{STRATEGIES_DIRNAME!r} directory holding {strategy_path.name} "
            f"(expected {strategies_dir.resolve().parent / STRATEGY_BINDINGS_FILE_NAME}) "
            "— the boot derives both paths from one config_dir, and a bindings "
            "file from elsewhere would resolve operands against content the "
            "deployment does not have"
        )
    return strategies_dir


def load_strategy_content(
    *, strategy_path: Path, bindings_path: Path
) -> LoadedStrategyContent:
    """Load, admit, and bind the strategy through the **production** path."""
    strategies_dir = _refuse_path_shape(
        strategy_path=strategy_path, bindings_path=bindings_path
    )
    try:
        loaded = load_strategies(
            strategies_dir, parse=parse_strategy, admit=strategy_admissible
        )
        loaded_bindings = load_strategy_bindings(bindings_path)
        _resolve_bindings_or_refuse(loaded, loaded_bindings)
        registry = _register_all(loaded, loaded_bindings.strategies)
    except ValueError as exc:
        raise Cp3RunnerRefusal(f"strategy content refused: {exc}") from exc

    selected = [
        entry
        for entry in loaded.strategies
        if entry.path.resolve() == strategy_path.resolve()
    ]
    if not selected:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: not among the strategy files the loader admitted "
            f"in {strategies_dir} ({[str(e.path) for e in loaded.strategies]})"
        )
    if len(loaded.strategies) != 1:
        raise Cp3RunnerRefusal(
            f"{strategies_dir}: holds {len(loaded.strategies)} strategy files — "
            "this replay drives one scope through one core, so the directory "
            "must hold exactly the one requested strategy"
        )
    entry = selected[0]
    key, reasons = derive_instrument_key(entry.strategy)
    if key is None:
        raise Cp3RunnerRefusal(
            f"{strategy_path}: no single dispatch key: {'; '.join(reasons)}"
        )
    policy = entry.strategy.policy
    if policy is None:  # pragma: no cover - admission already refused this
        raise Cp3RunnerRefusal(f"{strategy_path}: strategy carries no policy")
    one = loaded_bindings.strategies.get(entry.path.stem)
    return LoadedStrategyContent(
        strategy=entry.strategy,
        registry=registry,
        instrument_key=key,
        direction=_single_direction(entry.strategy, strategy_path=strategy_path),
        strategy_path=entry.path,
        strategy_sha256=entry.sha256_digest,
        bindings_path=loaded_bindings.path,
        bindings_sha256=loaded_bindings.sha256_digest,
        bindings=dict(one.bindings) if one is not None else {},
        work_steps=policy_work_steps(policy),
        rule_index=_build_rule_index(entry.strategy, strategy_path=entry.path),
    )
