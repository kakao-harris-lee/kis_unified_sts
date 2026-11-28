"""Boot refuses a ``capsule.position`` ref the tree cannot resolve (plan P4 §2 D5, stage S2)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import (
    POSITION_NAMESPACE,
    PositionSide,
    flat_position_context,
    project_position_context,
)
from tos.workload import RuntimeIdentity
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.strategy.resolve import (
    POSITION_DSL_FIELDS,
    STRATEGY_REFUSED_EVIDENCE_KIND,
    StrategyRegistryResolutionRefused,
    resolve_strategy_registry,
)

from .conftest import admissible_strategy_mapping, write_strategy_yaml

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class _FixedKeyProvider:
    def current(self) -> tuple[int, bytes]:
        return (1, b"test-fixed-key-bytes-position-refs")

    def generations(self) -> tuple[int, ...]:
        return (1,)

    def key_for(self, generation: int) -> bytes:
        del generation
        return b"test-fixed-key-bytes-position-refs"


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
        cell_id="test-position-refs", runtime_generation=0, process_nonce="nonce-pr"
    )


def _position_ref_mapping(*ref_tail: str) -> dict[str, Any]:
    """``admissible_strategy_mapping`` with its gating compare reading ``capsule.position.*``."""
    mapping = admissible_strategy_mapping()
    compare = mapping["policy"]["rules"][0]["all_of"][0]
    compare["left"] = {"ref": ["capsule", POSITION_NAMESPACE, *ref_tail]}
    compare["op"] = "LE"
    compare["right"] = {"const": -50}
    return mapping


def _resolve(
    config_dir: Path,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    identity: RuntimeIdentity,
    *,
    position_context_enabled: bool,
) -> Any:
    return resolve_strategy_registry(
        config_dir,
        injected_registry=None,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        identity=identity,
        position_context_enabled=position_context_enabled,
    )


def _tree_with(mapping: dict[str, Any], tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    strategies = config_dir / "strategies"
    strategies.mkdir(parents=True)
    write_strategy_yaml(strategies, "position_gated.yaml", mapping)
    return config_dir


def test_the_dsl_visible_names_are_exactly_what_a_real_record_projects() -> None:
    """Drift guard: the kernel exports no constant, so this tuple is pinned to the record."""
    flat = flat_position_context(
        source_ref="scope:a::b@evidence:1", as_of=0, scheme=_SCHEME
    )
    held = project_position_context(
        side=PositionSide.LONG,
        held_qty=1,
        entry_price=100,
        entry_price_basis="ORDER",
        entry_as_of=0,
        price=101,
        as_of=60_000,
        bar_interval_ms=60_000,
        source_ref="attempt:x@rcl:1:1",
        scheme=_SCHEME,
    )
    projected = set(flat.as_environment_mapping()) | set(held.as_environment_mapping())
    assert set(POSITION_DSL_FIELDS) == projected
    assert len(POSITION_DSL_FIELDS) == len(set(POSITION_DSL_FIELDS)) == 7


def test_a_position_ref_with_the_namespace_off_refuses_the_boot(
    tmp_path: Path, evidence_store, emergency_log, identity
) -> None:
    """The rule would narrow to False on every bar — a silently dead stop-loss."""
    config_dir = _tree_with(_position_ref_mapping("unrealized_bp"), tmp_path)
    with pytest.raises(
        StrategyRegistryResolutionRefused, match="position_context.enabled"
    ):
        _resolve(
            config_dir,
            evidence_store,
            emergency_log,
            identity,
            position_context_enabled=False,
        )
    assert STRATEGY_REFUSED_EVIDENCE_KIND in [
        row.kind for row in evidence_store.iter_entry_meta()
    ]


def test_a_position_ref_with_the_namespace_on_resolves(
    tmp_path: Path, evidence_store, emergency_log, identity
) -> None:
    config_dir = _tree_with(_position_ref_mapping("unrealized_bp"), tmp_path)
    resolved = _resolve(
        config_dir,
        evidence_store,
        emergency_log,
        identity,
        position_context_enabled=True,
    )
    assert resolved.loaded is not None
    assert len(resolved.registry.declared_keys()) == 1


@pytest.mark.parametrize(
    "ref_tail",
    [(), ("no_such_value",), ("unrealised_bp",), ("side", "value"), ("source_ref",)],
)
def test_a_position_ref_that_is_not_a_dsl_visible_name_refuses_the_boot(
    tmp_path: Path, evidence_store, emergency_log, identity, ref_tail: tuple[str, ...]
) -> None:
    """Only the seven projected names resolve; anything else is permanently false."""
    config_dir = _tree_with(_position_ref_mapping(*ref_tail), tmp_path)
    with pytest.raises(StrategyRegistryResolutionRefused, match="DSL-visible position"):
        _resolve(
            config_dir,
            evidence_store,
            emergency_log,
            identity,
            position_context_enabled=True,
        )


def test_a_tree_with_no_position_ref_is_untouched_by_the_refusal(
    tmp_path: Path, evidence_store, emergency_log, identity
) -> None:
    """Control: the refusal is scoped to rules that actually read the namespace."""
    config_dir = _tree_with(admissible_strategy_mapping(), tmp_path)
    resolved = _resolve(
        config_dir,
        evidence_store,
        emergency_log,
        identity,
        position_context_enabled=False,
    )
    assert resolved.loaded is not None
