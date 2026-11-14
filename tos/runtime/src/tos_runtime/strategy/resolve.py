"""Resolves the composition root's ONE strategy source (TOS Phase 3 슬라이스"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos.canonical import ArtifactIntegrityError
from tos.dsl import EvaluationConfig, ScalarValue
from tos.dsl.serialization import parse_strategy
from tos.engine import RegistrationRefused, StrategyRegistry
from tos.engine.admission import (
    iter_outcome_gating_compares,
    operand_source,
    strategy_admissible,
)
from tos.engine.vocabulary import CONFIG_CONTEXT_SOURCE
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.strategy.bindings import (
    STRATEGY_BINDINGS_FILE_NAME,
    LoadedStrategyBindings,
    OneStrategyBindings,
    StrategyBindingsLoadError,
    load_strategy_bindings,
)
from tos_runtime.strategy.loader import (
    LoadedStrategies,
    LoadedStrategy,
    StrategyLoadError,
    load_strategies,
)

__all__ = [
    "STRATEGIES_DIRNAME",
    "STRATEGY_REFUSED_EVIDENCE_KIND",
    "STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND",
    "ResolvedStrategyRegistry",
    "StrategyRegistryResolutionRefused",
    "resolve_strategy_registry",
]

STRATEGIES_DIRNAME = "strategies"

STRATEGY_REFUSED_EVIDENCE_KIND = "STRATEGY_REFUSED"

STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND = "STRATEGY_SOURCE_ABSENT_BY_OPERATOR_CHOICE"


class StrategyRegistryResolutionRefused(ArtifactIntegrityError):
    """Raised when the strategy source cannot be resolved unambiguously, or"""


@dataclass(frozen=True)
class ResolvedStrategyRegistry:
    """The resolved registry, plus the loaded-file set that fed it (``None``"""

    registry: StrategyRegistry
    loaded: LoadedStrategies | None
    loaded_bindings: LoadedStrategyBindings | None = None


def _refuse(
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    reason: str,
) -> None:
    """Durably record ``STRATEGY_REFUSED`` (both evidence paths) before the"""
    record_halt(
        evidence_store,
        emergency_log,
        payload={"detail": reason},
        kind=STRATEGY_REFUSED_EVIDENCE_KIND,
        record_class=STRATEGY_REFUSED_EVIDENCE_KIND,
        runtime_identity=identity,
    )


def _config_ref_paths(loaded_strategy: LoadedStrategy) -> tuple[tuple[str, ...], ...]:
    """Every DISTINCT ``config``-sourced ref, as its raw component tuple, any"""
    policy = loaded_strategy.strategy.policy
    if policy is None:  # pragma: no cover - admitted strategies always carry a policy
        return ()
    seen: list[tuple[str, ...]] = []
    for compare in iter_outcome_gating_compares(policy):
        for operand in (compare.left, compare.right):
            ref = operand.ref
            if (
                operand_source(operand) == CONFIG_CONTEXT_SOURCE
                and ref is not None
                and ref not in seen
            ):
                seen.append(ref)
    return tuple(seen)


def _ref_resolves_in_bindings(
    ref: tuple[str, ...], bindings: dict[str, ScalarValue]
) -> bool:
    """Whether ``ref[1:]`` resolves to a scalar leaf in ``bindings`` —"""
    value: Any = bindings
    for part in ref[1:]:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False
    return isinstance(value, bool | int | float | str)


def _refuse_stem_collisions(loaded: LoadedStrategies) -> None:
    """Refuse when two admitted strategy files share the same"""
    seen: dict[str, Path] = {}
    for entry in loaded.strategies:
        stem = entry.path.stem
        prior = seen.get(stem)
        if prior is not None:
            raise StrategyLoadError(
                f"{prior} and {entry.path} share the same stem {stem!r} — "
                "bindings are keyed by stem, so these two files cannot be "
                "given different bindings; refusing the collision"
            )
        seen[stem] = entry.path


def _resolve_bindings_or_refuse(
    loaded: LoadedStrategies, loaded_bindings: LoadedStrategyBindings
) -> None:
    """Positive resolution of every admitted strategy's ``config``-sourced"""
    _refuse_stem_collisions(loaded)
    entries_by_stem = loaded_bindings.strategies
    for entry in loaded.strategies:
        stem = entry.path.stem
        refs = _config_ref_paths(entry)
        binding_entry = entries_by_stem.get(stem)

        if binding_entry is None:
            if refs:
                raise StrategyLoadError(
                    f"{entry.path}: strategy carries {len(refs)} config-sourced "
                    f"context_ref(s) (e.g. {'.'.join(refs[0])!r}) but "
                    f"{loaded_bindings.path} has no entry for stem {stem!r} — "
                    "refusing rather than admitting a strategy whose config "
                    "operand can never resolve (rule 1)"
                )
            continue

        strategy_version = entry.strategy.config_binding_version
        if binding_entry.config_binding_version != strategy_version:
            raise StrategyLoadError(
                f"{entry.path}: {loaded_bindings.path} stem {stem!r} declares "
                f"config_binding_version={binding_entry.config_binding_version!r}, "
                f"the strategy file itself declares {strategy_version!r} — "
                "refusing on version mismatch (rule 2)"
            )

        referenced_keys: set[str] = set()
        for ref in refs:
            if not _ref_resolves_in_bindings(ref, binding_entry.bindings):
                raise StrategyLoadError(
                    f"{entry.path}: config-sourced ref {'.'.join(ref)!r} does "
                    f"not resolve to a scalar leaf in {loaded_bindings.path} "
                    f"stem {stem!r}'s bindings — refusing rather than "
                    "admitting a rule that can never resolve this operand "
                    "(rule 3)"
                )
            if len(ref) >= 2:
                referenced_keys.add(ref[1])

        unused = sorted(set(binding_entry.bindings) - referenced_keys)
        if unused:
            raise StrategyLoadError(
                f"{loaded_bindings.path}: stem {stem!r} declares bindings "
                f"key(s) {unused} that {entry.path} never references via a "
                "config-sourced context_ref — refusing (configuration "
                "drift; an unused knob is misconfiguration under "
                "CLAUDE.md's 'configuration-driven only', rule 4)"
            )

    admitted_stems = {entry.path.stem for entry in loaded.strategies}
    orphans = sorted(set(entries_by_stem) - admitted_stems)
    if orphans:
        raise StrategyLoadError(
            f"{loaded_bindings.path}: stem(s) {orphans} have no matching "
            "admitted strategy file — refusing an orphan bindings entry "
            "(rule 5)"
        )


def _register_all(
    loaded: LoadedStrategies, bindings_by_stem: dict[str, OneStrategyBindings]
) -> StrategyRegistry:
    """Register every loaded (already admitted, already positively resolved"""
    registry = StrategyRegistry()
    for entry in loaded.strategies:
        config_binding_version = entry.strategy.config_binding_version
        assert config_binding_version is not None
        one = bindings_by_stem.get(entry.path.stem)
        bindings = dict(one.bindings) if one is not None else {}
        config = EvaluationConfig(
            config_version=config_binding_version, bindings=bindings
        )
        registry.register(entry.strategy, config)
    return registry


def _resolve_injected_registry(
    injected_registry: StrategyRegistry,
    *,
    bindings_path: Path,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
) -> ResolvedStrategyRegistry:
    """The injected-registry (test-compatibility) path — no strategies"""
    if bindings_path.is_file():
        reason = (
            f"{bindings_path}: a strategy bindings file is present but "
            "strategies come from an injected StrategyRegistry — bindings "
            "apply only to the file strategy source; exactly one strategy "
            "source is admissible"
        )
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason)
    return ResolvedStrategyRegistry(registry=injected_registry, loaded=None)


def _resolve_neither_present(
    strategies_dir: Path,
    *,
    bindings_path: Path,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    allow_no_strategies: bool,
) -> ResolvedStrategyRegistry:
    """Neither a strategies directory nor an injected registry — the"""
    if not allow_no_strategies:
        reason = (
            f"{strategies_dir}: no strategies directory and no injected "
            "StrategyRegistry — an engine with zero admitted strategies "
            "is not a defined no-action (mirrors "
            "tos_runtime.strategy.loader.load_strategies's own "
            "zero-strategies refusal one layer down); pass "
            "allow_no_strategies=True to state this choice explicitly"
        )
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason)
    if bindings_path.is_file():
        reason = (
            f"{bindings_path}: a strategy bindings file is present but "
            "allow_no_strategies=True admits zero strategies — every "
            "bindings entry would be an orphan (rule 5); refusing rather "
            "than silently ignoring a stale bindings file"
        )
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason)
    evidence_store.append(
        {
            "detail": (
                f"{strategies_dir}: no strategies directory and no "
                "injected registry; allow_no_strategies=True"
            )
        },
        kind=STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND,
        record_class=STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND,
        runtime_identity=identity,
    )
    return ResolvedStrategyRegistry(registry=StrategyRegistry(), loaded=None)


def resolve_strategy_registry(
    config_dir: Path,
    *,
    injected_registry: StrategyRegistry | None,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    allow_no_strategies: bool = False,
) -> ResolvedStrategyRegistry:
    """Resolve the ONE strategy source for this compose (module docstring)."""
    strategies_dir = config_dir / STRATEGIES_DIRNAME
    bindings_path = config_dir / STRATEGY_BINDINGS_FILE_NAME
    dir_present = strategies_dir.is_dir()

    if dir_present and injected_registry is not None:
        reason = (
            f"{strategies_dir}: a strategies directory AND an injected "
            "StrategyRegistry were both supplied — exactly one strategy "
            "source is admissible, never both"
        )
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason)

    if not dir_present:
        if injected_registry is not None:
            return _resolve_injected_registry(
                injected_registry,
                bindings_path=bindings_path,
                evidence_store=evidence_store,
                emergency_log=emergency_log,
                identity=identity,
            )
        return _resolve_neither_present(
            strategies_dir,
            bindings_path=bindings_path,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
            allow_no_strategies=allow_no_strategies,
        )

    try:
        loaded = load_strategies(
            strategies_dir, parse=parse_strategy, admit=strategy_admissible
        )
        loaded_bindings = load_strategy_bindings(bindings_path)
        _resolve_bindings_or_refuse(loaded, loaded_bindings)
    except (StrategyLoadError, StrategyBindingsLoadError) as exc:
        _refuse(evidence_store, emergency_log, identity, str(exc))
        raise StrategyRegistryResolutionRefused(str(exc)) from exc

    try:
        registry = _register_all(loaded, loaded_bindings.strategies)
    except RegistrationRefused as exc:
        reason = f"{strategies_dir}: an admitted strategy failed registry registration: {exc}"
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason) from exc

    return ResolvedStrategyRegistry(
        registry=registry, loaded=loaded, loaded_bindings=loaded_bindings
    )
