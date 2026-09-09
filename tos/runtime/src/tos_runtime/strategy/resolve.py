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

**Config-sourced context refs are positively resolved against a bindings
file (finding #9, disposition applied — TOS Phase 3 슬라이스 D-R
``[D-R-3]``).** ``config`` is an
:data:`~tos.dsl.vocabulary.ADMISSIBLE_CONTEXT_SOURCES` member, and
``strategy_admissible`` only requires ONE capsule-sourced operand per
outcome-gating compare — so a compare such as ``capsule.resolved_values.close
LT config.lower_band_threshold`` parses and admits cleanly. An earlier
revision (``[D-R-2]``) always constructed :class:`~tos.dsl.EvaluationConfig`
with ``bindings={}``, which made any such rule permanently inert
(:func:`tos.dsl.vocabulary.resolve_operand` returns ``UNKNOWN`` for a
``config``-sourced ref against an empty mapping) — silently, with no
refusal, no evidence, no halt — so that revision refused any strategy
carrying one outright rather than admit an inert rule. This module now
resolves such a ref POSITIVELY instead, against
:mod:`tos_runtime.strategy.bindings` (``config_dir /
"strategy_bindings.yaml"``), enforcing five rules per admitted strategy
file (its own module docstring "five refusal rules"; ``stem`` = the
strategy file's :attr:`~pathlib.Path.stem`, e.g. ``"example.strategy"`` for
``example.strategy.yaml``):

1. The strategy carries ``>= 1`` config-sourced ref and the bindings file
   has no entry for its ``stem`` -> refused.
2. An entry's ``config_binding_version`` does not equal the strategy file's
   own -> refused (names both values).
3. Any config-sourced ref does not resolve to a scalar leaf in that entry's
   ``bindings`` (walked exactly like the kernel's own
   :func:`~tos.dsl.vocabulary.resolve_operand` walks ``ref[1:]`` — a ref
   longer than ``("config", <key>)`` can never resolve against the flat
   ``dict[str, ScalarValue]`` shape :mod:`tos_runtime.strategy.bindings`
   itself enforces) -> refused, naming the unresolvable path.
4. A ``bindings`` key the strategy never actually references via a
   config-sourced ref -> refused (drift: an unused knob is misconfiguration
   under CLAUDE.md's "configuration-driven only").
5. A bindings entry names a ``stem`` with no matching admitted strategy
   file -> refused (an orphan entry).

A strategy with ZERO config-sourced refs needs no entry at all (rule 1 does
not apply); if one is present anyway, rules 2-4 still apply verbatim — rule
4 alone already forces ``bindings == {}`` for a zero-ref strategy (every key
is "unused" when nothing references any key), so no separate special case
is needed.

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
    own digest (plan §1.2 item 3). ``loaded_bindings`` (``[D-R-3]``) is
    populated the SAME way — only in the file-strategy-source path — so the
    composition root can fold the bindings file's own digest into the same
    evidence record."""

    registry: StrategyRegistry
    loaded: LoadedStrategies | None
    loaded_bindings: LoadedStrategyBindings | None = None


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


def _config_ref_paths(loaded_strategy: LoadedStrategy) -> tuple[tuple[str, ...], ...]:
    """Every DISTINCT ``config``-sourced ref, as its raw component tuple, any
    outcome-gating :class:`~tos.dsl.vocabulary.Compare` in the strategy's
    policy names, in first-seen order.

    Enumerates via the kernel's OWN published walk —
    :func:`tos.engine.admission.iter_outcome_gating_compares` (which
    outcome-gating comparisons exist) and
    :func:`tos.engine.admission.operand_source` (which operand a ``ref``
    names) — rather than re-implementing the "``Operand`` only appears
    inside a ``Compare``" walk here (2026-09-09 independent-review finding
    #2, DRY): completeness of this ref enumeration is now INHERITED from
    the kernel's own admission-time enumerator, the same one
    ``strategy_admissible`` runs, rather than a second, independently
    asserted claim that could silently drift from it (e.g. if a future
    kernel revision lets a non-``Compare`` node carry an operand, this
    function tracks that automatically instead of quietly under-counting).
    This typed walk still recovers the EXACT ref path (the kernel's lowered
    candidate program does not — its node payload is intentionally
    structural, not literal, design #31), which positive resolution
    (:func:`_resolve_bindings_or_refuse`) needs to name in a refusal.

    Returns:
        The distinct ``ref`` tuples (e.g. ``("config", "lower_band_threshold")``),
        never a joined string — callers join with ``"."`` only for messages.
    """
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
    """Whether ``ref[1:]`` resolves to a scalar leaf in ``bindings`` —
    mirrors :func:`tos.dsl.vocabulary.resolve_operand`'s own walk exactly
    (``ref[0]`` is already known to be ``"config"`` by the caller), except it
    walks ``bindings`` directly rather than a full environment, since
    ``env["config"]`` IS ``dict(config.bindings)`` verbatim
    (:func:`tos.dsl.determinism.build_environment`)."""
    value: Any = bindings
    for part in ref[1:]:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False
    return isinstance(value, bool | int | float | str)


def _resolve_bindings_or_refuse(
    loaded: LoadedStrategies, loaded_bindings: LoadedStrategyBindings
) -> None:
    """Positive resolution of every admitted strategy's ``config``-sourced
    refs against ``loaded_bindings`` — the five rules this module's own
    docstring numbers (finding #9 disposition, ``[D-R-3]``).

    Args:
        loaded: The admitted strategy set (module invariant: never empty —
            :func:`~tos_runtime.strategy.loader.load_strategies` itself
            refuses an empty directory before this function is ever
            reached).
        loaded_bindings: The (possibly-absent — ``strategies`` is ``{}``
            either way) loaded bindings file.

    Raises:
        StrategyLoadError: The first (sorted-strategy-path order) violation
            of any of the five rules, naming the file/stem/path/key.
    """
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
    """Register every loaded (already admitted, already positively resolved
    against ``bindings_by_stem`` by :func:`_resolve_bindings_or_refuse`)
    strategy into a fresh registry, deriving each
    :class:`~tos.dsl.EvaluationConfig` from the strategy's own
    ``config_binding_version`` plus that stem's bindings (empty when the
    stem has no entry — always valid post-resolution: rule 1 already
    refused any zero-bindings strategy that actually needs one).

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
        one = bindings_by_stem.get(entry.path.stem)
        bindings = dict(one.bindings) if one is not None else {}
        config = EvaluationConfig(
            config_version=config_binding_version, bindings=bindings
        )
        registry.register(entry.strategy, config)
    return registry


def _resolve_neither_present(
    strategies_dir: Path,
    *,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    allow_no_strategies: bool,
) -> ResolvedStrategyRegistry:
    """Neither a strategies directory nor an injected registry — the
    "neither present" branch (module docstring finding #8), split out of
    :func:`resolve_strategy_registry` purely for the size budget."""
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
    # Explicit, stated operator choice (module docstring) — proceeds with an
    # empty registry; evidenced (NOT via record_halt: a successful boot,
    # not a halt/protective-action record).
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
    """Resolve the ONE strategy source for this compose (module docstring).

    Args:
        config_dir: The compose config directory; ``config_dir /
            "strategies"`` is checked for the file source and, when that
            source is used, ``config_dir / "strategy_bindings.yaml"`` is
            loaded and every admitted strategy's ``config``-sourced refs are
            positively resolved against it (module docstring finding #9).
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
        return _resolve_neither_present(
            strategies_dir,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
            allow_no_strategies=allow_no_strategies,
        )

    bindings_path = config_dir / STRATEGY_BINDINGS_FILE_NAME
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
