"""Resolves the composition root's ONE strategy source (TOS Phase 3 슬라이스
D-R ``[D-R-2]``, ``docs/plans/2026-09-09-tos-phase3-event-core-plan.md``
§1.2): either ``config_dir/strategies/*.yaml``/``*.yml`` (the production
path, via :func:`~tos_runtime.strategy.loader.load_strategies` wired to the
kernel's real :func:`tos.dsl.serialization.parse_strategy` /
:func:`tos.engine.admission.strategy_admissible`), or a caller-injected
:class:`~tos.engine.StrategyRegistry` (the test-compatibility path). Never
both — an operator who points compose at a strategies directory AND injects
a registry has two disagreeing sources of truth for what the engine will
dispatch, and this module refuses rather than silently preferring one.

**Neither present now REFUSES by default (2026-09-09 independent-review
finding #8, disposition applied).** An earlier revision fell back to a
silent empty :class:`~tos.engine.StrategyRegistry` here — a fail-open the
sibling rule one layer down
(:func:`~tos_runtime.strategy.loader.load_strategies`'s own "an engine with
zero admitted strategies... does not start") already refused for the
adjacent case (a directory that exists but is empty). The discriminator
between refusal and silent boot was whether a directory happened to exist
on disk, which is not an operator attestation of anything. This module now
treats "neither present" identically to "empty directory": it refuses,
UNLESS the caller passes ``allow_no_strategies=True`` — a keyword-only,
explicitly-stated choice (never the default) — in which case it proceeds
with an empty registry and records a non-halt
``STRATEGY_SOURCE_ABSENT_BY_OPERATOR_CHOICE`` evidence entry (a plain
:meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append`, NOT
:func:`~tos_runtime.evidence.emergency.record_halt` — this is a stated
choice that boots successfully, not a HALT/protective-action record).

**Config-sourced context refs without a bindings surface are refused at
load (finding #9, disposition applied).** ``config`` is an
:data:`~tos.dsl.vocabulary.ADMISSIBLE_CONTEXT_SOURCES` member, and
``strategy_admissible`` only requires ONE capsule-sourced operand per
outcome-gating compare — so a compare such as ``capsule.resolved_values.close
LT config.lower_band_threshold`` parses and admits cleanly. Wave 1 carries
no per-strategy bindings config surface yet (:func:`_register_all` always
constructs :class:`~tos.dsl.EvaluationConfig` with ``bindings={}`` — a
follow-up wave item, plan §7.1 deviation ④); with an empty bindings map,
:func:`tos.dsl.vocabulary.resolve_operand` returns ``UNKNOWN`` for any
``config``-sourced ref at evaluation time, silently making the rule never
fire — no refusal, no evidence, no halt. Until a bindings config surface
exists, this module refuses any admitted strategy file whose lowered
program (:func:`tos.dsl.lowering.lower_strategy` + :func:`tos.dsl.candidate.
iter_nodes` — read-only kernel consumption, no kernel behavior added) names
a ``config``-sourced ``context_ref`` while bindings are empty, naming both
the file and the ref path in the refusal, rather than admitting a strategy
that can never do anything.

**Evidence before halt.** Any REFUSAL here is durably recorded as one
``STRATEGY_REFUSED`` evidence entry (both the sqlite evidence store and the
sqlite-independent emergency log, via
:func:`~tos_runtime.evidence.emergency.record_halt` — mirrors
:func:`~tos_runtime.compose._boot_integrity.verify_rcl_log_or_halt`'s own
"never a silent halt" discipline) BEFORE :class:`StrategyRegistryResolutionRefused`
is raised, so an operator inspecting the evidence trail after a refused boot
sees exactly why, never just an uncaught exception. The ``allow_no_strategies``
SUCCESS path records its own, differently-kinded, non-halt evidence entry
instead (see above) — it never raises.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): ``tos.*`` (the
kernel — including :mod:`tos.dsl.serialization`, the D-K lane's parser) +
``tos_runtime.*`` + stdlib only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tos.canonical import ArtifactIntegrityError
from tos.dsl import EvaluationConfig
from tos.dsl.candidate import iter_nodes
from tos.dsl.lowering import lower_strategy
from tos.dsl.serialization import parse_strategy
from tos.dsl.vocabulary import KIND_CONTEXT_REF, Operand
from tos.engine import RegistrationRefused, StrategyRegistry
from tos.engine.admission import strategy_admissible
from tos.engine.vocabulary import CONFIG_CONTEXT_SOURCE
from tos.workload import RuntimeIdentity

from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.store import SqliteEvidenceStore
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

#: The strategies subdirectory name, directly under ``config_dir`` — mirrors
#: this compose root's other ``config_dir``-relative conventions (each
#: sibling config file is named directly, e.g. ``engine.yaml``; strategies
#: are plural so they get a subdirectory instead of one file).
STRATEGIES_DIRNAME = "strategies"

#: The evidence kind/record class this module's refusal path records.
STRATEGY_REFUSED_EVIDENCE_KIND = "STRATEGY_REFUSED"

#: The evidence kind/record class recorded on the ``allow_no_strategies=True``
#: SUCCESS path (module docstring finding #8) — deliberately NOT
#: ``STRATEGY_REFUSED``: this path boots successfully, it is not a halt.
STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND = "STRATEGY_SOURCE_ABSENT_BY_OPERATOR_CHOICE"


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


def _config_ref_path(loaded_strategy: LoadedStrategy) -> str | None:
    """Return the dotted ``config``-sourced ref path (e.g.
    ``"config.lower_band_threshold"``) of the FIRST outcome-gating
    :class:`~tos.dsl.vocabulary.Operand` naming the ``config`` context
    source, walking the strategy's own typed policy (rule guards only —
    ``Operand`` never appears outside a :class:`~tos.dsl.vocabulary.Compare`,
    see :mod:`tos.dsl.vocabulary`), or ``None`` if there is none.

    Used ONLY to name the ref in a refusal message once
    :func:`_refuse_config_refs_without_bindings` has already DETECTED the
    presence of a config-sourced ``context_ref`` via the kernel's own
    :func:`tos.dsl.lowering.lower_strategy` + :func:`tos.dsl.candidate.
    iter_nodes` (the lowered candidate node carries only the ref's source,
    not its full path — module docstring "Payload is intentionally
    structural, not literal" — so naming the exact path requires this
    separate, read-only walk of the typed authoring tree)."""
    policy = loaded_strategy.strategy.policy
    if policy is None:  # pragma: no cover - admitted strategies always carry a policy
        return None
    for rule in policy.rules:
        for compare in rule.all_of:
            for operand in (compare.left, compare.right):
                path = _operand_config_ref_path(operand)
                if path is not None:
                    return path
    return None


def _operand_config_ref_path(operand: Operand) -> str | None:
    """``"."``-joined ref path if ``operand`` is a ``config``-sourced ref, else ``None``."""
    if operand.ref is not None and operand.ref[0] == CONFIG_CONTEXT_SOURCE:
        return ".".join(operand.ref)
    return None


def _refuse_config_refs_without_bindings(loaded: LoadedStrategies) -> None:
    """Refuse any admitted strategy file whose lowered program contains a
    ``config``-sourced ``context_ref`` while bindings are empty (module
    docstring finding #9): with Wave 1's hard-coded ``bindings={}``
    (:func:`_register_all`), such a rule can never resolve its ``config``
    operand and silently never fires — no refusal, no evidence, no halt.

    Detection reuses the kernel's OWN lowering
    (:func:`tos.dsl.lowering.lower_strategy`) + tree walk
    (:func:`tos.dsl.candidate.iter_nodes`) — read-only consumption, no
    kernel behavior added — exactly the seam ``strategy_admissible`` already
    runs through (finding #9's suggested disposition).

    Raises:
        StrategyLoadError: The first (sorted-path order) offending file,
            naming both the file and the offending ref's dotted path
            (:func:`_config_ref_path`).
    """
    for entry in loaded.strategies:
        program = lower_strategy(entry.strategy)
        has_config_ref = any(
            node.kind == KIND_CONTEXT_REF and node.source == CONFIG_CONTEXT_SOURCE
            for node in iter_nodes(program)
        )
        if not has_config_ref:
            continue
        ref_path = _config_ref_path(entry)
        raise StrategyLoadError(
            f"{entry.path}: strategy carries a context_ref sourced from "
            f"{CONFIG_CONTEXT_SOURCE!r} ({ref_path or '<path unavailable>'}) while "
            "this compose root's bindings config surface is empty — the rule "
            "could never resolve this operand and would silently never fire "
            "(no bindings config source exists yet, plan §7.1 deviation ④); "
            "refusing rather than admitting an inert strategy"
        )


def _register_all(loaded: LoadedStrategies) -> StrategyRegistry:
    """Register every loaded (already admitted) strategy into a fresh
    registry, deriving each :class:`~tos.dsl.EvaluationConfig` from the
    strategy's own ``config_binding_version`` with empty ``bindings`` —
    Wave 1 scope carries no operator-configured per-strategy binding
    surface yet (every fixture and the example strategy file both use
    empty bindings today; a future wave adds a bindings config source
    without changing this call site's shape — see
    :func:`_refuse_config_refs_without_bindings`, run by the caller BEFORE
    this function, for what happens to a strategy that needs one).

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
    allow_no_strategies: bool = False,
) -> ResolvedStrategyRegistry:
    """Resolve the ONE strategy source for this compose (module docstring).

    Args:
        config_dir: The compose config directory; ``config_dir /
            "strategies"`` is checked for the file source.
        injected_registry: The caller-supplied registry (test-compatibility
            path), or ``None``.
        evidence_store: Where a refusal's (or the ``allow_no_strategies``
            success path's) evidence entry is durably recorded.
        emergency_log: The sqlite-independent refusal evidence path.
        identity: This process's runtime identity, stamped on the recorded
            evidence entry.
        allow_no_strategies: Keyword-only, defaults to ``False``. When
            neither a strategies directory nor an injected registry is
            supplied, the default REFUSES (module docstring finding #8);
            passing ``True`` is the explicit, stated operator choice to
            proceed with an empty registry instead. Has no effect when
            either source IS present.

    Returns:
        The resolved registry, plus the loaded file set (``None`` unless the
        file source was used).

    Raises:
        StrategyRegistryResolutionRefused: Both a strategies directory and
            an injected registry were supplied; neither was supplied and
            ``allow_no_strategies`` is ``False``; the directory failed to
            load or admitted a strategy this module itself refuses (
            :class:`~tos_runtime.strategy.loader.StrategyLoadError`); or an
            admitted strategy failed registry registration — always after
            the ``STRATEGY_REFUSED`` evidence entry is recorded.
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
        if injected_registry is not None:
            return ResolvedStrategyRegistry(registry=injected_registry, loaded=None)
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
        # Explicit, stated operator choice (module docstring) — proceeds
        # with an empty registry; evidenced (NOT via record_halt: this is a
        # successful boot, not a halt/protective-action record).
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

    try:
        loaded = load_strategies(
            strategies_dir, parse=parse_strategy, admit=strategy_admissible
        )
        _refuse_config_refs_without_bindings(loaded)
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
