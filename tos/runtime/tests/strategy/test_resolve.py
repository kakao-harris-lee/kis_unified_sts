"""Tests for ``tos_runtime.strategy.resolve``."""

from __future__ import annotations

from collections.abc import Iterator
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
    """``admissible_strategy_mapping`` with its outcome-gating compare's"""
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

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-resolve"


@pytest.fixture()
def evidence_store(tmp_path: Path) -> Iterator[SqliteEvidenceStore]:
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


def _resolve(
    config_dir: Path,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    **overrides: Any,
) -> ResolvedStrategyRegistry:
    """Resolve ``config_dir``'s registry onto this test's own evidence and emergency path."""
    overrides.setdefault("injected_registry", None)
    return resolve_strategy_registry(
        config_dir,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
        **overrides,
    )


def test_neither_present_refuses_by_default(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Neither a strategies"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    with pytest.raises(StrategyRegistryResolutionRefused):
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_neither_present_with_allow_no_strategies_returns_empty_registry_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """The stated-choice opt-out:"""
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
        _resolve(
            config_dir,
            evidence_store,
            emergency_log,
            identity,
            injected_registry=injected,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]
    assert (tmp_path / "emergency.jsonl").exists()


def test_empty_strategies_directory_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    with pytest.raises(StrategyRegistryResolutionRefused):
        _resolve(config_dir, evidence_store, emergency_log, identity)
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_load_strategies_error_is_the_underlying_cause(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    config_dir = tmp_path / "config"
    (config_dir / "strategies").mkdir(parents=True)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert isinstance(excinfo.value.__cause__, StrategyLoadError)


def test_config_sourced_ref_without_bindings_refuses_naming_the_ref(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A config-sourced ref without a bindings file is refused at load:"""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {
        "ref": ["config", "lower_band_threshold"]
    }
    path = write_strategy_yaml(strategies_dir, "config-ref.strategy.yaml", mapping)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        _resolve(config_dir, evidence_store, emergency_log, identity)
    message = str(excinfo.value)
    assert str(path) in message
    assert "config.lower_band_threshold" in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_escape_ref_source_is_refused_at_load(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A YAML strategy carrying an escape ``ref`` source"""
    config_dir = tmp_path / "config"
    strategies_dir = config_dir / "strategies"
    strategies_dir.mkdir(parents=True)
    mapping = admissible_strategy_mapping()
    mapping["policy"]["rules"][0]["all_of"][0]["right"] = {"ref": ["ambient", "now"]}
    path = write_strategy_yaml(strategies_dir, "escape-ref.strategy.yaml", mapping)
    with pytest.raises(StrategyRegistryResolutionRefused) as excinfo:
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert str(path) in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_version_mismatch_refuses_naming_both_values(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """Rule 2: an entry's ``config_binding_version`` must equal the target"""
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    message = str(excinfo.value)
    assert "WRONG-VERSION" in message
    assert mapping["config_binding_version"] in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_unresolvable_ref_path_refuses_naming_the_path(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A config-sourced ref longer than ``("config", <key>)`` can"""
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert "config.lower_band_threshold.nested" in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]

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
        _resolve(config_dir, evidence_store, emergency_log, identity)
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert "no-such-strategy" in str(excinfo.value)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_happy_path_registers_bindings_and_the_rule_actually_fires(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A config-sourced ref is no longer"""
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
    assert registered.strategy.policy is not None

    env = {
        "capsule": {"resolved_values": {"close": 100}},
        "config": dict(registered.config.bindings),
    }
    decision = evaluate_policy(registered.strategy.policy, env)
    assert decision.kind is DecisionKind.ACTION

    env_no_fire = {
        "capsule": {"resolved_values": {"close": 999}},
        "config": dict(registered.config.bindings),
    }
    default_decision = evaluate_policy(registered.strategy.policy, env_no_fire)
    assert default_decision.kind is DecisionKind.NO_ACTION


def test_zero_config_refs_with_matching_empty_entry_is_fine(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A strategy with zero config-sourced refs may still have a bindings"""
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
    """No ``strategy_bindings.yaml`` at all, and no strategy needs one —"""
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


def test_malformed_bindings_file_refuses_with_evidence(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """A malformed"""
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]
    assert emergency_log.path.read_text().strip() != ""


def test_duplicate_stem_across_yaml_and_yml_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """``band.strategy.yaml`` and ``band.strategy.yml``"""
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
        _resolve(config_dir, evidence_store, emergency_log, identity)
    message = str(excinfo.value)
    assert "band.strategy.yaml" in message
    assert "band.strategy.yml" in message
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_bindings_file_present_with_injected_registry_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """The injected-registry path: bindings apply only to"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_bindings_yaml(
        config_dir,
        {"strategies": {"whatever": {"config_binding_version": "v1", "bindings": {}}}},
    )
    injected = StrategyRegistry()
    with pytest.raises(StrategyRegistryResolutionRefused, match="injected"):
        _resolve(
            config_dir,
            evidence_store,
            emergency_log,
            identity,
            injected_registry=injected,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_bindings_file_present_with_allow_no_strategies_refuses(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """With ``allow_no_strategies=True`` and zero"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_bindings_yaml(
        config_dir,
        {"strategies": {"whatever": {"config_binding_version": "v1", "bindings": {}}}},
    )
    with pytest.raises(StrategyRegistryResolutionRefused, match="orphan"):
        _resolve(
            config_dir,
            evidence_store,
            emergency_log,
            identity,
            allow_no_strategies=True,
        )
    assert _refusal_evidence_kinds(evidence_store) == [STRATEGY_REFUSED_EVIDENCE_KIND]


def test_absent_bindings_file_is_fine_on_injected_and_allow_no_strategies_paths(
    tmp_path: Path, evidence_store, emergency_log, identity
):
    """An ABSENT bindings file is unaffected on both"""
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
