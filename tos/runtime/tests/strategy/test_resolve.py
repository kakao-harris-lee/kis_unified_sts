"""``tos_runtime.strategy.resolve`` tests (TOS Phase 3 슬라이스 D-R
``[D-R-2]``, docs/plans/2026-09-09-tos-phase3-event-core-plan.md §1.2).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.engine import StrategyRegistry
from tos.engine.records import InstrumentKey
from tos.engine.vocabulary import DispatchResolution
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
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


class _FixedKeyProvider:
    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-resolve")


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
