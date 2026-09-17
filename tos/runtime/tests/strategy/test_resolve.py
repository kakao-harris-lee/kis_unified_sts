"""``tos_runtime.strategy.resolve`` tests (TOS Phase 3 슬라이스 D-R
``[D-R-2]``, docs/plans/2026-09-09-tos-phase3-event-core-plan.md §1.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from tos.dsl.vocabulary import DecisionKind, evaluate_policy
from tos.engine import StrategyRegistry
from tos.engine.records import InstrumentKey
from tos.engine.vocabulary import DispatchResolution
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.strategy.bindings import STRATEGY_BINDINGS_FILE_NAME
from tos_runtime.strategy.loader import StrategyLoadError
from tos_runtime.strategy.resolve import (
    STRATEGY_REFUSED_EVIDENCE_KIND,
    STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND,
    ResolvedStrategyRegistry,
    StrategyRegistryResolutionRefused,
    resolve_strategy_registry,
)

from .conftest import (
    ACCOUNT,
    INSTRUMENT,
    admissible_strategy_mapping,
    write_strategy_yaml,
)


def _write_bindings_yaml(config_dir: Path, mapping: dict[str, Any]) -> Path:
    path = config_dir / STRATEGY_BINDINGS_FILE_NAME
    path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")
    return path


def _config_ref_strategy_mapping(**overrides: Any) -> dict[str, Any]:
    """``admissible_strategy_mapping`` with its outcome-gating compare's
    RIGHT operand swapped for a ``config``-sourced ref — the shape every
    positive-resolution test in this module needs (one capsule operand, one
    config operand, matching the D1<->D4 admission rule)."""
    mapping = admissible_strategy_mapping(**overrides)
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {
        "ref": ["config", "lower_band_threshold"]
    }
    return mapping


class _FixedKeyProvider:
    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-resolve")

    def generations(self) -> tuple[int, ...]:
        return (1,)


@pytest.fixture()
def evidence_store(tmp_path: Path) -> SqliteEvidenceStore:
    instance = SqliteEvidenceStore(
        tmp_path / "evidence.sqlite3", key_provider=_FixedKeyProvider()
    )
    yield instance
    instance.close()


@pytest.fixture()
def emergency_log(tmp_path: Path) -> EmergencyAppendLog:
    return EmergencyAppendLog(tmp_path / "emergency.jsonl")


@pytest.fixture()
def identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        cell_id="test-resolve", runtime_generation=0, process_nonce="nonce-resolve"
    )


def _refusal_evidence_kinds(store: SqliteEvidenceStore) -> list[str]:
    return [row.kind for row in store.iter_entry_meta()]


def test_neither_present_refuses_by_default(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """2026-09-09 independent-review finding #8: neither a strategies
    directory nor an injected registry is no longer a silent empty-registry
    fallback — it refuses, matching the loader's own "an engine with zero
    admitted strategies... does not start" rule one layer down. An operator
    who genuinely wants no strategies must say so via
    ``allow_no_strategies=True`` (see
    ``test_neither_present_with_allow_no_strategies_returns_empty_registry_with_evidence``).
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    with pytest.raises(StrategyRegistryResolutionRefused):
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_neither_present_with_allow_no_strategies_returns_empty_registry_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """The stated-choice opt-out (finding #8's suggested disposition):
    ``allow_no_strategies=True`` permits the empty registry, and records a
    non-halt ``STRATEGY_SOURCE_ABSENT_BY_OPERATOR_CHOICE`` evidence entry —
    never the silent, unevidenced fallback the old default was."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
        allow_no_strategies=True,
    )
    assert isinstance(resolved, ResolvedStrategyRegistry)
    assert resolved.loaded is None
    assert resolved.registry.declared_keys() == ()
    assert _refusal_evidence_kinds(evidence_store) == [
        STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND
    ]


def test_injected_registry_used_when_no_strategies_dir(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    injected = StrategyRegistry()
    injected.declare_key(InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT))
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=injected,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert resolved.registry is injected
    assert resolved.loaded is None


def test_file_source_builds_registry_from_directory(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    write_strategy_yaml(
        config_dir / "strategies", "band.strategy.yaml", admissible_strategy_mapping()
    )
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert resolved.loaded is not None
    assert len(resolved.loaded.strategies) == 1
    dispatch = resolved.registry.resolve(
        InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)
    )
    assert dispatch.resolution is DispatchResolution.DISPATCHED
    assert len(dispatch.entries) == 1
    assert _refusal_evidence_kinds(evidence_store) == []


def test_both_present_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    write_strategy_yaml(
        config_dir / "strategies", "band.strategy.yaml", admissible_strategy_mapping()
    )
    injected = StrategyRegistry()
    with pytest.raises(StrategyRegistryResolutionRefused, match="both supplied"):
        resolve_strategy_registry(
            config_dir,
            injected_registry=injected,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]
    assert (tmp_path / "emergency.jsonl").exists()


def test_empty_strategies_directory_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    with pytest.raises(StrategyRegistryResolutionRefused):
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_malformed_strategy_file_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    (strategies_dir / "bad.strategy.yaml").write_text(
        "not: valid: yaml: [[[", encoding="utf-8"
    )
    with pytest.raises(StrategyRegistryResolutionRefused):
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_load_strategies_error_is_the_underlying_cause(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert isinstance(excinfo.value.__cause__, StrategyLoadError)


def test_config_sourced_ref_without_bindings_refuses_naming_the_ref(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """2026-09-09 independent-review finding #9 (``[D-R-3]`` positive-
    resolution disposition, rule 1): reproduces the reviewer's own probe —
    a compare of ``capsule.resolved_values.close LT
    config.lower_band_threshold`` parses and is ADMISSIBLE (``config`` is an
    ``ADMISSIBLE_CONTEXT_SOURCES`` member and only ONE operand needs to be
    capsule-sourced), but no ``strategy_bindings.yaml`` exists at all in
    this test's ``config_dir`` — rule 1 ("a strategy carries >= 1
    config-sourced ref and the bindings file has no entry for its stem")
    refuses it at load, naming both the file and the ref path."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {
        "ref": ["config", "lower_band_threshold"]
    }
    path = write_strategy_yaml(strategies_dir, "config-ref.strategy.yaml", mapping)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    message = str(excinfo.value)
    assert str(path) in message
    assert "config.lower_band_threshold" in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_escape_ref_source_is_refused_at_load(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """2026-09-09 independent-review finding #17 (D-lane assertion (a)):
    a YAML strategy carrying an escape ``ref`` source
    (``("ambient", "now")`` — outside :data:`~tos.dsl.vocabulary.
    ADMISSIBLE_CONTEXT_SOURCES`) is refused at load. As of this writing
    ``Operand`` constructs an ambient ``ref`` without complaint (only the
    escape-checker, run inside ``strategy_admissible``, catches it) — if a
    concurrent kernel change tightens ``Operand._exactly_one`` to validate
    ``ref[0]`` positively, this same YAML would instead fail to PARSE, and
    ``load_strategies``'s own parse-refusal branch (a ``ValidationError`` /
    ``ArtifactIntegrityError`` caught in ``_load_one``) covers that outcome
    identically — either way ``StrategyRegistryResolutionRefused`` is what
    this module raises, so no branch here needs to change to track that."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {"ref": ["ambient", "now"]}
    path = write_strategy_yaml(strategies_dir, "escape-ref.strategy.yaml", mapping)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert str(path) in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


# ============================================================================
# [D-R-3b] positive bindings resolution (finding #9 disposition) — the five
# rules resolve.py's own module docstring numbers.
# ============================================================================


def test_version_mismatch_refuses_naming_both_values(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Rule 2: an entry's ``config_binding_version`` must equal the target
    strategy file's own."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = _config_ref_strategy_mapping()
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": "WRONG-VERSION",
                    "bindings": {"lower_band_threshold": 500},
                }
            }
        },
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    message = str(excinfo.value)
    assert "WRONG-VERSION" in message
    assert mapping["config_binding_version"] in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_unresolvable_ref_path_refuses_naming_the_path(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Rule 3: a config-sourced ref longer than ``("config", <key>)`` can
    never resolve against the flat ``bindings`` mapping. Also pins the
    BARE ``("config",)`` ref case (2026-09-09 independent-review finding
    #6) — a length-1 ref never enters the ``ref[1:]`` walk loop at all, so
    its refusal depends entirely on the leaf-type check rejecting the
    ``bindings`` dict itself; untested before this."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {
        "ref": ["config", "lower_band_threshold", "nested"]
    }
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": mapping["config_binding_version"],
                    "bindings": {"lower_band_threshold": 500},
                }
            }
        },
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert "config.lower_band_threshold.nested" in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]

    # Finding #6: a BARE ("config",) ref is refused the same way, never
    # silently UNKNOWN.
    bare_config_dir = tmp_path / "config-bare"
    bare_strategies_dir = bare_config_dir / "strategies"
    bare_strategies_dir.mkdir(parents=True)
    bare_mapping = admissible_strategy_mapping()
    bare_mapping["policy"]["rules"][0]["all_of"][0]["right"] = {"ref": ["config"]}
    write_strategy_yaml(bare_strategies_dir, "band.strategy.yaml", bare_mapping)
    _write_bindings_yaml(
        bare_config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": bare_mapping["config_binding_version"],
                    "bindings": {},
                }
            }
        },
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as bare_excinfo:
        resolve_strategy_registry(
            bare_config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert "config" in str(bare_excinfo.value)


def test_unused_bindings_key_refuses_naming_the_key(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Rule 4: a ``bindings`` key the strategy never references is drift."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = _config_ref_strategy_mapping()
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": mapping["config_binding_version"],
                    "bindings": {
                        "lower_band_threshold": 500,
                        "never_referenced": 1,
                    },
                }
            }
        },
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert "never_referenced" in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_orphan_bindings_stem_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Rule 5: a bindings entry for a stem with no matching strategy file."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "no-such-strategy": {
                    "config_binding_version": "cfg-anything",
                    "bindings": {},
                }
            }
        },
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert "no-such-strategy" in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_happy_path_registers_bindings_and_the_rule_actually_fires(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """The whole point of finding #9: a config-sourced ref is no longer
    inert. The registered ``EvaluationConfig.bindings`` carries the exact
    values, and evaluating the policy over an environment where
    ``capsule.resolved_values.close < config.lower_band_threshold`` holds
    actually SELECTS the ACTION decision — not silently UNKNOWN/default."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = _config_ref_strategy_mapping()
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": mapping["config_binding_version"],
                    "bindings": {"lower_band_threshold": 500},
                }
            }
        },
    )
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert _refusal_evidence_kinds(evidence_store) == []
    assert resolved.loaded_bindings is not None
    assert resolved.loaded_bindings.present is True
    assert resolved.loaded_bindings.sha256_digest is not None

    dispatch = resolved.registry.resolve(
        InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)
    )
    assert dispatch.resolution is DispatchResolution.DISPATCHED
    registered = dispatch.entries[0]
    assert registered.config.bindings == {"lower_band_threshold": 500}

    # The rule fires: close(100) < config.lower_band_threshold(500).
    env = {
        "capsule": {"resolved_values": {"close": 100}},
        "config": dict(registered.config.bindings),
    }
    decision = evaluate_policy(registered.strategy.policy, env)
    assert decision.kind is DecisionKind.ACTION

    # Control: close(999) is NOT below the threshold -> default NO_ACTION.
    env_no_fire = {
        "capsule": {"resolved_values": {"close": 999}},
        "config": dict(registered.config.bindings),
    }
    default_decision = evaluate_policy(registered.strategy.policy, env_no_fire)
    assert default_decision.kind is DecisionKind.NO_ACTION


def test_zero_config_refs_with_matching_empty_entry_is_fine(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A strategy with zero config-sourced refs may still have a bindings
    entry, as long as it version-matches and declares zero bindings (rule 4
    forces this: every key would otherwise be "unused")."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    write_strategy_yaml(strategies_dir, "band.strategy.yaml", mapping)
    _write_bindings_yaml(
        config_dir,
        {
            "strategies": {
                "band.strategy": {
                    "config_binding_version": mapping["config_binding_version"],
                    "bindings": {},
                }
            }
        },
    )
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert _refusal_evidence_kinds(evidence_store) == []
    dispatch = resolved.registry.resolve(
        InstrumentKey(account=ACCOUNT, instrument=INSTRUMENT)
    )
    assert dispatch.resolution is DispatchResolution.DISPATCHED


def test_no_bindings_file_and_zero_config_refs_is_fine(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """No ``strategy_bindings.yaml`` at all, and no strategy needs one —
    the file's absence is not itself a refusal (module docstring)."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    write_strategy_yaml(
        strategies_dir, "band.strategy.yaml", admissible_strategy_mapping()
    )
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert _refusal_evidence_kinds(evidence_store) == []
    assert resolved.loaded_bindings is not None
    assert resolved.loaded_bindings.present is False


# ============================================================================
# [D-R-3d] re-review dispositions #1, #3, #4 — see review-dr3.md.
# ============================================================================


def test_malformed_bindings_file_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Finding #1 (MEDIUM): pins that a
    :class:`~tos_runtime.strategy.bindings.StrategyBindingsLoadError` (a
    SIBLING of ``StrategyLoadError``, not a subclass of it) is caught by
    ``resolve_strategy_registry``'s own ``except`` clause and converted to
    ``StrategyRegistryResolutionRefused`` with BOTH evidence paths written
    — narrowing that ``except`` to ``StrategyLoadError`` alone would let a
    malformed-bindings failure escape uncaught, with no
    ``STRATEGY_REFUSED`` entry and no emergency-log line (the "never a
    silent halt" contract this module's own docstring states)."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    write_strategy_yaml(
        strategies_dir, "band.strategy.yaml", admissible_strategy_mapping()
    )
    (config_dir / STRATEGY_BINDINGS_FILE_NAME).write_text(
        "strategies:\n  band.strategy:\n"
        "    config_binding_version: null\n    bindings: {}\n",
        encoding="utf-8",
    )
    with pytest.raises(StrategyRegistryResolutionRefused):
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]
    assert emergency_log.path.read_text().strip() != ""


def test_duplicate_stem_across_yaml_and_yml_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Finding #3 (LOW): ``band.strategy.yaml`` and ``band.strategy.yml``
    are two distinct admitted strategies (the loader admits both suffixes)
    sharing one bindings stem — refused before any bindings rule runs,
    naming both files."""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    write_strategy_yaml(
        strategies_dir, "band.strategy.yaml", admissible_strategy_mapping()
    )
    write_strategy_yaml(
        strategies_dir, "band.strategy.yml", admissible_strategy_mapping()
    )
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    message = str(excinfo.value)
    assert "band.strategy.yaml" in message
    assert "band.strategy.yml" in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_bindings_file_present_with_injected_registry_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Finding #4 (LOW), injected-registry path: bindings apply only to
    the file strategy source — a present ``strategy_bindings.yaml`` next
    to an injected registry is refused rather than silently ignored."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_bindings_yaml(
        config_dir,
        {"strategies": {"whatever": {"config_binding_version": "v1", "bindings": {}}}},
    )
    injected = StrategyRegistry()
    with pytest.raises(StrategyRegistryResolutionRefused, match="injected"):
        resolve_strategy_registry(
            config_dir,
            injected_registry=injected,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_bindings_file_present_with_allow_no_strategies_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Finding #4 (LOW), ``allow_no_strategies=True`` path: with zero
    admitted strategies, every bindings entry would be an orphan (rule 5)
    — refused rather than silently ignored."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_bindings_yaml(
        config_dir,
        {"strategies": {"whatever": {"config_binding_version": "v1", "bindings": {}}}},
    )
    with pytest.raises(StrategyRegistryResolutionRefused, match="orphan"):
        resolve_strategy_registry(
            config_dir,
            injected_registry=None,
            evidence_store=evidence_store,
            emergency_log=emergency_log,
            identity=identity,
            allow_no_strategies=True,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_absent_bindings_file_is_fine_on_injected_and_allow_no_strategies_paths(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Finding #4 control: an ABSENT bindings file is unaffected on both
    non-file-source paths — nothing to refuse."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    injected = StrategyRegistry()
    resolved = resolve_strategy_registry(
        config_dir,
        injected_registry=injected,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
    )
    assert resolved.registry is injected
    assert _refusal_evidence_kinds(evidence_store) == []

    resolved2 = resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
        allow_no_strategies=True,
    )
    assert resolved2.registry.declared_keys() == ()
    assert _refusal_evidence_kinds(evidence_store) == [
        STRATEGY_SOURCE_ABSENT_EVIDENCE_KIND
    ]
