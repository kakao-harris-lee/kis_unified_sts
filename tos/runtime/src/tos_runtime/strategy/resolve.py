"""Resolves the composition root's ONE strategy source (TOS Phase 3 슬라이스
D-R ``[D-R-2]``, ``docs/plans/2026-09-09-tos-phase3-event-core-plan.md``
§1.2): either ``config_dir/strategies/*.yaml`` (the production path, via
:func:`~tos_runtime.strategy.loader.load_strategies` wired to the kernel's
real :func:`tos.dsl.serialization.parse_strategy` /
:func:`tos.engine.admission.strategy_admissible`), or a caller-injected
:class:`~tos.engine.StrategyRegistry` (the test-compatibility path). Never
both — an operator who points compose at a strategies directory AND injects
a registry has two disagreeing sources of truth for what the engine will
dispatch, and this module refuses rather than silently preferring one.

Neither present is NOT the same refusal as an *empty* strategies directory:
:func:`~tos_runtime.strategy.loader.load_strategies` itself already refuses
a strategies directory that exists but contains zero files (its own
docstring: "an engine with zero admitted strategies... does not start").
When the directory does not exist at all, this module falls back to an
empty :class:`~tos.engine.StrategyRegistry` (or the injected one, if given)
— the pre-existing default this compose root has always had for callers
that do not yet configure strategies at all (module-level docstring parity
with :func:`~tos_runtime.compose.root.compose_paper_runtime`'s own
``registry: The strategy registry (defaults to an empty one)``).

**Evidence before halt.** Any refusal here is durably recorded as one
``STRATEGY_REFUSED`` evidence entry (both the sqlite evidence store and the
sqlite-independent emergency log, via
:func:`~tos_runtime.evidence.emergency.record_halt` — mirrors
:func:`~tos_runtime.compose._boot_integrity.verify_rcl_log_or_halt`'s own
"never a silent halt" discipline) BEFORE :class:`StrategyRegistryResolutionRefused`
is raised, so an operator inspecting the evidence trail after a refused boot
sees exactly why, never just an uncaught exception.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): ``tos.*`` (the
kernel — including :mod:`tos.dsl.serialization`, the D-K lane's parser) +
``tos_runtime.*`` + stdlib only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tos.canonical import ArtifactIntegrityError
from tos.dsl import EvaluationConfig
from tos.dsl.serialization import parse_strategy
from tos.engine import RegistrationRefused, StrategyRegistry
from tos.engine.admission import strategy_admissible
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.strategy.loader import (
    LoadedStrategies,
    StrategyLoadError,
    load_strategies,
)

__all__ = [
    "STRATEGIES_DIRNAME",
    "STRATEGY_REFUSED_EVIDENCE_KIND",
    "ResolvedStrategyRegistry",
    "StrategyRegistryResolutionRefused",
    "resolve_strategy_registry",
]

#: The strategies subdirectory name, directly under ``config_dir`` — mirrors
#: this compose root's other ``config_dir``-relative conventions (each
#: sibling config file is named directly, e.g. ``engine.yaml``; strategies
#: are plural so they get a subdirectory instead of one file).
STRATEGIES_DIRNAME = "strategies"

#: The evidence kind/record class this module's refusal path records.
STRATEGY_REFUSED_EVIDENCE_KIND = "STRATEGY_REFUSED"


class StrategyRegistryResolutionRefused(ArtifactIntegrityError):
    """Raised when the strategy source cannot be resolved unambiguously, or
    the resolved file source fails to load/register — always AFTER a
    ``STRATEGY_REFUSED`` evidence entry has already been durably recorded
    (this module's own docstring)."""


@dataclass(frozen=True)
class ResolvedStrategyRegistry:
    """The resolved registry, plus the loaded-file set that fed it (``None``
    when the source was an injected registry or the legacy neither-present
    empty default) — the composition root needs ``loaded`` to extend the
    ``OPERATOR_ATTESTED_INPUTS`` evidence record with each strategy file's
    own digest (plan §1.2 item 3)."""

    registry: StrategyRegistry
    loaded: LoadedStrategies | None


def _refuse(
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    reason: str,
) -> None:
    """Durably record ``STRATEGY_REFUSED`` (both evidence paths) before the
    caller raises — never a silent halt (module docstring)."""
    record_halt(
        evidence_store,
        emergency_log,
        payload={"detail": reason},
        kind=STRATEGY_REFUSED_EVIDENCE_KIND,
        record_class=STRATEGY_REFUSED_EVIDENCE_KIND,
        runtime_identity=identity,
    )


def _register_all(loaded: LoadedStrategies) -> StrategyRegistry:
    """Register every loaded (already admitted) strategy into a fresh
    registry, deriving each :class:`~tos.dsl.EvaluationConfig` from the
    strategy's own ``config_binding_version`` with empty ``bindings`` —
    Wave 1 scope carries no operator-configured per-strategy binding
    surface yet (every fixture and the example strategy file both use
    empty bindings today; a future wave adds a bindings config source
    without changing this call site's shape).

    Raises:
        RegistrationRefused: Defensive only — ``load_strategies`` already
            ran the identical :func:`~tos.engine.admission.strategy_admissible`
            gate ``register`` re-runs, so a refusal here would mean the two
            gates disagree, which should not happen in practice.
    """
    registry = StrategyRegistry()
    for entry in loaded.strategies:
        config_binding_version = entry.strategy.config_binding_version
        assert config_binding_version is not None  # ISSUED strategy: required-covered
        config = EvaluationConfig(config_version=config_binding_version, bindings={})
        registry.register(entry.strategy, config)
    return registry


def resolve_strategy_registry(
    config_dir: Path,
    *,
    injected_registry: StrategyRegistry | None,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
) -> ResolvedStrategyRegistry:
    """Resolve the ONE strategy source for this compose (module docstring).

    Args:
        config_dir: The compose config directory; ``config_dir /
            "strategies"`` is checked for the file source.
        injected_registry: The caller-supplied registry (test-compatibility
            path), or ``None``.
        evidence_store: Where a refusal's evidence entry is durably recorded.
        emergency_log: The sqlite-independent refusal evidence path.
        identity: This process's runtime identity, stamped on the refusal
            record.

    Returns:
        The resolved registry, plus the loaded file set (``None`` unless the
        file source was used).

    Raises:
        StrategyRegistryResolutionRefused: Both a strategies directory and
            an injected registry were supplied, the directory failed to
            load (:class:`~tos_runtime.strategy.loader.StrategyLoadError`),
            or an admitted strategy failed registry registration — always
            after the ``STRATEGY_REFUSED`` evidence entry is recorded.
    """
    strategies_dir = config_dir / STRATEGIES_DIRNAME
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
        # Legacy neither-present default (module docstring) — NOT the same
        # refusal as an empty-but-present directory, which load_strategies
        # itself already refuses.
        return ResolvedStrategyRegistry(
            registry=(
                injected_registry
                if injected_registry is not None
                else StrategyRegistry()
            ),
            loaded=None,
        )

    try:
        loaded = load_strategies(
            strategies_dir, parse=parse_strategy, admit=strategy_admissible
        )
    except StrategyLoadError as exc:
        _refuse(evidence_store, emergency_log, identity, str(exc))
        raise StrategyRegistryResolutionRefused(str(exc)) from exc

    try:
        registry = _register_all(loaded)
    except RegistrationRefused as exc:
        reason = f"{strategies_dir}: an admitted strategy failed registry registration: {exc}"
        _refuse(evidence_store, emergency_log, identity, reason)
        raise StrategyRegistryResolutionRefused(reason) from exc

    return ResolvedStrategyRegistry(registry=registry, loaded=loaded)
